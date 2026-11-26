from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from pulse.agents.base import BaseAgent
from pulse.analytics.pace_and_tyre import (
    FuelCompensatedDegradationModel,
    PitWindowStrategySimulator,
    RollingCleanAirPaceEstimator,
    normalize_compound,
)
from pulse.contracts import Completeness, EventEnvelope, Finding, FindingStatus, Interpretation, Subject
from pulse.topics import AGENT_TOPICS

logger = logging.getLogger("pulse.agents.tyre_strategy")


class TyreStrategyAgent(BaseAgent):
    """
    Agent 04: Tyre Degradation & Strategic Pit-Window Intelligence (Scientific v2).

    Replaces fabricated +0.12/+0.08/+0.04 slopes and hardcoded age-23 driver stints with:
    - Fuel-burn compensated causal stint regression + hierarchical empirical-Bayes pooling.
    - Live session pit-loss learning from observed pit-in / pit-out transitions.
    - Field-gap re-entry rank projection & explicit calibration/uncertainty metadata.
    """

    def __init__(self, bus: Any = None) -> None:
        super().__init__(
            agent_id="agent-04-tyre-strategy",
            name="Tyre Strategy & Degradation",
            output_topic=AGENT_TOPICS["tyre_strategy"],
            bus=bus,
            model_version="2.0.0",
        )
        self.deg_model = FuelCompensatedDegradationModel()
        self.pit_sim = PitWindowStrategySimulator()
        self.pace_tracker = RollingCleanAirPaceEstimator()
        # Dynamically populated observed driver stint summary (never pre-seeded)
        self.driver_stints: dict[int, dict[str, Any]] = {}
        self.session_total_laps: dict[str, int] = {}
        self.session_current_lap: dict[str, int] = {}
        self.active_neutralisation: str | None = None
        self._last_deg_emit_count: dict[tuple[str, int], int] = {}

    def reset(self) -> None:
        super().reset()
        self.deg_model.reset()
        self.pit_sim.reset()
        self.pace_tracker.reset()
        self.driver_stints.clear()
        self.session_total_laps.clear()
        self.session_current_lap.clear()
        self.active_neutralisation = None
        self._last_deg_emit_count.clear()

    def _parse_float(self, raw: Any) -> float | None:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        s = str(raw).strip().upper().replace("+", "").replace("S", "").strip()
        if not s or "LAP" in s or s in {"NONE", "NAN", "NULL", "--"}:
            return None
        try:
            return float(s)
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
            "VSC_ENDED",
            "SC_ENDED",
            "GREEN_FLAG",
            "GREEN_FLAG_RESUMED",
            "TRACK_STATUS_GREEN",
            "LAP_COMPLETED",
            "PIT_ENTRY",
            "PIT_EXIT",
            "PIT_STOP",
            "PIT_STOP_RECORDED",
            "TYRE_FITTED",
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

            if et in {"VSC_ENDED", "SC_ENDED", "GREEN_FLAG", "GREEN_FLAG_RESUMED", "TRACK_STATUS_GREEN"}:
                self.active_neutralisation = None
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            if et == "PIT_ENTRY" and dn is not None:
                lap_num = payload.get("lap") or payload.get("lap_number")
                self.deg_model.record_pit_event(
                    session_id,
                    dn,
                    is_exit=False,
                    lap_number=int(lap_num) if isinstance(lap_num, (int, float)) else None,
                )
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            if et in {"PIT_EXIT", "TYRE_FITTED"} and dn is not None:
                comp = normalize_compound(payload.get("compound") or payload.get("tyre_compound"))
                lap_num = payload.get("lap") or payload.get("lap_number")
                self.deg_model.record_pit_event(
                    session_id,
                    dn,
                    is_exit=True,
                    compound=comp,
                    lap_number=int(lap_num) if isinstance(lap_num, (int, float)) else None,
                )
                self.driver_stints[dn] = {
                    "compound": comp,
                    "stint_age": 0,
                    "position": payload.get("position"),
                }
                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            if et == "LAP_COMPLETED" and dn is not None:
                lap_num_raw = payload.get("lap") or payload.get("lap_number")
                lap_num = int(lap_num_raw) if isinstance(lap_num_raw, (int, float)) and int(lap_num_raw) > 0 else 1
                self.session_current_lap[session_id] = max(self.session_current_lap.get(session_id, 0), lap_num)

                tl = payload.get("total_laps")
                if isinstance(tl, (int, float)) and int(tl) >= 15:
                    self.session_total_laps[session_id] = int(tl)
                total_laps = self.session_total_laps.get(session_id)

                lap_sec = self._parse_lap_seconds(payload)
                comp = normalize_compound(payload.get("compound") or payload.get("tyre_compound"))
                tyre_age_raw = payload.get("tyre_age")
                tyre_age = int(tyre_age_raw) if isinstance(tyre_age_raw, (int, float)) else None
                stint_raw = payload.get("stint") or payload.get("stint_id")
                stint_id = int(stint_raw) if isinstance(stint_raw, (int, float)) else None
                pos_raw = payload.get("position")
                pos = int(pos_raw) if isinstance(pos_raw, (int, float)) and int(pos_raw) > 0 else None
                gap_leader = self._parse_float(payload.get("gap_to_leader") or payload.get("gap_sec"))
                interval_val = self._parse_float(payload.get("interval") or payload.get("interval_sec"))

                self.pit_sim.update_driver_state(
                    session_id,
                    dn,
                    position=pos,
                    gap_to_leader_sec=gap_leader,
                    interval_sec=interval_val,
                )

                is_pit_in = bool(payload.get("pit_in_time") or payload.get("pit_entry") or payload.get("in_pit_in"))
                is_pit_out = bool(payload.get("pit_out_time") or payload.get("pit_exit") or payload.get("in_pit_out"))
                is_pit = is_pit_in or is_pit_out or bool(payload.get("in_pit"))
                neut = self.active_neutralisation is not None

                pred = self.pace_tracker.predict_baseline(
                    session_id,
                    dn,
                    target_lap=lap_num,
                    compound=comp,
                    stint_id=stint_id,
                )
                if is_pit_in or is_pit_out:
                    self.pit_sim.record_pit_lap_observation(
                        session_id,
                        dn,
                        lap_num,
                        lap_sec,
                        pred.baseline_sec,
                        is_pit_in=is_pit_in,
                        is_pit_out=is_pit_out,
                        neutralised=neut,
                    )

                self.pace_tracker.observe_lap(
                    session_id,
                    dn,
                    lap_num,
                    lap_sec,
                    stint_id=stint_id,
                    compound=comp,
                    clean_air=(interval_val is None or interval_val >= 1.8) and (not is_pit),
                    neutralised=neut,
                    total_laps=total_laps,
                    prior_prediction=pred,
                )
                self.deg_model.observe_lap(
                    session_id,
                    dn,
                    lap_num,
                    lap_sec,
                    compound=comp,
                    tyre_age=tyre_age,
                    stint_id=stint_id,
                    neutralised=neut,
                    pit_lap=is_pit,
                    total_laps=total_laps,
                )

                active_stint = self.deg_model.get_active_stint(session_id, dn)
                self.driver_stints[dn] = {
                    **active_stint,
                    "position": pos,
                    "gap_to_leader_sec": gap_leader,
                    "interval_sec": interval_val,
                }

                n_obs = active_stint["sample_laps"]
                last_emitted_n = self._last_deg_emit_count.get((session_id, dn), 0)
                if n_obs >= 5 and (n_obs - last_emitted_n >= 5 or last_emitted_n == 0):
                    deg_est = self.deg_model.estimate_degradation(session_id, dn)
                    if deg_est.calibration_status == "DRIVER_STINT_CALIBRATED":
                        self._last_deg_emit_count[(session_id, dn)] = n_obs
                        finding = Finding(
                            finding_id=f"f-deg-{uuid4().hex[:8]}",
                            agent_id=self.agent_id,
                            finding_type="DEGRADATION_ANALYSIS",
                            session_id=session_id,
                            run_id=run_id,
                            subject=Subject(driver_number=dn),
                            trigger_event_id=event.event_id,
                            as_of_event_time=event.time.event_time_utc,
                            model_version=self.model_version,
                            assessment_status=FindingStatus.CONFIRMED,
                            interpretation=Interpretation.DERIVED,
                            uncertainty={
                                "slope_se_sec_per_lap": deg_est.slope_se_sec_per_lap,
                                "sample_laps": deg_est.n_driver_laps,
                                "n_session_stints": deg_est.n_session_stints,
                            },
                            result={
                                "driver_number": dn,
                                "compound": deg_est.compound,
                                "stint_age": active_stint["stint_age"],
                                "slope_sec_per_lap": deg_est.slope_sec_per_lap,
                                "raw_uncompensated_slope_sec_per_lap": deg_est.raw_uncompensated_slope_sec_per_lap,
                                "slope_se_sec_per_lap": deg_est.slope_se_sec_per_lap,
                                "sample_laps": deg_est.n_driver_laps,
                                "n_session_stints": deg_est.n_session_stints,
                                "fuel_burn_sec_per_lap": deg_est.fuel_burn_sec_per_lap,
                                "r_squared": deg_est.r_squared,
                                "calibration_status": deg_est.calibration_status,
                                "source_provenance": event.source.provider,
                            },
                            reason_codes=["FUEL_COMPENSATED_STINT_REGRESSION"],
                            evidence_refs=[event.event_id],
                        )
                        await self.emit_finding(finding)
                        self.record_outcome("FINDING_EMITTED", (time.perf_counter_ns() - t0) / 1_000_000.0)
                        return

                self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            if et in {"VSC_DEPLOYED", "SC_DEPLOYED", "SAFETY_CAR_DEPLOYED"}:
                mode = "VSC" if "VSC" in et else "SC"
                self.active_neutralisation = mode
                affected = [
                    int(d)
                    for d in (payload.get("affected_drivers") or [])
                    if isinstance(d, (int, float)) and 1 <= int(d) <= 99
                ]
                if dn is not None:
                    target_drivers: list[int | None] = [dn]
                elif affected:
                    target_drivers = affected[:6]
                elif self.driver_stints:
                    target_drivers = sorted(self.driver_stints.keys())[:4]
                else:
                    target_drivers = [None]

                total_laps = self.session_total_laps.get(session_id)
                cur_lap = self.session_current_lap.get(session_id)
                remaining_laps = (total_laps - cur_lap) if (total_laps is not None and cur_lap is not None and total_laps >= cur_lap) else None

                for target_dn in target_drivers:
                    if target_dn is not None:
                        stint_info = self.deg_model.get_active_stint(session_id, target_dn)
                        current_compound = stint_info["compound"]
                        stint_age = stint_info["stint_age"]
                        deg_est = self.deg_model.estimate_degradation(session_id, target_dn)
                        strat = self.pit_sim.evaluate_pit_window(
                            session_id,
                            target_dn,
                            mode,
                            current_compound=current_compound,
                            stint_age=stint_age,
                            deg_estimate=deg_est,
                            remaining_laps=remaining_laps,
                        )
                    else:
                        deg_est = self.deg_model.estimate_degradation(session_id, -1)
                        strat = self.pit_sim.evaluate_pit_window(
                            session_id,
                            -1,
                            mode,
                            current_compound="UNKNOWN",
                            stint_age=None,
                            deg_estimate=deg_est,
                            remaining_laps=remaining_laps,
                        )

                    is_calibrated = (
                        deg_est.calibration_status != "PRIOR_UNMEASURED"
                        or "EMPIRICAL_PIT_CALIBRATED" in strat["calibration_status"]
                    )
                    finding = Finding(
                        finding_id=f"f-strat-{uuid4().hex[:8]}",
                        agent_id=self.agent_id,
                        finding_type="PIT_WINDOW_OPPORTUNITY",
                        session_id=session_id,
                        run_id=run_id,
                        subject=Subject(driver_number=target_dn),
                        trigger_event_id=event.event_id,
                        as_of_event_time=event.time.event_time_utc,
                        model_version=self.model_version,
                        assessment_status=FindingStatus.CONFIRMED if is_calibrated else FindingStatus.PROVISIONAL,
                        interpretation=Interpretation.PREDICTED if is_calibrated else Interpretation.INFERRED,
                        uncertainty={
                            "uncertainty_sec": strat["uncertainty_sec"],
                            "calibration_status": strat["calibration_status"],
                            "slope_se_sec_per_lap": deg_est.slope_se_sec_per_lap,
                        },
                        result={
                            "driver_number": target_dn,
                            "neutralisation_mode": mode,
                            **strat,
                            "degradation_estimate": {
                                "compound": deg_est.compound,
                                "slope_sec_per_lap": deg_est.slope_sec_per_lap,
                                "raw_uncompensated_slope_sec_per_lap": deg_est.raw_uncompensated_slope_sec_per_lap,
                                "slope_se_sec_per_lap": deg_est.slope_se_sec_per_lap,
                                "sample_laps": deg_est.n_driver_laps,
                                "n_session_stints": deg_est.n_session_stints,
                                "fuel_burn_sec_per_lap": deg_est.fuel_burn_sec_per_lap,
                                "calibration_status": deg_est.calibration_status,
                            },
                            "assumptions": {
                                "calculation_version": self.model_version,
                                "pit_loss_calibration": strat["calibration_status"],
                                "degradation_calibration": deg_est.calibration_status,
                                "fuel_burn_sec_per_lap": deg_est.fuel_burn_sec_per_lap,
                                "uncertainty_basis": "EMPIRICAL_MAD_AND_SLOPE_SE" if is_calibrated else "UNMEASURED_F1_PRIOR",
                                "data_provenance": event.source.provider,
                            },
                        },
                        reason_codes=[
                            f"{mode}_PIT_LOSS_ARBITRAGE",
                            "EMPIRICALLY_CALIBRATED" if is_calibrated else "UNMEASURED_PRIOR_ADVISORY",
                        ],
                        evidence_refs=[event.event_id],
                    )
                    await self.emit_finding(finding)

                self.record_outcome("FINDING_EMITTED", (time.perf_counter_ns() - t0) / 1_000_000.0)
                return

            self.record_outcome("NO_FINDING", (time.perf_counter_ns() - t0) / 1_000_000.0)

        except Exception as e:
            logger.error("TyreStrategyAgent error: %s", e, exc_info=True)
            self.record_outcome("FAILED", (time.perf_counter_ns() - t0) / 1_000_000.0)
