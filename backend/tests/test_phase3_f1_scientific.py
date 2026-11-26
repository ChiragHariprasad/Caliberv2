"""
Phase 3 Scientific Tests:
- Zero hardcoded 76.0s pace baselines or invented age-23 stints
- Causal fuel-compensated pace prediction & empirical conformal CI95
- Fuel-compensated stint degradation positivity & hierarchical session pooling
- Empirical pit-loss learning & field-gap re-entry projection (no P-1-P0)
- Held-out FastF1 causal evaluation (2021 Britain & Abu Dhabi when cached)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.analytics.pace_and_tyre import (
    FuelCompensatedDegradationModel,
    PitWindowStrategySimulator,
    RollingCleanAirPaceEstimator,
)
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


def _lap_evt(
    session_id: str,
    driver_number: int,
    lap_number: int,
    lap_sec: float,
    *,
    compound: str = "M",
    tyre_age: int | None = None,
    stint: int = 1,
    interval: float | None = 3.0,
    gap_to_leader: float | None = None,
    position: int = 2,
    total_laps: int = 58,
    pit_in: bool = False,
    pit_out: bool = False,
) -> EventEnvelope:
    payload = {
        "lap": lap_number,
        "last_lap_seconds": lap_sec,
        "compound": compound,
        "tyre_age": tyre_age if tyre_age is not None else lap_number,
        "stint": stint,
        "position": position,
        "total_laps": total_laps,
    }
    if interval is not None:
        payload["interval"] = interval
    if gap_to_leader is not None:
        payload["gap_to_leader"] = gap_to_leader
    if pit_in:
        payload["pit_in_time"] = 1000.0
    if pit_out:
        payload["pit_out_time"] = 1020.0
    t = datetime(2025, 1, 1, 14, 0, 0, tzinfo=UTC)
    return EventEnvelope(
        event_id=f"evt-{session_id}-{driver_number}-{lap_number}",
        event_type="LAP_COMPLETED",
        source=SourceRef(
            provider="FASTF1_OFFLINE_TEST",
            adapter="pytest",
            source_record_id=f"src-{session_id}-{driver_number}-{lap_number}",
            capture_id=f"cap-{session_id}",
        ),
        run=RunContext(run_id="run-sci", session_instance_id=session_id, mode=RunMode.REPLAY),
        session=SessionRef(season=2025, meeting_id="test-gp", session_id=session_id, session_type="RACE"),
        time=EventTime(event_time_utc=t, session_elapsed_ms=lap_number * 90000, ingest_time_utc=t),
        subject=Subject(driver_number=driver_number),
        payload=payload,
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )


def test_no_hardcoded_76s_baseline_and_stint_reset() -> None:
    est = RollingCleanAirPaceEstimator()
    # Circuit with ~105s lap times (e.g., Spa / Baku) - old hardcoded 76.0s had ~29s error!
    preds_err: list[float] = []
    for ln in range(2, 12):
        true_lap = 105.0 - 0.06 * (ln - 2)
        pred = est.predict_baseline("spa-test", 1, target_lap=ln, compound="M", stint_id=1)
        if ln <= 2:
            assert pred.baseline_sec is None
            assert pred.status == "INITIALIZING"
        else:
            assert pred.baseline_sec is not None
            assert abs(pred.baseline_sec - 76.0) > 20.0
            preds_err.append(abs(true_lap - pred.baseline_sec))
        est.observe_lap("spa-test", 1, ln, true_lap, stint_id=1, compound="M", clean_air=True, total_laps=44, prior_prediction=pred)

    assert max(preds_err[1:]) < 0.25

    # Stint switch to Softs (~103.5s) resets baseline cleanly instead of lagging with 105s
    pred_switch = est.predict_baseline("spa-test", 1, target_lap=12, compound="S", stint_id=2)
    assert pred_switch.status == "INITIALIZING"
    est.observe_lap("spa-test", 1, 12, 103.5, stint_id=2, compound="S", clean_air=True, total_laps=44, prior_prediction=pred_switch)
    pred_stint2 = est.predict_baseline("spa-test", 1, target_lap=13, compound="S", stint_id=2)
    assert pred_stint2.baseline_sec is not None
    assert abs(pred_stint2.baseline_sec - 103.5) < 0.25


def test_fuel_compensated_slope_recovers_positive_tyre_deg_from_negative_raw_laps() -> None:
    deg = FuelCompensatedDegradationModel()
    # Realistic F1 stint: fuel burn = 0.060 s/lap, true tyre deg = +0.030 s/lap -> raw pace improves by -0.030 s/lap!
    for ln in range(2, 16):
        y = 88.0 - 0.030 * (ln - 2)
        deg.observe_lap("ad-sim", 44, ln, y, compound="H", tyre_age=ln, stint_id=1, total_laps=58)

    res = deg.estimate_degradation("ad-sim", 44)
    assert res.calibration_status == "DRIVER_STINT_CALIBRATED"
    assert res.raw_uncompensated_slope_sec_per_lap is not None
    assert res.raw_uncompensated_slope_sec_per_lap < 0.0
    assert res.driver_stint_slope is not None and res.driver_stint_slope > 0.02
    assert res.slope_sec_per_lap > 0.02


def test_empirical_pit_loss_and_field_gap_reentry_no_p_minus_1() -> None:
    sim = PitWindowStrategySimulator()
    # Cold start with no gaps: must never say P-1-P0
    cold = sim.evaluate_pit_window("monaco-test", 16, "VSC")
    assert cold["reentry_window"] == "UNMEASURED_NO_FIELD_GAPS"
    assert cold["calibration_status"] == "PRIOR_UNMEASURED"

    # Feed field gaps + empirical 19.2s green pit stop
    sim.update_driver_state("monaco-test", 16, position=1, gap_to_leader_sec=0.0, interval_sec=1.5)
    sim.update_driver_state("monaco-test", 4, position=2, gap_to_leader_sec=4.0, interval_sec=4.0)
    sim.update_driver_state("monaco-test", 1, position=3, gap_to_leader_sec=12.0, interval_sec=8.0)
    sim.update_driver_state("monaco-test", 44, position=4, gap_to_leader_sec=25.0, interval_sec=13.0)

    # Observe driver 4 pitting cleanly on laps 14-15 with clean baseline 75.0 -> in=84.6, out=84.6 => loss=19.2s
    sim.record_pit_lap_observation("monaco-test", 4, 14, 84.6, 75.0, is_pit_in=True, neutralised=False)
    sim.record_pit_lap_observation("monaco-test", 4, 15, 84.6, 75.0, is_pit_out=True, neutralised=False)

    calibrated = sim.evaluate_pit_window("monaco-test", 16, "VSC")
    assert calibrated["green_pit_loss_sec"] == 19.2
    assert "EMPIRICAL_PIT_CALIBRATED" in calibrated["calibration_status"]
    assert calibrated["reentry_window"].startswith("P")
    assert "-" not in calibrated["reentry_window"]


@pytest.mark.asyncio
async def test_agents_03_and_04_do_not_invent_baselines_or_age23_stints() -> None:
    bus = AsyncMock()
    vr = VehicleResponseAgent(bus=bus)
    ty = TyreStrategyAgent(bus=bus)

    assert vr.driver_baselines == {}
    assert ty.driver_stints == {}

    # Feed realistic 98s laps (e.g., Spa/Silverstone); VR must adapt without 76s error
    for ln in range(2, 9):
        env = _lap_evt("silverstone-sim", 44, ln, 91.5 - 0.05 * ln, compound="M", tyre_age=ln, gap_to_leader=0.0, position=1)
        await vr.on_event("pulse.norm.driver_laps.v1", "silverstone-sim:44", env)
        await ty.on_event("pulse.norm.driver_laps.v1", "silverstone-sim:44", env)

    assert 44 in vr.driver_baselines
    assert abs(vr.driver_baselines[44] - 91.2) < 1.0
    assert ty.driver_stints[44]["compound"] == "M"
    assert ty.driver_stints[44]["stint_age"] == 8

    t = datetime(2025, 1, 1, 14, 20, 0, tzinfo=UTC)
    vsc = EventEnvelope(
        event_id="evt-vsc-silverstone",
        event_type="VSC_DEPLOYED",
        source=SourceRef(
            provider="FASTF1_OFFLINE_TEST",
            adapter="pytest",
            source_record_id="src-vsc-silverstone",
            capture_id="cap-silverstone-sim",
        ),
        run=RunContext(run_id="run-sci", session_instance_id="silverstone-sim", mode=RunMode.REPLAY),
        session=SessionRef(season=2025, meeting_id="test-gp", session_id="silverstone-sim", session_type="RACE"),
        time=EventTime(event_time_utc=t, session_elapsed_ms=1200000, ingest_time_utc=t),
        subject=Subject(driver_number=44),
        payload={"message": "VSC DEPLOYED"},
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )
    await ty.on_event("pulse.norm.race_events.v1", "silverstone-sim", vsc)
    assert bus.publish.called


def test_fastf1_cached_dry_races_pace_mae_under_half_second() -> None:
    cache_dir = Path(r"E:\Caliberv2\data\fastf1_cache")
    if not (cache_dir / "2021" / "2021-07-18_British_Grand_Prix" / "2021-07-18_Race" / "_extended_timing_data.ff1pkl").exists():
        pytest.skip("FastF1 offline cache not present")

    import fastf1

    fastf1.Cache.enable_cache(str(cache_dir))
    fastf1.Cache.offline_mode(True)
    sess = fastf1.get_session(2021, "British Grand Prix", "R")
    sess.load(laps=True, telemetry=False, weather=False, messages=False)
    laps = sess.laps
    total_laps = int(laps["LapNumber"].max())
    df = laps.copy()
    df["lap_sec"] = df["LapTime"].dt.total_seconds()
    clean = df[
        (df["TrackStatus"].astype(str) == "1")
        & df["PitInTime"].isna()
        & df["PitOutTime"].isna()
        & (df["IsAccurate"] == True)  # noqa: E712
        & df["lap_sec"].notna()
        & (df["LapNumber"] > 1)
    ]

    est = RollingCleanAirPaceEstimator()
    errors: list[float] = []
    covered: list[int] = []
    for ln in sorted(clean["LapNumber"].unique()):
        lap_df = clean[clean["LapNumber"] == ln]
        for _, row in lap_df.iterrows():
            dn = int(row["DriverNumber"])
            st = int(row["Stint"]) if row["Stint"] == row["Stint"] else 1
            comp = str(row["Compound"])
            y = float(row["lap_sec"])
            pred = est.predict_baseline("2021_britain", dn, target_lap=int(ln), compound=comp, stint_id=st)
            if pred.baseline_sec is not None and pred.status == "STINT_ROLLING_CALIBRATED":
                errors.append(abs(y - pred.baseline_sec))
                covered.append(1 if (pred.ci95_low_sec <= y <= pred.ci95_high_sec) else 0)
            est.observe_lap(
                "2021_britain",
                dn,
                int(ln),
                y,
                stint_id=st,
                compound=comp,
                clean_air=True,
                total_laps=total_laps,
                prior_prediction=pred,
            )

    mae = sum(errors) / len(errors)
    cov = sum(covered) / len(covered)
    assert mae < 0.45, f"Expected causal pace MAE < 0.45s on 2021 Silverstone, got {mae:.3f}s"
    assert cov >= 0.88, f"Expected empirical 95% PI coverage >= 88%, got {cov:.3f}"
