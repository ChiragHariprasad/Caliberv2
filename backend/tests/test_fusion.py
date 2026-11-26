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
    # Strictly prohibit promoting uncalibrated PRIOR_UNMEASURED findings to CONFIRMED without positive calibration & corroboration
    assert v2.status == FindingStatus.PROVISIONAL
    assert "UNCALIBRATED_PRIOR_BASELINE" in v2.uncertainty["conflicts"]
    assert v1.status == FindingStatus.SUPERSEDED
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


def _make_strat_finding(
    session_id: str = "sess-ev",
    driver_number: int = 1,
    cal_status: str = "EMPIRICAL_PIT_CALIBRATED+DRIVER_STINT_CALIBRATED",
    sample_laps: int = 8,
    deg_cal: str = "DRIVER_STINT_CALIBRATED",
    extra_result: dict | None = None,
    assessment_status: FindingStatus = FindingStatus.CONFIRMED,
) -> Finding:
    res = {
        "driver_number": driver_number,
        "target_compound": "H",
        "stint_age_current": 16,
        "net_time_saving_sec": 11.2,
        "uncertainty_sec": 1.1,
        "calibration_status": cal_status,
        "sample_count": sample_laps,
        "degradation_estimate": {
            "compound": "M",
            "slope_sec_per_lap": 0.045,
            "slope_se_sec_per_lap": 0.01,
            "sample_laps": sample_laps,
            "calibration_status": deg_cal,
        },
        "reentry_window": "P2",
    }
    if extra_result:
        res.update(extra_result)
    return Finding(
        finding_id=f"f-strat-{session_id}-{driver_number}-{cal_status[:6]}",
        agent_id="agent-04-tyre-strategy",
        finding_type="PIT_WINDOW_OPPORTUNITY",
        session_id=session_id,
        run_id="run-ev",
        subject=Subject(driver_number=driver_number),
        trigger_event_id="evt-vsc",
        as_of_event_time=datetime.now(UTC),
        interpretation=Interpretation.PREDICTED if "EMPIRICAL" in cal_status else Interpretation.INFERRED,
        assessment_status=assessment_status,
        result=res,
        evidence_refs=["evt-vsc"],
    )


@pytest.mark.asyncio
async def test_fusion_uncalibrated_prior_cannot_confirm():
    """1. Uncalibrated prior must stay PROVISIONAL even when no SIA integrity alert is present."""
    fusion = ConsequenceFusionEngine(bus=AsyncMock())
    f = _make_strat_finding("s1", 1, cal_status="PRIOR_UNMEASURED", deg_cal="PRIOR_UNMEASURED", sample_laps=0, assessment_status=FindingStatus.PROVISIONAL)
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s1:1", f)
    a = fusion._scoped_assessments[("s1", 1)]
    assert a.status == FindingStatus.PROVISIONAL
    assert "UNCALIBRATED_PRIOR_BASELINE" in a.uncertainty["conflicts"]


@pytest.mark.asyncio
async def test_fusion_missing_telemetry_blocks_confirmation():
    """2. Missing telemetry blocks confirmation across pace and strategy findings."""
    fusion = ConsequenceFusionEngine(bus=AsyncMock())
    now = datetime.now(UTC)
    pace = Finding(
        finding_id="f-miss-pace",
        agent_id="agent-03-vehicle-response",
        finding_type="PACE_DEVIATION",
        session_id="s2",
        run_id="run-2",
        subject=Subject(driver_number=4),
        trigger_event_id="evt-1",
        as_of_event_time=now,
        interpretation=Interpretation.OBSERVED,
        result={"driver_number": 4, "pace_delta_sec": None, "baseline_status": "STINT_ROLLING_CALIBRATED", "clean_air": None, "clean_air_status": "CLEAN_AIR_UNKNOWN", "missing_telemetry": True},
        evidence_refs=["evt-1"],
    )
    await fusion.on_finding("pulse.agent.vehicle_response.findings.v1", "s2:4", pace)
    assert fusion._scoped_assessments[("s2", 4)].status == FindingStatus.PROVISIONAL

    strat = _make_strat_finding("s2", 4, extra_result={"independently_corroborated": True})
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s2:4", strat)
    assert fusion._scoped_assessments[("s2", 4)].status == FindingStatus.PROVISIONAL
    assert "MISSING_TELEMETRY_COVERAGE" in fusion._scoped_assessments[("s2", 4)].uncertainty["conflicts"]


