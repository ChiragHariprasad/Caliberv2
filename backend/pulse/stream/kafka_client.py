"""Unified async Kafka transport backed by calibre kafka_io (`RF=3`, `MIN_ISR=2`, `DriverSlots`)."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Any

from aiokafka import AIOKafkaConsumer
from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import AdminClient
from pydantic import BaseModel

from pulse.config import get_settings
from pulse.stream.kafka_io import (
    CalibreProducer,
    DriverSlots,
    build_topic_catalogue,
    driver_partition,
    ensure_topics as ensure_catalogue_topics,
    get_driver_slots,
)
from pulse.topics import ALL_TOPICS

logger = logging.getLogger("pulse.kafka")


def json_serializer(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    raise TypeError(f"Type {type(obj)} not serializable")


def _infer_driver_id(key: str | bytes | None, value: Any) -> Any:
    if isinstance(value, BaseModel):
        subj = getattr(value, "subject", None)
        dn = getattr(subj, "driver_number", None) if subj is not None else None
        if dn is not None:
            return dn
    elif isinstance(value, dict):
        subj = value.get("subject")
        if isinstance(subj, dict) and subj.get("driver_number") is not None:
            return subj["driver_number"]
        if value.get("driver_number") is not None:
            return value["driver_number"]
    if key is not None:
        key_str = key.decode("utf-8", errors="ignore") if isinstance(key, (bytes, bytearray)) else str(key)
        if ":" in key_str:
            suffix = key_str.rsplit(":", 1)[-1]
            if suffix.isdigit():
                return int(suffix)
        elif key_str.isdigit():
            return int(key_str)
    return None


class KafkaBroker:
    """
    Production Kafka broker transport consolidating async runtime callers onto kafka_io:
    - Idempotent librdkafka producer (`acks=all`, `enable.idempotence=True`, `gzip`)
    - Topic catalogue enforcement (`RF=3`, `min.insync.replicas=2`, `driver_partitions=11`)
    - Hybrid key + deterministic DriverSlots partitioning on multi-partition streams
    - Read-committed consumers with partition-assignment readiness synchronization
    """

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        settings = get_settings()
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self.driver_partitions = settings.driver_partitions
        self.slots: DriverSlots = get_driver_slots()
        self._producer: CalibreProducer | None = None
        self._admin: AdminClient | None = None
        self._is_connected = False
        self._consumers: list[AIOKafkaConsumer] = []
        self._poll_stop: threading.Event | None = None
        self._poll_thread: threading.Thread | None = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def _start_poller(self) -> None:
        if self._poll_thread is not None and self._poll_thread.is_alive():
            return
        stop_ev = threading.Event()
        self._poll_stop = stop_ev

        def _poll_loop() -> None:
            while not stop_ev.is_set():
                prod = self._producer
                if prod is not None:
                    try:
                        prod._p.poll(0.05)
                    except Exception:
                        pass
                else:
                    time.sleep(0.05)

        t = threading.Thread(target=_poll_loop, name="pulse-kafka-poller", daemon=True)
        t.start()
        self._poll_thread = t

    def _stop_poller(self) -> None:
        if self._poll_stop is not None:
            self._poll_stop.set()
        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)
        self._poll_stop = None
        self._poll_thread = None

    async def start(self) -> None:
        try:
            logger.info("Connecting to Kafka KRaft cluster at %s (kafka_io backbone)...", self.bootstrap_servers)
            self._admin = AdminClient({"bootstrap.servers": self.bootstrap_servers})
            md = await asyncio.to_thread(self._admin.list_topics, None, 10)
            if not md.brokers:
                raise RuntimeError(f"No Kafka brokers returned from {self.bootstrap_servers}")

            await self.ensure_topics()
            self._producer = CalibreProducer(
                bootstrap_servers=self.bootstrap_servers,
                linger_ms=5,
                compression_type="gzip",
            )
            self._start_poller()
            self._is_connected = True
            logger.info(
                "Kafka producer connected (%d brokers, RF=3/MIN_ISR=2, driver_partitions=%d).",
                len(md.brokers),
                self.driver_partitions,
            )
        except Exception as e:
            logger.error("Failed to start Kafka transport: %s", e)
            self._is_connected = False
            raise

    async def ensure_topics(self) -> None:
        if not self._admin:
            return
        try:
            catalogue = build_topic_catalogue(driver_partitions=self.driver_partitions)
            present = {spec.name for spec in catalogue}
            # Ensure any runtime topic in ALL_TOPICS not in catalogue gets registered safely too
            from pulse.stream.kafka_io import DAY_MS, TopicSpec
            for t in ALL_TOPICS:
                if t not in present:
                    catalogue.append(TopicSpec(t, 1, 7 * DAY_MS))
            await asyncio.to_thread(ensure_catalogue_topics, self._admin, catalogue)
        except Exception as e:
            logger.warning("Error checking or creating Kafka topics: %s", e)

    async def publish(
        self,
        topic: str,
        key: str,
        value: Any,
        driver_id: Any = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        if not self._producer or not self._is_connected:
            raise RuntimeError("Kafka producer is not running")

        if isinstance(value, (bytes, bytearray)):
            payload = bytes(value)
        elif isinstance(value, BaseModel):
            payload = value.model_dump_json().encode("utf-8")
        elif isinstance(value, dict):
            payload = json.dumps(value, default=json_serializer).encode("utf-8")
        else:
            payload = json.dumps({"data": value}, default=json_serializer).encode("utf-8")

        key_b = key.encode("utf-8") if isinstance(key, str) else key
        resolved_driver = driver_id if driver_id is not None else _infer_driver_id(key, value)
        pcount = await asyncio.to_thread(self._producer.partition_count, topic)
        partition = driver_partition(self.slots, resolved_driver, pcount) if (resolved_driver is not None and pcount > 1) else -1

        hdr_items = [("content-type", b"application/json"), ("correlation_id", key_b or b"")]
        if headers:
            for hk, hv in headers.items():
                if hv is not None:
                    hdr_items.append((hk, hv if isinstance(hv, bytes) else str(hv).encode("utf-8")))

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()

        def _on_delivery(err: KafkaError | None, msg: Any) -> None:
            self._producer._on_delivery(err, msg)  # type: ignore[union-attr]
            if err is not None:
                err_exc = RuntimeError(f"Kafka delivery failed for topic {topic}: {err}")
                if not fut.done():
                    loop.call_soon_threadsafe(fut.set_exception, err_exc)
            else:
                if not fut.done():
                    loop.call_soon_threadsafe(fut.set_result, None)

        for _ in range(100):
            try:
                self._producer._p.produce(
                    topic,
                    value=payload,
                    key=key_b,
                    partition=partition,
                    headers=hdr_items,
                    on_delivery=_on_delivery,
                )
                break
            except BufferError:
                self._producer._p.poll(0.1)
                await asyncio.sleep(0.01)
        else:
            raise BufferError(f"Kafka local producer queue saturated for topic {topic}")

        self._producer.stats.enqueued += 1
        self._producer._p.poll(0)
        await fut

    def publish_dlq(self, topic: str, partition: int, offset: int, key: bytes | str | None, value: bytes, error: Exception) -> None:
        if not self._producer:
            return

        class _RawMsg:
            def topic(self): return topic
            def partition(self): return partition
            def offset(self): return offset
            def key(self): return key.encode("utf-8") if isinstance(key, str) else key
            def value(self): return value
            def headers(self): return None

        self._producer.publish_dlq(_RawMsg(), error)  # type: ignore[arg-type]

    async def create_consumer(
        self,
        topics: list[str],
        group_id: str,
        auto_offset_reset: str = "latest",
        isolation_level: str = "read_committed",
        enable_auto_commit: bool = True,
        ready_timeout_s: float = 5.0,
    ) -> AIOKafkaConsumer:
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            isolation_level=isolation_level,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")) if v is not None else None,
            enable_auto_commit=enable_auto_commit,
        )
        await consumer.start()
        deadline = time.monotonic() + max(ready_timeout_s, 0.0)
        while not consumer.assignment() and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        self._consumers.append(consumer)
        return consumer

    async def stop(self) -> None:
        logger.info("Stopping Kafka broker transport...")
        for c in self._consumers:
            try:
                await c.stop()
            except Exception as e:
                logger.debug("Error stopping consumer: %s", e)
        self._consumers.clear()

        if self._producer:
            try:
                await asyncio.to_thread(self._producer._p.flush, 10.0)
            except Exception as e:
                logger.debug("Error flushing producer on stop: %s", e)
            self._producer = None

        self._stop_poller()
        self._admin = None
        self._is_connected = False
        logger.info("Kafka broker transport stopped.")


_broker: KafkaBroker | None = None


def get_kafka_broker() -> KafkaBroker:
    global _broker
    if _broker is None:
        _broker = KafkaBroker()
    return _broker
