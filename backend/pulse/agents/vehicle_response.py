from __future__ import annotations

import logging
import time
from typing import Any

from pulse.agents.base import BaseAgent
from pulse.contracts import Completeness, EventEnvelope, Finding, FindingStatus, Interpretation, Subject
from pulse.topics import AGENT_TOPICS

logger = logging.getLogger("pulse.agent.vehicle_response")


class VehicleResponseAgent(BaseAgent):
    """Agent 3: Vehicle-Response Intelligence.
    
    Establishes driver performance baselines, evaluates contextual speed and sector pace
    deviations, detects dirty air traffic congestion and anomalies, and handles insufficient telemetry.
    """

    def __init__(self, bus: Any = None) -> None:
        super().__init__(
            agent_id="agent-03-vehicle-response",
            name="Vehicle-Response Intelligence",
            output_topic=AGENT_TOPICS["vehicle_response"],
            bus=bus,
            model_version="1.0.0",
        )
        # Dynamic baseline and state storage per driver_number
        self.driver_baselines: dict[int, float] = {
            16: 75.80,  # Leclerc baseline seconds (e.g. 1:15.80)
            4: 76.00,   # Norris
            1: 76.10,   # Verstappen
            44: 75.82,  # Hamilton
            81: 76.35,  # Piastri
        }
        self.driver_intervals: dict[int, float] = {}
        self.driver_stint_laps: dict[int, int] = {}
        self.vsc_active = False
        self._driver_last_classification: dict[int, str] = {}
        self._driver_event_count: dict[int, int] = {}

    def reset(self) -> None:
        """Reset agent domain state and metrics for a fresh run."""
        super().reset()
        self.driver_intervals.clear()
        self.driver_stint_laps.clear()
        self.vsc_active = False
        self._driver_last_classification.clear()
        self._driver_event_count.clear()

    async def on_event(self, topic: str, key: str, event: Any) -> None:
        t0 = time.perf_counter()
        if isinstance(event, dict):
            event = EventEnvelope.model_validate(event)

        self.record_input(event.event_id, eligible=True, run_id=event.run.run_id)

        try:
            event_type = event.event_type.upper()
            payload = event.payload or {}
            dn = event.subject.driver_number
            provenance = {
                "provider": event.source.provider,
                "adapter": event.source.adapter,
                "source_record_id": event.source.source_record_id,
                "capture_id": event.source.capture_id,
                "data_mode": event.run.mode if isinstance(event.run.mode, str) else event.run.mode.value,
            }

            # Handle race control context updates
            if event_type == "VSC_DEPLOYED":
                self.vsc_active = True
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("NO_FINDING", latency_ms=latency)
                return
            elif event_type in {"VSC_ENDED", "SESSION_STARTED"}:
                self.vsc_active = False
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("NO_FINDING", latency_ms=latency)
                return

            # Check for data completeness
            if event.quality.completeness in {Completeness.MISSING, Completeness.UNAVAILABLE}:
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("INSUFFICIENT_DATA", latency_ms=latency)
                return

            # Track intervals
            if dn and "interval" in payload:
                try:
                    val_str = str(payload["interval"]).replace("+", "").replace("s", "").strip()
                    if val_str and val_str != "—":
                        self.driver_intervals[dn] = float(val_str)
                except ValueError:
                    pass

            # Handle Lap Completion, Position update, or Driver Telemetry with timing data
            if event_type in {"LAP_COMPLETED", "POSITION_UPDATE", "DRIVER_TELEMETRY", "CAR_TELEMETRY", "CAR_TELEMETRY_SAMPLE"}:
                if not dn:
                    latency = (time.perf_counter() - t0) * 1000.0
                    self.record_outcome("NO_FINDING", latency_ms=latency)
                    return

                # Stint age tracking
                stint_age = payload.get("tyre_age", self.driver_stint_laps.get(dn, 20))
                self.driver_stint_laps[dn] = stint_age

                # Lap time extraction
                lap_seconds = payload.get("lap_time_seconds")
                if not lap_seconds and "last_lap_seconds" in payload:
                    lap_seconds = float(payload["last_lap_seconds"])

                # If no lap time in this packet and no telemetry anomaly, check for pace delta
                pace_delta = payload.get("pace_delta_sec")
                if pace_delta is None and lap_seconds:
                    baseline = self.driver_baselines.get(dn, 76.0)
                    pace_delta = round(lap_seconds - baseline, 3)

                # If still no timing data available in sample, mark insufficient data
                if pace_delta is None and "speed_kmh" not in payload and "speed" not in payload and "pace_loss_sec" not in payload:
                    latency = (time.perf_counter() - t0) * 1000.0
                    self.record_outcome("INSUFFICIENT_DATA", latency_ms=latency)
                    return

                # Evaluate contextual factors: traffic vs degradation vs neutralisation
                pos = payload.get("position", 1)
                interval = self.driver_intervals.get(dn, payload.get("interval_seconds", 1.2 if 2 <= pos <= 12 else 3.0))
                in_traffic = (interval < 1.8 or (2 <= pos <= 10)) and not self.vsc_active
                effective_pace_delta = pace_delta if pace_delta is not None else (0.42 if in_traffic else float(payload.get("pace_loss_sec", 0.15)))

                # Determine reason code and classification without alleging mechanical failure
                if self.vsc_active:
                    reason = "VSC_DELTA_REGULATION_COMPLIANCE"
                    classification = "NEUTRALISATION_DELTA"
                elif in_traffic and effective_pace_delta > 0.2:
                    reason = "TRAFFIC_CONGESTION_PACE_LOSS"
                    classification = "DIRTY_AIR_IMPEDED"
                elif stint_age > 15 and effective_pace_delta > 0.3:
                    reason = "TYRE_DEGRADATION_PACE_LOSS"
                    classification = "TYRE_THERMAL_DEGRADATION"
                else:
                    reason = "PACE_MONITORING_NOMINAL"
                    classification = "NOMINAL_PACING"

                # Filter out purely nominal pacing so finding streams reflect genuine anomalies/events
                if classification == "NOMINAL_PACING":
                    latency = (time.perf_counter() - t0) * 1000.0
                    self.record_outcome("NO_FINDING", latency_ms=latency)
                    return

                last_cls = self._driver_last_classification.get(dn)
                count = self._driver_event_count.get(dn, 0) + 1
                self._driver_event_count[dn] = count
                if last_cls == classification and event_type != "LAP_COMPLETED" and (count % 25 != 0):
                    latency = (time.perf_counter() - t0) * 1000.0
                    self.record_outcome("NO_FINDING", latency_ms=latency)
                    return
                self._driver_last_classification[dn] = classification

                interpretation_val = (
                    Interpretation.INFERRED
                    if classification == "DIRTY_AIR_IMPEDED"
                    else Interpretation.DERIVED
                )

                finding = Finding(
                    finding_id=f"finding-veh-{event.event_id}-{dn}",
                    agent_id=self.agent_id,
                    finding_type="PACE_DEVIATION",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(driver_number=dn),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=interpretation_val,
                    result={
                        "driver_number": dn,
                        "pace_delta_sec": effective_pace_delta,
                        "classification": classification,
                        "clean_air": not in_traffic,
                        "interval_to_ahead_sec": interval,
                        "stint_laps_observed": stint_age,
                        "neutralisation_active": self.vsc_active,
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.PROVISIONAL,
                    reason_codes=[reason],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("NO_FINDING", latency_ms=latency)

        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("FAILED", latency_ms=latency)
            logger.error("VehicleResponseAgent error: %s", e, exc_info=True)
            raise
