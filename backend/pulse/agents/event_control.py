from __future__ import annotations

import logging
import time
from typing import Any

from pulse.agents.base import BaseAgent
from pulse.contracts import EventEnvelope, Finding, FindingStatus, Interpretation, Subject, utc_now
from pulse.topics import AGENT_TOPICS

logger = logging.getLogger("pulse.agent.event_control")


class EventControlAgent(BaseAgent):
    """Agent 1: Race Event & Control Intelligence.
    
    Tracks race control event lifecycles (Safety Car, VSC, Yellow, Red, Green flag start)
    and evaluates driver spatial neutralisation exposure without hardcoded session assumptions.
    """

    def __init__(self, bus: Any = None) -> None:
        super().__init__(
            agent_id="agent-01-event-control",
            name="Race Event & Control Intelligence",
            output_topic=AGENT_TOPICS["event_context"],
            bus=bus,
            model_version="1.0.0",
        )
        self.active_lifecycle = "NONE"
        self.active_event_type: str | None = None
        self.active_session_id: str | None = None
        self.outcomes_count = {
            "FINDING_EMITTED": 0,
            "NO_FINDING": 0,
            "FILTERED": 0,
            "FAILED": 0,
        }

    async def on_event(self, topic: str, key: str, event: Any) -> None:
        t0 = time.perf_counter()
        if isinstance(event, dict):
            event = EventEnvelope.model_validate(event)

        self.record_input(event.event_id, eligible=True, run_id=event.run.run_id)
        self.active_session_id = event.session.session_id

        try:
            event_type = event.event_type.upper()
            provenance = {
                "provider": event.source.provider,
                "adapter": event.source.adapter,
                "source_record_id": event.source.source_record_id,
                "capture_id": event.source.capture_id,
                "data_mode": event.run.mode if isinstance(event.run.mode, str) else event.run.mode.value,
            }

            if event_type == "SESSION_STARTED":
                self.active_lifecycle = "ACTIVE"
                self.active_event_type = "GREEN_FLAG"
                finding_start = Finding(
                    finding_id=f"finding-start-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="RACE_EVENT_LIFECYCLE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=event.subject.segment_id or "track"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={
                        "event_type": "GREEN_FLAG",
                        "lifecycle": "ACTIVE",
                        "scope": "TRACK_WIDE",
                        "incident_location": "Start / Finish Line",
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["SESSION_GREEN_FLAG_START"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_start)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type == "VSC_DEPLOYED":
                self.active_lifecycle = "ACTIVE"
                self.active_event_type = "VSC"

                # 1. Canonical lifecycle finding
                segment_id = event.subject.segment_id or "track"
                incident_reason = event.payload.get("reason", "Incident neutralisation")
                finding_lc = Finding(
                    finding_id=f"finding-lc-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="RACE_EVENT_LIFECYCLE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=segment_id),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={
                        "event_type": "VSC",
                        "lifecycle": "ACTIVE",
                        "scope": "TRACK_WIDE",
                        "incident_location": incident_reason,
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["RCM_VSC_DEPLOYED"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_lc)

                # 2. Determine affected drivers dynamically
                affected_drivers: list[int] = []
                if event.subject.driver_number is not None:
                    affected_drivers.append(event.subject.driver_number)
                if "affected_drivers" in event.payload and isinstance(event.payload["affected_drivers"], list):
                    for d in event.payload["affected_drivers"]:
                        if d not in affected_drivers:
                            affected_drivers.append(d)

                for dn in affected_drivers:
                    driver_cfgs = event.payload.get("driver_exposures", {})
                    dn_cfg = driver_cfgs.get(str(dn), {})
                    exposure_level = dn_cfg.get("exposure_level", "CRITICAL_OPPORTUNITY" if dn == 16 else "HIGH_TRAFFIC_RISK")
                    pit_status = dn_cfg.get("pit_window_status", "OPEN" if dn == 16 else "EXPOSED")
                    finding_exp = Finding(
                        finding_id=f"finding-exp-{event.event_id}-{dn}",
                        agent_id=self.agent_id,
                        finding_type="DRIVER_EVENT_EXPOSURE",
                        session_id=event.session.session_id,
                        run_id=event.run.run_id,
                        subject=Subject(driver_number=dn),
                        trigger_event_id=event.event_id,
                        as_of_event_time=event.time.event_time_utc,
                        interpretation=Interpretation.DERIVED,
                        result={
                            "driver_number": dn,
                            "exposure_level": exposure_level,
                            "pit_window_status": pit_status,
                            "event_type": "VSC",
                            "source_provenance": provenance,
                        },
                        evidence_refs=[event.event_id],
                        assessment_status=FindingStatus.PROVISIONAL,
                        reason_codes=["VSC_EXPOSURE_CALCULATED"],
                        model_version=self.model_version,
                    )
                    await self.emit_finding(finding_exp)

                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type == "VSC_ENDING":
                self.active_lifecycle = "ENDING"
                finding_ending = Finding(
                    finding_id=f"finding-ending-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="RACE_EVENT_LIFECYCLE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=event.subject.segment_id or "track"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={"event_type": "VSC", "lifecycle": "ENDING", "source_provenance": provenance},
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["RCM_VSC_ENDING"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_ending)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type == "VSC_ENDED":
                self.active_lifecycle = "ENDED"
                finding_ended = Finding(
                    finding_id=f"finding-ended-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="RACE_EVENT_LIFECYCLE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=event.subject.segment_id or "track"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={"event_type": "VSC", "lifecycle": "ENDED", "source_provenance": provenance},
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["RCM_VSC_ENDED"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_ended)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type in {"SAFETY_CAR_DEPLOYED", "SAFETY_CAR_ENDING", "SAFETY_CAR_ENDED", "RED_FLAG", "YELLOW_FLAG"}:
                status_lifecycle = "ACTIVE" if "DEPLOYED" in event_type or "FLAG" in event_type else ("ENDING" if "ENDING" in event_type else "ENDED")
                self.active_lifecycle = status_lifecycle
                finding_sc = Finding(
                    finding_id=f"finding-{event_type.lower()}-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="RACE_EVENT_LIFECYCLE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=event.subject.segment_id or "track"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={"event_type": event_type, "lifecycle": status_lifecycle, "source_provenance": provenance},
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=[f"RCM_{event_type}"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_sc)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            else:
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("NO_FINDING", latency_ms=latency)
                self.outcomes_count["NO_FINDING"] += 1

        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("FAILED", latency_ms=latency)
            self.outcomes_count["FAILED"] += 1
            logger.error("EventControlAgent error processing event: %s", e, exc_info=True)
            raise
