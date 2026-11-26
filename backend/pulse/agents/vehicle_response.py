from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from pulse.agents.base import BaseAgent
from pulse.analytics.pace_and_tyre import (
    FuelCompensatedDegradationModel,
    RollingCleanAirPaceEstimator,
    normalize_compound,
)
from pulse.contracts import Completeness, EventEnvelope, Finding, FindingStatus, Interpretation, Subject
from pulse.topics import AGENT_TOPICS

logger = logging.getLogger("pulse.agents.vehicle_response")


class VehicleResponseAgent(BaseAgent):
    """
    Agent 03: Vehicle-Response & Clean-Air Pace Intelligence (Scientific v2).

    Replaces hardcoded 76.0s pace baselines and invented intervals with:
    - Causal per-stint rolling clean-air baseline estimation + conformal/MAD 95% PIs.
    - Fuel-burn and persistent weather/evolution shift compensation.
    - Cross-checked stint degradation context so pace anomalies separate traffic,
      genuine thermal degradation, and neutralised/outlier laps honestly.
    """

    def __init__(self, bus: Any = None) -> None:
        super().__init__(
            agent_id="agent-03-vehicle-response",
            name="Vehicle-Response Intelligence",
            output_topic=AGENT_TOPICS["vehicle_response"],
            bus=bus,
            model_version="2.0.0",
        )
        self.pace_estimator = RollingCleanAirPaceEstimator()
        self.deg_model = FuelCompensatedDegradationModel()
        # Live dynamically populated baseline cache (never pre-seeded with constants)
        self.driver_baselines: dict[int, float] = {}
        self.driver_intervals: dict[int, float] = {}
        self.driver_stint_laps: dict[int, int] = {}
        self.session_total_laps: dict[str, int] = {}
        self.vsc_active = False
        self._driver_last_classification: dict[int, str] = {}
        self._driver_event_count: dict[int, int] = {}

    def reset(self) -> None:
        super().reset()
        self.pace_estimator.reset()
        self.deg_model.reset()
        self.driver_baselines.clear()
        self.driver_intervals.clear()
        self.driver_stint_laps.clear()
        self.session_total_laps.clear()
        self.vsc_active = False
        self._driver_last_classification.clear()
        self._driver_event_count.clear()

    def _parse_interval(self, raw_interval: Any) -> float | None:
        if raw_interval is None:
            return None
        if isinstance(raw_interval, (int, float)):
            return float(raw_interval)
        s = str(raw_interval).strip().upper()
        if not s or "LAP" in s or s in {"NONE", "NAN", "NULL", "--"}:
            return None
        try:
            return float(s.replace("+", "").replace("S", "").strip())
        except ValueError:
            return None

    def _parse_lap_seconds(self, payload: dict[str, Any]) -> float | None:
        for key in ("last_lap_seconds", "lap_time_sec", "lap_sec", "lap_time_seconds"):
            val = payload.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        ms = payload.get("lap_time_ms")
        if isinstance(ms, (int, float)) and ms > 0:
            return float(ms) / 1000.0
        return None

    async def on_event(self, topic: str, key: str, event: EventEnvelope) -> None:
        t0 = time.perf_counter_ns()
        et = event.event_type.upper()
        payload = event.payload or {}
        session_id = event.session.session_id
        run_id = event.run.run_id
        dn = event.subject.driver_number if event.subject else None

        relevant = et in {
            "SESSION_STARTED",
            "VSC_DEPLOYED",
            "SC_DEPLOYED",
            "SAFETY_CAR_DEPLOYED",
            "RED_FLAG",
            "VSC_ENDED",
            "SC_ENDED",
            "GREEN_FLAG",
            "GREEN_FLAG_RESUMED",
            "TRACK_STATUS_GREEN",
            "LAP_COMPLETED",
            "CAR_TELEMETRY",
        }
        self.record_input(event.event_id, eligible=relevant, filtered=not relevant, run_id=run_id)
        if not relevant:
            self.record_outcome("FILTERED", (time.perf_counter_ns() - t0) / 1_000_000.0)
            return

        try:
            if event.quality.completeness == Completeness.MISSING:
                self.record_outcome("INSUFFICIENT_DATA", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            if et == "SESSION_STARTED":
                tl = payload.get("total_laps")
                if isinstance(tl, (int, float)) and int(tl) >= 15:
                    self.session_total_laps[session_id] = int(tl)
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            if et in {"VSC_DEPLOYED", "SC_DEPLOYED", "SAFETY_CAR_DEPLOYED", "RED_FLAG"}:
                self.vsc_active = True
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return
            if et in {"VSC_ENDED", "SC_ENDED", "GREEN_FLAG", "GREEN_FLAG_RESUMED", "TRACK_STATUS_GREEN"}:
                self.vsc_active = False
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            if dn is None:
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            interval_val = self._parse_interval(payload.get("interval") or payload.get("interval_sec"))
            if interval_val is not None:
                self.driver_intervals[dn] = interval_val

            tyre_age_raw = payload.get("tyre_age")
            tyre_age = int(tyre_age_raw) if isinstance(tyre_age_raw, (int, float)) else None
            if tyre_age is not None:
                self.driver_stint_laps[dn] = tyre_age

            lap_seconds = self._parse_lap_seconds(payload)
            if lap_seconds is None:
                if et == "CAR_TELEMETRY":
                    self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                else:
                    self.record_outcome("INSUFFICIENT_DATA", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            lap_num_raw = payload.get("lap") or payload.get("lap_number") or getattr(event.subject, "lap_number", None)
            lap_num = int(lap_num_raw) if isinstance(lap_num_raw, (int, float)) and int(lap_num_raw) > 0 else 2
            total_laps_raw = payload.get("total_laps")
            if isinstance(total_laps_raw, (int, float)) and int(total_laps_raw) >= 15:
                self.session_total_laps[session_id] = int(total_laps_raw)
            total_laps = self.session_total_laps.get(session_id)

            stint_raw = payload.get("stint") or payload.get("stint_id")
            stint_id = int(stint_raw) if isinstance(stint_raw, (int, float)) else None
            compound = normalize_compound(payload.get("compound") or payload.get("tyre_compound"))
            pos_raw = payload.get("position")
            pos = int(pos_raw) if isinstance(pos_raw, (int, float)) and int(pos_raw) > 0 else None

            observed_interval = interval_val if interval_val is not None else self.driver_intervals.get(dn)
            if observed_interval is not None:
                clean_air: bool | None = observed_interval >= 1.8
            elif pos == 1:
                clean_air = True
            else:
                clean_air = None

            # Strictly causal prediction BEFORE observing current lap
            pred = self.pace_estimator.predict_baseline(
                session_id=session_id,
                driver_number=dn,
                target_lap=lap_num,
                compound=compound,
                stint_id=stint_id,
            )
            if pred.baseline_sec is not None:
                self.driver_baselines[dn] = pred.baseline_sec

            pace_delta: float | None = None
            z_score: float | None = None
            is_slow_outlier = False
            if pred.baseline_sec is not None:
                pace_delta = round(lap_seconds - pred.baseline_sec, 3)
                unc = max(pred.uncertainty_sec or 0.45, 0.25)
                z_score = round(pace_delta / unc, 2)
                is_slow_outlier = pace_delta > max(0.35, 1.5 * unc)

            deg_est = self.deg_model.estimate_degradation(session_id, dn, compound=compound if compound != "UNKNOWN" else None)

            if clean_air is False and (pace_delta is None or pace_delta > 0.20):
                classification = "DIRTY_AIR_IMPEDED"
                reason = "TRAFFIC_CONGESTION_PACE_LOSS"
                interpretation = Interpretation.INFERRED
            elif is_slow_outlier and not self.vsc_active and (
                (tyre_age or 0) >= 10 or (deg_est.slope_sec_per_lap > 0.03 and deg_est.calibration_status != "PRIOR_UNMEASURED")
            ):
                classification = "TYRE_THERMAL_DEGRADATION"
                reason = "EXCEEDED_THERMAL_DEG_WINDOW"
                interpretation = Interpretation.DERIVED
            elif is_slow_outlier and not self.vsc_active:
                classification = "PACE_OUTLIER_SLOW"
                reason = "STATISTICAL_PACE_DEVIATION"
                interpretation = Interpretation.DERIVED
            elif pred.status == "INITIALIZING":
                classification = "BASELINE_INITIALIZING"
                reason = "INSUFFICIENT_CLEAN_HISTORY"
                interpretation = Interpretation.OBSERVED
            else:
                classification = "NOMINAL_PACING"
                reason = "NOMINAL_AERO_STABILITY"
                interpretation = Interpretation.OBSERVED

            is_pit = bool(payload.get("in_pit") or payload.get("pit_in_time") or payload.get("pit_out_time"))
            self.pace_estimator.observe_lap(
                session_id=session_id,
                driver_number=dn,
                lap_number=lap_num,
                lap_sec=lap_seconds,
                stint_id=stint_id,
                compound=compound,
                clean_air=(clean_air is not False) and (not is_pit),
                neutralised=self.vsc_active,
                total_laps=total_laps,
                prior_prediction=pred,
            )
            self.deg_model.observe_lap(
                session_id=session_id,
                driver_number=dn,
                lap_number=lap_num,
                lap_sec=lap_seconds,
                compound=compound,
                tyre_age=tyre_age,
                stint_id=stint_id,
                neutralised=self.vsc_active,
                pit_lap=is_pit,
                total_laps=total_laps,
            )

            prev_class = self._driver_last_classification.get(dn)
            evt_cnt = self._driver_event_count.get(dn, 0) + 1
            self._driver_event_count[dn] = evt_cnt

            if classification != prev_class or evt_cnt == 1 or evt_cnt % 15 == 0:
                self._driver_last_classification[dn] = classification
                finding = Finding(
                    finding_id=f"f-vr-{uuid4().hex[:8]}",
                    agent_id=self.agent_id,
                    finding_type="PACE_DEVIATION",
                    session_id=session_id,
                    run_id=run_id,
                    subject=Subject(driver_number=dn),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    model_version=self.model_version,
                    assessment_status=FindingStatus.CONFIRMED if pred.baseline_sec is not None else FindingStatus.PROVISIONAL,
                    interpretation=interpretation,
                    uncertainty={
                        "baseline_status": pred.status,
                        "ci95_low_sec": pred.ci95_low_sec,
                        "ci95_high_sec": pred.ci95_high_sec,
                        "uncertainty_sec": pred.uncertainty_sec,
                        "sample_count": pred.sample_count,
                    },
                    result={
                        "driver_number": dn,
                        "lap_number": lap_num,
                        "lap_time_sec": round(lap_seconds, 3),
                        "baseline_sec": pred.baseline_sec,
                        "baseline_ci95_low_sec": pred.ci95_low_sec,
                        "baseline_ci95_high_sec": pred.ci95_high_sec,
                        "baseline_uncertainty_sec": pred.uncertainty_sec,
                        "baseline_status": pred.status,
                        "baseline_sample_count": pred.sample_count,
                        "fuel_burn_sec_per_lap": pred.fuel_burn_sec_per_lap,
                        "pace_delta_sec": pace_delta,
                        "pace_z_score": z_score,
                        "classification": classification,
                        "clean_air": clean_air,
                        "interval_to_ahead_sec": observed_interval,
                        "stint_laps_observed": self.driver_stint_laps.get(dn),
                        "neutralisation_active": self.vsc_active,
                        "source_provenance": event.source.provider,
                    },
                    reason_codes=[reason],
                    evidence_refs=[event.event_id],
                )
                await self.emit_finding(finding)
                self.record_outcome("FINDING_EMITTED", (time.perf_counter_ns() - t0) / 1_000_000.0)
            else:
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)

        except Exception as e:
            logger.error("VehicleResponseAgent error: %s", e, exc_info=True)
            self.record_outcome("FAILED", (time.perf_counter_ns() - t0) / 1_000_000.0)