@pytest.mark.asyncio
async def test_fusion_insufficient_samples_blocks_confirmation():
    """3. Insufficient samples (<5 clean laps) prevent confirmation even if empirical pit flag exists."""
    fusion = ConsequenceFusionEngine(bus=AsyncMock())
    sia_ok = Finding(
        finding_id="f-sia-ok-3",
        agent_id="agent-06-integrity",
        finding_type="INTEGRITY_ASSESSMENT",
        session_id="s3",
        run_id="run-3",
        subject=Subject(driver_number=16),
        as_of_event_time=datetime.now(UTC),
        interpretation=Interpretation.DERIVED,
        result={"integrity_state": "HEALTHY", "finality_status": "FINAL"},
    )
    await fusion.on_finding("pulse.agent.integrity.findings.v1", "s3:16", sia_ok)
    strat = _make_strat_finding("s3", 16, sample_laps=2, deg_cal="INSUFFICIENT_SAMPLES")
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s3:16", strat)
    a = fusion._scoped_assessments[("s3", 16)]
    assert a.status == FindingStatus.PROVISIONAL
    assert "INSUFFICIENT_SAMPLE_SIZE" in a.uncertainty["conflicts"]


@pytest.mark.asyncio
async def test_fusion_conflicting_evidence_blocks_and_contradiction_rejects():
    """4. Conflicting evidence stays PROVISIONAL while hard contradiction transitions to REJECTED."""
    fusion = ConsequenceFusionEngine(bus=AsyncMock())
    strat_conf = _make_strat_finding("s4", 11, extra_result={"conflicting_evidence": True, "independently_corroborated": True})
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s4:11", strat_conf)
    assert fusion._scoped_assessments[("s4", 11)].status == FindingStatus.PROVISIONAL
    assert "CONFLICTING_DOMAIN_EVIDENCE" in fusion._scoped_assessments[("s4", 11)].uncertainty["conflicts"]

    strat_bad = _make_strat_finding("s4b", 11, extra_result={"contradicts": True})
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s4b:11", strat_bad)
    assert fusion._scoped_assessments[("s4b", 11)].status == FindingStatus.REJECTED


@pytest.mark.asyncio
async def test_fusion_independently_corroborated_evidence_confirms():
    """5. Missing SIA alert alone does NOT confirm; calibrated empirical strategy + calibrated clean-air telemetry confirms."""
    fusion = ConsequenceFusionEngine(bus=AsyncMock())
    # Empirical strategy alone with NO telemetry and NO SIA stays PROVISIONAL
    strat_only = _make_strat_finding("s5a", 4)
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s5a:4", strat_only)
    assert fusion._scoped_assessments[("s5a", 4)].status == FindingStatus.PROVISIONAL

    # Add independent clean-air calibrated pace telemetry -> OBSERVED pace, then CONFIRMED strategy
    pace = Finding(
        finding_id="f-pace-cal-5",
        agent_id="agent-03-vehicle-response",
        finding_type="PACE_DEVIATION",
        session_id="s5b",
        run_id="run-5b",
        subject=Subject(driver_number=4),
        trigger_event_id="evt-l10",
        as_of_event_time=datetime.now(UTC),
        interpretation=Interpretation.OBSERVED,
        assessment_status=FindingStatus.OBSERVED,
        result={
            "driver_number": 4,
            "lap_number": 10,
            "pace_delta_sec": -0.12,
            "baseline_status": "STINT_ROLLING_CALIBRATED",
            "baseline_sample_count": 6,
            "clean_air": True,
            "clean_air_status": "CLEAN_AIR_CONFIRMED",
        },
    )
    await fusion.on_finding("pulse.agent.vehicle_response.findings.v1", "s5b:4", pace)
    assert fusion._scoped_assessments[("s5b", 4)].status == FindingStatus.OBSERVED
    strat_corr = _make_strat_finding("s5b", 4)
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s5b:4", strat_corr)
    assert fusion._scoped_assessments[("s5b", 4)].status == FindingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_fusion_historical_revision_marks_superseded():
    """6. Historical revision supersedes prior PROVISIONAL assessment cleanly."""
    fusion = ConsequenceFusionEngine(bus=AsyncMock())
    exp = Finding(
        finding_id="f-exp-rev",
        agent_id="agent-01-event-control",
        finding_type="DRIVER_EVENT_EXPOSURE",
        session_id="s6",
        run_id="run-6",
        subject=Subject(driver_number=81),
        as_of_event_time=datetime.now(UTC),
        interpretation=Interpretation.DERIVED,
        result={"driver_number": 81},
    )
    await fusion.on_finding("pulse.agent.event_context.findings.v1", "s6:81", exp)
    v1 = fusion._scoped_assessments[("s6", 81)]
    assert v1.status == FindingStatus.PROVISIONAL

    sia_ok = Finding(
        finding_id="f-sia-ok-6",
        agent_id="agent-06-integrity",
        finding_type="INTEGRITY_ASSESSMENT",
        session_id="s6",
        run_id="run-6",
        subject=Subject(driver_number=81),
        as_of_event_time=datetime.now(UTC),
        interpretation=Interpretation.DERIVED,
        result={"integrity_state": "HEALTHY", "finality_status": "FINAL"},
    )
    await fusion.on_finding("pulse.agent.integrity.findings.v1", "s6:81", sia_ok)
    strat = _make_strat_finding("s6", 81)
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s6:81", strat)
    v2 = fusion._scoped_assessments[("s6", 81)]
    assert v1.status == FindingStatus.SUPERSEDED
    assert v2.status == FindingStatus.CONFIRMED
    assert v2.supersedes_assessment_id == v1.assessment_id


