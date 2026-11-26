from datetime import UTC, datetime
import pytest

from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.analytics.pace_and_tyre import (
    FuelCompensatedDegradationModel,
    PitWindowStrategySimulator,
    RollingCleanAirPaceEstimator,
    resolve_clean_air_status,
)
from pulse.contracts import (
    Assessment,
    CleanAirStatus,
    Completeness,
    EventEnvelope,
    EventTime,
    FindingStatus,
    Forecast,
    Impact,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
)
from pulse.state.store import StateStore


def _lap_env(
    dn: int,
    lap: int,
    sec: float,
    *,
    interval: float | None = None,
    position: int | None = None,
    compound: str = "M",
) -> EventEnvelope:
    now = datetime.now(UTC)
    payload: dict = {"lap": lap, "last_lap_seconds": sec, "compound": compound, "stint": 1}
    if interval is not None:
        payload["interval"] = interval
    if position is not None:
        payload["position"] = position
    return EventEnvelope(
        event_id=f"evt-ca-{dn}-{lap}",
        event_type="LAP_COMPLETED",
        source=SourceRef(provider="SYNTH_TEST", adapter="unit", source_record_id=f"{dn}-{lap}", capture_id="cap-test"),
        run=RunContext(run_id="run-ca", session_instance_id="sess-ca", mode=RunMode.REPLAY),
        session=SessionRef(season=2024, meeting_id="m", session_id="sess-ca"),
        time=EventTime(event_time_utc=now, session_elapsed_ms=lap * 90000, ingest_time_utc=now),
        subject=Subject(driver_number=dn, lap_number=lap),
        payload=payload,
        quality=Quality(interpretation=Interpretation.OBSERVED, unit_validation=UnitValidation.PASSED, completeness=Completeness.COMPLETE),
    )


def test_clean_air_tristate_never_assumes_missing_is_clean():
    assert resolve_clean_air_status(None, None) == (CleanAirStatus.CLEAN_AIR_UNKNOWN, None)
    assert resolve_clean_air_status(position=1) == (CleanAirStatus.CLEAN_AIR_CONFIRMED, True)
    assert resolve_clean_air_status(position=4, interval_sec=None) == (CleanAirStatus.CLEAN_AIR_UNKNOWN, None)
    assert resolve_clean_air_status(position=4, interval_sec=1.2) == (CleanAirStatus.TRAFFIC_AFFECTED, False)
    assert resolve_clean_air_status(position=4, interval_sec=2.1) == (CleanAirStatus.CLEAN_AIR_CONFIRMED, True)
    assert resolve_clean_air_status(position=1, is_pit=True) == (CleanAirStatus.TRAFFIC_AFFECTED, False)

    est = RollingCleanAirPaceEstimator()
    for ln in range(2, 8):
        est.observe_lap("s-unk", 4, ln, 90.0, compound="M", stint_id=1)  # missing interval & not P1 -> UNKNOWN
    pred = est.predict_baseline("s-unk", 4, target_lap=8, compound="M", stint_id=1)
    assert pred.status == "INITIALIZING"
    summary = est.get_clean_air_summary("s-unk", 4)
    assert summary["CLEAN_AIR_UNKNOWN"] == 6
    assert summary["CLEAN_AIR_CONFIRMED"] == 0


@pytest.mark.asyncio
async def test_vehicle_response_and_tyre_agent_preserve_clean_air_unknown():
    vr = VehicleResponseAgent()
    ty = TyreStrategyAgent()
    for ln in range(2, 6):
        env = _lap_env(4, ln, 88.5, interval=None, position=4)
        await vr.on_event("t", "k", env)
        await ty.on_event("t", "k", env)

    assert vr.driver_baselines == {}
    assert vr.pace_estimator.get_clean_air_summary("sess-ca", 4)["CLEAN_AIR_UNKNOWN"] == 4
    assert ty.pace_tracker.get_clean_air_summary("sess-ca", 4)["CLEAN_AIR_UNKNOWN"] == 4

    # Leader (pos=1) without interval resolves CLEAN_AIR_CONFIRMED cleanly
    for ln in range(2, 6):
        env_p1 = _lap_env(1, ln, 87.0, interval=None, position=1)
        await vr.on_event("t", "k", env_p1)
    assert 1 in vr.driver_baselines
    assert vr.pace_estimator.get_clean_air_summary("sess-ca", 1)["CLEAN_AIR_CONFIRMED"] == 4


def test_degradation_sample_sufficiency_and_pit_window_honest_limitations():
    deg = FuelCompensatedDegradationModel()
    for ln in range(2, 5):
        deg.observe_lap("s-deg", 16, ln, 78.0 + 0.05 * ln, compound="M", tyre_age=ln, stint_id=1, total_laps=78)
    est_insufficient = deg.estimate_degradation("s-deg", 16)
    assert est_insufficient.calibration_status == "INSUFFICIENT_SAMPLES"
    assert est_insufficient.n_driver_laps == 3

    sim = PitWindowStrategySimulator()
    out = sim.evaluate_pit_window(
        "s-deg",
        16,
        "VSC",
        current_compound="M",
        stint_age=12,
        deg_estimate=est_insufficient,
        remaining_laps=2,
    )
    assert out["strategy_scope"] == "ADVISORY_LOCAL_PIT_WINDOW_ONLY"
    assert out["is_globally_optimal"] is False
    assert out["pit_window_viable"] is False
    assert any("END_OF_RACE_HORIZON_TOO_SHORT" in m for m in out["model_limitations"])
    assert any("insufficient clean stint samples" in m.lower() or "prior" in m.lower() for m in out["model_limitations"])


def test_state_store_assessment_supersession_consistency():
    store = StateStore()
    now = datetime.now(UTC)
    v1 = Assessment(
        assessment_id="a-v1",
        assessment_version=1,
        session_id="s-st",
        run_id="r-st",
        as_of_event_time=now,
        trigger={"type": "EXPOSURE"},
        subject=Subject(driver_number=44),
        impact=Impact(summary="v1", forecast=Forecast(horizon_laps=2, status=FindingStatus.PROVISIONAL)),
        status=FindingStatus.PROVISIONAL,
    )
    v2 = Assessment(
        assessment_id="a-v2",
        assessment_version=2,
        session_id="s-st",
        run_id="r-st",
        as_of_event_time=now,
        trigger={"type": "CONVERGENCE"},
        subject=Subject(driver_number=44),
        impact=Impact(summary="v2", forecast=Forecast(horizon_laps=2, status=FindingStatus.CONFIRMED)),
        status=FindingStatus.CONFIRMED,
        supersedes_assessment_id="a-v1",
    )
    store.record_assessment(v1)
    assert store.assessment_history[0].status == FindingStatus.PROVISIONAL
    store.record_assessment(v2)
    assert store.assessment_history[0].status == FindingStatus.SUPERSEDED
    assert store.assessment_history[1].status == FindingStatus.CONFIRMED
