"""Canonical event processor shared by replay playback and reconstruction."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pulse.contracts import EventEnvelope
from pulse.stream.normalizer import StreamNormalizer
from pulse.topics import raw_topic_for_event, routing_key


class ReplayProcessingError(RuntimeError):
    """Raised when a replay event cannot enter the canonical pipeline."""


class ReplayEventProcessor:
    """Normalize and dispatch a replay envelope through one canonical path.

    ``raw_publisher`` is optional because simulator/memory replay has no
    broker transport.  Reconstruction never invokes it, preventing a seek
    from duplicating already recorded source events.
    """

    def __init__(
        self,
        normalizer: StreamNormalizer,
        dispatch: Callable[[str, str, EventEnvelope], Awaitable[None]],
        raw_publisher: Callable[[str, str, EventEnvelope], Awaitable[None]] | None = None,
    ) -> None:
        self._normalizer = normalizer
        self._dispatch = dispatch
        self._raw_publisher = raw_publisher

    async def process(self, envelope: EventEnvelope, *, publish: bool) -> None:
        key = routing_key(
            envelope.run.session_instance_id,
            envelope.subject.driver_number,
            envelope.subject.segment_id,
        )
        if publish and self._raw_publisher is not None:
            await self._raw_publisher(raw_topic_for_event(envelope.event_type), key, envelope)

        canonical, topic = self._normalizer.process(envelope)
        if canonical is None or topic is None:
            raise ReplayProcessingError(f"replay event {envelope.event_id} was rejected: {topic}")
        await self._dispatch(topic, key, canonical)
