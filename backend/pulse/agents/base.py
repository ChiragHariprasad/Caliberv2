from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pulse.contracts import EventEnvelope, Finding
from pulse.stream.bus import PulseEventBus, get_event_bus

logger = logging.getLogger("pulse.agent")


class AgentExecutionMetrics(BaseModel):
    """Execution transparency and lineage telemetry for PULSE specialist agents."""
    model_config = ConfigDict(protected_namespaces=())

    agent_id: str
    name: str
    model_version: str
    run_id: str | None = None
    inputs_received: int = 0
    eligible_inputs: int = 0
    successfully_processed: int = 0
    findings_emitted: int = 0
    valid_no_finding_outcomes: int = 0
    insufficient_data_outcomes: int = 0
    filtered_inputs: int = 0
    failures: int = 0
    retries: int = 0
    processing_latency_ms: float = 0.0
    last_processed_event_id: str | None = None
    last_outcome: str = "INITIALIZED"
    output_finding_ids: list[str] = Field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base class for all PULSE specialist agents with durable execution transparency."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        output_topic: str,
        bus: PulseEventBus | None = None,
        model_version: str = "1.0.0",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.output_topic = output_topic
        self.bus = bus or get_event_bus()
        self.model_version = model_version
        self.is_active = True

        # Transparency metrics
        self.run_id: str | None = None
        self.inputs_received = 0
        self.eligible_inputs = 0
        self.successfully_processed = 0
        self.emitted_findings = 0
        self.valid_no_finding_outcomes = 0
        self.insufficient_data_outcomes = 0
        self.filtered_inputs = 0
        self.failures = 0
        self.retries = 0
        self.last_latency_ms = 0.0
        self.last_processed_event_id: str | None = None
        self.last_outcome: str = "INITIALIZED"
        self.output_finding_ids: list[str] = []

    @property
    def processed_events(self) -> int:
        """Backward compatibility with existing test assertions."""
        return self.inputs_received

    @processed_events.setter
    def processed_events(self, val: int) -> None:
        self.inputs_received = val

    def record_input(self, event_id: str, eligible: bool = True, filtered: bool = False, run_id: str | None = None) -> None:
        """Records an incoming event into transparency metrics."""
        self.inputs_received += 1
        self.last_processed_event_id = event_id
        if run_id:
            self.run_id = run_id
        if filtered:
            self.filtered_inputs += 1
        elif eligible:
            self.eligible_inputs += 1

    def record_outcome(self, outcome: str, latency_ms: float = 0.0) -> None:
        """Records the terminal execution outcome for the current event."""
        self.last_outcome = outcome
        self.last_latency_ms = latency_ms
        if outcome == "FINDING_EMITTED":
            self.successfully_processed += 1
        elif outcome == "NO_FINDING":
            self.successfully_processed += 1
            self.valid_no_finding_outcomes += 1
        elif outcome == "INSUFFICIENT_DATA":
            self.insufficient_data_outcomes += 1
        elif outcome == "FILTERED":
            pass
        elif outcome in {"FAILED", "ERROR"}:
            self.failures += 1

    async def emit_finding(self, finding: Finding) -> None:
        """Publishes finding to Kafka topic and bus with full lineage tracking."""
        self.emitted_findings += 1
        if finding.finding_id not in self.output_finding_ids:
            self.output_finding_ids.append(finding.finding_id)
        routing_key = f"{finding.session_id}:{finding.subject.driver_number or 'session'}"
        await self.bus.publish(self.output_topic, routing_key, finding)
        try:
            from pulse.state.store import get_state_store
            get_state_store().record_finding(finding)
        except Exception:
            pass
        logger.debug(
            "Agent [%s] emitted finding [%s] of type %s",
            self.agent_id,
            finding.finding_id,
            finding.finding_type,
        )

    def get_metrics(self) -> AgentExecutionMetrics:
        """Returns run-scoped execution transparency metrics."""
        return AgentExecutionMetrics(
            agent_id=self.agent_id,
            name=self.name,
            model_version=self.model_version,
            run_id=self.run_id,
            inputs_received=self.inputs_received,
            eligible_inputs=self.eligible_inputs,
            successfully_processed=self.successfully_processed,
            findings_emitted=self.emitted_findings,
            valid_no_finding_outcomes=self.valid_no_finding_outcomes,
            insufficient_data_outcomes=self.insufficient_data_outcomes,
            filtered_inputs=self.filtered_inputs,
            failures=self.failures,
            retries=self.retries,
            processing_latency_ms=self.last_latency_ms,
            last_processed_event_id=self.last_processed_event_id,
            last_outcome=self.last_outcome,
            output_finding_ids=list(self.output_finding_ids),
        )

    def reset_metrics(self) -> None:
        """Resets run-scoped metrics."""
        self.inputs_received = 0
        self.eligible_inputs = 0
        self.successfully_processed = 0
        self.emitted_findings = 0
        self.valid_no_finding_outcomes = 0
        self.insufficient_data_outcomes = 0
        self.filtered_inputs = 0
        self.failures = 0
        self.retries = 0
        self.last_latency_ms = 0.0
        self.last_processed_event_id = None
        self.last_outcome = "RESET"
        self.output_finding_ids.clear()

    @abstractmethod
    async def on_event(self, topic: str, key: str, event: EventEnvelope) -> None:
        """Process incoming stream event and optionally emit findings."""
        pass
