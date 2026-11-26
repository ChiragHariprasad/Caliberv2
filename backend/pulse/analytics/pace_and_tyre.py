"""
Scientific Formula 1 Pace, Fuel-Compensated Degradation & Pit Strategy Models.

Replaces hardcoded 76.0s pace baselines, uncompensated negative raw stint OLS
slopes, fabricated +0.12/+0.08/+0.04 constants, and invented age-23 stints with:
- Causal rolling clean-air baseline estimation + conformal/MAD 95% intervals.
- Physical fuel-burn normalization + persistent weather/drying regime shift tracking.
- Inverse-variance precision pooling (driver stint + session compound pool + weak prior).
- Empirical circuit pit-loss learning + live field-gap re-entry rank projection.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from pulse.contracts import CleanAirStatus

# Generic physical priors (explicitly tagged as UNMEASURED_PRIOR whenever used)
DEFAULT_FUEL_BURN_SEC_PER_LAP = 0.060
DEFAULT_USABLE_FUEL_KG = 100.0
FUEL_SENSITIVITY_SEC_PER_KG = 0.035

PRIOR_PIT_LOSS_GREEN_SEC = 21.5
PRIOR_PIT_LOSS_VSC_SEC = 11.0
PRIOR_PIT_LOSS_SC_SEC = 8.5
PRIOR_PIT_LOSS_UNCERTAINTY_SEC = 3.0

# Weakly-informative modern Pirelli dry/wet fuel-corrected slope priors (s/lap)
PRIOR_DEG_SLOPE_SEC_PER_LAP: dict[str, float] = {
    "S": 0.055,
    "M": 0.030,
    "H": 0.018,
    "I": 0.060,
    "W": 0.070,
    "UNKNOWN": 0.030,
}
PRIOR_DEG_SLOPE_SE = 0.060


def normalize_compound(raw: Any) -> str:
    """Normalizes F1 tyre compound names into canonical codes (S/M/H/I/W/UNKNOWN)."""
    if raw is None:
        return "UNKNOWN"
    s = str(raw).strip().upper()
    if not s or s in {"NONE", "NAN", "NULL", "UNK", "UNKNOWN"}:
        return "UNKNOWN"
    if s.startswith("SOFT") or s == "S" or s in {"C4", "C5", "C6"}:
        return "S"
    if s.startswith("MED") or s == "M" or s == "C3":
        return "M"
    if s.startswith("HARD") or s == "H" or s in {"C0", "C1", "C2"}:
        return "H"
    if s.startswith("INT") or s == "I":
        return "I"
    if s.startswith("WET") or s == "W":
        return "W"
    return s[0] if s[0] in {"S", "M", "H", "I", "W"} else "UNKNOWN"


def estimate_fuel_burn_rate(total_laps: int | None) -> tuple[float, str]:
    """
    Returns (fuel_burn_sec_per_lap, source_tag).
    Uses ~100 kg usable race fuel distributed across scheduled race distance.
    """
    if total_laps is not None and total_laps >= 15:
        rate = (DEFAULT_USABLE_FUEL_KG / float(total_laps)) * FUEL_SENSITIVITY_SEC_PER_KG
        return round(min(max(rate, 0.045), 0.095), 4), "CIRCUIT_LAP_COUNT_MODEL"
    return DEFAULT_FUEL_BURN_SEC_PER_LAP, "GENERIC_FUEL_PRIOR"


def resolve_clean_air_status(
    clean_air: bool | None = None,
    clean_air_status: CleanAirStatus | str | None = None,
    *,
    is_pit: bool = False,
    position: int | None = None,
    interval_sec: float | None = None,
    threshold_sec: float = 1.8,
) -> tuple[CleanAirStatus, bool | None]:
    """Resolve tri-state clean-air classification without equating missing interval data to clean air."""
    if is_pit:
        return CleanAirStatus.TRAFFIC_AFFECTED, False
    if clean_air_status is not None:
        norm = clean_air_status if isinstance(clean_air_status, CleanAirStatus) else CleanAirStatus(str(clean_air_status))
        if norm == CleanAirStatus.CLEAN_AIR_CONFIRMED:
            return CleanAirStatus.CLEAN_AIR_CONFIRMED, True
        if norm == CleanAirStatus.TRAFFIC_AFFECTED:
            return CleanAirStatus.TRAFFIC_AFFECTED, False
        return CleanAirStatus.CLEAN_AIR_UNKNOWN, None
    if interval_sec is not None and math.isfinite(interval_sec):
        if interval_sec >= threshold_sec:
            return CleanAirStatus.CLEAN_AIR_CONFIRMED, True
        return CleanAirStatus.TRAFFIC_AFFECTED, False
    if position == 1:
        return CleanAirStatus.CLEAN_AIR_CONFIRMED, True
    if clean_air is True:
        return CleanAirStatus.CLEAN_AIR_CONFIRMED, True
    if clean_air is False:
        return CleanAirStatus.TRAFFIC_AFFECTED, False
    return CleanAirStatus.CLEAN_AIR_UNKNOWN, None


def safe_ols_slope(x: list[float], y: list[float]) -> tuple[float, float, float] | None:
    """
    Fits unweighted OLS y = a + b*x and returns (slope, standard_error, r2)
    when >= 5 finite samples span >= 3 stint laps.
    """
    pts = [(float(xi), float(yi)) for xi, yi in zip(x, y) if math.isfinite(xi) and math.isfinite(yi)]
    if len(pts) < 5:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if (max(xs) - min(xs)) < 3.0:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((xi - mx) ** 2 for xi in xs)
    if sxx <= 1e-9:
        return None
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(xs, ys))
    syy = sum((yi - my) ** 2 for yi in ys)
    slope = sxy / sxx
    sse = sum((yi - (my + slope * (xi - mx))) ** 2 for xi, yi in zip(xs, ys))
    dof = max(n - 2, 1)
    se = math.sqrt(max(sse / dof, 1e-9) / sxx)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 1e-9 else 0.0
    return slope, se, max(0.0, min(1.0, r2))


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


@dataclass
class BaselinePrediction:
    baseline_sec: float | None
    ci95_low_sec: float | None
    ci95_high_sec: float | None
    uncertainty_sec: float | None
    sample_count: int
    status: str  # STINT_ROLLING_CALIBRATED | SESSION_COMPOUND_PRIOR | SINGLE_LAP_INIT | INITIALIZING
    fuel_burn_sec_per_lap: float
    fuel_source: str


@dataclass
class DegradationEstimate:
    compound: str
    slope_sec_per_lap: float
    raw_uncompensated_slope_sec_per_lap: float | None
    slope_se_sec_per_lap: float
    n_driver_laps: int
    n_session_stints: int
    fuel_burn_sec_per_lap: float
    calibration_status: str  # DRIVER_STINT_CALIBRATED | SESSION_POOL_CALIBRATED | PRIOR_UNMEASURED
    driver_stint_slope: float | None = None
    session_pool_slope: float | None = None
    r_squared: float | None = None


@dataclass
class _DriverPaceMemory:
    last_stint_id: int | None = None
    last_compound: str = "UNKNOWN"
    stint_laps: deque[tuple[int, float]] = field(default_factory=lambda: deque(maxlen=12))
    pending_shift_laps: deque[tuple[int, float]] = field(default_factory=lambda: deque(maxlen=3))
    abs_errors: deque[float] = field(default_factory=lambda: deque(maxlen=40))
    last_clean_lap: tuple[int, int, float] | None = None  # (lap_num, stint_id, lap_sec)


class RollingCleanAirPaceEstimator:
    """
    Strictly causal clean-air lap baseline estimator with conformal-scaled uncertainty.

    Replaces hardcoded 76.0s baselines with:
    1. Per-stint sliding clean-air median adjusted for fuel burn & major track shifts.
    2. Stint reset upon pit/compound change (preventing wet/inter or worn laps poisoning fresh stints).
    3. Conformal-calibrated empirical 95% prediction intervals using causal MAD + past absolute errors.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[int, _DriverPaceMemory]] = {}
        self._session_compound_laps: dict[str, dict[str, deque[float]]] = {}
        self._session_total_laps: dict[str, int] = {}
        # Causal track evolution (only updates on major regime shifts |delta| > 0.20s across >=4 cars)
        self._lap_driver_obs: dict[str, dict[int, dict[int, tuple[float, int]]]] = {}
        self._track_evo_index: dict[str, dict[int, float]] = {}
        self._cum_evo: dict[str, float] = {}
        self._evo_last_lap: dict[str, int] = {}
        self._clean_air_counts: dict[tuple[str, int], dict[str, int]] = {}

    def reset(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._sessions.clear()
            self._session_compound_laps.clear()
            self._session_total_laps.clear()
            self._lap_driver_obs.clear()
            self._track_evo_index.clear()
            self._cum_evo.clear()
            self._evo_last_lap.clear()
            self._clean_air_counts.clear()
        else:
            self._sessions.pop(session_id, None)
            self._session_compound_laps.pop(session_id, None)
            self._session_total_laps.pop(session_id, None)
            self._lap_driver_obs.pop(session_id, None)
            self._track_evo_index.pop(session_id, None)
            self._cum_evo.pop(session_id, None)
            self._evo_last_lap.pop(session_id, None)
            for k in [key for key in self._clean_air_counts if key[0] == session_id]:
                self._clean_air_counts.pop(k, None)

    def get_clean_air_summary(self, session_id: str, driver_number: int) -> dict[str, int]:
        counts = self._clean_air_counts.get((session_id, driver_number))
        if counts is None:
            return {
                CleanAirStatus.CLEAN_AIR_CONFIRMED.value: 0,
                CleanAirStatus.TRAFFIC_AFFECTED.value: 0,
                CleanAirStatus.CLEAN_AIR_UNKNOWN.value: 0,
            }
        return dict(counts)

    def _get_driver(self, session_id: str, driver_number: int) -> _DriverPaceMemory:
        sess = self._sessions.setdefault(session_id, {})
        return sess.setdefault(driver_number, _DriverPaceMemory())

    def _get_evo(self, session_id: str, lap_number: int) -> float:
        evo_map = self._track_evo_index.get(session_id, {})
        if lap_number in evo_map:
            return evo_map[lap_number]
        return self._cum_evo.get(session_id, 0.0)

    def _advance_track_evo(self, session_id: str, current_lap: int, fuel_burn: float) -> None:
        # Advance only up to current_lap - 1 so all cars on prior completed laps have been observed
        ready_lap = current_lap - 1
        prev_processed = self._evo_last_lap.get(session_id, 1)
        if ready_lap <= prev_processed:
            return
        by_lap = self._lap_driver_obs.get(session_id, {})
        evo_map = self._track_evo_index.setdefault(session_id, {})
        cum = self._cum_evo.get(session_id, 0.0)
        for ln in range(max(2, prev_processed + 1), ready_lap + 1):
            evo_map[ln] = cum
            prev_obs = by_lap.get(ln - 1, {})
            curr_obs = by_lap.get(ln, {})
            diffs: list[float] = []
            for drv, (t_curr, st_curr) in curr_obs.items():
                if drv in prev_obs:
                    t_prev, st_prev = prev_obs[drv]
                    if st_curr == st_prev:
                        diffs.append((t_curr - t_prev) + fuel_burn)
            if len(diffs) >= 4:
                med = statistics.median(diffs)
                if abs(med) > 0.20:
                    cum += max(-1.5, min(1.5, med))
            by_lap.pop(ln - 3, None)
        self._cum_evo[session_id] = cum
        self._evo_last_lap[session_id] = ready_lap

    def predict_baseline(
        self,
        session_id: str,
        driver_number: int,
        target_lap: int | None = None,
        compound: Any = None,
        stint_id: int | None = None,
    ) -> BaselinePrediction:
        total_laps = self._session_total_laps.get(session_id)
        fuel_burn, fuel_source = estimate_fuel_burn_rate(total_laps)
        comp = normalize_compound(compound)
        mem = self._get_driver(session_id, driver_number)

        stint_changed = (
            (stint_id is not None and mem.last_stint_id is not None and stint_id != mem.last_stint_id)
            or (comp != "UNKNOWN" and mem.last_compound != "UNKNOWN" and comp != mem.last_compound)
        )
        history = [] if stint_changed else list(mem.stint_laps)[-5:]

        ref_lap = target_lap if target_lap is not None else ((history[-1][0] + 1) if history else 2)
        evo_target = self._get_evo(session_id, ref_lap)

        if len(history) >= 2:
            adjusted = [
                sec - fuel_burn * (ref_lap - lp) + (evo_target - self._get_evo(session_id, lp))
                for lp, sec in history
            ]
            pred = statistics.median(adjusted)
            mad = statistics.median([abs(v - pred) for v in adjusted]) if len(adjusted) >= 3 else abs(adjusted[-1] - adjusted[-2]) * 0.5
            sigma = max(1.4826 * mad, 0.25)
            n_w = len(adjusted)
            if len(mem.abs_errors) >= 15:
                q95 = _quantile(sorted(mem.abs_errors), 0.95)
                half_w = max(q95, 2.2 * sigma)
            else:
                half_w = 2.6 * sigma * math.sqrt(1.0 + 1.0 / n_w)
            return BaselinePrediction(
                baseline_sec=round(pred, 3),
                ci95_low_sec=round(pred - half_w, 3),
                ci95_high_sec=round(pred + half_w, 3),
                uncertainty_sec=round(half_w / 1.96, 3),
                sample_count=n_w,
                status="STINT_ROLLING_CALIBRATED",
                fuel_burn_sec_per_lap=fuel_burn,
                fuel_source=fuel_source,
            )

        if len(history) == 1:
            lp, sec = history[0]
            pred = sec - fuel_burn * max(0, ref_lap - lp)
            half_w = 1.50
            return BaselinePrediction(
                baseline_sec=round(pred, 3),
                ci95_low_sec=round(pred - half_w, 3),
                ci95_high_sec=round(pred + half_w, 3),
                uncertainty_sec=round(half_w / 1.96, 3),
                sample_count=1,
                status="SINGLE_LAP_INIT",
                fuel_burn_sec_per_lap=fuel_burn,
                fuel_source=fuel_source,
            )

        # Fallback upon stint transition / cold-start on a known compound with session samples
        comp_pool = self._session_compound_laps.get(session_id, {}).get(comp)
        if comp != "UNKNOWN" and comp_pool and len(comp_pool) >= 3:
            pool_vals = list(comp_pool)[-30:]
            pred = statistics.median(pool_vals)
            mad = statistics.median([abs(v - pred) for v in pool_vals])
            half_w = max(2.6 * max(1.4826 * mad, 0.45), 1.25)
            return BaselinePrediction(
                baseline_sec=round(pred, 3),
                ci95_low_sec=round(pred - half_w, 3),
                ci95_high_sec=round(pred + half_w, 3),
                uncertainty_sec=round(half_w / 1.96, 3),
                sample_count=len(pool_vals),
                status="SESSION_COMPOUND_PRIOR",
                fuel_burn_sec_per_lap=fuel_burn,
                fuel_source=fuel_source,
            )

        return BaselinePrediction(
            baseline_sec=None,
            ci95_low_sec=None,
            ci95_high_sec=None,
            uncertainty_sec=None,
            sample_count=0,
            status="INITIALIZING",
            fuel_burn_sec_per_lap=fuel_burn,
            fuel_source=fuel_source,
        )

    def observe_lap(
        self,
        session_id: str,
        driver_number: int,
        lap_number: int,
        lap_sec: float | None,
        *,
        stint_id: int | None = None,
        compound: Any = None,
        clean_air: bool | None = None,
        clean_air_status: CleanAirStatus | str | None = None,
        position: int | None = None,
        interval_sec: float | None = None,
        neutralised: bool = False,
        total_laps: int | None = None,
        prior_prediction: BaselinePrediction | None = None,
    ) -> None:
        if total_laps is not None and total_laps >= 15:
            self._session_total_laps[session_id] = int(total_laps)
        if lap_sec is None or not math.isfinite(lap_sec) or lap_sec <= 35.0 or lap_sec >= 300.0:
            return

        resolved_status, resolved_flag = resolve_clean_air_status(
            clean_air=clean_air,
            clean_air_status=clean_air_status,
            position=position,
            interval_sec=interval_sec,
        )
        is_confirmed_clean_air = resolved_status == CleanAirStatus.CLEAN_AIR_CONFIRMED
        counts = self._clean_air_counts.setdefault(
            (session_id, driver_number),
            {
                CleanAirStatus.CLEAN_AIR_CONFIRMED.value: 0,
                CleanAirStatus.TRAFFIC_AFFECTED.value: 0,
                CleanAirStatus.CLEAN_AIR_UNKNOWN.value: 0,
            },
        )
        counts[resolved_status.value] = counts.get(resolved_status.value, 0) + 1

        comp = normalize_compound(compound)
        mem = self._get_driver(session_id, driver_number)
        st_num = stint_id if stint_id is not None else (mem.last_stint_id or 1)

        if (stint_id is not None and mem.last_stint_id is not None and stint_id != mem.last_stint_id) or (
            comp != "UNKNOWN" and mem.last_compound != "UNKNOWN" and comp != mem.last_compound
        ):
            mem.stint_laps.clear()
            mem.pending_shift_laps.clear()
        if stint_id is not None:
            mem.last_stint_id = stint_id
        elif mem.last_stint_id is None:
            mem.last_stint_id = 1
        if comp != "UNKNOWN":
            mem.last_compound = comp

        # Only learn confirmed clean green-flag flying laps > lap 1 into baseline (never CLEAN_AIR_UNKNOWN)
        if neutralised or lap_number <= 1:
            return

        if (
            is_confirmed_clean_air
            and prior_prediction is not None
            and prior_prediction.baseline_sec is not None
            and prior_prediction.status == "STINT_ROLLING_CALIBRATED"
        ):
            mem.abs_errors.append(abs(lap_sec - prior_prediction.baseline_sec))

        # Guard clean baseline window from single-lap anomalies while adapting to real 2-lap pace regime shifts (e.g. drying track / red-flag tyre change)
        if is_confirmed_clean_air and resolved_flag is True:
            if mem.stint_laps:
                cur_med = statistics.median([s for _, s in mem.stint_laps])
                if abs(lap_sec - cur_med) <= 4.0 or len(mem.stint_laps) < 2:
                    mem.stint_laps.append((lap_number, lap_sec))
                    mem.pending_shift_laps.clear()
                else:
                    mem.pending_shift_laps.append((lap_number, lap_sec))
                    if len(mem.pending_shift_laps) >= 2:
                        _, prev_shift_sec = mem.pending_shift_laps[-2]
                        if abs(lap_sec - prev_shift_sec) <= 4.0:
                            mem.stint_laps.clear()
                            mem.stint_laps.extend(list(mem.pending_shift_laps)[-2:])
                            mem.pending_shift_laps.clear()
            else:
                mem.stint_laps.append((lap_number, lap_sec))
                mem.pending_shift_laps.clear()

            if comp != "UNKNOWN":
                comp_hist = self._session_compound_laps.setdefault(session_id, {}).setdefault(comp, deque(maxlen=60))
                comp_hist.append(lap_sec)

            by_lap = self._lap_driver_obs.setdefault(session_id, {}).setdefault(lap_number, {})
            by_lap[driver_number] = (lap_sec, st_num)
            fuel_burn, _ = estimate_fuel_burn_rate(self._session_total_laps.get(session_id))
            self._advance_track_evo(session_id, lap_number, fuel_burn)


@dataclass
class _StintRecord:
    stint_id: int
    compound: str
    start_lap: int
    observations: list[tuple[int, int, float]] = field(default_factory=list)  # (lap_num, tyre_age, lap_sec)
    current_tyre_age: int | None = None
    in_pit: bool = False


class FuelCompensatedDegradationModel:
    """
    Causal fuel-burn normalized tyre degradation estimator with precision-weighted
    hierarchical pooling across session drivers + explicit uncertainty bounds.
    """

    def __init__(self) -> None:
        self._stints: dict[str, dict[int, list[_StintRecord]]] = {}
        self._session_total_laps: dict[str, int] = {}

    def reset(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._stints.clear()
            self._session_total_laps.clear()
        else:
            self._stints.pop(session_id, None)
            self._session_total_laps.pop(session_id, None)

    def get_active_stint(self, session_id: str, driver_number: int) -> dict[str, Any]:
        stints = self._stints.get(session_id, {}).get(driver_number, [])
        if not stints:
            return {"compound": "UNKNOWN", "stint_age": None, "stint_id": None, "sample_laps": 0}
        cur = stints[-1]
        return {
            "compound": cur.compound,
            "stint_age": cur.current_tyre_age,
            "stint_id": cur.stint_id,
            "sample_laps": len(cur.observations),
        }

    def record_pit_event(self, session_id: str, driver_number: int, is_exit: bool, compound: Any = None, lap_number: int | None = None) -> None:
        drv_stints = self._stints.setdefault(session_id, {}).setdefault(driver_number, [])
        comp = normalize_compound(compound)
        if not is_exit:
            if drv_stints:
                drv_stints[-1].in_pit = True
            return
        next_id = (drv_stints[-1].stint_id + 1) if drv_stints else 1
        drv_stints.append(
            _StintRecord(
                stint_id=next_id,
                compound=comp,
                start_lap=lap_number or 1,
                current_tyre_age=0,
                in_pit=False,
            )
        )

    def observe_lap(
        self,
        session_id: str,
        driver_number: int,
        lap_number: int,
        lap_sec: float | None,
        *,
        compound: Any = None,
        tyre_age: int | None = None,
        stint_id: int | None = None,
        neutralised: bool = False,
        pit_lap: bool = False,
        total_laps: int | None = None,
    ) -> None:
        if total_laps is not None and total_laps >= 15:
            self._session_total_laps[session_id] = int(total_laps)

        drv_stints = self._stints.setdefault(session_id, {}).setdefault(driver_number, [])
        comp = normalize_compound(compound)

        if not drv_stints:
            drv_stints.append(
                _StintRecord(
                    stint_id=stint_id or 1,
                    compound=comp,
                    start_lap=lap_number,
                    current_tyre_age=tyre_age,
                )
            )
        else:
            cur = drv_stints[-1]
            compound_switched = comp != "UNKNOWN" and cur.compound != "UNKNOWN" and comp != cur.compound
            stint_switched = stint_id is not None and stint_id != cur.stint_id
            age_reset = tyre_age is not None and cur.current_tyre_age is not None and tyre_age < cur.current_tyre_age
            if compound_switched or stint_switched or age_reset:
                drv_stints.append(
                    _StintRecord(
                        stint_id=stint_id or (cur.stint_id + 1),
                        compound=comp if comp != "UNKNOWN" else cur.compound,
                        start_lap=lap_number,
                        current_tyre_age=tyre_age,
                    )
                )
            else:
                if comp != "UNKNOWN" and cur.compound == "UNKNOWN":
                    cur.compound = comp
                if tyre_age is not None:
                    cur.current_tyre_age = tyre_age

        cur = drv_stints[-1]
        effective_age = tyre_age if tyre_age is not None else max(1, lap_number - cur.start_lap + 1)
        if cur.current_tyre_age is None or effective_age >= cur.current_tyre_age:
            cur.current_tyre_age = effective_age

        if (
            neutralised
            or pit_lap
            or cur.in_pit
            or lap_number <= 1
            or lap_sec is None
            or not math.isfinite(lap_sec)
            or lap_sec <= 35.0
            or lap_sec >= 300.0
        ):
            cur.in_pit = False
            return

        cur.observations.append((lap_number, effective_age, float(lap_sec)))

    def _fit_stint(self, stint: _StintRecord, fuel_burn: float) -> tuple[float, float, float, float, int] | None:
        if len(stint.observations) < 5:
            return None
        # Filter outliers > 3.5s from stint median so race traffic spikes don't corrupt OLS
        raw_ys = [o[2] for o in stint.observations]
        med_y = statistics.median(raw_ys)
        inliers = [o for o in stint.observations if abs(o[2] - med_y) <= 3.5]
        if len(inliers) < 5 or (inliers[-1][0] - inliers[0][0]) < 3:
            return None
        l0 = inliers[0][0]
        ages = [float(o[1]) for o in inliers]
        y_raw = [o[2] for o in inliers]
        y_fuel = [o[2] + fuel_burn * (o[0] - l0) for o in inliers]

        fit_fuel = safe_ols_slope(ages, y_fuel)
        fit_raw = safe_ols_slope(ages, y_raw)
        if fit_fuel is None or fit_raw is None:
            return None
        slope_f, se_f, r2_f = fit_fuel
        slope_r, _, _ = fit_raw
        # Guard wild physical non-sense on short noisy stints
        slope_f = max(-0.25, min(0.50, slope_f))
        return slope_f, max(se_f, 0.005), slope_r, r2_f, len(inliers)

    def estimate_degradation(
        self,
        session_id: str,
        driver_number: int,
        compound: Any = None,
    ) -> DegradationEstimate:
        fuel_burn, _ = estimate_fuel_burn_rate(self._session_total_laps.get(session_id))
        sess_stints = self._stints.get(session_id, {})
        drv_list = sess_stints.get(driver_number, [])
        active = drv_list[-1] if drv_list else None
        comp = normalize_compound(compound) if compound is not None else (active.compound if active else "UNKNOWN")

        drv_fit = self._fit_stint(active, fuel_burn) if active and (comp == "UNKNOWN" or active.compound == comp) else None

        pool_fits: list[tuple[float, float]] = []
        if comp != "UNKNOWN":
            for drv, slist in sess_stints.items():
                for st in slist:
                    if drv == driver_number and active is st:
                        continue
                    if st.compound == comp:
                        res = self._fit_stint(st, fuel_burn)
                        if res is not None:
                            pool_fits.append((res[0], res[1]))

        prior_slope = PRIOR_DEG_SLOPE_SEC_PER_LAP.get(comp, PRIOR_DEG_SLOPE_SEC_PER_LAP["UNKNOWN"])
        prior_prec = 1.0 / (PRIOR_DEG_SLOPE_SE ** 2)

        pool_slope: float | None = None
        if pool_fits:
            sum_w = sum(1.0 / (se * se) for _, se in pool_fits)
            pool_slope = sum(sl / (se * se) for sl, se in pool_fits) / sum_w

        if drv_fit is None and not pool_fits:
            n_obs = len(active.observations) if active else 0
            cal_tag = "INSUFFICIENT_SAMPLES" if n_obs > 0 else "PRIOR_UNMEASURED"
            return DegradationEstimate(
                compound=comp,
                slope_sec_per_lap=round(prior_slope, 4),
                raw_uncompensated_slope_sec_per_lap=None,
                slope_se_sec_per_lap=PRIOR_DEG_SLOPE_SE,
                n_driver_laps=n_obs,
                n_session_stints=0,
                fuel_burn_sec_per_lap=fuel_burn,
                calibration_status=cal_tag,
            )

        num = prior_slope * prior_prec
        den = prior_prec
        for sl, se in pool_fits:
            w = 1.0 / (se * se)
            num += sl * w
            den += w
        if drv_fit is not None:
            sl_d, se_d, raw_r, r2_d, n_inliers = drv_fit
            w_d = 1.0 / (se_d * se_d)
            num += sl_d * w_d
            den += w_d
            posterior_slope = num / den
            posterior_se = math.sqrt(1.0 / den)
            return DegradationEstimate(
                compound=comp,
                slope_sec_per_lap=round(posterior_slope, 4),
                raw_uncompensated_slope_sec_per_lap=round(raw_r, 4),
                slope_se_sec_per_lap=round(posterior_se, 4),
                n_driver_laps=n_inliers,
                n_session_stints=len(pool_fits) + 1,
                fuel_burn_sec_per_lap=fuel_burn,
                calibration_status="DRIVER_STINT_CALIBRATED",
                driver_stint_slope=round(sl_d, 4),
                session_pool_slope=round(pool_slope, 4) if pool_slope is not None else None,
                r_squared=round(r2_d, 3),
            )

        # Only session pool fits available (driver stint still young)
        posterior_slope = num / den
        posterior_se = math.sqrt(1.0 / den)
        return DegradationEstimate(
            compound=comp,
            slope_sec_per_lap=round(posterior_slope, 4),
            raw_uncompensated_slope_sec_per_lap=None,
            slope_se_sec_per_lap=round(posterior_se, 4),
            n_driver_laps=len(active.observations) if active else 0,
            n_session_stints=len(pool_fits),
            fuel_burn_sec_per_lap=fuel_burn,
            calibration_status="SESSION_POOL_CALIBRATED",
            driver_stint_slope=None,
            session_pool_slope=round(pool_slope, 4) if pool_slope is not None else None,
        )


class PitWindowStrategySimulator:
    """
    Learns session pit-lane transit losses empirically from PitIn/PitOut cycles
    and evaluates pit-window strategy under explicit field-gap re-entry projection
    and uncertainty bounds.
    """

    def __init__(self) -> None:
        self._green_pit_losses: dict[str, list[float]] = {}
        self._neutralised_pit_losses: dict[str, list[float]] = {}
        self._pending_pit_in: dict[str, dict[int, tuple[int, float, bool]]] = {}  # drv -> (in_lap, in_sec, neutralised)
        self._field_state: dict[str, dict[int, dict[str, Any]]] = {}

    def reset(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._green_pit_losses.clear()
            self._neutralised_pit_losses.clear()
            self._pending_pit_in.clear()
            self._field_state.clear()
        else:
            self._green_pit_losses.pop(session_id, None)
            self._neutralised_pit_losses.pop(session_id, None)
            self._pending_pit_in.pop(session_id, None)
            self._field_state.pop(session_id, None)

    def update_driver_state(
        self,
        session_id: str,
        driver_number: int,
        *,
        position: int | None = None,
        gap_to_leader_sec: float | None = None,
        interval_sec: float | None = None,
    ) -> None:
        drv_map = self._field_state.setdefault(session_id, {}).setdefault(driver_number, {})
        if position is not None and position > 0:
            drv_map["position"] = int(position)
        if gap_to_leader_sec is not None and math.isfinite(gap_to_leader_sec):
            drv_map["gap_to_leader_sec"] = float(gap_to_leader_sec)
        if interval_sec is not None and math.isfinite(interval_sec):
            drv_map["interval_sec"] = float(interval_sec)

    def record_pit_lap_observation(
        self,
        session_id: str,
        driver_number: int,
        lap_number: int,
        lap_sec: float | None,
        clean_baseline_sec: float | None,
        *,
        is_pit_in: bool = False,
        is_pit_out: bool = False,
        neutralised: bool = False,
    ) -> None:
        if lap_sec is None or clean_baseline_sec is None or not math.isfinite(lap_sec) or clean_baseline_sec <= 35.0:
            return
        pending = self._pending_pit_in.setdefault(session_id, {})
        if is_pit_in:
            pending[driver_number] = (lap_number, float(lap_sec), neutralised)
            return
        if is_pit_out and driver_number in pending:
            in_lap, in_sec, was_neut = pending.pop(driver_number)
            if lap_number in (in_lap + 1, in_lap):
                loss = (in_sec - clean_baseline_sec) + (float(lap_sec) - clean_baseline_sec)
                if 10.0 <= loss <= 45.0:
                    target = self._neutralised_pit_losses if (neutralised or was_neut) else self._green_pit_losses
                    target.setdefault(session_id, []).append(round(loss, 3))

    def get_pit_loss_calibration(self, session_id: str, neutralisation_mode: str) -> tuple[float, float, float, str]:
        """Returns (green_loss, active_loss, uncertainty_sec, calibration_status)."""
        green_obs = self._green_pit_losses.get(session_id, [])
        neut_obs = self._neutralised_pit_losses.get(session_id, [])

        if green_obs:
            green_loss = statistics.median(green_obs)
            green_unc = max(1.4826 * statistics.median([abs(x - green_loss) for x in green_obs]), 0.8) if len(green_obs) >= 2 else 1.8
            cal_status = "EMPIRICAL_PIT_CALIBRATED"
        else:
            green_loss = PRIOR_PIT_LOSS_GREEN_SEC
            green_unc = PRIOR_PIT_LOSS_UNCERTAINTY_SEC
            cal_status = "PRIOR_UNMEASURED"

        mode = neutralisation_mode.upper()
        if neut_obs:
            active_loss = statistics.median(neut_obs)
        elif "SC" in mode and "VSC" not in mode:
            active_loss = round(green_loss * (PRIOR_PIT_LOSS_SC_SEC / PRIOR_PIT_LOSS_GREEN_SEC), 2) if green_obs else PRIOR_PIT_LOSS_SC_SEC
        elif "VSC" in mode:
            active_loss = round(green_loss * (PRIOR_PIT_LOSS_VSC_SEC / PRIOR_PIT_LOSS_GREEN_SEC), 2) if green_obs else PRIOR_PIT_LOSS_VSC_SEC
        else:
            active_loss = green_loss

        return round(green_loss, 2), round(active_loss, 2), round(green_unc, 2), cal_status

    def project_reentry(self, session_id: str, driver_number: int, pit_loss_sec: float) -> tuple[str, int | None]:
        field = self._field_state.get(session_id, {})
        drv = field.get(driver_number, {})
        cur_gap = drv.get("gap_to_leader_sec")
        cur_pos = drv.get("position")

        if cur_gap is not None:
            reentry_gap = cur_gap + pit_loss_sec
            cars_ahead = 0
            known_others = 0
            for other_drv, info in field.items():
                if other_drv == driver_number:
                    continue
                og = info.get("gap_to_leader_sec")
                if og is not None:
                    known_others += 1
                    if og < reentry_gap:
                        cars_ahead += 1
            if known_others >= 2:
                pos = cars_ahead + 1
                return f"P{pos}", pos

        if cur_pos is not None:
            return f"~P{cur_pos}+ (GAPS_PARTIAL)", None
        return "UNMEASURED_NO_FIELD_GAPS", None

    def evaluate_pit_window(
        self,
        session_id: str,
        driver_number: int,
        neutralisation_mode: str,
        *,
        current_compound: str = "UNKNOWN",
        stint_age: int | None = None,
        deg_estimate: DegradationEstimate | None = None,
        remaining_laps: int | None = None,
    ) -> dict[str, Any]:
        green_loss, active_loss, pit_unc, pit_cal = self.get_pit_loss_calibration(session_id, neutralisation_mode)

        # Target compound decision grounded on remaining stint horizon when known
        if current_compound == "I" or current_compound == "W":
            target_compound = current_compound
        elif remaining_laps is not None and remaining_laps <= 18 and current_compound != "M":
            target_compound = "M"
        elif current_compound == "H":
            target_compound = "M" if (remaining_laps is not None and remaining_laps <= 28) else "H"
        else:
            target_compound = "H"

        # Expected compound delta gain over remaining horizon (zero when stint_age unmeasured)
        slope = deg_estimate.slope_sec_per_lap if deg_estimate is not None else PRIOR_DEG_SLOPE_SEC_PER_LAP.get(current_compound, 0.03)
        slope_se = deg_estimate.slope_se_sec_per_lap if deg_estimate is not None else PRIOR_DEG_SLOPE_SE
        horizon = min(max(remaining_laps or 10, 1), 20)
        if stint_age is not None and stint_age > 0 and slope > 0:
            # Conservative marginal gain: avoiding further wear on old tyre over short horizon
            age_advantage = round(min(4.0, max(0.0, slope * min(stint_age, 12) * 0.25)), 2)
        else:
            age_advantage = 0.0

        pit_delta_saving = round(green_loss - active_loss, 2)
        net_saving = round(pit_delta_saving + age_advantage, 2)
        total_unc = round(math.sqrt(pit_unc * pit_unc + (slope_se * horizon * 0.5) ** 2), 2)

        reentry_str, reentry_pos = self.project_reentry(session_id, driver_number, active_loss)
        drv_info = self._field_state.get(session_id, {}).get(driver_number, {})
        gap_to_p2 = drv_info.get("interval_sec")

        model_limitations: list[str] = [
            "Advisory heuristic over uniform 100 kg fuel approximation; not a globally optimal mixed-integer strategy solver",
            "Assumes static opponent pit-response (no reactive undercut/overcut game theory)",
            "Neutralisation end lap (SC/VSC duration) is unknown causal horizon",
        ]
        pit_window_viable = True
        if remaining_laps is None:
            model_limitations.append("Remaining race distance unknown; degradation horizon defaulted to 10 laps")
        elif remaining_laps <= 2:
            pit_window_viable = False
            model_limitations.append("END_OF_RACE_HORIZON_TOO_SHORT: remaining distance <= 2 laps")
        if gap_to_p2 is None:
            model_limitations.append("Missing interval_to_ahead telemetry for defender margin")
        if "UNMEASURED" in reentry_str or "PARTIAL" in reentry_str:
            model_limitations.append("Insufficient live field gaps for exact re-entry traffic penalty estimation")
        if "PRIOR_UNMEASURED" in pit_cal:
            model_limitations.append("Using generic uncalibrated prior pit-lane transit loss")
        if deg_estimate is None or deg_estimate.calibration_status in {"PRIOR_UNMEASURED", "INSUFFICIENT_SAMPLES"}:
            model_limitations.append("Tyre degradation slope lacks sufficient clean stint samples (>= 5 laps, span >= 3)")
        if current_compound in {"UNKNOWN", "I", "W"}:
            model_limitations.append("Wet/intermediate or unknown compound crossover highly sensitive to track evolution")

        scenarios = [
            {
                "label": "OPTIMISTIC (-1.5 sigma)",
                "pit_now_delta_sec": round(net_saving + 1.5 * total_unc, 2),
                "projected_reentry": reentry_str,
                "horizon_laps": horizon,
            },
            {
                "label": "EXPECTED (MEDIAN)",
                "pit_now_delta_sec": net_saving,
                "projected_reentry": reentry_str,
                "horizon_laps": horizon,
            },
            {
                "label": "CONSERVATIVE (+1.5 sigma)",
                "pit_now_delta_sec": round(net_saving - 1.5 * total_unc, 2),
                "projected_reentry": reentry_str,
                "horizon_laps": horizon,
            },
        ]

        overall_cal = pit_cal if (deg_estimate is None or deg_estimate.calibration_status in {"PRIOR_UNMEASURED", "INSUFFICIENT_SAMPLES"}) else f"{pit_cal}+{deg_estimate.calibration_status}"
        return {
            "target_compound": target_compound,
            "stint_age_current": stint_age,
            "current_compound": current_compound,
            "net_time_saving_sec": net_saving,
            "pit_delta_saving_sec": pit_delta_saving,
            "green_pit_loss_sec": green_loss,
            "neutralised_pit_loss_sec": active_loss,
            "uncertainty_sec": total_unc,
            "calibration_status": overall_cal,
            "reentry_window": reentry_str,
            "projected_reentry_pos": reentry_pos,
            "gap_to_p2_sec": gap_to_p2,
            "scenarios": scenarios,
            "strategy_scope": "ADVISORY_LOCAL_PIT_WINDOW_ONLY",
            "is_globally_optimal": False,
            "pit_window_viable": pit_window_viable,
            "sample_count": deg_estimate.n_driver_laps if deg_estimate is not None else 0,
            "model_limitations": model_limitations,
        }
