from __future__ import annotations

import logging
import time
from typing import Any

from pulse.agents.base import BaseAgent
from pulse.contracts import EventEnvelope, Finding, FindingStatus, Interpretation, Subject
from pulse.topics import AGENT_TOPICS

logger = logging.getLogger("pulse.agent.track_state")


class TrackStateAgent(BaseAgent):
    """Agent 2: Track-State Intelligence.
    
    Evaluates micro-sector and sector track conditions, weather dynamics, and
    surface state transitions without inferring grip from vehicle lap times.
    """

    def __init__(self, bus: Any = None) -> None:
        super().__init__(
            agent_id="agent-02-track-state",
            name="Track-State Intelligence",
            output_topic=AGENT_TOPICS["track_state"],
            bus=bus,
            model_version="1.0.0",
        )
        self.sector_states: dict[str, dict[str, Any]] = {
            "sector-1": {"condition": "UNKNOWN", "status": "CLEAR", "water_film_mm": None},
            "sector-2": {"condition": "UNKNOWN", "status": "CLEAR", "water_film_mm": None},
            "sector-3": {"condition": "UNKNOWN", "status": "CLEAR", "water_film_mm": None},
        }
        self.current_weather: dict[str, Any] = {
            "air_temp_c": None,
            "track_temp_c": None,
            "humidity_pct": None,
            "rain_intensity_mm_h": None,
            "rain_risk_percent": None,
            "weather_observed": False,
        }
        self.last_transition: dict[str, Any] | None = None

    def reset(self) -> None:
        """Reset agent domain state and metrics for a fresh run."""
        super().reset()
        self.sector_states = {
            "sector-1": {"condition": "UNKNOWN", "status": "CLEAR", "water_film_mm": None},
            "sector-2": {"condition": "UNKNOWN", "status": "CLEAR", "water_film_mm": None},
            "sector-3": {"condition": "UNKNOWN", "status": "CLEAR", "water_film_mm": None},
        }
        self.current_weather = {
            "air_temp_c": None,
            "track_temp_c": None,
            "humidity_pct": None,
            "rain_intensity_mm_h": None,
            "rain_risk_percent": None,
            "weather_observed": False,
        }
        self.last_transition = None

    async def on_event(self, topic: str, key: str, event: Any) -> None:
        t0 = time.perf_counter()
        if isinstance(event, dict):
            event = EventEnvelope.model_validate(event)

        self.record_input(event.event_id, eligible=True, run_id=event.run.run_id)

        try:
            event_type = event.event_type.upper()
            payload = event.payload or {}
            provenance = {
                "provider": event.source.provider,
                "adapter": event.source.adapter,
                "source_record_id": event.source.source_record_id,
                "capture_id": event.source.capture_id,
                "data_mode": event.run.mode if isinstance(event.run.mode, str) else event.run.mode.value,
            }

            # 1. Weather observation handling
            if event_type == "WEATHER_OBSERVATION":
                if not payload or ("air_temp_c" not in payload and "track_temp_c" not in payload):
                    latency = (time.perf_counter() - t0) * 1000.0
                    self.record_outcome("INSUFFICIENT_DATA", latency_ms=latency)
                    return

                prev_rain_risk = self.current_weather.get("rain_risk_percent")
                new_rain_risk = float(payload["rain_risk_percent"]) if payload.get("rain_risk_percent") is not None else prev_rain_risk
                air_temp = float(payload["air_temp_c"]) if payload.get("air_temp_c") is not None else self.current_weather.get("air_temp_c")
                track_temp = float(payload["track_temp_c"]) if payload.get("track_temp_c") is not None else self.current_weather.get("track_temp_c")
                prev_track = self.current_weather.get("track_temp_c")

                transition_detected = bool(
                    (prev_rain_risk is not None and new_rain_risk is not None and abs(new_rain_risk - prev_rain_risk) > 15.0)
                    or (prev_track is not None and track_temp is not None and abs(track_temp - prev_track) > 2.0)
                )
                hum = float(payload["humidity_pct"]) if payload.get("humidity_pct") is not None else self.current_weather.get("humidity_pct")
                rain_mm = float(payload["rain_intensity_mm_h"]) if payload.get("rain_intensity_mm_h") is not None else self.current_weather.get("rain_intensity_mm_h")
                self.current_weather.update({
                    "air_temp_c": air_temp,
                    "track_temp_c": track_temp,
                    "humidity_pct": hum,
                    "rain_intensity_mm_h": rain_mm,
                    "rain_risk_percent": new_rain_risk,
                    "weather_observed": True,
                })

                finding_w = Finding(
                    finding_id=f"finding-weather-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="WEATHER_TRANSITION" if transition_detected else "WEATHER_STATE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id="circuit"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={
                        "weather": dict(self.current_weather),
                        "transition_detected": transition_detected,
                        "surface_water_risk": "ELEVATED" if (new_rain_risk or 0.0) > 50.0 else ("NOMINAL" if new_rain_risk is not None else "UNMEASURED"),
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["WEATHER_TELEMETRY_UPDATED" if not transition_detected else "WEATHER_TRANSITION_ALERT"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_w)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            # 2. Track status / sector condition updates
            if event_type in {"TRACK_STATUS_UPDATE", "SEGMENT_STATUS_UPDATE"}:
                sec_id = event.subject.segment_id or f"sector-{payload.get('sector_index', 2)}"
                new_status = payload.get("status", "CLEAR")
                new_condition = payload.get("condition", "UNKNOWN")
                cond_l = str(new_condition).lower()
                if any(tok in cond_l for tok in ("wet", "damp", "rain", "slick_wet", "inter")):
                    surface_state = "WET_OR_DAMP"
                elif any(tok in cond_l for tok in ("dry", "clear", "vsc", "green")):
                    surface_state = "DRY"
                else:
                    surface_state = "UNKNOWN"

                water_mm = float(payload["water_film_mm"]) if payload.get("water_film_mm") is not None else None
                self.sector_states[sec_id] = {
                    "condition": new_condition,
                    "status": new_status,
                    "water_film_mm": water_mm,
                }

                finding_trk = Finding(
                    finding_id=f"finding-track-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="TRACK_CONDITION_STATE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=sec_id),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={
                        "segment_id": sec_id,
                        "status": new_status,
                        "condition": new_condition,
                        "surface_state": surface_state,
                        "sector_states": dict(self.sector_states),
                        "weather_context": dict(self.current_weather),
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["TRACK_STATUS_OBSERVED"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_trk)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            # 3. Correlation with VSC / Session events
            if event_type in {"VSC_DEPLOYED", "VSC_ENDED", "SESSION_STARTED"}:
                is_vsc = (event_type == "VSC_DEPLOYED")
                sec_id = event.subject.segment_id or "sector-2"
                target_sector = sec_id if sec_id in self.sector_states else "sector-2"
                self.sector_states[target_sector]["status"] = "VSC_CONTROLLED" if is_vsc else "CLEAR"
                inferred_surface = (
                    "WET_OR_DAMP"
                    if (self.current_weather.get("rain_intensity_mm_h") or 0.0) > 0.0
                    else ("DRY" if self.current_weather.get("weather_observed") else "UNMEASURED")
                )

                finding = Finding(
                    finding_id=f"finding-track-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="TRACK_CONDITION_STATE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=sec_id),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={
                        "sector_2_state": "VSC_CONTROLLED" if is_vsc else "CLEAR",
                        "track_surface": inferred_surface,
                        "track_temp_c": self.current_weather["track_temp_c"],
                        "air_temp_c": self.current_weather["air_temp_c"],
                        "rain_risk_percent": self.current_weather["rain_risk_percent"],
                        "weather_observed": self.current_weather["weather_observed"],
                        "sector_states": dict(self.sector_states),
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["DRY_CIRCUIT_OBSERVED" if not is_vsc else "NEUTRALISATION_SECTOR_CONTROL"],
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
            logger.error("TrackStateAgent error processing event: %s", e, exc_info=True)
            raise
