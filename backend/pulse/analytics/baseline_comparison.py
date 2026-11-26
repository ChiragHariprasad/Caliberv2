"""
Scientific Validation & Baseline Comparison Framework (Priority B).

Evaluates 6 pace prediction models under identical strictly causal walk-forward,
calibration/holdout, and leave-one-race-out (LORO) protocols on cached FastF1 races
with causal inter-car interval reconstruction and zero future-data leakage.
"""
from __future__ import annotations

import asyncio
import math
import statistics
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.analytics.pace_and_tyre import (
    FuelCompensatedDegradationModel,
    RollingCleanAirPaceEstimator,
    estimate_fuel_burn_rate,
    normalize_compound,
    resolve_clean_air_status,
)
from pulse.contracts import (
    CleanAirStatus,
    Finding,
    FindingStatus,
    Interpretation,
    Subject,
)

CALIBRATION_RACES: list[tuple[int, str]] = [
    (2021, "British Grand Prix"),
    (2021, "Saudi Arabian Grand Prix"),
    (2022, "Monaco Grand Prix"),
]

HOLDOUT_RACES: list[tuple[int, str]] = [
    (2021, "Abu Dhabi Grand Prix"),
    (2022, "Japanese Grand Prix"),
]

EDGE_CASE_RACES: list[tuple[int, str]] = [
    (2021, "Belgian Grand Prix"),
]

ALL_EVAL_RACES: list[tuple[int, str]] = CALIBRATION_RACES + HOLDOUT_RACES

# Exact Student-t 97.5th percentile two-sided factors for 95% PI on small windows
_T_975_BY_DF: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
}


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = max(0.0, min(1.0, q)) * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


@dataclass
class CausalLapRecord:
    session_id: str
    driver_number: int
    lap_number: int
    lap_sec: float
    stint_id: int
    compound: str
    tyre_age: int
    position: int | None
    interval_sec: float | None
    clean_air_status: CleanAirStatus
    is_pit: bool
    neutralised: bool
    total_laps: int


@dataclass
class LapPredictionPoint:
    pred_sec: float | None
    ci95_low_sec: float | None
    ci95_high_sec: float | None
    confidence: float
    actual_sec: float
    clean_air_status: CleanAirStatus


def load_fastf1_causal_laps(cache_dir: str | Path, year: int, gp_name: str) -> dict[str, Any]:
    """Load cached FastF1 race offline and reconstruct strictly causal lap records + intervals."""
    import fastf1

    fastf1.Cache.enable_cache(str(cache_dir))
    session = fastf1.get_session(year, gp_name, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=False)
    laps_df = session.laps.copy()
    if laps_df.empty:
        return {"session_id": f"{year}_{gp_name}", "total_laps": 0, "records": []}

    total_laps = int(laps_df["LapNumber"].max()) if laps_df["LapNumber"].notna().any() else 0
    # Precompute causal lap start times per lap so interval_to_ahead at lap start uses only <= lap_start_time
    lap_starts_by_lap: dict[int, list[tuple[float, int]]] = {}
    for row in laps_df.itertuples():
        ln = getattr(row, "LapNumber", None)
        ls = getattr(row, "LapStartTime", None)
        dn = getattr(row, "DriverNumber", None)
        if ln is not None and ls is not None and str(ls) != "NaT" and dn is not None:
            try:
                sec = float(ls.total_seconds())
                if math.isfinite(sec):
                    lap_starts_by_lap.setdefault(int(ln), []).append((sec, int(dn)))
            except Exception:
                continue
    for ln in lap_starts_by_lap:
        lap_starts_by_lap[ln].sort(key=lambda item: item[0])

    # Sort strictly in causal crossing order using Time (completion timestamp), breaking ties by LapNumber
    laps_df = laps_df.sort_values(by=["LapNumber", "Time"], na_position="last")
    records: list[CausalLapRecord] = []
    sess_id = f"{year}_{gp_name.lower().replace(' ', '_')}"

    for row in laps_df.itertuples():
        lt = getattr(row, "LapTime", None)
        if lt is None or str(lt) == "NaT":
            continue
        try:
            lap_sec = float(lt.total_seconds())
        except Exception:
            continue
        if not math.isfinite(lap_sec) or lap_sec <= 35.0 or lap_sec >= 300.0:
            continue

        dn = int(row.DriverNumber)
        lap_num = int(row.LapNumber)
        stint_raw = getattr(row, "Stint", None)
        stint_id = int(stint_raw) if stint_raw is not None and not math.isnan(float(stint_raw)) else 1
        comp = normalize_compound(getattr(row, "Compound", None))
        age_raw = getattr(row, "TyreLife", None)
        tyre_age = int(age_raw) if age_raw is not None and not math.isnan(float(age_raw)) else lap_num
        pos_raw = getattr(row, "Position", None)
        pos = int(pos_raw) if pos_raw is not None and not math.isnan(float(pos_raw)) else None

        is_pit_in = getattr(row, "PitInTime", None)
        is_pit_out = getattr(row, "PitOutTime", None)
        is_pit = (is_pit_in is not None and str(is_pit_in) != "NaT") or (
            is_pit_out is not None and str(is_pit_out) != "NaT"
        )
        ts = str(getattr(row, "TrackStatus", "1") or "1")
        neut = any(code in ts for code in ("4", "5", "6", "7"))

        # Causal interval reconstruction from lap-start timestamps on same lap (never peeking future laps)
        interval_sec: float | None = None
        ls_td = getattr(row, "LapStartTime", None)
        if pos != 1 and ls_td is not None and str(ls_td) != "NaT" and lap_num in lap_starts_by_lap:
            try:
                my_start = float(ls_td.total_seconds())
                candidates = lap_starts_by_lap[lap_num]
                prev_starts = [t for t, other_dn in candidates if t < my_start and other_dn != dn]
                if prev_starts:
                    interval_sec = round(max(0.0, my_start - prev_starts[-1]), 3)
            except Exception:
                interval_sec = None

        ca_status, _ = resolve_clean_air_status(position=pos, interval_sec=interval_sec, is_pit=is_pit)
        records.append(
            CausalLapRecord(
                session_id=sess_id,
                driver_number=dn,
                lap_number=lap_num,
                lap_sec=lap_sec,
                stint_id=stint_id,
                compound=comp,
                tyre_age=tyre_age,
                position=pos,
                interval_sec=interval_sec,
                clean_air_status=ca_status,
                is_pit=is_pit,
                neutralised=neut,
                total_laps=total_laps,
            )
        )

    return {"session_id": sess_id, "year": year, "gp_name": gp_name, "total_laps": total_laps, "records": records}


