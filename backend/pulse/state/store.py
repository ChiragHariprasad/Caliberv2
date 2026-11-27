from __future__ import annotations

import asyncio
import json
import logging
import pickle
import time
from collections import deque
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
        self._finding_ids: set[str] = set()
        self._assessment_ids: set[str] = set()
        self._seen_event_ids: set[str] = set()
        self._seen_event_order: deque[str] = deque(maxlen=20000)
        self._retired_run_ids: set[str] = set()
        self._retired_run_order: deque[str] = deque(maxlen=500)
        self.processed_events_count: int = 0
        self.duplicate_events_count: int = 0
        self.last_event_time: datetime | None = None
        self._listeners: list[asyncio.Queue[dict[str, Any]]] = []
        self._history_events: list[dict[str, Any]] = []
        self.sse_sequence_counter: int = 0
        self._last_driver_sse_wall_time: float = 0.0
        self._lock = asyncio.Lock()
        self.agents: dict[str, Any] = {}

        # Neutral unmeasured strategy templates until real neutralisation/pit findings arrive
        self.default_strategies = self._initial_strategy_templates()

    @staticmethod
    def _initial_strategy_templates() -> list[dict[str, Any]]:
        return [
            {
                "label": "Box on neutralisation",
                "action": "Evaluate pit window when VSC/SC deploys",
                "score": None,
                "delta": "Awaiting trigger",
                "tone": "neutral",
                "status": "AWAITING_EVENT",
                "calibration_status": "UNMEASURED",
                "note": "Strategies populate quantitatively once neutralisation and empirical lap data arrive.",
            },
            {
                "label": "Hold 1 lap",
                "action": "Monitor track position & traffic gap",
                "score": None,
                "delta": "Awaiting trigger",
                "tone": "neutral",
                "status": "AWAITING_EVENT",
                "calibration_status": "UNMEASURED",
                "note": "Re-entry traffic projection depends on live field gaps and circuit pit transit loss.",
            },
            {
                "label": "Stay out",
                "action": "Continue current stint",
                "score": None,
                "delta": "Awaiting trigger",
                "tone": "neutral",
                "status": "AWAITING_EVENT",
                "calibration_status": "UNMEASURED",
                "note": "Empirical fuel-compensated tyre degradation requires >= 5 clean stint laps.",
            },
        ]

    def register_agent(self, agent: Any) -> None:
        """Registers a specialist agent to track durable execution metrics."""
        self.agents[agent.agent_id] = agent

    def retire_run(self, run_id: str | None) -> None:
        """Mark a superseded/abandoned replay run ID so delayed broker messages are discarded."""
        if not run_id:
            return
        if run_id in self._retired_run_ids:
            return
        if len(self._retired_run_order) == self._retired_run_order.maxlen:
            evicted = self._retired_run_order.popleft()
            self._retired_run_ids.discard(evicted)
        self._retired_run_ids.add(run_id)
        self._retired_run_order.append(run_id)

    def is_run_retired(self, run_id: str | None) -> bool:
        return bool(run_id and run_id in self._retired_run_ids)

    def begin_run(self, run_id: str) -> None:
        """Associate subsequent projection and SSE state with one replay run."""
        self.current_run_id = run_id
        self._retired_run_ids.discard(run_id)
        self._seen_event_ids.clear()
        self._seen_event_order.clear()
        for agent in self.agents.values():
            if hasattr(agent, "run_id"):
                agent.run_id = run_id

    def get_agent_metrics(self) -> dict[str, Any]:
        """Returns execution transparency metrics across all registered agents."""
        return {
            aid: a.get_metrics().model_dump(mode="json")
            for aid, a in self.agents.items()
            if hasattr(a, "get_metrics")
        }

    def switch_session(self, session_id: str, *, preserve_wal: bool = False) -> None:
        """Configures state and driver grid for the chosen session."""
        self.current_session_id = session_id
        self._finding_ids.clear()
        self._assessment_ids.clear()
        self._seen_event_ids.clear()
        self._seen_event_order.clear()
        self.processed_events_count = 0
        self.duplicate_events_count = 0
        self.last_event_time = None
        self.default_strategies = self._initial_strategy_templates()
        self.projector.reset_sectors()
        meta = get_session_by_id(session_id)

        ia_restored = False
        for agent in self.agents.values():
            if hasattr(agent, "reset_metrics"):
                agent.reset_metrics()
            if agent.agent_id == "agent-06-integrity":
                if hasattr(agent, "set_session_id"):
                    agent.set_session_id(session_id)
                if preserve_wal and hasattr(agent, "restore_from_wal") and agent.restore_from_wal():
                    ia_restored = True
                    continue
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
            repo_root = Path(__file__).resolve().parents[3]
            candidate_dirs = [
                repo_root / "captures" / capture_id,
                repo_root / "captures" / session_id,
                Path("captures") / capture_id,
                Path("captures") / session_id,
                Path("../captures") / capture_id,
                Path("../captures") / session_id,
                Path("../../captures") / capture_id,
                Path("../../captures") / session_id,
            ]
            entry_file: Path | None = None
            for cd in candidate_dirs:
                ef = cd / "entry_list.json"
                if ef.exists():
                    entry_file = ef
                    break

            if entry_file is not None and entry_file.exists():
                entries = json.loads(entry_file.read_text(encoding="utf-8"))
                self.projector.load_session_entry_list(entries)

            if "agent-06-integrity" in self.agents and not ia_restored:
                try:
                    self.agents["agent-06-integrity"].initialize_session_grid(
                        session_id, list(self.projector.drivers.keys())
                    )
                except Exception as e:
                    logger.debug("Failed initializing session grid on integrity agent: %s", e)

            logger.info("Session switched to HISTORICAL [%s] (%d drivers, file: %s)", session_id, len(self.projector.drivers), str(entry_file))
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

            if "agent-06-integrity" in self.agents and not ia_restored:
                try:
                    self.agents["agent-06-integrity"].initialize_session_grid(
                        session_id, list(self.projector.drivers.keys())
                    )
                except Exception as e:
                    logger.debug("Failed initializing session grid on integrity agent: %s", e)
            logger.info("Session switched to SIMULATION [%s]", session_id)
            self.notify_session_state()
            self.notify_driver_state()

    def record_canonical_event(self, envelope: EventEnvelope) -> None:
        """Applies canonical event to projector, updates telemetry stats, and pushes SSE notifications."""
        eid = envelope.event_id
        if eid in self._seen_event_ids:
            self.duplicate_events_count += 1
            return
        if len(self._seen_event_order) == self._seen_event_order.maxlen:
            evicted = self._seen_event_order.popleft()
            self._seen_event_ids.discard(evicted)
        self._seen_event_ids.add(eid)
        self._seen_event_order.append(eid)

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

        if et in {"CAR_TELEMETRY", "CAR_TELEMETRY_SAMPLE", "DRIVER_TELEMETRY", "POSITION_UPDATE"}:
            dn = envelope.subject.driver_number or p.get("driver_number")
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
        if finding.finding_id in self._finding_ids:
            return
        self._finding_ids.add(finding.finding_id)
        self.findings.append(finding)
        if finding.finding_type == "PIT_WINDOW_OPPORTUNITY" and "scenarios" in finding.result:
            self.default_strategies = finding.result["scenarios"]
        if finding.finding_type == "INTEGRITY_ASSESSMENT":
            self.notify_integrity_state(finding.result)

        self._notify_listeners("finding", finding.model_dump(mode="json"))
        self._notify_listeners("AGENT_FINDING_UPDATED", finding.model_dump(mode="json"))
        self._notify_listeners("AGENT_STATUS_UPDATED", self.get_agent_metrics())

    def record_assessment(self, assessment: Assessment) -> None:
        """Stores fused driver consequence assessment, updates superseded revisions, and emits SSE update."""
        if assessment.assessment_id in self._assessment_ids:
            return
        self._assessment_ids.add(assessment.assessment_id)
        if assessment.supersedes_assessment_id:
            for prev in self.assessment_history:
                if (
                    prev.assessment_id == assessment.supersedes_assessment_id
                    and prev.status not in {FindingStatus.REJECTED, FindingStatus.WITHDRAWN, FindingStatus.SUPERSEDED}
                ):
                    prev.status = FindingStatus.SUPERSEDED
        dn = assessment.subject.driver_number
        if dn:
            self.latest_assessments[dn] = assessment
            if dn in self.projector.drivers:
                tone = "negative" if ("congestion" in assessment.impact.summary.lower() or "loss" in assessment.impact.summary.lower()) else "positive"
                self.projector.drivers[dn]["impact"] = {
                    "tone": tone,
                    "label": assessment.impact.summary[:30],
                }
        self.assessment_history.append(assessment)

        self._notify_listeners("assessment", assessment.model_dump(mode="json"))
        self._notify_listeners("IMPACT_ASSESSMENT_UPDATED", assessment.model_dump(mode="json"))

    # --- Typed Domain Notification Helpers for SSE ---

    def notify_session_state(self) -> None:
        self._notify_listeners("SESSION_STATE_UPDATED", self.get_session())

    def notify_driver_state(self, driver_number: int | None = None) -> None:
        payload: dict[str, Any] = {"drivers": self.get_drivers()}
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

    def notify_integrity_state(self, integrity_payload: dict[str, Any]) -> None:
        """Push integrity assessment updates to SSE listeners."""
        self._notify_listeners("INTEGRITY_STATE_UPDATED", integrity_payload)

    # --- SSE Subscription & Event Delivery ---

    def add_listener(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)
        self._listeners.append(queue)
        return queue

    def try_add_listener(self, max_listeners: int) -> asyncio.Queue[dict[str, Any]] | None:
        if len(self._listeners) >= max_listeners:
            return None
        return self.add_listener()

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
        meta = get_session_by_id(self.current_session_id)
        try:
            from pulse.config import get_settings
            transport_mode = f"{get_settings().transport_mode.upper()} TRANSPORT"
        except Exception:
            transport_mode = "SIMULATOR TRANSPORT"
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
            "dataRegime": meta.data_regime if meta else "SYNTHETIC",
            "datasetClassification": meta.dataset_classification if meta else "SYNTHETIC_SIMULATOR",
            "sourceProvenance": meta.source_provenance if meta else "PULSE_SYNTHETIC_SIMULATOR",
            "timingBaseline": meta.timing_baseline if meta else "Deterministic Simulator Stream",
            "licenceReference": meta.licence_reference if meta else "PULSE-SYNTHETIC-SIM-INTERNAL",
            "isSynthetic": meta.is_synthetic if meta else True,
            "transportMode": transport_mode,
            "sourceLabel": f"PULSE {meta.data_regime if meta else 'SYNTHETIC'} · {self.projector.session_name}",
            "lastUpdated": "live" if self.last_event_time else "ready",
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

            tone = (
                "negative"
                if ("congestion" in narrative.lower() or "loss" in narrative.lower() or "deficit" in narrative.lower() or "conflict" in narrative.lower())
                else ("positive" if ("opens" in narrative.lower() or "favourable" in narrative.lower() or "saving" in narrative.lower()) else "neutral")
            )

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
                    "Hold track position (0 net delta)"
                    if (a.impact.forecast and a.impact.forecast.position_delta_range == (0, 0))
                    else (
                        f"Projected net delta: {a.impact.forecast.position_delta_range[0]:+d} pos"
                        if (
                            a.impact.forecast
                            and a.impact.forecast.position_delta_range
                            and a.impact.forecast.position_delta_range[0] == a.impact.forecast.position_delta_range[1]
                        )
                        else (
                            f"Projected net delta: {a.impact.forecast.position_delta_range[0]:+d} to {a.impact.forecast.position_delta_range[1]:+d} pos"
                            if a.impact.forecast and a.impact.forecast.position_delta_range
                            else "Awaiting gap convergence"
                        )
                    )
                ),
                "alternative": a.impact.alternatives[0] if a.impact.alternatives else "Hold track position and monitor",
                "evidence": a.evidence_refs,
                "supersedesId": a.supersedes_assessment_id,
                "changedAt": a.as_of_event_time.isoformat() if a.as_of_event_time else "recent",
            })

        formatted.sort(key=lambda x: (self.projector.drivers.get(x["driverNumber"], {}).get("position", 99), x["driverNumber"]))
        return formatted

    def export_checkpoint(self) -> bytes:
        """Capture full deterministic StateStore + all specialist agent states for fast seek keyframes."""
        agent_snaps: dict[str, tuple[str, Any]] = {}
        for aid, agent in self.agents.items():
            if hasattr(agent, "export_checkpoint"):
                agent_snaps[aid] = ("custom", agent.export_checkpoint())
            else:
                saved_bus = getattr(agent, "bus", None)
                try:
                    if hasattr(agent, "bus"):
                        agent.bus = None
                    agent_snaps[aid] = ("pickle", pickle.dumps(agent.__dict__, protocol=pickle.HIGHEST_PROTOCOL))
                finally:
                    if hasattr(agent, "bus"):
                        agent.bus = saved_bus

        payload = {
            "current_session_id": self.current_session_id,
            "current_run_id": self.current_run_id,
            "projector_blob": pickle.dumps(self.projector, protocol=pickle.HIGHEST_PROTOCOL),
            "latest_assessments": self.latest_assessments,
            "assessment_history": self.assessment_history,
            "findings": self.findings,
            "_finding_ids": self._finding_ids,
            "_assessment_ids": self._assessment_ids,
            "_seen_event_ids": self._seen_event_ids,
            "_seen_event_order": self._seen_event_order,
            "processed_events_count": self.processed_events_count,
            "duplicate_events_count": self.duplicate_events_count,
            "last_event_time": self.last_event_time,
            "default_strategies": self.default_strategies,
            "agents": agent_snaps,
        }
        return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    def restore_checkpoint(self, blob: bytes) -> None:
        """Restore StateStore + all specialist agents from a captured keyframe checkpoint."""
        payload = pickle.loads(blob)
        self.current_session_id = payload["current_session_id"]
        self.current_run_id = payload["current_run_id"]
        self.projector = pickle.loads(payload["projector_blob"])
        self.latest_assessments = payload["latest_assessments"]
        self.assessment_history = payload["assessment_history"]
        self.findings = payload["findings"]
        self._finding_ids = payload["_finding_ids"]
        self._assessment_ids = payload["_assessment_ids"]
        self._seen_event_ids = payload["_seen_event_ids"]
        self._seen_event_order = payload["_seen_event_order"]
        self.processed_events_count = payload["processed_events_count"]
        self.duplicate_events_count = payload["duplicate_events_count"]
        self.last_event_time = payload["last_event_time"]
        self.default_strategies = payload["default_strategies"]

        for aid, (kind, data) in payload["agents"].items():
            agent = self.agents.get(aid)
            if agent is None:
                continue
            if kind == "custom" and hasattr(agent, "restore_checkpoint"):
                agent.restore_checkpoint(data)
            elif kind == "pickle":
                saved_bus = getattr(agent, "bus", None)
                restored_dict = pickle.loads(data)
                agent.__dict__.update(restored_dict)
                if hasattr(agent, "bus"):
                    agent.bus = saved_bus

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
                "agent-06-integrity",
            ],
        }

    def get_snapshot(self) -> dict[str, Any]:
        """Provides full consumer-facing snapshot matching PulseSnapshot interface."""
        sess = self.get_session()

        # Integrity summary (if agent is registered)
        integrity_summary = None
        ia = self.agents.get("agent-06-integrity")
        if ia and hasattr(ia, "get_summary"):
            try:
                integrity_summary = ia.get_summary()
            except Exception as e:
                logger.warning("Failed to retrieve integrity summary for snapshot: %s", e)

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
            "dataRegime": sess.get("dataRegime", "SYNTHETIC"),
            "datasetClassification": sess.get("datasetClassification", "SYNTHETIC_SIMULATOR"),
            "sourceProvenance": sess.get("sourceProvenance", "PULSE_SYNTHETIC_SIMULATOR"),
            "timingBaseline": sess.get("timingBaseline", "Deterministic Simulator Stream"),
            "licenceReference": sess.get("licenceReference", "PULSE-SYNTHETIC-SIM-INTERNAL"),
            "isSynthetic": sess.get("isSynthetic", True),
            "transportMode": sess.get("transportMode", "SIMULATOR TRANSPORT"),
            "sourceLabel": sess["sourceLabel"],
            "lastUpdated": sess["lastUpdated"],
            "drivers": self.get_drivers(),
            "timeline": self.get_timeline(),
            "assessments": self.get_assessments(),
            "strategies": self.get_strategy(),
            "sectors": self.get_track(),
            "officialNotices": self.get_official_notices(),
            "integrity": integrity_summary,
        }


_store: StateStore | None = None


def get_state_store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore()
    return _store
