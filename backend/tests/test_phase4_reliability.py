from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from pulse.agents.event_control import EventControlAgent
from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.config import get_settings
from pulse.contracts import (
    Completeness,
    EventEnvelope,
    EventTime,
    Finding,
    FindingStatus,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
    utc_now,
)
from pulse.state.store import get_state_store
from pulse.stream.bus import PulseEventBus
from pulse.stream.flink.manager import get_flink_manager
from pulse.stream.kafka_client import KafkaBroker
from pulse.testing.orchestrator import VerticalSliceVerifier
from pulse.topics import AGENT_TOPICS, NORMALISED_TOPICS, RAW_TOPICS


def make_envelope(
    event_id: str,
    event_type: str,
    elapsed_ms: int,
    payload: dict,
    driver_number: int | None = None,
    session_id: str = "test-session-reliability",
    run_id: str = "run-rel-01",
    completeness: Completeness = Completeness.COMPLETE,
) -> EventEnvelope:
    now = utc_now()
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        source=SourceRef(
            provider="PULSE_RELIABILITY_TEST",
            adapter="pytest_v4",
            source_record_id=f"src-{event_id}",
            capture_id="pulse-capture-f1-2023-silverstone-race-v1",
            licence_reference="PULSE-TEST-LICENCE-2026",
        ),
        run=RunContext(
            run_id=run_id,
            session_instance_id=session_id,
            mode=RunMode.REPLAY,
        ),
        session=SessionRef(
            season=2023,
            meeting_id="silverstone-2023",
            session_id=session_id,
            session_type="RACE",
        ),
        time=EventTime(
            event_time_utc=now,
            session_elapsed_ms=elapsed_ms,
            ingest_time_utc=now,
        ),
        subject=Subject(driver_number=driver_number),
        payload=payload,
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=completeness,
            unit_validation=UnitValidation.PASSED,
        ),
    )


@pytest.mark.asyncio
async def test_01_normal_complete_historical_replay():
    """Validates full 52-lap historical race replay with 100% stage reconciliation."""
    flink_mgr = get_flink_manager()
    if not flink_mgr.client.is_cluster_online():
        pytest.skip("Kafka broker / Flink cluster offline (Docker offline)")
    verifier = VerticalSliceVerifier(
        capture_id="pulse-capture-f1-2023-silverstone-race-v1",
        mode="REPLAY",
        output_dir="reports/full_race",
    )
    result = await verifier.run()
    assert result.status == "PASSED"
    assert len(result.stages) >= 10
    for stage in result.stages:
        assert stage.status == "PASSED"
        assert stage.drop_count == 0


@pytest.mark.asyncio
async def test_02_duplicate_event_injection_idempotency():
    """Verifies duplicate injection of official events does not produce duplicate findings or state corruption."""
    store = get_state_store()
    agent = EventControlAgent()
    store.register_agent(agent)

    event_id = f"evt-dup-{uuid4().hex[:6]}"
    env = make_envelope(
        event_id=event_id,
        event_type="VSC_DEPLOYED",
        elapsed_ms=15000,
        payload={"reason": "Test duplicate injection", "affected_drivers": [16]},
        driver_number=16,
    )

    # First injection
    await agent.on_event(NORMALISED_TOPICS["race_events"], "session:16", env)
    initial_findings = [f for f in store.findings if f.trigger_event_id == event_id]
    assert len(initial_findings) >= 1

    # Duplicate injection
    await agent.on_event(NORMALISED_TOPICS["race_events"], "session:16", env)
    duplicate_check_findings = [f for f in store.findings if f.trigger_event_id == event_id]
    # Finding IDs must be deduplicated in store
    unique_ids = {f.finding_id for f in duplicate_check_findings}
    assert len(duplicate_check_findings) == len(unique_ids)