class _BaselineState:
    def __init__(self) -> None:
        self.all_laps: dict[tuple[int, int], deque[tuple[int, float]]] = {}
        self.clean_laps: dict[tuple[int, int], deque[tuple[int, float]]] = {}
        self.errors: dict[int, deque[float]] = {}
        self.last_stint: dict[int, int] = {}

    def check_stint_reset(self, dn: int, stint_id: int) -> None:
        prev = self.last_stint.get(dn)
        if prev is not None and prev != stint_id:
            self.all_laps.pop((dn, prev), None)
            self.clean_laps.pop((dn, prev), None)
        self.last_stint[dn] = stint_id


def _eval_regression_fit(
    train_races: list[dict[str, Any]],
) -> tuple[float, float, float]:
    """
    Fits strictly on training races using normalized pace ratio residual vs tyre_age & race_progress:
      ratio = lap_sec / stint_initial_pace -> residual_sec = beta_age * (age - 1) + beta_prog * progress
    """
    xs_age: list[float] = []
    xs_prog: list[float] = []
    ys: list[float] = []
    res_abs: list[float] = []

    for race in train_races:
        stint_init: dict[tuple[int, int], list[float]] = {}
        for r in race["records"]:
            if r.neutralised or r.is_pit or r.lap_number <= 1:
                continue
            key = (r.driver_number, r.stint_id)
            buf = stint_init.setdefault(key, [])
            if len(buf) < 2:
                if r.clean_air_status == CleanAirStatus.CLEAN_AIR_CONFIRMED:
                    buf.append(r.lap_sec)
                continue
            if r.clean_air_status == CleanAirStatus.CLEAN_AIR_CONFIRMED:
                base = statistics.median(buf)
                diff = r.lap_sec - base
                if abs(diff) <= 5.0:
                    xs_age.append(float(r.tyre_age - 1))
                    xs_prog.append(float(r.lap_number) / max(float(r.total_laps), 1.0))
                    ys.append(diff)

    if len(ys) < 10:
        return 0.02, -1.5, 1.2

    # Simple 2-feature OLS via normal equations with ridge stabilizer
    n = float(len(ys))
    s11 = sum(a * a for a in xs_age) + 1e-3
    s12 = sum(a * p for a, p in zip(xs_age, xs_prog))
    s22 = sum(p * p for p in xs_prog) + 1e-3
    t1 = sum(a * y for a, y in zip(xs_age, ys))
    t2 = sum(p * y for p, y in zip(xs_prog, ys))
    det = s11 * s22 - s12 * s12
    beta_age = max(-0.1, min(0.25, (t1 * s22 - t2 * s12) / det))
    beta_prog = max(-5.0, min(1.0, (s11 * t2 - s12 * t1) / det))

    for a, p, y in zip(xs_age, xs_prog, ys):
        res_abs.append(abs(y - (beta_age * a + beta_prog * p)))
    half_w95 = max(_quantile(sorted(res_abs), 0.95), 0.5)
    return round(beta_age, 5), round(beta_prog, 5), round(half_w95, 3)


