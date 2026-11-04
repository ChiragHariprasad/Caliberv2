from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from pulse.agents.event_control import EventControlAgent
from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.agents.track_state import TrackStateAgent
from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
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
from pulse.topics import NORMALISED_TOPICS


def make_test_envelope(
    event_id: str,
    event_type: str,
    payload: dict | None = None,
    driver_number: int | None = None,
    segment_id: str | None = None,
    completeness: Completeness = Completeness.COMPLETE,
) -> EventEnvelope:
    now = utc_now()
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        source=SourceRef(
            provider="PULSE_MULTI_AGENT_TEST",
            adapter="multi_agent_test_v1",
            source_record_id=f"src-{event_id}",
            capture_id="multi-agent-spec-2026",
        ),
        run=RunContext(
            run_id="run-multi-agent-01",
            session_instance_id="session-multi-agent-01",
            mode=RunMode.REPLAY,
        ),
        session=SessionRef(
            season=2026,
            meeting_id="silverstone-2026",
            session_id="session-multi-agent-01",
            session_type="RACE",
        ),
        time=EventTime(
            event_time_utc=now,
            session_elapsed_ms=35000,
            ingest_time_utc=now,
        ),
        subject=Subject(driver_number=driver_number, segment_id=segment_id),
        payload=payload or {},
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=completeness,
            unit_validation=UnitValidation.PASSED,
        ),
    )


@pytest.mark.asyncio
async def test_agent_1_lifecycle_and_transparency():
    mock_bus = AsyncMock()
    agent = EventControlAgent(bus=mock_bus)

    # Session start
    start_evt = make_test_envelope("evt-start-01", "SESSION_STARTED")
    await agent.on_event("pulse.norm.race_events.v1", "session", start_evt)

    assert agent.active_lifecycle == "ACTIVE"
    assert agent.active_event_type == "GREEN_FLAG"
    assert mock_bus.publish.call_count == 1

    metrics = agent.get_metrics()
    assert metrics.inputs_received == 1
    assert metrics.eligible_inputs == 1
    assert metrics.findings_emitted == 1
    assert metrics.last_outcome == "FINDING_EMITTED"
    assert "finding-start-evt-start-01" in metrics.output_finding_ids


@pytest.mark.asyncio
async def test_agent_2_track_state_and_weather():
    mock_bus = AsyncMock()
    agent = TrackStateAgent(bus=mock_bus)

    # 1. Weather observation with temperature and rain probability
    weather_evt = make_test_envelope(
        "evt-wthr-01",
        "WEATHER_OBSERVATION",
        payload={"air_temp_c": 21.5, "track_temp_c": 31.0, "humidity_pct": 68.0, "rain_risk_percent": 35.0},
    )
    await agent.on_event("pulse.norm.track_segments.v1", "circuit", weather_evt)

    assert mock_bus.publish.call_count == 1
    call_args = mock_bus.publish.call_args[0]
    finding = call_args[2]
    assert finding.finding_type in {"WEATHER_STATE", "WEATHER_TRANSITION"}
    assert finding.result["weather"]["track_temp_c"] == 31.0

    # 2. Incomplete weather payload -> explicit INSUFFICIENT_DATA outcome
    bad_weather_evt = make_test_envelope("evt-wthr-bad", "WEATHER_OBSERVATION", payload={})
    await agent.on_event("pulse.norm.track_segments.v1", "circuit", bad_weather_evt)

    metrics = agent.get_metrics()
    assert metrics.insufficient_data_outcomes == 1


