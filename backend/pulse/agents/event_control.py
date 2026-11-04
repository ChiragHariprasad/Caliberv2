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

            elif event_type in {"SAFETY_CAR_DEPLOYED", "SAFETY_CAR_ENDING", "SAFETY_CAR_ENDED", "SAFETY_CAR_IN_THIS_LAP", "RED_FLAG", "YELLOW_FLAG"}:
                status_lifecycle = "ACTIVE" if ("DEPLOYED" in event_type or "FLAG" in event_type) else ("ENDING" if ("ENDING" in event_type or "IN_THIS_LAP" in event_type) else "ENDED")
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

            elif event_type in {"GREEN_FLAG_RESUMED", "GREEN_FLAG", "TRACK_STATUS_GREEN"}:
                self.active_lifecycle = "ACTIVE"
                self.active_event_type = "GREEN_FLAG"
                finding_green = Finding(
                    finding_id=f"finding-green-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="RACE_EVENT_LIFECYCLE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id=event.subject.segment_id or "track"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={"event_type": "GREEN_FLAG", "lifecycle": "ACTIVE", "source_provenance": provenance},
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["RCM_GREEN_FLAG_RESUMED"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_green)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type in {"DRIVER_RETIRED", "RETIREMENT"}:
                dn = event.subject.driver_number
                finding_ret = Finding(
                    finding_id=f"finding-ret-{event.event_id}-{dn or 'unk'}",
                    agent_id=self.agent_id,
                    finding_type="DRIVER_RETIREMENT",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(driver_number=dn),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={
                        "driver_number": dn,
                        "status": "RETIRED",
                        "reason": event.payload.get("detail", event.payload.get("reason", "Mechanical failure")),
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["FIA_DRIVER_RETIREMENT_CONFIRMED"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_ret)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type in {"STEWARD_DECISION", "STEWARDS_DECISION", "PENALTY"}:
                dn = event.subject.driver_number
                finding_stew = Finding(
                    finding_id=f"finding-stew-{event.event_id}-{dn or 'unk'}",
                    agent_id=self.agent_id,
                    finding_type="STEWARD_ACTION",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(driver_number=dn),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={
                        "driver_number": dn,
                        "decision": event.payload.get("title", "Steward Action"),
                        "detail": event.payload.get("detail", ""),
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["FIA_STEWARDS_DECISION_APPLIED"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_stew)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type in {"SESSION_CHEQUERED", "CHEQUERED_FLAG"}:
                self.active_lifecycle = "CONCLUDED"
                finding_chq = Finding(
                    finding_id=f"finding-chq-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type="RACE_EVENT_LIFECYCLE",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(segment_id="track"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result={"event_type": "CHEQUERED_FLAG", "lifecycle": "CONCLUDED", "source_provenance": provenance},
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=["SESSION_CHEQUERED_FLAG"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_chq)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                self.outcomes_count["FINDING_EMITTED"] += 1

            elif event_type in {"RACE_CONTROL_MESSAGE", "RACE_CONTROL_NOTICE"}:
                cat = (event.payload.get("category") or "").upper()
                flag = (event.payload.get("flag") or "").upper()
                title = (event.payload.get("title") or "").upper()
                dn = event.subject.driver_number
                finding_type = "RACE_EVENT_LIFECYCLE"
                reason_code = "RCM_NOTICE"
                res_payload: dict[str, Any] = {"category": cat, "flag": flag, "title": event.payload.get("title", ""), "source_provenance": provenance}

                if "CHEQUERED" in title:
                    finding_type = "RACE_EVENT_LIFECYCLE"
                    reason_code = "SESSION_CHEQUERED_FLAG"
                    self.active_lifecycle = "CONCLUDED"
                    res_payload.update({"event_type": "CHEQUERED_FLAG", "lifecycle": "CONCLUDED"})
                elif cat == "RETIREMENT" or "RETIRED" in title:
                    finding_type = "DRIVER_RETIREMENT"
                    reason_code = "FIA_DRIVER_RETIREMENT_CONFIRMED"
                    res_payload.update({"driver_number": dn, "status": "RETIRED", "detail": event.payload.get("detail", "")})
                elif cat == "STEWARDS" or "STEWARDS DECISION" in title or "PENALTY" in title:
                    finding_type = "STEWARD_ACTION"
                    reason_code = "FIA_STEWARDS_DECISION_APPLIED"
                    res_payload.update({"driver_number": dn, "detail": event.payload.get("detail", "")})
                elif cat == "INCIDENT" or "STOPPED" in title:
                    finding_type = "INCIDENT_TRACK_HAZARD"
                    reason_code = "RCM_INCIDENT_REPORTED"
                    res_payload.update({"driver_number": dn, "location": event.payload.get("title", "")})
                elif "SAFETY_CAR" in cat or flag == "YELLOW":
                    finding_type = "RACE_EVENT_LIFECYCLE"
                    reason_code = "RCM_NEUTRALISATION"
                    res_payload.update({"event_type": "SAFETY_CAR", "lifecycle": "ACTIVE"})

                finding_rcm = Finding(
                    finding_id=f"finding-rcm-{event.event_id}",
                    agent_id=self.agent_id,
                    finding_type=finding_type,
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(driver_number=dn, segment_id=event.subject.segment_id or "track"),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.OBSERVED,
                    result=res_payload,
                    evidence_refs=[event.event_id],
                    assessment_status=FindingStatus.CONFIRMED,
                    reason_codes=[reason_code],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_rcm)
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
