from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from pulse.contracts import (
    Assessment,
    Completeness,
    DriverState,
    EventEnvelope,
    Finding,
    FindingStatus,
    PipelineHealth,
    RunMode,
    RunRecord,
    RunStatus,
    utc_now,
)
from pulse.stream.projections import RaceStateProjector

logger = logging.getLogger("pulse.state.store")


class StateStore:
    """In-memory operational and analytical state store.
    
    Synchronizes stream projections, agent findings, fused assessments,
    and simulator runner status for low-latency queries and SSE streams.
    """

    def __init__(self, projector: RaceStateProjector | None = None) -> None:
        self.projector = projector or RaceStateProjector()
        self.latest_assessments: dict[int, Assessment] = {}
        self.assessment_history: list[Assessment] = []
        self.findings: list[Finding] = []
        self.processed_events_count: int = 0
        self.duplicate_events_count: int = 0
        self.last_event_time: datetime | None = None
        self._listeners: list[asyncio.Queue[dict[str, Any]]] = []
        self._lock = asyncio.Lock()
        self.agents: dict[str, Any] = {}

        # Default strategy models (updated dynamically as findings arrive)
        self.default_strategies = [
            {
                "label": "Box this lap",
                "action": "Switch to Hard compound",
                "score": 88,
                "delta": "+10.5s VSC saving",
                "tone": "positive",
                "note": "Capitalises on neutralisation pit loss compression before green flag resumption.",
            },
            {
                "label": "Hold 1 lap",
                "action": "Maintain track position",
                "score": 58,
                "delta": "+0.4s projected",
                "tone": "neutral",
                "note": "High risk of VSC concluding before next lap pit entry window.",
            },
            {
                "label": "Stay out",
                "action": "One-stop deep stint",
                "score": 32,
                "delta": "−1.3s projected",
                "tone": "negative",
                "note": "Severe undercut risk if P2 Norris or P3 Verstappen take discounted stop.",
            },
        ]

    def register_agent(self, agent: Any) -> None:
        """Registers a specialist agent to track durable execution metrics."""
        self.agents[agent.agent_id] = agent

    def get_agent_metrics(self) -> dict[str, Any]:
        """Returns execution transparency metrics across all registered agents."""
        return {
            aid: a.get_metrics().model_dump(mode="json")
            for aid, a in self.agents.items()
            if hasattr(a, "get_metrics")
        }

    def record_canonical_event(self, envelope: EventEnvelope) -> None:
        """Applies canonical event to projector and updates telemetry stats."""
        self.processed_events_count += 1
        self.last_event_time = envelope.time.event_time_utc
        self.projector.apply_event(envelope)
        self._notify_listeners("event", envelope.model_dump(mode="json"))

    def record_finding(self, finding: Finding) -> None:
        """Stores a specialist agent finding."""
        if not any(f.finding_id == finding.finding_id for f in self.findings):
            self.findings.append(finding)
        # Update strategy cards if pit opportunity finding
        if finding.finding_type == "PIT_WINDOW_OPPORTUNITY" and "scenarios" in finding.result:
            self.default_strategies = finding.result["scenarios"]
        self._notify_listeners("finding", finding.model_dump(mode="json"))

    def record_assessment(self, assessment: Assessment) -> None:
        """Stores fused driver consequence assessment."""
        dn = assessment.subject.driver_number
        if dn:
            self.latest_assessments[dn] = assessment
        if not any(a.assessment_id == assessment.assessment_id for a in self.assessment_history):
            self.assessment_history.append(assessment)
        self._notify_listeners("assessment", assessment.model_dump(mode="json"))

    def add_listener(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._listeners.append(queue)
        return queue

    def remove_listener(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._listeners:
            self._listeners.remove(queue)

    def _notify_listeners(self, event_type: str, data: Any) -> None:
        message = {"type": event_type, "data": data, "timestamp": utc_now().isoformat()}
        for queue in list(self._listeners):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.debug("Listener queue full, dropping message")
            except Exception:
                pass

    # --- Query Methods ---

    def get_session(self) -> dict[str, Any]:
        return {
            "mode": self.projector.data_mode,
            "sessionName": self.projector.session_name,
            "sessionType": self.projector.session_type,
            "lap": self.projector.current_lap,
            "totalLaps": self.projector.total_laps,
            "status": "Neutralised" if self.projector.active_lifecycle == "ACTIVE" else "Green Flag",
            "elapsed": self.projector.elapsed_time,
            "activeEvent": self.projector.active_event_display,
            "sourceLabel": f"PULSE {self.projector.data_mode.lower()} pipeline · Monaco GP",
            "lastUpdated": "live",
            "lastEventTime": self.last_event_time.isoformat() if self.last_event_time else None,
        }

    def get_drivers(self) -> list[dict[str, Any]]:
        return self.projector.get_ordered_drivers()

    def get_timeline(self) -> list[dict[str, Any]]:
        return self.projector.timeline

    def get_assessments(self, driver_number: int | None = None) -> list[dict[str, Any]]:
        assessments_to_format = (
            [self.latest_assessments[driver_number]]
            if (driver_number and driver_number in self.latest_assessments)
            else list(self.latest_assessments.values())
        )

        formatted = []
        for a in assessments_to_format:
            dn = a.subject.driver_number or 0
            narrative = a.impact.summary
            if a.impact.inferred_effects:
                narrative = a.impact.inferred_effects[0]

            # Tone determination
            tone = "positive" if dn == 16 else ("negative" if dn == 44 else "neutral")

            formatted.append({
                "id": a.assessment_id,
                "version": a.assessment_version,
                "driverNumber": dn,
                "title": a.impact.summary,
                "narrative": narrative,
                "driverRadio": None,
                "impact": tone,
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                "confidence": a.uncertainty.get("confidence_score"),
                "calibrationStatus": a.uncertainty.get("calibration_status", "UNCALIBRATED"),
                "forecast": (
                    f"Position retention projected: P{a.impact.forecast.position_delta_range[0]}–P{a.impact.forecast.position_delta_range[1]}"
                    if a.impact.forecast and a.impact.forecast.position_delta_range
                    else "P1 retention highly probable across pit cycle"
                ),
                "alternative": a.impact.alternatives[0] if a.impact.alternatives else "Stay out and risk track position",
                "evidence": a.evidence_refs,
                "supersedesId": a.supersedes_assessment_id,
                "changedAt": "recently",
            })

        # Sort so Leclerc (#16) and Hamilton (#44) appear prominently
        formatted.sort(key=lambda x: (0 if x["driverNumber"] == 16 else (1 if x["driverNumber"] == 44 else 2)))
        return formatted

    def get_strategy(self) -> list[dict[str, Any]]:
        return self.default_strategies

    def get_track(self) -> list[dict[str, Any]]:
        return self.projector.sectors

    def get_health(self) -> dict[str, Any]:
        from pulse.config import get_settings
        from pulse.stream.kafka_client import get_kafka_broker
        settings = get_settings()
        broker = get_kafka_broker()
        mode = settings.transport_mode.upper()
        active_transport = "KAFKA" if (mode == "KAFKA" and broker.is_connected) else mode
        return {
            "status": "HEALTHY",
            "transport_mode": mode,
            "kafka_connected": broker.is_connected,
            "transport": active_transport,
            "processed_events": self.processed_events_count,
            "duplicate_events": self.duplicate_events_count,
            "last_event_time_utc": self.last_event_time.isoformat() if self.last_event_time else None,
            "active_agents": [
                "agent-01-event-control",
                "agent-02-track-state",
                "agent-03-vehicle-response",
                "agent-04-tyre-strategy",
                "agent-05-fusion",
            ],
        }

    def get_snapshot(self) -> dict[str, Any]:
        """Provides full consumer-facing snapshot matching PulseSnapshot interface."""
        sess = self.get_session()
        return {
            "mode": sess["mode"],
            "sessionName": sess["sessionName"],
            "sessionType": sess["sessionType"],
            "lap": sess["lap"],
            "totalLaps": sess["totalLaps"],
            "status": sess["status"],
            "elapsed": sess["elapsed"],
            "activeEvent": sess["activeEvent"],
            "sourceLabel": sess["sourceLabel"],
            "lastUpdated": sess["lastUpdated"],
            "drivers": self.get_drivers(),
            "timeline": self.get_timeline(),
            "assessments": self.get_assessments(),
            "strategies": self.get_strategy(),
            "sectors": self.get_track(),
        }


_store: StateStore | None = None


def get_state_store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore()
    return _store