@pytest.mark.asyncio
async def test_agent_3_vehicle_response_and_traffic():
    mock_bus = AsyncMock()
    agent = VehicleResponseAgent(bus=mock_bus)

    # Driver 4 (Norris) in traffic: lap time 76.50s (baseline 76.00s) with interval 0.8s
    lap_evt = make_test_envelope(
        "evt-lap-norris",
        "LAP_COMPLETED",
        driver_number=4,
        payload={"last_lap_seconds": 76.50, "interval": "+0.80s", "tyre_age": 14},
    )
    await agent.on_event("pulse.norm.driver_laps.v1", "session:4", lap_evt)

    assert mock_bus.publish.call_count == 1
    finding = mock_bus.publish.call_args[0][2]
    assert finding.finding_type == "PACE_DEVIATION"
    assert finding.result["driver_number"] == 4
    assert finding.result["clean_air"] is False
    assert finding.result["classification"] == "DIRTY_AIR_IMPEDED"
    assert "TRAFFIC_CONGESTION_PACE_LOSS" in finding.reason_codes

    # Missing completeness payload -> explicit INSUFFICIENT_DATA
    missing_evt = make_test_envelope(
        "evt-lap-missing",
        "LAP_COMPLETED",
        driver_number=4,
        completeness=Completeness.MISSING,
    )
    await agent.on_event("pulse.norm.driver_laps.v1", "session:4", missing_evt)
    metrics = agent.get_metrics()
    assert metrics.insufficient_data_outcomes == 1


@pytest.mark.asyncio
async def test_agent_4_tyre_strategy_scenarios():
    mock_bus = AsyncMock()
    agent = TyreStrategyAgent(bus=mock_bus)

    # VSC deployed triggers pit window evaluation for driver #1 (Verstappen)
    vsc_evt = make_test_envelope(
        "evt-vsc-ver",
        "VSC_DEPLOYED",
        driver_number=1,
        payload={"reason": "Sector 2 barrier inspection"},
    )
    await agent.on_event("pulse.norm.race_events.v1", "session:1", vsc_evt)

    assert mock_bus.publish.call_count == 1
    finding = mock_bus.publish.call_args[0][2]
    assert finding.finding_type == "PIT_WINDOW_OPPORTUNITY"
    assert finding.result["driver_number"] == 1
    assert finding.result["net_time_saving_sec"] == 10.5
    assert "assumptions" in finding.result
    assert finding.result["assumptions"]["calculation_version"] == agent.model_version
    assert len(finding.result["scenarios"]) == 3


@pytest.mark.asyncio
async def test_agent_5_asynchronous_fusion_and_revisions():
    mock_bus = AsyncMock()
    fusion = ConsequenceFusionEngine(bus=mock_bus)
    now = utc_now()

    # 1. Agent 1 exposure finding arrives -> provisional v1
    exp_f = Finding(
        finding_id="f-exp-01",
        agent_id="agent-01-event-control",
        finding_type="DRIVER_EVENT_EXPOSURE",
        session_id="silverstone-2026",
        run_id="run-01",
        subject=Subject(driver_number=81),  # Piastri
        trigger_event_id="evt-vsc-piastri",
        as_of_event_time=now,
        interpretation=Interpretation.DERIVED,
        result={"driver_number": 81, "exposure_level": "CRITICAL_OPPORTUNITY"},
        evidence_refs=["evt-vsc-piastri"],
    )
    await fusion.on_finding("pulse.agent.event_context.findings.v1", "silverstone:81", exp_f)

    assert 81 in fusion.latest_assessments
    v1 = fusion.latest_assessments[81]
    assert v1.assessment_version == 1
    assert v1.status == FindingStatus.PROVISIONAL

    # 2. Agent 4 tyre strategy arrives later -> superseding v2
    strat_f = Finding(
        finding_id="f-strat-01",
        agent_id="agent-04-tyre-strategy",
        finding_type="PIT_WINDOW_OPPORTUNITY",
        session_id="silverstone-2026",
        run_id="run-01",
        subject=Subject(driver_number=81),
        trigger_event_id="evt-vsc-piastri",
        as_of_event_time=now,
        interpretation=Interpretation.DERIVED,
        result={
            "driver_number": 81,
            "target_compound": "H",
            "stint_age_current": 18,
            "net_time_saving_sec": 10.5,
        },
        evidence_refs=["evt-vsc-piastri", "stint-med-18"],
    )
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "silverstone:81", strat_f)

    v2 = fusion.latest_assessments[81]
    assert v2.assessment_version == 2
    assert v2.status == FindingStatus.CONFIRMED
    assert v2.supersedes_assessment_id == v1.assessment_id
    assert v1.assessment_id in v2.evidence_refs

