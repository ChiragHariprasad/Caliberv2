"""Phase H Targeted Verification & Hardening Tests.

Covers critical fixes verified during Phase H audit:
1. Flink v3 SQL normalization of pulse.raw.telemetry.car.v1 & pulse.raw.session_status.v1.
2. Out-of-order cross-partition session_t0 supersession invariance in IntegrityAgent.
3. SIAWALStore.sync_engine() + set_wal_paused(False) + crash-restart restore_from_wal().
4. FastAPI lifespan WAL preservation on restart vs explicit reset cleanup.
5. IdempotentVerdictSink pre-check + duplicate/poison protection cleanly coupled to WAL.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from pulse.contracts import (
    Completeness,
    EventEnvelope,
    EventTime,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
)
from pulse.integrity.agent import IntegrityAgent
from pulse.main import create_app
from pulse.replay.controller import get_replay_controller
from pulse.state.store import get_state_store
from pulse.stream.flink.manager import get_flink_manager
from pulse.stream.kafka_client import KafkaBroker
from pulse.stream.kafka_io import IdempotentVerdictSink
from pulse.topics import NORMALISED_TOPICS, RAW_TOPICS


def _make_evt(
    event_id: str,
    event_type: str,
    evt_dt: datetime,
    elapsed_ms: int,
    payload: dict,
    *,
    session_id: str,
    driver_number: int | None = None,
    provider: str = "FASTF1_RESEARCH",
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        source=SourceRef(
            provider=provider,
            adapter="phase_h_test",
            source_record_id=f"src-{event_id}",
            capture_id=session_id,
        ),
        run=RunContext(
            run_id=f"run-ph-{uuid4().hex[:6]}",
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
            event_time_utc=evt_dt,
            session_elapsed_ms=elapsed_ms,
        ),
        subject=Subject(driver_number=driver_number),
        payload=payload,
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )


@pytest.mark.asyncio
async def test_cross_partition_out_of_order_session_t0_supersession_invariance(tmp_path: Path) -> None:
    """Verify authoritative SESSION_STARTED supersedes provisional session_t0 from earlier partition."""
    t0 = datetime(2023, 7, 9, 14, 0, 0, tzinfo=timezone.utc)
    t_lap = t0 + timedelta(seconds=90)
    sess_seq = f"sess-seq-{uuid4().hex[:6]}"
    sess_ooo = f"sess-ooo-{uuid4().hex[:6]}"

    # Path A: Natural order (SESSION_STARTED arrives before LAP_COMPLETED)
    ia_seq = IntegrityAgent(wal_path=tmp_path / "seq.sqlite", session_id=sess_seq)
    e_start_a = _make_evt(
        f"e-start-a-{uuid4().hex[:4]}",
        "SESSION_STARTED",
        t0,
        0,
        {"lap": 1},
        session_id=sess_seq,
    )
    e_lap_a = _make_evt(
        f"e-lap-a-{uuid4().hex[:4]}",
        "LAP_COMPLETED",
        t_lap,
        90_000,
        {"lap_number": 1, "lap_time_seconds": 90.0},
        session_id=sess_seq,
        driver_number=16,
    )
    await ia_seq.on_event(NORMALISED_TOPICS["race_events"], sess_seq, e_start_a)
    await ia_seq.on_event(NORMALISED_TOPICS["driver_laps"], f"{sess_seq}:16", e_lap_a)

    # Path B: Out-of-order cross-partition arrival (LAP_COMPLETED arrives before SESSION_STARTED)
    ia_ooo = IntegrityAgent(wal_path=tmp_path / "ooo.sqlite", session_id=sess_ooo)
    e_start_b = _make_evt(
        f"e-start-b-{uuid4().hex[:4]}",
        "SESSION_STARTED",
        t0,
        0,
        {"lap": 1},
        session_id=sess_ooo,
    )
    e_lap_b = _make_evt(
        f"e-lap-b-{uuid4().hex[:4]}",
        "LAP_COMPLETED",
        t_lap,
        90_000,
        {"lap_number": 1, "lap_time_seconds": 90.0},
        session_id=sess_ooo,
        driver_number=16,
    )
    await ia_ooo.on_event(NORMALISED_TOPICS["driver_laps"], f"{sess_ooo}:16", e_lap_b)
    await ia_ooo.on_event(NORMALISED_TOPICS["race_events"], sess_ooo, e_start_b)

    t0_seq = ia_seq._engine.ledger.facts("session_t0")
    t0_ooo = ia_ooo._engine.ledger.facts("session_t0")
    assert len(t0_seq) == 1
    assert len(t0_ooo) == 2
    assert t0_ooo[-1].fact.supersedes == t0_ooo[0].fact.fact_id
    assert t0_ooo[-1].fact.value == t0_seq[0].fact.value
    assert ia_ooo._session_t0_official is True
    ia_seq._wal.close()
    ia_ooo._wal.close()


@pytest.mark.asyncio
async def test_sia_wal_pause_sync_engine_and_crash_restart_recovery(tmp_path: Path) -> None:
    """Exercise fixed sync_engine() via set_wal_paused and verify full crash/restart recovery."""
    wal_db = tmp_path / "pulse_sia_wal.sqlite"
    sess = f"sess-crash-{uuid4().hex[:6]}"
    t0 = datetime(2023, 7, 9, 14, 0, 0, tzinfo=timezone.utc)

    ia1 = IntegrityAgent(wal_path=wal_db, session_id=sess)
    ia1.set_wal_paused(True)
    await ia1.on_event(
        NORMALISED_TOPICS["race_events"],
        sess,
        _make_evt("e-start", "SESSION_STARTED", t0, 0, {"lap": 1}, session_id=sess),
    )
    await ia1.on_event(
        NORMALISED_TOPICS["track_segments"],
        sess,
        _make_evt("e-wx", "WEATHER_OBSERVATION", t0 + timedelta(seconds=10), 10_000, {"air_temp_c": 23.4}, session_id=sess),
    )
    await ia1.on_event(
        NORMALISED_TOPICS["driver_laps"],
        f"{sess}:44",
        _make_evt("e-lap", "LAP_COMPLETED", t0 + timedelta(seconds=90), 90_000, {"lap_number": 1, "lap_time_seconds": 89.2}, session_id=sess, driver_number=44),
    )
    # Force WAL sync (previously threw AttributeError in sia_core.wal.sync_engine!)
    ia1.set_wal_paused(False)

    orig_counts = ia1._engine.ledger.counts()
    orig_verify = ia1._engine.verify()
    orig_verdicts = {v["decision_instance_id"]: v["record_hash"] for v in ia1.get_all_verdicts()}
    assert orig_counts["atoms"] >= 2
    assert orig_counts["facts"] >= 2
    assert len(orig_verdicts) >= 1
    assert all(res == "OK" for res in orig_verify.values())
    ia1._wal.close()

    # Simulate clean restart into brand-new IntegrityAgent bound to same WAL
    ia2 = IntegrityAgent(wal_path=wal_db, session_id=sess)
    assert ia2.restore_from_wal() is True
    assert ia2._engine.ledger.counts() == orig_counts
    assert ia2._engine.verify() == orig_verify
    restored_verdicts = {v["decision_instance_id"]: v["record_hash"] for v in ia2.get_all_verdicts()}
    assert restored_verdicts == orig_verdicts
    assert ia2._session_t0_admitted is True
    ia2._wal.close()


@pytest.mark.asyncio
async def test_idempotent_verdict_sink_precheck_and_atomicity(tmp_path: Path) -> None:
    """Verify has_verdict + insert_verdict prevents crash-window loss and duplicate commits."""
    sink = IdempotentVerdictSink(tmp_path / "verdicts_phase_h.sqlite")
    topic, part, offset = NORMALISED_TOPICS["race_events"], 0, 77
    assert sink.has_verdict(topic, part, offset) is False
    assert sink.insert_verdict(topic, part, offset, "sess:16", "evt-77") is True
    assert sink.has_verdict(topic, part, offset) is True
    assert sink.insert_verdict(topic, part, offset, "sess:16", "evt-77") is False
    assert sink.count() == 1


def test_lifespan_wal_preserved_on_restart_and_cleared_on_reset(tmp_path: Path, monkeypatch) -> None:
    """Verify main.py wires settings.sia_wal_path cleanly on startup and preserves crash WAL."""
    wal_file = tmp_path / "lifespan_wal.sqlite"
    monkeypatch.setenv("PULSE_TRANSPORT_MODE", "MEMORY")
    monkeypatch.setenv("PULSE_SIA_WAL_PATH", str(wal_file))
    from pulse.config import get_settings
    get_settings.cache_clear()
    try:
        # Boot 1: ingest weather atom via API / StateStore
        app1 = create_app()
        with TestClient(app1):
            store1 = get_state_store()
            rc1 = get_replay_controller()
            ia1 = store1.agents["agent-06-integrity"]
            assert ia1._wal is not None
            assert Path(ia1._wal.db_path) == wal_file
            asyncio.run(
                ia1.on_event(
                    NORMALISED_TOPICS["track_segments"],
                    rc1.session_id,
                    _make_evt(
                        f"evt-life-{uuid4().hex[:6]}",
                        "WEATHER_OBSERVATION",
                        datetime(2023, 7, 9, 14, 0, 5, tzinfo=timezone.utc),
                        5000,
                        {"air_temp_c": 25.0},
                        session_id=rc1.session_id,
                    ),
                )
            )
            assert ia1._engine.ledger.counts()["atoms"] >= 1
            ia1._wal.close()

        # Boot 2: startup preserves WAL state automatically without wiping prior ledger
        app2 = create_app()
        with TestClient(app2) as client2:
            ia2 = get_state_store().agents["agent-06-integrity"]
            assert ia2._engine.ledger.counts()["atoms"] >= 1
            assert any(v["integrity_state"] == "HEALTHY" for v in ia2.get_all_verdicts())
            # Explicit replay reset clears session WAL cleanly for a fresh run
            res_reset = client2.post("/api/replay/reset")
            assert res_reset.status_code == 200
            assert ia2._engine.ledger.counts()["atoms"] == 0
            if ia2._wal is not None:
                ia2._wal.close()
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_flink_v3_normalizes_telemetry_car_and_session_status() -> None:
    """Verify Flink pulse-canonical-normalizer-v3 handles the 2 previously dropped RAW_TOPICS."""
    from confluent_kafka import Consumer, TopicPartition

    flink_mgr = get_flink_manager()
    if not flink_mgr.client.is_cluster_online():
        pytest.skip("Flink cluster offline")

    settings = get_flink_manager()  # reuse manager
    from pulse.config import get_settings
    cfg = get_settings()
    jid = flink_mgr.ensure_normalizer_job_running()
    assert jid

    probe = Consumer({
        "bootstrap.servers": cfg.kafka_bootstrap_servers,
        "group.id": f"ph-flink-probe-{uuid4().hex[:6]}",
        "isolation.level": "read_committed",
        "enable.auto.commit": False,
    })
    start_tps = []
    md = probe.list_topics(timeout=10.0)
    for topic in (NORMALISED_TOPICS["driver_state"], NORMALISED_TOPICS["race_events"]):
        tmeta = md.topics[topic]
        for pid in sorted(tmeta.partitions):
            start_tps.append(TopicPartition(topic, pid, probe.get_watermark_offsets(TopicPartition(topic, pid), timeout=5.0)[1]))
    probe.assign(start_tps)

    broker = KafkaBroker(bootstrap_servers=cfg.kafka_bootstrap_servers)
    await broker.start()
    tag = uuid4().hex[:8]
    evt_tel = _make_evt(
        f"evt-tel-{tag}",
        "CAR_TELEMETRY",
        datetime(2023, 7, 9, 14, 1, 0, tzinfo=timezone.utc),
        60_000,
        {"speed_kph": 308.0},
        session_id=f"sess-ph-{tag}",
        driver_number=16,
    )
    evt_stat = _make_evt(
        f"evt-stat-{tag}",
        "SESSION_STATUS",
        datetime(2023, 7, 9, 14, 1, 2, tzinfo=timezone.utc),
        62_000,
        {"status": "Started"},
        session_id=f"sess-ph-{tag}",
    )

    await broker.publish(RAW_TOPICS["telemetry_car"], f"sess-ph-{tag}:16", evt_tel)
    await broker.publish(RAW_TOPICS["session_status"], f"sess-ph-{tag}", evt_stat)
    await broker.stop()

    found_ids: set[str] = set()
    deadline = asyncio.get_event_loop().time() + 20.0
    while len(found_ids) < 2 and asyncio.get_event_loop().time() < deadline:
        msgs = probe.consume(num_messages=200, timeout=0.5)
        for m in msgs:
            if m.error() or m.value() is None:
                continue
            try:
                data = json.loads(m.value().decode("utf-8"))
            except Exception:
                continue
            eid = data.get("event_id")
            if eid in {evt_tel.event_id, evt_stat.event_id}:
                found_ids.add(eid)
        await asyncio.sleep(0.1)
    probe.close()

    assert evt_tel.event_id in found_ids, "Flink v3 did not normalize pulse.raw.telemetry.car.v1 -> driver_state!"
    assert evt_stat.event_id in found_ids, "Flink v3 did not normalize pulse.raw.session_status.v1 -> race_events!"