def evaluate_all_baselines_on_race(
    race: dict[str, Any],
    *,
    regression_params: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """
    Evaluate all 6 baselines on identical green-flag non-pit flying laps (lap >= 2).
    Guarantees identical test windows so MAE/RMSE/PI coverage are strictly apples-to-apples.
    """
    records: list[CausalLapRecord] = race["records"]
    beta_age, beta_prog, reg_half_w = regression_params or (0.02, -1.5, 1.5)

    # Model states
    prev_state = _BaselineState()
    med5_state = _BaselineState()
    clean5_state = _BaselineState()
    reg_stint_hist: dict[tuple[int, int], list[tuple[int, int, float]]] = {}
    reg_abs_err: dict[int, deque[float]] = {}

    existing_est = RollingCleanAirPaceEstimator(fast_restart_recovery=False)
    revised_est = RollingCleanAirPaceEstimator(fast_restart_recovery=True)
    revised_err_pool: deque[float] = deque(maxlen=60)
    revised_stint_errs: dict[tuple[int, int], deque[float]] = {}

    outputs: dict[str, list[LapPredictionPoint]] = {
        "previous_lap": [],
        "rolling_5_median": [],
        "rolling_clean_air_median": [],
        "circuit_normalized_regression": [],
        "existing_fuel_compensated": [],
        "revised_pulse": [],
    }
    failure_cases: list[dict[str, Any]] = []

    for rec in records:
        dn = rec.driver_number
        st = rec.stint_id
        ln = rec.lap_number
        is_target = (not rec.neutralised) and (not rec.is_pit) and (ln >= 2) and (
            rec.clean_air_status == CleanAirStatus.CLEAN_AIR_CONFIRMED
        )

        # 1. Previous-lap predictor
        p_hist = prev_state.all_laps.get((dn, st))
        if is_target and p_hist:
            p_pred = p_hist[-1][1]
            errs = sorted(prev_state.errors.get(dn, []))
            hw = _quantile(errs, 0.95) if len(errs) >= 5 else (2.5 * max(statistics.median(errs), 0.35) if errs else 2.0)
            outputs["previous_lap"].append(LapPredictionPoint(p_pred, p_pred - hw, p_pred + hw, 0.95, rec.lap_sec, rec.clean_air_status))
        elif is_target:
            outputs["previous_lap"].append(LapPredictionPoint(None, None, None, 0.0, rec.lap_sec, rec.clean_air_status))

        # 2. Rolling-5-lap median (unfiltered)
        m5_hist = med5_state.all_laps.get((dn, st))
        if is_target and m5_hist and len(m5_hist) >= 2:
            vals = [v for _, v in m5_hist][-5:]
            m5_pred = statistics.median(vals)
            mad = statistics.median([abs(v - m5_pred) for v in vals]) if len(vals) >= 3 else abs(vals[-1] - vals[-2]) * 0.5
            sig = max(1.4826 * mad, 0.25)
            hw = 2.6 * sig * math.sqrt(1.0 + 1.0 / len(vals))
            outputs["rolling_5_median"].append(LapPredictionPoint(m5_pred, m5_pred - hw, m5_pred + hw, 0.95, rec.lap_sec, rec.clean_air_status))
        elif is_target:
            outputs["rolling_5_median"].append(LapPredictionPoint(None, None, None, 0.0, rec.lap_sec, rec.clean_air_status))

        # 3. Rolling clean-air median (strict CLEAN_AIR_CONFIRMED)
        c5_hist = clean5_state.clean_laps.get((dn, st))
        if is_target and c5_hist and len(c5_hist) >= 2:
            vals = [v for _, v in c5_hist][-5:]
            c5_pred = statistics.median(vals)
            mad = statistics.median([abs(v - c5_pred) for v in vals]) if len(vals) >= 3 else abs(vals[-1] - vals[-2]) * 0.5
            sig = max(1.4826 * mad, 0.25)
            hw = 2.6 * sig * math.sqrt(1.0 + 1.0 / len(vals))
            outputs["rolling_clean_air_median"].append(LapPredictionPoint(c5_pred, c5_pred - hw, c5_pred + hw, 0.95, rec.lap_sec, rec.clean_air_status))
        elif is_target:
            outputs["rolling_clean_air_median"].append(LapPredictionPoint(None, None, None, 0.0, rec.lap_sec, rec.clean_air_status))

        # 4. Circuit-normalized causal regression
        r_hist = reg_stint_hist.get((dn, st))
        if is_target and r_hist and len(r_hist) >= 2:
            prog_cur = float(ln) / max(float(rec.total_laps), 1.0)
            adj_bases = [
                obs_sec - beta_age * float(obs_age - 1) - beta_prog * (float(obs_lap) / max(float(rec.total_laps), 1.0))
                for obs_lap, obs_age, obs_sec in r_hist[:5]
            ]
            intercept = statistics.median(adj_bases)
            reg_pred = intercept + beta_age * float(rec.tyre_age - 1) + beta_prog * prog_cur
            r_errs = sorted(reg_abs_err.get(dn, []))
            hw = max(_quantile(r_errs, 0.95), 0.5) if len(r_errs) >= 10 else reg_half_w
            outputs["circuit_normalized_regression"].append(LapPredictionPoint(reg_pred, reg_pred - hw, reg_pred + hw, 0.95, rec.lap_sec, rec.clean_air_status))
        elif is_target:
            outputs["circuit_normalized_regression"].append(LapPredictionPoint(None, None, None, 0.0, rec.lap_sec, rec.clean_air_status))

        # 5. Existing fuel-compensated baseline (uses STINT_ROLLING_CALIBRATED + legacy clean_air != False & fixed 2.6 sigma)
        ex_pred = existing_est.predict_baseline(rec.session_id, dn, target_lap=ln, compound=rec.compound, stint_id=st)
        if is_target and ex_pred.baseline_sec is not None and ex_pred.status == "STINT_ROLLING_CALIBRATED":
            outputs["existing_fuel_compensated"].append(
                LapPredictionPoint(ex_pred.baseline_sec, ex_pred.ci95_low_sec, ex_pred.ci95_high_sec, 0.95, rec.lap_sec, rec.clean_air_status)
            )
        elif is_target:
            outputs["existing_fuel_compensated"].append(LapPredictionPoint(None, None, None, 0.0, rec.lap_sec, rec.clean_air_status))

        # 6. Revised PULSE model (strict CLEAN_AIR_CONFIRMED only + bounded Student-t / trimmed split-conformal scaling)
        rev_pred = revised_est.predict_baseline(rec.session_id, dn, target_lap=ln, compound=rec.compound, stint_id=st)
        if is_target and rev_pred.baseline_sec is not None and rev_pred.status == "STINT_ROLLING_CALIBRATED":
            n_win = max(2, min(rev_pred.sample_count, 12))
            t_factor = min(_T_975_BY_DF.get(n_win - 1, 2.145), 3.182)
            base_sig = max((rev_pred.uncertainty_sec or 0.45) * 0.75, 0.25)
            drv_errs = list(revised_stint_errs.get((dn, st), []))
            if len(drv_errs) >= 10:
                hw = min(max(_quantile(sorted(drv_errs), 0.95), t_factor * base_sig), 8.0)
            elif len(revised_err_pool) >= 20:
                q_pool = _quantile(sorted(revised_err_pool), 0.95)
                hw = min(max(t_factor * base_sig, 0.65 * q_pool + 0.35 * t_factor * base_sig), 8.0)
            else:
                hw = min(max(t_factor * base_sig * math.sqrt(1.0 + 1.0 / n_win), 0.70), 8.0)
            lo = rev_pred.baseline_sec - hw
            hi = rev_pred.baseline_sec + hw
            outputs["revised_pulse"].append(LapPredictionPoint(rev_pred.baseline_sec, lo, hi, 0.95, rec.lap_sec, rec.clean_air_status))
            if not (lo <= rec.lap_sec <= hi) and len(failure_cases) < 25:
                failure_cases.append({
                    "race": rec.session_id,
                    "driver": dn,
                    "lap": ln,
                    "compound": rec.compound,
                    "pred_sec": round(rev_pred.baseline_sec, 3),
                    "actual_sec": round(rec.lap_sec, 3),
                    "error_sec": round(rec.lap_sec - rev_pred.baseline_sec, 3),
                    "pi_half_width": round(hw, 3),
                })
        elif is_target:
            outputs["revised_pulse"].append(LapPredictionPoint(None, None, None, 0.0, rec.lap_sec, rec.clean_air_status))

        # --- Causal update AFTER predicting ---
        if (not rec.neutralised) and (not rec.is_pit) and ln >= 2:
            if p_hist:
                prev_state.errors.setdefault(dn, deque(maxlen=25)).append(abs(rec.lap_sec - p_hist[-1][1]))
            prev_state.check_stint_reset(dn, st)
            prev_state.all_laps.setdefault((dn, st), deque(maxlen=12)).append((ln, rec.lap_sec))

            if m5_hist and len(m5_hist) >= 2:
                med5_state.errors.setdefault(dn, deque(maxlen=25)).append(abs(rec.lap_sec - statistics.median([v for _, v in m5_hist])))
            med5_state.check_stint_reset(dn, st)
            med5_state.all_laps.setdefault((dn, st), deque(maxlen=12)).append((ln, rec.lap_sec))

            if rec.clean_air_status == CleanAirStatus.CLEAN_AIR_CONFIRMED:
                clean5_state.check_stint_reset(dn, st)
                clean5_state.clean_laps.setdefault((dn, st), deque(maxlen=12)).append((ln, rec.lap_sec))

                if r_hist and len(r_hist) >= 2:
                    prog_cur = float(ln) / max(float(rec.total_laps), 1.0)
                    adj = [
                        obs_sec - beta_age * float(obs_age - 1) - beta_prog * (float(obs_lap) / max(float(rec.total_laps), 1.0))
                        for obs_lap, obs_age, obs_sec in r_hist[:5]
                    ]
                    r_pred = statistics.median(adj) + beta_age * float(rec.tyre_age - 1) + beta_prog * prog_cur
                    reg_abs_err.setdefault(dn, deque(maxlen=25)).append(abs(rec.lap_sec - r_pred))
                reg_stint_hist.setdefault((dn, st), []).append((ln, rec.tyre_age, rec.lap_sec))

            # Pre-Phase-I estimator emulated permissive clean_air != False (unknown treated as clean!)
            permissive_clean = (rec.clean_air_status != CleanAirStatus.TRAFFIC_AFFECTED)
            existing_est.observe_lap(
                rec.session_id,
                dn,
                ln,
                rec.lap_sec,
                stint_id=st,
                compound=rec.compound,
                clean_air=permissive_clean,
                neutralised=rec.neutralised,
                total_laps=rec.total_laps,
                prior_prediction=ex_pred,
            )

            # Revised estimator strictly rejects CLEAN_AIR_UNKNOWN and trims regime-shift spikes > 8s from PI pool
            if rev_pred.baseline_sec is not None and rev_pred.status == "STINT_ROLLING_CALIBRATED" and rec.clean_air_status == CleanAirStatus.CLEAN_AIR_CONFIRMED:
                ae = abs(rec.lap_sec - rev_pred.baseline_sec)
                if ae <= 8.0:
                    revised_err_pool.append(ae)
                    revised_stint_errs.setdefault((dn, st), deque(maxlen=25)).append(ae)
            revised_est.observe_lap(
                rec.session_id,
                dn,
                ln,
                rec.lap_sec,
                stint_id=st,
                compound=rec.compound,
                clean_air_status=rec.clean_air_status,
                position=rec.position,
                interval_sec=rec.interval_sec,
                neutralised=rec.neutralised,
                total_laps=rec.total_laps,
                prior_prediction=rev_pred,
            )

    summary = {}
    for model_name, pts in outputs.items():
        summary[model_name] = _summarize_predictions(pts)
    return {
        "session_id": race["session_id"],
        "total_laps": race["total_laps"],
        "models": summary,
        "revised_failure_cases_sample": failure_cases[:10],
    }


def _summarize_predictions(pts: list[LapPredictionPoint]) -> dict[str, Any]:
    eval_pts = [p for p in pts if p.pred_sec is not None]
    if not eval_pts:
        return {
            "n_target_laps": len(pts),
            "n_predicted": 0,
            "mae_sec": None,
            "rmse_sec": None,
            "pi95_coverage": None,
            "mean_pi95_width_sec": None,
            "calibration_gap_from_95pct": None,
        }
    errs = [p.actual_sec - p.pred_sec for p in eval_pts if p.pred_sec is not None]
    abs_errs = [abs(e) for e in errs]
    cov_hits = [
        1
        for p in eval_pts
        if p.ci95_low_sec is not None and p.ci95_high_sec is not None and p.ci95_low_sec <= p.actual_sec <= p.ci95_high_sec
    ]
    widths = [
        (p.ci95_high_sec - p.ci95_low_sec)
        for p in eval_pts
        if p.ci95_low_sec is not None and p.ci95_high_sec is not None
    ]
    cov = len(cov_hits) / len(eval_pts)
    return {
        "n_target_laps": len(pts),
        "n_predicted": len(eval_pts),
        "coverage_fraction": round(len(eval_pts) / max(len(pts), 1), 4),
        "mae_sec": round(sum(abs_errs) / len(abs_errs), 4),
        "rmse_sec": round(math.sqrt(sum(e * e for e in errs) / len(errs)), 4),
        "median_ae_sec": round(statistics.median(abs_errs), 4),
        "pi95_coverage": round(cov, 4),
        "mean_pi95_width_sec": round(sum(widths) / len(widths), 4) if widths else None,
        "calibration_gap_from_95pct": round(cov - 0.95, 4),
    }


def run_ablation_study(races: list[dict[str, Any]]) -> dict[str, Any]:
    """
    7-component ablation study measuring individual impact of:
    1. clean_air_filtering
    2. fuel_compensation
    3. track_evolution
    4. compound_effects
    5. shrinkage_estimation
    6. sia_gating
    7. consequence_fusion
    """
    configs = {
        "full_revised": {"clean_air_filter": True, "fuel_comp": True, "track_evo": True, "compound_reset": True},
        "no_clean_air_filter": {"clean_air_filter": False, "fuel_comp": True, "track_evo": True, "compound_reset": True},
        "no_fuel_comp": {"clean_air_filter": True, "fuel_comp": False, "track_evo": True, "compound_reset": True},
        "no_track_evo": {"clean_air_filter": True, "fuel_comp": True, "track_evo": False, "compound_reset": True},
        "no_compound_effects": {"clean_air_filter": True, "fuel_comp": True, "track_evo": True, "compound_reset": False},
    }

    pace_ablation: dict[str, dict[str, Any]] = {}
    for cname, cfg in configs.items():
        all_pts: list[LapPredictionPoint] = []
        for race in races:
            pts = _run_ablation_variant_on_race(race, **cfg)
            all_pts.extend(pts)
        pace_ablation[cname] = _summarize_predictions(all_pts)

    # 5. Shrinkage estimation ablation on stint half-split holdout lap prediction
    shrinkage_res = _ablate_shrinkage_on_races(races)

    # 6 & 7. SIA gating + Agent 05 consequence fusion ablation on confirmation precision/recall/FPR
    gating_res = asyncio.run(_ablate_sia_and_fusion_gating())

    return {
        "pace_components": pace_ablation,
        "shrinkage_estimation": shrinkage_res,
        "sia_gating_and_consequence_fusion": gating_res,
    }


def _run_ablation_variant_on_race(
    race: dict[str, Any],
    *,
    clean_air_filter: bool,
    fuel_comp: bool,
    track_evo: bool,
    compound_reset: bool,
) -> list[LapPredictionPoint]:
    """Run genuine RollingCleanAirPaceEstimator with individual Priority-B ablation switches."""
    records: list[CausalLapRecord] = race["records"]
    est = RollingCleanAirPaceEstimator(
        enable_fuel_comp=fuel_comp,
        enable_track_evo=track_evo,
        enable_compound_effects=compound_reset,
        fast_restart_recovery=True,
    )
    pts: list[LapPredictionPoint] = []

    for rec in records:
        st_arg = rec.stint_id if compound_reset else 1
        comp_arg = rec.compound if compound_reset else "UNKNOWN"
        pred = est.predict_baseline(rec.session_id, rec.driver_number, target_lap=rec.lap_number, compound=comp_arg, stint_id=st_arg)

        is_target = (not rec.neutralised) and (not rec.is_pit) and (rec.lap_number >= 2) and (
            rec.clean_air_status == CleanAirStatus.CLEAN_AIR_CONFIRMED
        )
        if is_target and pred.baseline_sec is not None and pred.status == "STINT_ROLLING_CALIBRATED":
            pts.append(
                LapPredictionPoint(
                    pred.baseline_sec,
                    pred.ci95_low_sec,
                    pred.ci95_high_sec,
                    0.95,
                    rec.lap_sec,
                    rec.clean_air_status,
                )
            )
        elif is_target:
            pts.append(LapPredictionPoint(None, None, None, 0.0, rec.lap_sec, rec.clean_air_status))

        ca_arg = rec.clean_air_status if clean_air_filter else (
            CleanAirStatus.TRAFFIC_AFFECTED if rec.is_pit else CleanAirStatus.CLEAN_AIR_CONFIRMED
        )
        est.observe_lap(
            rec.session_id,
            rec.driver_number,
            rec.lap_number,
            rec.lap_sec,
            stint_id=st_arg,
            compound=comp_arg,
            clean_air_status=ca_arg,
            neutralised=rec.neutralised,
            total_laps=rec.total_laps,
            prior_prediction=pred,
        )

    return pts


def _ablate_shrinkage_on_races(races: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare hierarchical shrinkage slope vs unpooled raw driver stint OLS on predicting later stint laps."""
    err_unpooled: list[float] = []
    err_shrunk: list[float] = []

    for race in races:
        deg = FuelCompensatedDegradationModel()
        by_driver_stint: dict[tuple[int, int], list[CausalLapRecord]] = {}
        for r in race["records"]:
            if not r.neutralised and not r.is_pit and r.lap_number >= 2 and r.clean_air_status == CleanAirStatus.CLEAN_AIR_CONFIRMED:
                by_driver_stint.setdefault((r.driver_number, r.stint_id), []).append(r)

        # Feed early stint laps (first 6 laps) for all drivers so session pool builds cleanly, then evaluate laps 7+
        for r in race["records"]:
            if r.lap_number <= 15:
                deg.observe_lap(
                    race["session_id"],
                    r.driver_number,
                    r.lap_number,
                    r.lap_sec,
                    compound=r.compound,
                    tyre_age=r.tyre_age,
                    stint_id=r.stint_id,
                    neutralised=r.neutralised,
                    pit_lap=r.is_pit,
                    total_laps=r.total_laps,
                )

        fuel_burn, _ = estimate_fuel_burn_rate(race["total_laps"])
        for (dn, _st), stint_recs in by_driver_stint.items():
            if len(stint_recs) < 10:
                continue
            train_part = stint_recs[:6]
            test_part = stint_recs[6:11]
            # Fit pooled estimate on first 6 laps cleanly
            d_local = FuelCompensatedDegradationModel()
            for (o_dn, _o_st), o_recs in by_driver_stint.items():
                lim = 6 if o_dn == dn else 12
                for rec in o_recs[:lim]:
                    d_local.observe_lap(
                        race["session_id"],
                        rec.driver_number,
                        rec.lap_number,
                        rec.lap_sec,
                        compound=rec.compound,
                        tyre_age=rec.tyre_age,
                        stint_id=rec.stint_id,
                        total_laps=rec.total_laps,
                    )
            est = d_local.estimate_degradation(race["session_id"], dn, compound=train_part[0].compound)
            if est.driver_stint_slope is None:
                continue
            base_lap = train_part[-1].lap_number
            base_sec = train_part[-1].lap_sec
            for t in test_part:
                dl = t.lap_number - base_lap
                pred_raw = base_sec + (est.driver_stint_slope - fuel_burn) * dl
                pred_shrunk = base_sec + (est.slope_sec_per_lap - fuel_burn) * dl
                err_unpooled.append(abs(t.lap_sec - pred_raw))
                err_shrunk.append(abs(t.lap_sec - pred_shrunk))

    if not err_unpooled:
        return {"n_stint_laps": 0}
    return {
        "n_stint_laps": len(err_unpooled),
        "unpooled_ols_mae_sec": round(sum(err_unpooled) / len(err_unpooled), 4),
        "shrinkage_posterior_mae_sec": round(sum(err_shrunk) / len(err_shrunk), 4),
        "delta_mae_sec": round((sum(err_shrunk) - sum(err_unpooled)) / len(err_unpooled), 4),
    }


async def _ablate_sia_and_fusion_gating() -> dict[str, Any]:
    """
    Deterministic evaluation benchmark measuring False Positive Rate (FPR), Precision, and Recall
    for CONFIRMED assessments across valid, uncalibrated, missing-telemetry, and SIA-corrupted scenarios.
    """
    from datetime import UTC, datetime

    now = datetime(2025, 7, 1, 14, 0, 0, tzinfo=UTC)
    scenarios = [
        # (name, ground_truth_confirmable, cal_status, sia_state, finality, clean_air, sample_laps, missing)
        ("valid_corroborated_final", True, "EMPIRICAL_PIT_CALIBRATED+DRIVER_STINT_CALIBRATED", "HEALTHY", "FINAL", True, 10, False),
        ("valid_multi_agent_clean", True, "EMPIRICAL_PIT_CALIBRATED+DRIVER_STINT_CALIBRATED", None, None, True, 8, False),
        ("uncalibrated_prior_no_sia", False, "PRIOR_UNMEASURED", None, None, None, 0, False),
        ("uncalibrated_prior_open", False, "PRIOR_UNMEASURED", "HEALTHY", "FINAL", True, 6, False),
        ("sia_suspect_block", False, "EMPIRICAL_PIT_CALIBRATED", "SUSPECT", "FINAL", True, 8, False),
        ("sia_unknown_block", False, "EMPIRICAL_PIT_CALIBRATED", "UNKNOWN", "OPEN", True, 8, False),
        ("sia_degraded_reject", False, "EMPIRICAL_PIT_CALIBRATED", "DEGRADED", "FINAL", True, 8, False),
        ("non_finalized_quarantine", False, "EMPIRICAL_PIT_CALIBRATED", "HEALTHY", "OPEN", True, 8, False),
        ("missing_telemetry_clean_unknown", False, "EMPIRICAL_PIT_CALIBRATED", "HEALTHY", "FINAL", None, 2, True),
        ("traffic_conflict_dirty_air", False, "EMPIRICAL_PIT_CALIBRATED", "HEALTHY", "FINAL", False, 8, False),
    ]

    def _score(preds: list[tuple[bool, bool]]) -> dict[str, Any]:
        tp = sum(1 for y, p in preds if y and p)
        fp = sum(1 for y, p in preds if (not y) and p)
        fn = sum(1 for y, p in preds if y and (not p))
        tn = sum(1 for y, p in preds if (not y) and (not p))
        prec = tp / max(tp + fp, 1)
        rec = tp / max(tp + fn, 1)
        fpr = fp / max(fp + tn, 1)
        return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(prec, 4), "recall": round(rec, 4), "fpr": round(fpr, 4)}

    pre_phase_i_preds: list[tuple[bool, bool]] = []
    phase_i_preds: list[tuple[bool, bool]] = []

    for idx, (name, truth, cal, sia_st, fin, ca, samp, missing) in enumerate(scenarios):
        sid = f"abl-{idx}-{name}"
        # Legacy pre-Phase-I fusion promoted whenever SIA wasn't SUSPECT/QUARANTINED/VOID
        legacy_confirm = sia_st not in {"SUSPECT", "QUARANTINED", "VOID"}
        pre_phase_i_preds.append((truth, legacy_confirm))

        fusion = ConsequenceFusionEngine()
        if sia_st is not None:
            await fusion.on_finding(
                "pulse.agent.integrity.findings.v1",
                f"{sid}:1",
                Finding(
                    finding_id=f"f-sia-{idx}",
                    agent_id="agent-06-integrity",
                    finding_type="INTEGRITY_ASSESSMENT",
                    session_id=sid,
                    run_id="r",
                    subject=Subject(driver_number=1),
                    as_of_event_time=now,
                    interpretation=Interpretation.DERIVED,
                    result={"integrity_state": sia_st, "finality_status": fin},
                ),
            )
        if ca is not None or missing:
            await fusion.on_finding(
                "pulse.agent.vehicle_response.findings.v1",
                f"{sid}:1",
                Finding(
                    finding_id=f"f-pace-{idx}",
                    agent_id="agent-03-vehicle-response",
                    finding_type="PACE_DEVIATION",
                    session_id=sid,
                    run_id="r",
                    subject=Subject(driver_number=1),
                    as_of_event_time=now,
                    interpretation=Interpretation.OBSERVED,
                    assessment_status=FindingStatus.OBSERVED if not missing else FindingStatus.PROVISIONAL,
                    result={
                        "driver_number": 1,
                        "pace_delta_sec": 0.1 if not missing else None,
                        "baseline_status": "STINT_ROLLING_CALIBRATED" if not missing else "INITIALIZING",
                        "baseline_sample_count": samp,
                        "clean_air": ca,
                        "clean_air_status": (
                            CleanAirStatus.CLEAN_AIR_CONFIRMED.value
                            if ca is True
                            else (CleanAirStatus.TRAFFIC_AFFECTED.value if ca is False else CleanAirStatus.CLEAN_AIR_UNKNOWN.value)
                        ),
                        "missing_telemetry": missing,
                    },
                ),
            )
        await fusion.on_finding(
            "pulse.agent.tyre_strategy.findings.v1",
            f"{sid}:1",
            Finding(
                finding_id=f"f-st-{idx}",
                agent_id="agent-04-tyre-strategy",
                finding_type="PIT_WINDOW_OPPORTUNITY",
                session_id=sid,
                run_id="r",
                subject=Subject(driver_number=1),
                as_of_event_time=now,
                interpretation=Interpretation.PREDICTED if "EMPIRICAL" in cal else Interpretation.INFERRED,
                assessment_status=FindingStatus.CONFIRMED if "EMPIRICAL" in cal else FindingStatus.PROVISIONAL,
                result={
                    "driver_number": 1,
                    "calibration_status": cal,
                    "sample_count": samp,
                    "net_time_saving_sec": 10.0,
                    "degradation_estimate": {"sample_laps": samp, "calibration_status": "DRIVER_STINT_CALIBRATED" if samp >= 5 else "INSUFFICIENT_SAMPLES"},
                },
            ),
        )
        out = fusion._scoped_assessments[(sid, 1)]
        phase_i_preds.append((truth, out.status == FindingStatus.CONFIRMED))

    return {
        "n_scenarios": len(scenarios),
        "pre_phase_i_no_calibration_gate": _score(pre_phase_i_preds),
        "phase_i_strict_sia_and_fusion_gate": _score(phase_i_preds),
    }


def run_full_validation_suite(cache_dir: str | Path) -> dict[str, Any]:
    """Runs complete calibration/holdout + LORO validation across all cached FastF1 races."""
    cal_data = [load_fastf1_causal_laps(cache_dir, y, gp) for y, gp in CALIBRATION_RACES]
    hold_data = [load_fastf1_causal_laps(cache_dir, y, gp) for y, gp in HOLDOUT_RACES]
    edge_data = [load_fastf1_causal_laps(cache_dir, y, gp) for y, gp in EDGE_CASE_RACES]
    all_main = cal_data + hold_data

    # 1. Calibration -> Holdout strict out-of-sample regression fit
    cal_reg_params = _eval_regression_fit(cal_data)
    cal_results = [evaluate_all_baselines_on_race(r, regression_params=cal_reg_params) for r in cal_data]
    hold_results = [evaluate_all_baselines_on_race(r, regression_params=cal_reg_params) for r in hold_data]
    edge_results = [evaluate_all_baselines_on_race(r, regression_params=cal_reg_params) for r in edge_data]

    # 2. Leave-One-Race-Out (LORO) across all 5 full-distance races
    loro_results = []
    for idx, test_race in enumerate(all_main):
        train_races = [r for j, r in enumerate(all_main) if j != idx]
        params = _eval_regression_fit(train_races)
        res = evaluate_all_baselines_on_race(test_race, regression_params=params)
        res["loro_regression_params"] = {"beta_age": params[0], "beta_prog": params[1], "half_w95": params[2]}
        loro_results.append(res)

    # Aggregate macro/micro stats across LORO 5 races for each of 6 baselines
    model_names = list(loro_results[0]["models"].keys()) if loro_results else []
    loro_aggregate: dict[str, Any] = {}
    for m in model_names:
        rows = [r["models"][m] for r in loro_results if r["models"][m]["n_predicted"] > 0]
        total_n = sum(row["n_predicted"] for row in rows)
        if total_n == 0:
            loro_aggregate[m] = {"n_predicted": 0}
            continue
        w_mae = sum(row["mae_sec"] * row["n_predicted"] for row in rows) / total_n
        w_rmse = math.sqrt(sum((row["rmse_sec"] ** 2) * row["n_predicted"] for row in rows) / total_n)
        w_cov = sum(row["pi95_coverage"] * row["n_predicted"] for row in rows) / total_n
        w_width = sum((row["mean_pi95_width_sec"] or 0.0) * row["n_predicted"] for row in rows) / total_n
        loro_aggregate[m] = {
            "n_predicted": total_n,
            "weighted_mae_sec": round(w_mae, 4),
            "weighted_rmse_sec": round(w_rmse, 4),
            "weighted_pi95_coverage": round(w_cov, 4),
            "weighted_pi95_width_sec": round(w_width, 4),
            "calibration_gap_from_95pct": round(w_cov - 0.95, 4),
            "calibrated_at_95pct_within_2pct": abs(w_cov - 0.95) <= 0.02,
        }

    # 3. 7-component ablation
    ablation = run_ablation_study(all_main)

    return {
        "protocol": {
            "calibration_races": [f"{y} {gp}" for y, gp in CALIBRATION_RACES],
            "holdout_races": [f"{y} {gp}" for y, gp in HOLDOUT_RACES],
            "edge_case_races": [f"{y} {gp}" for y, gp in EDGE_CASE_RACES],
            "leakage_guard": "Strictly causal crossing-order stream; lap_start intervals use same-lap prior cars only; regression coefficients fit only on LORO/calibration training folds.",
            "calibration_regression_params": {"beta_age": cal_reg_params[0], "beta_prog": cal_reg_params[1], "half_w95": cal_reg_params[2]},
        },
        "calibration_split": cal_results,
        "holdout_split": hold_results,
        "edge_case_belgium_2021": edge_results,
        "loro_validation": loro_results,
        "loro_aggregate_comparison": loro_aggregate,
        "ablation_study": ablation,
    }
