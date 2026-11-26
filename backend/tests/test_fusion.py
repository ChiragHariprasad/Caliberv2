from datetime import UTC, datetime
import pytest
from unittest.mock import AsyncMock

from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.contracts import Finding, FindingStatus, Interpretation, Subject


@pytest.mark.asyncio
async def test_fusion_engine_provisional_v1_and_superseding_v2():
    mock_bus = AsyncMock()
    fusion = ConsequenceFusionEngine(bus=mock_bus)

    now = datetime.now(UTC)

    # 1. Agent 1 emits exposure finding -> triggers v1
    exp_finding = Finding(
        finding_id="finding-exp-1",
        agent_id="agent-01-event-control",
        finding_type="DRIVER_EVENT_EXPOSURE",
        session_id="sim-monaco",
        run_id="run-01",
        subject=Subject(driver_number=16),
        trigger_event_id="evt-vsc-1",
        as_of_event_time=now,
        interpretation=Interpretation.DERIVED,
        result={"driver_number": 16, "exposure_level": "CRITICAL_OPPORTUNITY"},
        evidence_refs=["evt-vsc-1"],
    )

    await fusion.on_finding("pulse.agent.event_context.findings.v1", "sim-monaco:16", exp_finding)

    assert 16 in fusion.latest_assessments
    v1 = fusion.latest_assessments[16]
    assert v1.assessment_version == 1
    assert v1.status == FindingStatus.PROVISIONAL
    assert v1.supersedes_assessment_id is None

    # 2. Agent 4 emits tyre strategy finding -> triggers superseding v2
    strat_finding = Finding(
        finding_id="finding-strat-1",
        agent_id="agent-04-tyre-strategy",
        finding_type="PIT_WINDOW_OPPORTUNITY",
        session_id="sim-monaco",
        run_id="run-01",
        subject=Subject(driver_number=16),
        trigger_event_id="evt-vsc-1",
        as_of_event_time=now,
        interpretation=Interpretation.DERIVED,
        result={
            "driver_number": 16,
            "target_compound": "H",
            "stint_age_current": 23,
            "net_time_saving_sec": 10.5,
            "gap_to_p2_sec": 2.48,
        },
        evidence_refs=["evt-vsc-1", "stint-med-23"],
    )

    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "sim-monaco:16", strat_finding)

    assert 16 in fusion.latest_assessments
    v2 = fusion.latest_assessments[16]
    assert v2.assessment_version == 2
    assert v2.status == FindingStatus.CONFIRMED
    assert v2.supersedes_assessment_id == v1.assessment_id
    assert len(fusion.assessment_history) == 2


@pytest.mark.asyncio
async def test_fusion_handles_none_pace_delta_bounded_buffer_and_sia_conflict_gate():
    mock_bus = AsyncMock()
    fusion = ConsequenceFusionEngine(bus=mock_bus)
    now = datetime.now(UTC)

    # 1. Cold-start pace finding with pace_delta_sec=None must not crash and must record INITIALIZING
    pace_cold = Finding(
        finding_id="finding-pace-cold",
        agent_id="agent-03-vehicle-response",
        finding_type="PACE_DEVIATION",
        session_id="sess-a",
        run_id="run-a",
        subject=Subject(driver_number=4),
        trigger_event_id="evt-lap1",
        as_of_event_time=now,
        interpretation=Interpretation.INFERRED,
        result={
            "driver_number": 4,
            "pace_delta_sec": None,
            "baseline_status": "INITIALIZING",
            "classification": "DIRTY_AIR_IMPEDED",
            "clean_air": False,
        },
        evidence_refs=["evt-lap1"],
    )
    await fusion.on_finding("pulse.agent.vehicle_response.findings.v1", "sess-a:4", pace_cold)
    assert 4 in fusion.latest_assessments
    assert "PACE_BASELINE_INITIALIZING" in fusion.latest_assessments[4].uncertainty["conflicts"]

    # 2. Inject SIA SUSPECT integrity verdict for driver 4 in sess-a -> must block CONFIRMED strategy endorsement
    sia_alert = Finding(
        finding_id="finding-sia-1",
        agent_id="agent-06-integrity",
        finding_type="INTEGRITY_VERDICT",
        session_id="sess-a",
        run_id="run-a",
        subject=Subject(driver_number=4),
        trigger_event_id="evt-pit-spd",
        as_of_event_time=now,
        interpretation=Interpretation.DERIVED,
        result={"verdict": "SUSPECT", "reason": "distance_check violation"},
        evidence_refs=["evt-pit-spd"],
    )
    await fusion.on_finding("pulse.agent.integrity.findings.v1", "sess-a:4", sia_alert)

    strat = Finding(
        finding_id="finding-strat-conflict",
        agent_id="agent-04-tyre-strategy",
        finding_type="PIT_WINDOW_OPPORTUNITY",
        session_id="sess-a",
        run_id="run-a",
        subject=Subject(driver_number=4),
        trigger_event_id="evt-vsc-2",
        as_of_event_time=now,
        interpretation=Interpretation.PREDICTED,
        result={
            "driver_number": 4,
            "target_compound": "H",
            "stint_age_current": 18,
            "net_time_saving_sec": 9.8,
            "uncertainty_sec": 1.4,
            "calibration_status": "EMPIRICAL_PIT_CALIBRATED",
            "reentry_window": "P5",
        },
        evidence_refs=["evt-vsc-2"],
    )
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "sess-a:4", strat)
    fused = fusion._scoped_assessments[("sess-a", 4)]
    assert fused.status == FindingStatus.PROVISIONAL
    assert fused.uncertainty["tactical_recommendation"] == "HOLD_VERIFY_INTEGRITY"
    assert "TRAFFIC_REENTRY_VS_PIT_WINDOW_CONFLICT" in fused.uncertainty["conflicts"]
    assert any(c.startswith("SIA_INTEGRITY_SUSPECT") for c in fused.uncertainty["conflicts"])

    # 3. Buffer bound enforcement (maxlen=25) & session isolation (sess-b must not see sess-a conflict)
    for i in range(40):
        f_loop = Finding(
            finding_id=f"f-loop-{i}",
            agent_id="agent-03-vehicle-response",
            finding_type="PACE_DEVIATION",
            session_id="sess-b",
            run_id="run-b",
            subject=Subject(driver_number=4),
            trigger_event_id=f"evt-{i}",
            as_of_event_time=now,
            interpretation=Interpretation.OBSERVED,
            result={"driver_number": 4, "pace_delta_sec": 0.1, "baseline_status": "STINT_ROLLING_CALIBRATED", "clean_air": True},
            evidence_refs=[f"evt-{i}"],
        )
        await fusion.on_finding("pulse.agent.vehicle_response.findings.v1", "sess-b:4", f_loop)

    assert len(fusion._buf("sess-b", 4)) == 25
    assert "SIA_INTEGRITY_SUSPECT" not in str(fusion._scoped_assessments[("sess-b", 4)].uncertainty["conflicts"])