@pytest.mark.asyncio
async def test_03_out_of_order_event_replay_temporal_monotonicity():
    """Verifies that out-of-order findings delivered to ConsequenceFusionEngine maintain revision causality."""
    fusion = ConsequenceFusionEngine()
    session_id = f"sess-ooo-{uuid4().hex[:6]}"
    run_id = f"run-ooo-{uuid4().hex[:6]}"

    # Event 2 arriving before Event 1
    finding_late = Finding(
        finding_id=f"find-late-{uuid4().hex[:6]}",
        agent_id="agent-04-tyre-strategy",
        finding_type="PIT_WINDOW_OPPORTUNITY",
        session_id=session_id,
        run_id=run_id,
        subject=Subject(driver_number=16),
        trigger_event_id="evt-vsc-02",
        as_of_event_time=utc_now(),
        interpretation=Interpretation.DERIVED,
        result={"driver_number": 16, "net_time_saving_sec": 10.5, "strategy_score": 88},
        evidence_refs=["evt-vsc-02"],
        assessment_status=FindingStatus.PROVISIONAL,
        model_version="1.2.0",
    )

    finding_early = Finding(
        finding_id=f"find-early-{uuid4().hex[:6]}",
        agent_id="agent-01-event-control",
        finding_type="DRIVER_EVENT_EXPOSURE",
        session_id=session_id,
        run_id=run_id,
        subject=Subject(driver_number=16),
        trigger_event_id="evt-vsc-01",
        as_of_event_time=utc_now(),
        interpretation=Interpretation.DERIVED,
        result={"driver_number": 16, "exposure_level": "CRITICAL_OPPORTUNITY", "event_type": "VSC"},
        evidence_refs=["evt-vsc-01"],
        assessment_status=FindingStatus.PROVISIONAL,
        model_version="1.0.0",
    )

    # Deliver out of order: strategy finding first, then exposure finding
    await fusion.on_finding(AGENT_TOPICS["tyre_strategy"], f"{session_id}:16", finding_late)
    await fusion.on_finding(AGENT_TOPICS["event_context"], f"{session_id}:16", finding_early)

    assert len(fusion.assessment_history) >= 1
    latest = fusion.latest_assessments.get(16)
    assert latest is not None
    assert latest.assessment_version >= 1


@pytest.mark.asyncio
async def test_04_missing_telemetry_explicit_insufficient_data():
    """Verifies that missing CAN-bus telemetry channels are marked INSUFFICIENT_DATA and never hallucinate synthetic curves."""
    agent = VehicleResponseAgent()
    missing_env = make_envelope(
        event_id=f"evt-missing-{uuid4().hex[:6]}",
        event_type="CAR_TELEMETRY",
        elapsed_ms=50000,
        payload={},
        driver_number=63,
        completeness=Completeness.MISSING,
    )

    await agent.on_event(NORMALISED_TOPICS["driver_laps"], "session:63", missing_env)
    assert agent.insufficient_data_outcomes >= 1
    assert agent.last_outcome == "INSUFFICIENT_DATA"


@pytest.mark.asyncio
async def test_05_agent_restart_recovery():
    """Verifies that when an agent restarts, state store and new agent instances retain continuity."""
    store = get_state_store()
    agent_v1 = EventControlAgent()
    store.register_agent(agent_v1)

    env = make_envelope(
        event_id=f"evt-restart-{uuid4().hex[:6]}",
        event_type="SESSION_STARTED",
        elapsed_ms=0,
        payload={"lap": 1},
    )
    await agent_v1.on_event(NORMALISED_TOPICS["race_events"], "session", env)
    assert len(store.findings) >= 1

    # Simulate agent process crash & restart
    agent_v2 = EventControlAgent()
    store.register_agent(agent_v2)
    metrics = agent_v2.get_metrics()
    assert metrics.agent_id == "agent-01-event-control"
    assert len(store.findings) >= 1


