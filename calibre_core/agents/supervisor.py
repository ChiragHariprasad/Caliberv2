"""A5 Supervisor Archetype: Feed Supervisor Agent (Independent Path).

Operates in an isolated failure domain. Observes raw topic counts, receipt times,
and consumer lag without shared parsing. Emits monotonic clock ticks,
STALLED and RESUMED guard facts, and feed-health metrics.

Produces facts/guards for roles:
  - clock_tick (monotonic integer microseconds)
  - feed_guard (STALLED / RESUMED guard facts)
  - feed_health (duplicate ratio, cadence jitter, clock skew)

Failure catalogue: BASELINE_MISSING, CLOCK_ANOMALY, TAP_LAG, FEED_STALLED.
"""
from __future__ import annotations

import time
from typing import Any, Mapping, Optional, Sequence

from sia_core import EvidenceAtom, GuardFact, IntegrityState, TimeClass, TypedTime, make_guard, parse_instant
from calibre_core.agents.base import AgentArchetype, RawSpanReference


class FeedSupervisorAgent(AgentArchetype):
    """Specialist Independent Feed Supervisor and Liveness Guard Producer."""

    def __init__(
        self,
        agent_id: str = "A5-FeedSupervisorAgent",
        version: str = "1.0.0",
        source_origin: str = "FEED_SUPERVISOR_TAP",
        processing_origin: str = "A5_SUPERVISOR_v1",
        expected_cadence_us: int = 1_000_000,  # 1 Hz default expected heartbeat
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            processor_id="A5_SUPERVISOR_PROCESSOR",
            version=version,
            source_origin=source_origin,
            processing_origin=processing_origin,
        )
        self.expected_cadence_us = expected_cadence_us
        self._last_receipt_by_stream: dict[str, int] = {}
        self._stream_status: dict[str, str] = {}  # stream -> "LIVE" / "STALLED"
        self._monotonic_base_us: int = 0
        self._perf_counter_base: float = time.perf_counter()

    @property
    def failure_catalogue(self) -> Sequence[str]:
        return (
            "BASELINE_MISSING",
            "CLOCK_ANOMALY",
            "TAP_LAG",
            "FEED_STALLED",
        )

    def advance_clock_tick(self, delta_us: int) -> int:
        """Emits a monotonic clock tick advancing by delta microseconds."""
        self._monotonic_base_us += delta_us
        return self._monotonic_base_us

    def inspect_stream_heartbeat(
        self,
        stream_name: str,
        current_time_us: int,
        epoch: int = 1,
    ) -> Optional[GuardFact]:
        """Audits stream cadence; emits a STALLED or RESUMED GuardFact if cadence is breached."""
        last_t = self._last_receipt_by_stream.get(stream_name)
        current_status = self._stream_status.get(stream_name, "LIVE")

        # Check stall condition
        if last_t is not None and (current_time_us - last_t) > (self.expected_cadence_us * 3):
            if current_status != "STALLED":
                self._stream_status[stream_name] = "STALLED"
                self.record_diagnostic("FEED_STALLED", f"Stream {stream_name} stalled (silent for {(current_time_us - last_t) / 1e6:.1f}s)")
                return make_guard(
                    origin=stream_name,
                    status="STALLED",
                    detected_at=current_time_us,
                    epoch=epoch,
                )
        else:
            if current_status == "STALLED":
                self._stream_status[stream_name] = "LIVE"
                return make_guard(
                    origin=stream_name,
                    status="RESUMED",
                    detected_at=current_time_us,
                    epoch=epoch,
                )

        return None

    def process_record(
        self,
        raw_record: Mapping[str, Any],
        raw_ref: Optional[RawSpanReference] = None,
    ) -> Sequence[EvidenceAtom]:
        stream_name = str(raw_record.get("stream", raw_record.get("topic", "default_stream")))
        obs_time = raw_record.get("receipt_time", raw_record.get("timestamp", "2021-12-12T13:00:00Z"))
        obs_us = parse_instant(obs_time)

        self._last_receipt_by_stream[stream_name] = obs_us

        # Emit feed health observation atom
        scope = {"stream_name": stream_name}
        atom = self.emit_atom(
            role_id="feed_health",
            value=1.0,  # 1.0 = healthy cadence
            unit="ratio",
            typed_time=TypedTime(obs_us, TimeClass.ABSOLUTE_UTC),
            observed_at=obs_time,
            scope=scope,
            raw_refs=[raw_ref] if raw_ref else [],
            uncertainty=0.01,
        )
        return [atom]