@pytest.mark.asyncio
async def test_fusion_sia_unknown_suspect_degraded_and_finalized():
    """7-10. SIA UNKNOWN/SUSPECT hold PROVISIONAL, SIA DEGRADED -> REJECTED, finalized HEALTHY -> CONFIRMED."""
    fusion = ConsequenceFusionEngine(bus=AsyncMock())
    now = datetime.now(UTC)

    # 7. SIA UNKNOWN
    await fusion.on_finding(
        "pulse.agent.integrity.findings.v1",
        "s7:1",
        Finding(finding_id="sia-unk", agent_id="agent-06-integrity", finding_type="INTEGRITY_ASSESSMENT", session_id="s7", run_id="r7", subject=Subject(driver_number=1), as_of_event_time=now, interpretation=Interpretation.DERIVED, result={"integrity_state": "UNKNOWN", "finality_status": "OPEN"}),
    )
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s7:1", _make_strat_finding("s7", 1))
    assert fusion._scoped_assessments[("s7", 1)].status == FindingStatus.PROVISIONAL
    assert any("SIA_INTEGRITY_UNKNOWN" in c for c in fusion._scoped_assessments[("s7", 1)].uncertainty["conflicts"])

    # 8. SIA SUSPECT
    await fusion.on_finding(
        "pulse.agent.integrity.findings.v1",
        "s8:1",
        Finding(finding_id="sia-sus", agent_id="agent-06-integrity", finding_type="INTEGRITY_ASSESSMENT", session_id="s8", run_id="r8", subject=Subject(driver_number=1), as_of_event_time=now, interpretation=Interpretation.DERIVED, result={"integrity_state": "SUSPECT", "finality_status": "FINAL"}),
    )
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s8:1", _make_strat_finding("s8", 1))
    assert fusion._scoped_assessments[("s8", 1)].status == FindingStatus.PROVISIONAL
    assert fusion._scoped_assessments[("s8", 1)].uncertainty["tactical_recommendation"] == "HOLD_VERIFY_INTEGRITY"

    # 9. SIA DEGRADED -> REJECTED
    await fusion.on_finding(
        "pulse.agent.integrity.findings.v1",
        "s9:1",
        Finding(finding_id="sia-deg", agent_id="agent-06-integrity", finding_type="INTEGRITY_ASSESSMENT", session_id="s9", run_id="r9", subject=Subject(driver_number=1), as_of_event_time=now, interpretation=Interpretation.DERIVED, result={"integrity_state": "DEGRADED", "finality_status": "FINAL"}),
    )
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s9:1", _make_strat_finding("s9", 1))
    assert fusion._scoped_assessments[("s9", 1)].status == FindingStatus.REJECTED

    # 10. Non-finalized HEALTHY stays PROVISIONAL; Finalized HEALTHY + calibrated -> CONFIRMED
    await fusion.on_finding(
        "pulse.agent.integrity.findings.v1",
        "s10:1",
        Finding(finding_id="sia-open", agent_id="agent-06-integrity", finding_type="INTEGRITY_ASSESSMENT", session_id="s10", run_id="r10", subject=Subject(driver_number=1), as_of_event_time=now, interpretation=Interpretation.DERIVED, result={"integrity_state": "HEALTHY", "finality_status": "OPEN"}),
    )
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s10:1", _make_strat_finding("s10", 1))
    assert fusion._scoped_assessments[("s10", 1)].status == FindingStatus.PROVISIONAL
    assert "SIA_EVIDENCE_NOT_FINALIZED" in fusion._scoped_assessments[("s10", 1)].uncertainty["conflicts"]

    await fusion.on_finding(
        "pulse.agent.integrity.findings.v1",
        "s10b:1",
        Finding(finding_id="sia-final", agent_id="agent-06-integrity", finding_type="INTEGRITY_ASSESSMENT", session_id="s10b", run_id="r10", subject=Subject(driver_number=1), as_of_event_time=now, interpretation=Interpretation.DERIVED, result={"integrity_state": "HEALTHY", "finality_status": "FINAL"}),
    )
    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "s10b:1", _make_strat_finding("s10b", 1))
    assert fusion._scoped_assessments[("s10b", 1)].status == FindingStatus.CONFIRMED


