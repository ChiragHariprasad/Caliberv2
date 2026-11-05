from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

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
from pulse.sessions.registry import get_session_by_id
from pulse.stream.projections import RaceStateProjector

logger = logging.getLogger("pulse.state.store")


class StateStore:
    """In-memory operational and analytical state store.
    
    Synchronizes stream projections, agent findings, fused assessments,
    and replay controller status for low-latency queries and continuous SSE streams.
    """

    def __init__(self, projector: RaceStateProjector | None = None) -> None:
        self.projector = projector or RaceStateProjector()
        self.current_session_id: str = "f1-2026-monaco-sim"
        self.current_run_id: str = f"run-init-{uuid4().hex[:8]}"
        self.latest_assessments: dict[int, Assessment] = {}
        self.assessment_history: list[Assessment] = []
        self.findings: list[Finding] = []
        self.processed_events_count: int = 0
        self.duplicate_events_count: int = 0
        self.last_event_time: datetime | None = None
        self._listeners: list[asyncio.Queue[dict[str, Any]]] = []
        self._history_events: list[dict[str, Any]] = []
        self.sse_sequence_counter: int = 0
        self._last_driver_sse_wall_time: float = 0.0
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

    def switch_session(self, session_id: str) -> None:
        """Configures state and driver grid for the chosen session."""
        self.current_session_id = session_id
        meta = get_session_by_id(session_id)

        for agent in self.agents.values():
            if hasattr(agent, "reset_metrics"):
                agent.reset_metrics()
            if hasattr(agent, "reset"):
                agent.reset()

        if not meta or meta.availability_status == "NO_SESSION_DATA":
            circuit = meta.circuit_id if meta else "suzuka"
            name = meta.grand_prix_name if meta else "Japanese Grand Prix"
            self.projector.circuit_id = circuit
            self.projector.session_name = name
            self.projector.session_type = "PREVIEW_ONLY"
            self.projector.current_lap = 0
            self.projector.total_laps = meta.total_laps if meta else 53
            self.projector.active_lifecycle = "NONE"
            self.projector.active_event = "NONE"
            self.projector.active_event_display = "NO_SESSION_DATA_AVAILABLE"
            self.projector.status = "NO_SESSION_DATA"
            self.projector.elapsed_time = "00:00:00"
            self.projector.drivers = {}
            self.projector.timeline = []
            self.projector.official_notices = []
            self.findings.clear()
            self.latest_assessments.clear()
            self.assessment_history.clear()
            logger.info("Session switched to NO_SESSION_DATA for [%s]", session_id)
            self.notify_session_state()
            self.notify_driver_state()
            return

        if meta.availability_status == "AVAILABLE_HISTORICAL":
            self.projector.circuit_id = meta.circuit_id
            self.projector.session_name = meta.grand_prix_name
            self.projector.session_type = meta.session_type
            self.projector.current_lap = 1
            self.projector.total_laps = meta.total_laps
            self.projector.active_lifecycle = "NONE"
            self.projector.active_event = "GREEN_FLAG"
            self.projector.active_event_display = "Green Flag"
            self.projector.status = "Green Flag"
            self.projector.elapsed_time = "00:00:00"
            self.projector.data_mode = "REPLAY"
            self.projector.timeline = []
            self.projector.official_notices = []
            self.findings.clear()
            self.latest_assessments.clear()
            self.assessment_history.clear()

            # Load entry list dynamically from capture directory
            capture_id = meta.capture_id or session_id
            entry_file = Path("captures") / capture_id / "entry_list.json"
            if not entry_file.exists():
                entry_file = Path("captures") / session_id / "entry_list.json"
            if not entry_file.exists():
                entry_file = Path("captures/f1-2023-silverstone-race/entry_list.json")
            if entry_file.exists():
                entries = json.loads(entry_file.read_text(encoding="utf-8"))
                self.projector.load_session_entry_list(entries)
            logger.info("Session switched to HISTORICAL [%s] (%d drivers)", session_id, len(self.projector.drivers))
            self.notify_session_state()
            self.notify_driver_state()
            return

        if meta.availability_status == "AVAILABLE_SIMULATION":
            self.projector.circuit_id = meta.circuit_id
            self.projector.session_name = meta.grand_prix_name
            self.projector.session_type = meta.session_type
            self.projector.current_lap = 24
            self.projector.total_laps = meta.total_laps
            self.projector.active_event_display = "Green Flag"
            self.projector.status = "Green Flag"
            self.projector.data_mode = "SIMULATED"
            self.projector.drivers = self.projector._init_full_grid()
            self.projector.official_notices = self.projector._init_official_notices()
            self.findings.clear()
            self.latest_assessments.clear()
            self.assessment_history.clear()
            logger.info("Session switched to SIMULATION [%s]", session_id)
            self.notify_session_state()
            self.notify_driver_state()

    def record_canonical_event(self, envelope: EventEnvelope) -> None:
        """Applies canonical event to projector, updates telemetry stats, and pushes SSE notifications."""
        self.processed_events_count += 1
        self.last_event_time = envelope.time.event_time_utc
        self.projector.apply_event(envelope)

        et = envelope.event_type.upper()
        p = envelope.payload

        # Emit backward-compatible event message
        self._notify_listeners("event", envelope.model_dump(mode="json"))

        now = time.monotonic()
        is_priority = et in {
            "LAP_COMPLETED", "DRIVER_RETIRED", "DRIVER_DNS",
            "VSC_DEPLOYED", "VSC_ENDED", "SAFETY_CAR_DEPLOYED",
            "SAFETY_CAR_ENDING", "STEWARD_DECISION", "SESSION_CHEQUERED",
            "PIT_ENTRY", "PIT_EXIT", "SESSION_STARTED"
        }

        # Pace driver & session broadcasts to ~0.5s cadence for smooth, non-bursty frontend rendering
        if is_priority or (now - self._last_driver_sse_wall_time >= 0.5):
            self._last_driver_sse_wall_time = now
            self.notify_session_state()
            self.notify_driver_state(envelope.subject.driver_number)

        if et in {"CAR_TELEMETRY", "CAR_TELEMETRY_SAMPLE"}:
            dn = envelope.subject.driver_number
            if dn:
                self.notify_telemetry(dn, self.projector.get_driver_telemetry(dn) or p)

        if et in {"WEATHER_OBSERVATION", "TRACK_STATUS_UPDATE", "TRACK_STATUS_GREEN"}:
            self.notify_track_state()

        if et in {
            "RACE_CONTROL_MESSAGE", "RACE_CONTROL_NOTICE", "VSC_DEPLOYED", "VSC_ENDED",
            "SAFETY_CAR_DEPLOYED", "SAFETY_CAR_ENDING", "STEWARD_DECISION", "SESSION_CHEQUERED",
        }:
            self.notify_race_control()

    def load_session_entry_list(self, entries: list[dict[str, Any]]) -> None:
        """Dynamically loads session entry list into the projector and notifies listeners."""
        self.projector.load_session_entry_list(entries)
        self._notify_listeners("entry_list", {"count": len(entries)})
        self.notify_driver_state()

    def record_finding(self, finding: Finding) -> None:
        """Stores a specialist agent finding and emits SSE updates."""
        if not any(f.finding_id == finding.finding_id for f in self.findings):
            self.findings.append(finding)
        if finding.finding_type == "PIT_WINDOW_OPPORTUNITY" and "scenarios" in finding.result:
            self.default_strategies = finding.result["scenarios"]

        self._notify_listeners("finding", finding.model_dump(mode="json"))
        self._notify_listeners("AGENT_FINDING_UPDATED", finding.model_dump(mode="json"))
        self._notify_listeners("AGENT_STATUS_UPDATED", self.get_agent_metrics())

    def record_assessment(self, assessment: Assessment) -> None:
        """Stores fused driver consequence assessment and emits SSE update."""
        dn = assessment.subject.driver_number
        if dn:
            self.latest_assessments[dn] = assessment
        if not any(a.assessment_id == assessment.assessment_id for a in self.assessment_history):
            self.assessment_history.append(assessment)

        self._notify_listeners("assessment", assessment.model_dump(mode="json"))
        self._notify_listeners("IMPACT_ASSESSMENT_UPDATED", assessment.model_dump(mode="json"))

    # --- Typed Domain Notification Helpers for SSE ---

    def notify_session_state(self) -> None:
        self._notify_listeners("SESSION_STATE_UPDATED", self.get_session())

    def notify_driver_state(self, driver_number: int | None = None) -> None:
        payload = {"drivers": self.get_drivers()}
        if driver_number is not None:
            payload["updatedDriverNumber"] = driver_number
        self._notify_listeners("DRIVER_STATE_UPDATED", payload)

    def notify_telemetry(self, driver_number: int, telemetry: dict[str, Any]) -> None:
        self._notify_listeners("TELEMETRY_UPDATED", {
            "driverNumber": driver_number,
            "telemetry": telemetry,
        })

    def notify_track_state(self) -> None:
        self._notify_listeners("TRACK_STATE_UPDATED", {
            "sectors": self.get_track(),
        })

    def notify_race_control(self) -> None:
        self._notify_listeners("RACE_CONTROL_UPDATED", {
            "notices": self.get_official_notices(),
            "timeline": self.get_timeline(),
        })

    def notify_replay_status(self, status_payload: dict[str, Any]) -> None:
        self._notify_listeners("REPLAY_STATUS_UPDATED", status_payload)

    def notify_pipeline_metrics(self, metrics_payload: dict[str, Any]) -> None:
        self._notify_listeners("PIPELINE_METRICS_UPDATED", metrics_payload)

    # --- SSE Subscription & Event Delivery ---

    def add_listener(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)
        self._listeners.append(queue)
        return queue

    def remove_listener(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._listeners:
            self._listeners.remove(queue)

    def get_history_after_id(self, last_event_id: str) -> list[dict[str, Any]]:
        """Returns buffered events following last_event_id for reconnect resumption."""
        try:
            target_seq = int(last_event_id.replace("sse-evt-", ""))
            return [e for e in self._history_events if e.get("seq", 0) > target_seq]
        except Exception:
            return []

    def _notify_listeners(self, event_type: str, data: Any) -> None:
        self.sse_sequence_counter += 1
        now_str = utc_now().isoformat()

        envelope = {
            "id": f"sse-evt-{self.sse_sequence_counter}",
            "seq": self.sse_sequence_counter,
            "session_id": self.current_session_id,
            "run_id": self.current_run_id,
            "data_mode": self.projector.data_mode,
            "event_time_utc": (self.last_event_time.isoformat() if self.last_event_time else now_str),
            "ingest_time_utc": now_str,
            "type": event_type,
            "update_type": event_type,
            "data": data,
        }

        # Keep rolling buffer of last 500 events
        self._history_events.append(envelope)
        if len(self._history_events) > 500:
            self._history_events.pop(0)

        for queue in list(self._listeners):
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(envelope)
                except Exception:
                    pass
            except Exception:
                pass

    # --- Query Methods ---

    def get_session(self) -> dict[str, Any]:
        return {
            "mode": self.projector.data_mode,
            "pipelineStatus": self.projector.pipeline_status,
            "circuitId": self.projector.circuit_id,
            "sessionName": self.projector.session_name,
            "sessionType": self.projector.session_type,
            "sessionId": self.current_session_id,
            "lap": self.projector.current_lap,
            "totalLaps": self.projector.total_laps,
            "status": "NO_SESSION_DATA" if getattr(self.projector, "status", None) == "NO_SESSION_DATA" else ("Neutralised" if self.projector.active_lifecycle == "ACTIVE" else getattr(self.projector, "status", "Green Flag")),
            "elapsed": self.projector.elapsed_time,
            "activeEvent": self.projector.active_event_display,
            "sourceLabel": f"PULSE {self.projector.data_mode.lower()} pipeline · {self.projector.session_name}",
            "lastUpdated": "live",
            "lastEventTime": self.last_event_time.isoformat() if self.last_event_time else None,
        }

    def get_drivers(self) -> list[dict[str, Any]]:
        return self.projector.get_ordered_drivers()

    def get_driver_telemetry(self, driver_number: int) -> dict[str, Any] | None:
        return self.projector.get_driver_telemetry(driver_number)

    def get_official_notices(self) -> list[dict[str, Any]]:
        return self.projector.get_official_notices()

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
            "pipelineStatus": sess.get("pipelineStatus", "CONNECTED"),
            "circuitId": sess.get("circuitId", "monaco"),
            "sessionName": sess["sessionName"],
            "sessionType": sess["sessionType"],
            "sessionId": sess.get("sessionId", self.current_session_id),
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
            "officialNotices": self.get_official_notices(),
        }


_store: StateStore | None = None


def get_state_store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore()
    return _store
