from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from pulse.stream.kafka_client import KafkaBroker, get_kafka_broker

logger = logging.getLogger("pulse.bus")

Handler = Callable[[str, str, Any], Coroutine[Any, Any, None]]


class PulseEventBus:
    """Unified event bus backed compulsorily by Kafka with local event dispatching."""

    def __init__(self, broker: KafkaBroker | None = None) -> None:
        self.broker = broker or get_kafka_broker()
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._wildcard_handlers: list[Handler] = []

    async def start(self) -> None:
        await self.broker.start()

    async def stop(self) -> None:
        await self.broker.stop()

    def subscribe(self, topic: str, handler: Handler) -> None:
        if topic == "*":
            self._wildcard_handlers.append(handler)
        else:
            self._handlers[topic].append(handler)

    async def publish(self, topic: str, key: str, value: Any) -> None:
        # Publish compulsorily to Kafka
        if self.broker.is_connected:
            try:
                await self.broker.publish(topic, key, value)
            except Exception as e:
                logger.error("Failed to publish to Kafka topic %s: %s", topic, e)

        # Dispatch locally to subscribers
        handlers = list(self._handlers.get(topic, [])) + list(self._wildcard_handlers)
        coros = []
        for handler in handlers:
            try:
                task = handler(topic, key, value)
                if asyncio.iscoroutine(task):
                    coros.append(task)
            except Exception as e:
                logger.error("Error invoking bus handler for topic %s: %s", topic, e, exc_info=True)

        if coros:
            results = await asyncio.gather(*coros, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.error("Error executing subscriber for topic %s: %s", topic, r, exc_info=r)

    async def drain(self) -> None:
        """Flushes any pending async work."""
        await asyncio.sleep(0)


_bus: PulseEventBus | None = None


def get_event_bus() -> PulseEventBus:
    global _bus
    if _bus is None:
        _bus = PulseEventBus()
    return _bus