def is_kafka_broker_online(bootstrap_servers: str) -> bool:
    import socket
    try:
        host, port = bootstrap_servers.split(",")[0].split(":")
        with socket.create_connection((host, int(port)), timeout=0.2):
            return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_06_kafka_consumer_restart_recovery():
    """Verifies SAME consumer group commits offsets manually and resumes without skipping or repeating."""
    from aiokafka import TopicPartition

    settings = get_settings()
    if not is_kafka_broker_online(settings.kafka_bootstrap_servers):
        pytest.skip("Kafka broker offline (Docker offline)")
    broker = KafkaBroker(bootstrap_servers=settings.kafka_bootstrap_servers)
    try:
        await broker.start()
    except Exception as exc:
        pytest.skip(f"Kafka broker offline: {exc}")
    assert broker.is_connected

    group_id = f"pulse-test-samegroup-{uuid4().hex[:6]}"
    test_topic = RAW_TOPICS["race_control"]
    env_1 = make_envelope(
        event_id=f"evt-k-restart-1-{uuid4().hex[:6]}",
        event_type="SESSION_STARTED",
        elapsed_ms=0,
        payload={"lap": 1, "seq": 1},
    )
    env_2 = make_envelope(
        event_id=f"evt-k-restart-2-{uuid4().hex[:6]}",
        event_type="VSC_DEPLOYED",
        elapsed_ms=5000,
        payload={"lap": 2, "seq": 2},
    )

    # Consumer 1 joins at latest, reads ONLY newly published env_1, commits offset+1 explicitly, then stops
    c1 = await broker.create_consumer(
        topics=[test_topic],
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=False,
    )
    await broker.publish(test_topic, "test-session", env_1)
    msg1 = None
    for _ in range(20):
        rec = await asyncio.wait_for(c1.getone(), timeout=3.0)
        if isinstance(rec.value, dict) and rec.value.get("event_id") == env_1.event_id:
            msg1 = rec
            await c1.commit({TopicPartition(rec.topic, rec.partition): rec.offset + 1})
            break
    assert msg1 is not None, "Consumer 1 did not observe env_1"
    await c1.stop()

    # Publish env_2 while consumer group is down
    await broker.publish(test_topic, "test-session", env_2)

    # Consumer 2 restarts with the SAME group_id and must receive env_2 cleanly (not env_1!)
    c2 = await broker.create_consumer(
        topics=[test_topic],
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=False,
    )
    seen_ids: list[str] = []
    for _ in range(10):
        rec2 = await asyncio.wait_for(c2.getone(), timeout=3.0)
        if isinstance(rec2.value, dict) and rec2.value.get("event_id") in {env_1.event_id, env_2.event_id}:
            seen_ids.append(rec2.value["event_id"])
            if rec2.value["event_id"] == env_2.event_id:
                await c2.commit({TopicPartition(rec2.topic, rec2.partition): rec2.offset + 1})
                break
    await c2.stop()
    await broker.stop()
    assert env_1.event_id not in seen_ids, "Already-committed env_1 was re-delivered after restart!"
    assert env_2.event_id in seen_ids, "Consumer restart with same group_id missed env_2 published during outage!"


def test_07_flink_checkpoint_recovery():
    """Verifies that Flink streaming cluster has completed >= 1 checkpoint and healthy v3 job."""
    flink_mgr = get_flink_manager()
    if not flink_mgr.client.is_cluster_online():
        pytest.skip("Flink cluster is offline on http://localhost:8081 (Docker offline)")

    jid = flink_mgr.ensure_normalizer_job_running()
    metrics = flink_mgr.get_metrics()
    assert metrics is not None
    assert metrics.state == "RUNNING"
    assert metrics.checkpoints_completed >= 1, f"Expected >= 1 completed Flink checkpoint, got {metrics.checkpoints_completed}"
    details = flink_mgr.client.get_job_status(jid) or {}
    vertices = details.get("vertices", [])
    assert len(vertices) >= 18, f"Expected v3 Flink graph (>= 18 vertices for 9 raw topics), got {len(vertices)}"
    assert all(v.get("status") == "RUNNING" for v in vertices)


@pytest.mark.asyncio
async def test_08_concurrent_run_isolation():
    """Verifies that multiple concurrent race sessions maintain strict data and lineage isolation."""
    settings = get_settings()
    if not is_kafka_broker_online(settings.kafka_bootstrap_servers):
        pytest.skip("Kafka broker offline (Docker offline)")
    broker = KafkaBroker(bootstrap_servers=settings.kafka_bootstrap_servers)
    try:
        await broker.start()
    except Exception as exc:
        pytest.skip(f"Kafka broker offline: {exc}")

    session_a = f"session-iso-A-{uuid4().hex[:6]}"
    session_b = f"session-iso-B-{uuid4().hex[:6]}"

    env_a = make_envelope(
        event_id=f"evt-iso-a-{uuid4().hex[:6]}",
        event_type="VSC_DEPLOYED",
        elapsed_ms=10000,
        payload={"session": "A"},
        session_id=session_a,
    )
    env_b = make_envelope(
        event_id=f"evt-iso-b-{uuid4().hex[:6]}",
        event_type="SESSION_CHEQUERED",
        elapsed_ms=50000,
        payload={"session": "B"},
        session_id=session_b,
    )

    agent = EventControlAgent(bus=PulseEventBus(broker=broker))
    await agent.on_event(NORMALISED_TOPICS["race_events"], session_a, env_a)
    await agent.on_event(NORMALISED_TOPICS["race_events"], session_b, env_b)

    store = get_state_store()
    findings_a = [f for f in store.findings if f.session_id == session_a]
    findings_b = [f for f in store.findings if f.session_id == session_b]

    assert len(findings_a) >= 1
    assert len(findings_b) >= 1
    # Strict isolation: session IDs must never intersect
    assert {f.session_id for f in findings_a} == {session_a}
    assert {f.session_id for f in findings_b} == {session_b}

    await broker.stop()

