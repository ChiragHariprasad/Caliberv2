"""Centralized Production Kafka IO Layer for CALIBRE / PULSE.

Provides:
1. Topic catalogue with explicit partition tiers (DRIVER=11, OPS=3, SINGLE=1), RF=3, min.isr=2,
   retention and compaction policies, plus broker drift verification.
2. Driver-affine partitioning via deterministic DriverSlots.
3. High-throughput idempotent producers with gzip compression (universally supported by Flink & librdkafka) and delivery latency tracking.
4. Consumers with cooperative-sticky rebalance, static membership, and read_committed isolation.
5. Exactly-once consume-transform-produce transactional loop for Kafka-to-Kafka stages.
6. Centralized DLQ dispatch with source coordinates and exception details.
7. Idempotent SQLite sink with (topic, partition, offset) primary key.
8. Consumer lag reporting and health inspection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generator
from uuid import uuid4

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Message,
    OFFSET_BEGINNING,
    Producer,
    TopicPartition,
)
from confluent_kafka.admin import AdminClient, ConfigResource, NewTopic, RESOURCE_TOPIC
from pydantic import BaseModel

from pulse.config import get_settings

logger = logging.getLogger("calibre.kafka.io")

DAY_MS = 86_400_000
RF = 3
MIN_ISR = 2
PARTITION_UA = -1


# ==============================================================================
# 1. TOPIC SPECIFICATION & CATALOGUE (Phase 2)
# ==============================================================================

@dataclass(frozen=True)
class TopicSpec:
    name: str
    partitions: int
    retention_ms: int | None = 7 * DAY_MS
    cleanup_policy: str = "delete"
    extra: dict[str, str] = field(default_factory=dict)

    def configs(self) -> dict[str, str]:
        c = {
            "cleanup.policy": self.cleanup_policy,
            "min.insync.replicas": str(MIN_ISR),
            "unclean.leader.election.enable": "false",
            "segment.bytes": str(128 * 1024 * 1024),  # 128 MB
        }
        if self.retention_ms is not None and self.cleanup_policy == "delete":
            c["retention.ms"] = str(self.retention_ms)
        c.update(self.extra)
        return c


def build_topic_catalogue(driver_partitions: int = 11) -> list[TopicSpec]:
    """Builds authoritative topic catalogue matching production CALIBRE and PULSE specifications."""
    specs = [
        # --- CALIBRE CORE CATALOGUE (Section 5) ---
        TopicSpec("calibre.raw.f1_signalr.all", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.f1_signalr.car_data", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.f1_signalr.position", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.f1_signalr.timing", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.f1_signalr.race_control", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.f1_signalr.weather", 1, 7 * DAY_MS),

        TopicSpec("calibre.raw.fastf1.car_data", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.position", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.laps", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.timing", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.stints", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.weather", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.race_control", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.track_status", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.fastf1.session_status", 1, 7 * DAY_MS),

        TopicSpec("calibre.raw.openf1.car_data", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.position", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.laps", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.timing", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.stints", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.weather", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.race_control", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.track_status", 1, 7 * DAY_MS),
        TopicSpec("calibre.raw.openf1.session_status", 1, 7 * DAY_MS),

        TopicSpec("calibre.evidence.vehicle", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.evidence.timing", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.evidence.incident", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.evidence.environment", 1, 7 * DAY_MS),
        TopicSpec("calibre.evidence.system", 1, 7 * DAY_MS),

        TopicSpec("calibre.guard.liveness", 1, 7 * DAY_MS),
        TopicSpec("calibre.guard.clock", 1, 7 * DAY_MS),

        TopicSpec(
            "calibre.config.contracts",
            1,
            retention_ms=None,
            cleanup_policy="compact",
            extra={"min.cleanable.dirty.ratio": "0.1", "segment.ms": "3600000"},
        ),

        TopicSpec("calibre.core.verdict_history", driver_partitions, 30 * DAY_MS),
        TopicSpec("calibre.out.database", driver_partitions, 30 * DAY_MS),
        TopicSpec("calibre.out.dashboard", driver_partitions, 1 * DAY_MS),
        TopicSpec("calibre.out.analytics", driver_partitions, 7 * DAY_MS),
        TopicSpec("calibre.analytics.metrics", 3, 7 * DAY_MS),
        TopicSpec("calibre.alerts", 1, 7 * DAY_MS),

        TopicSpec("calibre.dlq", 3, 30 * DAY_MS),
        TopicSpec("calibre.side.quarantine", 3, 30 * DAY_MS),
        TopicSpec("calibre.side.overflow", 3, 30 * DAY_MS),

        # --- PULSE BACKWARD-COMPATIBILITY CATALOGUE ---
        TopicSpec("pulse.raw.race_control.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.raw.track_status.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.raw.timing.laps.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.raw.timing.positions.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.raw.telemetry.car.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.raw.weather.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.raw.tyres.stints.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.raw.pit.events.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.raw.session_status.v1", 1, 7 * DAY_MS),

        TopicSpec("pulse.norm.race_events.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.norm.driver_laps.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.norm.driver_state.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.norm.track_segments.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.norm.tyre_stints.v1", driver_partitions, 7 * DAY_MS),

        TopicSpec("pulse.features.vehicle_response.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.features.tyre_stints.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.features.race_context.v1", 1, 7 * DAY_MS),

        TopicSpec("pulse.agent.event_context.findings.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.agent.track_state.findings.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.agent.vehicle_response.findings.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.agent.tyre_strategy.findings.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.agent.race_impact.findings.v1", driver_partitions, 7 * DAY_MS),

        TopicSpec("pulse.intelligence.driver_impact.v1", driver_partitions, 7 * DAY_MS),
        TopicSpec("pulse.intelligence.track_alerts.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.intelligence.strategy_alerts.v1", 1, 7 * DAY_MS),
        TopicSpec("pulse.intelligence.race_timeline.v1", 1, 7 * DAY_MS),

        TopicSpec("pulse.ops.agent_health.v1", 3, 7 * DAY_MS),
        TopicSpec("pulse.ops.pipeline_metrics.v1", 3, 7 * DAY_MS),
        TopicSpec("pulse.dlq", 3, 30 * DAY_MS),
    ]
    return specs


def ensure_topics(admin: AdminClient, specs: list[TopicSpec]) -> None:
    """Idempotent topic creation. Never alters existing topics."""
    md = admin.list_topics(timeout=15)
    existing_topics = set(md.topics.keys())
    missing = [s for s in specs if s.name not in existing_topics]

    if not missing:
        logger.debug("All %d topics in catalogue exist on broker.", len(specs))
        return

    logger.info("Declaring %d missing topics as code...", len(missing))
    new_topics = [
        NewTopic(s.name, num_partitions=s.partitions, replication_factor=RF, config=s.configs())
        for s in missing
    ]

    futs = admin.create_topics(new_topics, operation_timeout=30)
    for topic, f in futs.items():
        try:
            f.result()
            logger.info("Created topic '%s'", topic)
        except KafkaException as e:
            if e.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                logger.error("Failed to create topic %s: %s", topic, e)
                raise


def verify_topics(admin: AdminClient, specs: list[TopicSpec]) -> list[str]:
    """Compares live broker state with the catalogue. Returns problems list (empty if clean)."""
    md = admin.list_topics(timeout=15)
    problems, present = [], []

    for s in specs:
        t = md.topics.get(s.name)
        if t is None or t.error is not None:
            problems.append(f"{s.name}: MISSING")
            continue
        present.append(s)
        if len(t.partitions) != s.partitions:
            problems.append(f"{s.name}: partitions {len(t.partitions)} != {s.partitions}")
        for pid, p in t.partitions.items():
            if p.leader < 0:
                problems.append(f"{s.name}[{pid}]: OFFLINE (leader={p.leader})")
            if len(p.replicas) != RF:
                problems.append(f"{s.name}[{pid}]: RF {len(p.replicas)} != {RF}")
            if len(p.isrs) < MIN_ISR:
                problems.append(f"{s.name}[{pid}]: under-replicated isr {len(p.isrs)} < {MIN_ISR}")

    by = {s.name: s for s in present}
    if by:
        futs = admin.describe_configs([ConfigResource(RESOURCE_TOPIC, n) for n in by])
        for res, f in futs.items():
            try:
                live = f.result()
                wanted_configs = by[res.name].configs()
                for k, want in wanted_configs.items():
                    got = live[k].value if k in live else None
                    if got != want:
                        problems.append(f"{res.name}: {k}={got} != {want}")
            except Exception as e:
                problems.append(f"{res.name}: describe_configs failed: {e}")

    return problems


# ==============================================================================
# 2. DRIVER-AFFINE PARTITIONING (Phase 3)
# ==============================================================================

def _sort_key(d: str) -> tuple[int, int, str]:
    return (0, int(d), "") if d.isdigit() else (1, 0, d)


class DriverSlots:
    """Stable, thread-safe driver -> dense slot map.
    
    Seed from the session DriverList so replays reproduce identical layouts.
    Late drivers (reserves) take the next available slot without shifting existing slots.
    """

    def __init__(self, driver_ids: list[Any] | None = None) -> None:
        self._slots: dict[str, int] = {}
        self._lock = threading.Lock()
        if driver_ids:
            self.seed(driver_ids)

    def seed(self, driver_ids: list[Any]) -> None:
        for d in sorted({str(d) for d in driver_ids if d is not None}, key=_sort_key):
            self.slot(d)

    def slot(self, driver_id: Any) -> int:
        d = str(driver_id)
        with self._lock:
            if d not in self._slots:
                self._slots[d] = len(self._slots)
            return self._slots[d]

    def mapping(self) -> dict[str, int]:
        with self._lock:
            return dict(self._slots)


def driver_partition(slots: DriverSlots, driver_id: Any, num_partitions: int) -> int:
    """Computes deterministic driver-affine partition."""
    if num_partitions <= 1:
        return 0
    return slots.slot(driver_id) % num_partitions


# Global driver slots singleton derived deterministically
_GLOBAL_SLOTS: DriverSlots | None = None


def get_driver_slots() -> DriverSlots:
    global _GLOBAL_SLOTS
    if _GLOBAL_SLOTS is None:
        _GLOBAL_SLOTS = DriverSlots()
    return _GLOBAL_SLOTS


# ==============================================================================
# 3. PRODUCER ARCHITECTURE (Phase 4)
# ==============================================================================

@dataclass
class ProducerStats:
    enqueued: int = 0
    delivered: int = 0
    failed: int = 0
    latency_sum_s: float = 0.0
    latency_max_s: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return (self.latency_sum_s / self.delivered * 1000.0) if self.delivered > 0 else 0.0

    @property
    def max_latency_ms(self) -> float:
        return self.latency_max_s * 1000.0


class CalibreProducer:
    """Production-grade Kafka producer with idempotence, gzip compression, and stats tracking."""

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        client_id: str | None = None,
        transactional_id: str | None = None,
        linger_ms: int = 20,
        compression_type: str = "gzip",
    ) -> None:
        settings = get_settings()
        self.bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
        self.client_id = client_id or f"{settings.instance_id}-producer-{uuid4().hex[:6]}"
        self.transactional_id = transactional_id
        self.slots = get_driver_slots()
        self.stats = ProducerStats()
        self._partition_cache: dict[str, int] = {}
        self._admin: AdminClient | None = None

        conf: dict[str, Any] = {
            "bootstrap.servers": self.bootstrap,
            "client.id": self.client_id,
            "acks": "all",
            "enable.idempotence": True,
            "max.in.flight.requests.per.connection": 5,
            "linger.ms": linger_ms,
            "batch.size": 524288,
            "batch.num.messages": 20000,
            "compression.type": compression_type,
            "delivery.timeout.ms": 120000,
            "queue.buffering.max.messages": 500000,
            "queue.buffering.max.kbytes": 1048576,
        }

        if transactional_id:
            conf["transactional.id"] = transactional_id
            conf["transaction.timeout.ms"] = 60000

        self._p = Producer(conf)
        self.admin = AdminClient({"bootstrap.servers": self.bootstrap})

    def partition_count(self, topic: str) -> int:
        if topic not in self._partition_cache:
            try:
                md = self.admin.list_topics(topic, timeout=10)
                t = md.topics.get(topic)
                self._partition_cache[topic] = len(t.partitions) if t else 1
            except Exception:
                self._partition_cache[topic] = 1
        return self._partition_cache[topic]

    def _on_delivery(self, err: KafkaError | None, msg: Message) -> None:
        if err is not None:
            self.stats.failed += 1
            logger.error("Message delivery failed: %s", err)
            return
        self.stats.delivered += 1
        lat = msg.latency() or 0.0
        self.stats.latency_sum_s += lat
        self.stats.latency_max_s = max(self.stats.latency_max_s, lat)

    def publish(
        self,
        topic: str,
        value: Any,
        *,
        key: str | bytes | None = None,
        driver_id: Any = None,
        headers: dict[str, Any] | None = None,
        correlation_id: str | bytes | None = None,
    ) -> None:
        """Publishes record to Kafka with driver-affine routing and bytes preservation."""
        if isinstance(value, (bytes, bytearray)):
            payload = bytes(value)
        elif isinstance(value, BaseModel):
            payload = value.model_dump_json(by_alias=True).encode("utf-8")
        elif isinstance(value, dict):
            payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        else:
            payload = str(value).encode("utf-8")

        if key is None:
            key_b = None
        elif isinstance(key, bytes):
            key_b = key
        else:
            key_b = str(key).encode("utf-8")

        corr = correlation_id or key_b or b""
        corr_b = corr.encode("utf-8") if isinstance(corr, str) else corr

        hdrs_dict: dict[str, Any] = {
            "content-type": "application/json",
            "correlation_id": corr_b,
        }
        if headers:
            hdrs_dict.update(headers)

        hdrs = [
            (k, v if isinstance(v, bytes) else str(v).encode("utf-8"))
            for k, v in hdrs_dict.items()
            if v is not None
        ]

        if driver_id is not None:
            partition = driver_partition(self.slots, driver_id, self.partition_count(topic))
        else:
            partition = PARTITION_UA

        for _ in range(100):
            try:
                self._p.produce(
                    topic,
                    value=payload,
                    key=key_b,
                    partition=partition,
                    headers=hdrs,
                    on_delivery=self._on_delivery,
                )
                break
            except BufferError:
                self._p.poll(0.2)
        else:
            raise BufferError(f"Local queue stayed full publishing to {topic}")

        self.stats.enqueued += 1
        self._p.poll(0)

    def publish_dlq(self, msg: Message, err: Exception, topic: str = "calibre.dlq") -> None:
        """Publishes poisoned/failed record to DLQ preserving coordinates and error details."""
        orig: dict[str, Any] = {}
        if msg.headers():
            orig = {k: (v if v is not None else b"") for k, v in msg.headers()}

        orig.update({
            "x-error": repr(err)[:500].encode("utf-8"),
            "x-src-topic": (msg.topic() or "").encode("utf-8"),
            "x-src-partition": str(msg.partition() if msg.partition() is not None else -1).encode("utf-8"),
            "x-src-offset": str(msg.offset() if msg.offset() is not None else -1).encode("utf-8"),
            "x-failed-at-ms": str(int(time.time() * 1000)).encode("utf-8"),
        })

        self.publish(
            topic,
            msg.value() or b"",
            key=msg.key() or b"unknown",
            headers=orig,
        )

    def flush(self, timeout: float = 60.0) -> None:
        left = self._p.flush(timeout)
        if left:
            raise TimeoutError(f"{left} message(s) still queued after {timeout}s flush")
        if self.stats.failed:
            raise RuntimeError(f"{self.stats.failed} delivery failure(s) recorded")

    async def publish_async(
        self,
        topic: str,
        value: Any,
        *,
        key: str | bytes | None = None,
        driver_id: Any = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Asynchronously dispatch to producer avoiding blocking the event loop."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.publish(topic, value, key=key, driver_id=driver_id, headers=headers))


# ==============================================================================
# 4. CONSUMER ARCHITECTURE (Phase 5)
# ==============================================================================

class PoisonRecord(Exception):
    """Irrecoverable payload error -> sent immediately to DLQ."""
    pass


class RetryableError(Exception):
    """Transient operational error -> backoff, retry, then DLQ."""
    pass


class CalibreConsumer:
    """Production consumer with cooperative-sticky rebalance, read_committed, and lag monitoring."""

    def __init__(
        self,
        topics: list[str],
        group_id: str,
        bootstrap_servers: str | None = None,
        auto_offset_reset: str = "earliest",
        group_instance_id: str | None = None,
        enable_auto_commit: bool = True,
        max_retries: int = 3,
        dlq_producer: CalibreProducer | None = None,
    ) -> None:
        settings = get_settings()
        self.bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
        self.topics = topics
        self.group_id = group_id
        self.max_retries = max_retries
        self.dlq = dlq_producer or CalibreProducer(bootstrap_servers=self.bootstrap)

        conf: dict[str, Any] = {
            "bootstrap.servers": self.bootstrap,
            "group.id": self.group_id,
            "partition.assignment.strategy": "cooperative-sticky",
            "auto.offset.reset": auto_offset_reset,
            "isolation.level": "read_committed",
            "enable.auto.commit": enable_auto_commit,
            "enable.auto.offset.store": False,
            "auto.commit.interval.ms": 5000,
            "session.timeout.ms": 45000,
            "heartbeat.interval.ms": 3000,
            "max.poll.interval.ms": 300000,
            "fetch.min.bytes": 1,
            "fetch.wait.max.ms": 100,
            "topic.metadata.refresh.interval.ms": 30000,
        }

        if group_instance_id:
            conf["group.instance.id"] = group_instance_id

        self._c = Consumer(conf)

    def _on_assign(self, consumer: Consumer, partitions: list[TopicPartition]) -> None:
        logger.info("Partitions assigned: %s", partitions)

    def _on_revoke(self, consumer: Consumer, partitions: list[TopicPartition]) -> None:
        logger.info("Partitions revoked: %s", partitions)
        try:
            consumer.commit(asynchronous=False)
        except KafkaException as e:
            if e.args[0].code() != KafkaError._NO_OFFSET:
                logger.warning("Commit error on revoke: %s", e)

    def lag(self) -> int:
        """Returns total lag across assigned partitions."""
        total = 0
        try:
            assigned = self._c.assignment()
            if not assigned:
                return 0
            positions = self._c.position(assigned)
            for tp in positions:
                if tp.offset >= 0:
                    _, high = self._c.get_watermark_offsets(tp, cached=True)
                    total += max(high - tp.offset, 0)
        except Exception as e:
            logger.debug("Error computing lag: %s", e)
        return total

    def run(self, handler: Callable[[Message], None], stop_event: threading.Event) -> None:
        """Main processing loop with poison pill DLQ routing and manual offset storing."""
        self._c.subscribe(self.topics, on_assign=self._on_assign, on_revoke=self._on_revoke)
        last_lag_log = time.time()

        try:
            while not stop_event.is_set():
                if time.time() - last_lag_log > 10.0:
                    logger.info("Consumer group [%s] current lag: %d", self.group_id, self.lag())
                    last_lag_log = time.time()

                msgs = self._c.consume(num_messages=500, timeout=1.0)
                for m in msgs:
                    if m.error():
                        if m.error().code() == KafkaError._PARTITION_EOF:
                            continue
                        if m.error().fatal():
                            raise KafkaException(m.error())
                        continue

                    # Process with retries
                    for attempt in range(self.max_retries + 1):
                        try:
                            handler(m)
                            break
                        except RetryableError as e:
                            if attempt == self.max_retries:
                                self.dlq.publish_dlq(m, e)
                                self.dlq.flush(10.0)
                                break
                            time.sleep(min(0.1 * (2 ** attempt), 5.0))
                        except Exception as e:
                            self.dlq.publish_dlq(m, e)
                            self.dlq.flush(10.0)
                            break

                    self._c.store_offsets(m)
        finally:
            self._c.close()


# ==============================================================================
# 5. EXACTLY-ONCE CONSUME-TRANSFORM-PRODUCE (Phase 6)
# ==============================================================================

@dataclass
class TransformOutput:
    topic: str
    value: Any
    key: str | bytes | None = None
    driver_id: Any = None
    headers: dict[str, Any] | None = None


class TransactionalProcessor:
    """Transactional Kafka-to-Kafka processor with exactly-once semantics inside Kafka."""

    def __init__(
        self,
        stage_name: str,
        input_topics: list[str],
        instance_id: str | None = None,
        bootstrap_servers: str | None = None,
    ) -> None:
        settings = get_settings()
        self.stage_name = stage_name
        self.input_topics = input_topics
        self.instance_id = instance_id or f"{settings.instance_id}-{stage_name}"
        self.bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
        self.transactional_id = f"calibre-{stage_name}-{self.instance_id}"

        # Transactional Producer
        self.producer = CalibreProducer(
            bootstrap_servers=self.bootstrap,
            transactional_id=self.transactional_id,
        )

        # Consumer configured for transactions (auto-commit disabled)
        self.consumer_conf = {
            "bootstrap.servers": self.bootstrap,
            "group.id": f"calibre-group-{stage_name}",
            "partition.assignment.strategy": "cooperative-sticky",
            "auto.offset.reset": "earliest",
            "isolation.level": "read_committed",
            "enable.auto.commit": False,
            "session.timeout.ms": 45000,
            "heartbeat.interval.ms": 3000,
            "max.poll.interval.ms": 300000,
        }
        self.consumer = Consumer(self.consumer_conf)

    def _rewind(self) -> None:
        """Rewinds uncommitted offsets on aborted transactions."""
        committed = self.consumer.committed(self.consumer.assignment(), timeout=30)
        for tp in committed:
            if tp.offset < 0:
                tp.offset = OFFSET_BEGINNING
            self.consumer.seek(tp)

    def run(
        self,
        transform_fn: Callable[[Message], Generator[TransformOutput, None, None]],
        stop_event: threading.Event,
        batch_size: int = 200,
        batch_timeout_s: float = 0.1,
    ) -> None:
        """Executes transactional loop committing transformed records & consumer offsets together."""
        self.producer._p.init_transactions()
        self.consumer.subscribe(self.input_topics)

        try:
            while not stop_event.is_set():
                batch: list[Message] = []
                t0 = time.time()
                while len(batch) < batch_size and (time.time() - t0) < batch_timeout_s:
                    msgs = self.consumer.consume(num_messages=batch_size - len(batch), timeout=0.05)
                    for m in msgs:
                        if not m.error():
                            batch.append(m)

                if not batch:
                    continue

                # Execute Transaction
                p = self.producer._p
                p.begin_transaction()
                try:
                    for m in batch:
                        try:
                            for out in transform_fn(m):
                                self.producer.publish(
                                    out.topic,
                                    out.value,
                                    key=out.key,
                                    driver_id=out.driver_id,
                                    headers=out.headers,
                                )
                        except Exception as e:
                            self.producer.publish_dlq(m, e)

                    offsets = [
                        TopicPartition(tp.topic, tp.partition, tp.offset)
                        for tp in self.consumer.position(self.consumer.assignment())
                        if tp.offset >= 0
                    ]
                    p.send_offsets_to_transaction(offsets, self.consumer.consumer_group_metadata())
                    p.commit_transaction()
                except KafkaException as e:
                    if e.args[0].fatal():
                        raise
                    p.abort_transaction()
                    self._rewind()
                except Exception as e:
                    logger.error("Transaction failed: %s, aborting and rewinding...", e)
                    p.abort_transaction()
                    self._rewind()
                    raise
        finally:
            self.consumer.close()


# ==============================================================================
# 6. IDEMPOTENT SINK WITH (TOPIC, PARTITION, OFFSET) (Phase 7)
# ==============================================================================

class IdempotentVerdictSink:
    """Idempotent SQLite sink enforcing (topic, partition, offset) unique constraint under WAL mode."""

    def __init__(self, db_path: str | Path = "verdicts.db") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS verdicts (
                    topic TEXT,
                    partition INTEGER,
                    offset INTEGER,
                    key TEXT,
                    value TEXT,
                    created_at_utc TEXT,
                    PRIMARY KEY (topic, partition, offset)
                );
            """)

    def has_verdict(self, topic: str, partition: int, offset: int) -> bool:
        """Returns True if (topic, partition, offset) was already recorded."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM verdicts WHERE topic = ? AND partition = ? AND offset = ? LIMIT 1",
                (topic, partition, offset),
            )
            return cur.fetchone() is not None

    def insert_verdict(self, topic: str, partition: int, offset: int, key: str, value: str) -> bool:
        """Inserts record idempotently. Returns True if newly inserted, False if ignored."""
        try:
            with self._lock, self._conn:
                cur = self._conn.cursor()
                cur.execute(
                    "INSERT OR IGNORE INTO verdicts VALUES (?, ?, ?, ?, ?, ?)",
                    (topic, partition, offset, key, value, datetime.now(timezone.utc).isoformat()),
                )
                return cur.rowcount > 0
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                raise RetryableError(f"Database locked: {e}") from e
            raise PoisonRecord(f"Database operational error: {e}") from e
        except Exception as e:
            raise PoisonRecord(f"Failed to insert verdict: {e}") from e

    def count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM verdicts")
            return int(cur.fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ==============================================================================
# 7. UNIFIED BROKER / CLIENT WRAPPER (Drop-in compatibility)
# ==============================================================================

class UnifiedKafkaBroker:
    """Drop-in unified Kafka broker replacement managing admin, producers, and topic catalogue."""

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        settings = get_settings()
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self.admin = AdminClient({"bootstrap.servers": self.bootstrap_servers})
        self.producer = CalibreProducer(bootstrap_servers=self.bootstrap_servers)
        self.slots = get_driver_slots()
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def start(self) -> None:
        """Starts broker transport and verifies KRaft cluster connectivity."""
        try:
            md = self.admin.list_topics(timeout=10)
            if not md.brokers:
                raise RuntimeError("No Kafka brokers returned from cluster metadata")
            self._is_connected = True
            logger.info("Connected to Kafka KRaft cluster with %d active brokers.", len(md.brokers))

            # Ensure all topics from the catalogue exist explicitly
            settings = get_settings()
            catalogue = build_topic_catalogue(driver_partitions=settings.driver_partitions)
            ensure_topics(self.admin, catalogue)
        except Exception as e:
            self._is_connected = False
            logger.error("Failed to connect to Kafka cluster at %s: %s", self.bootstrap_servers, e)
            raise

    async def ensure_topics(self, extra_topics: list[str] | None = None) -> None:
        settings = get_settings()
        catalogue = build_topic_catalogue(driver_partitions=settings.driver_partitions)
        if extra_topics:
            existing = {s.name for s in catalogue}
            for t in extra_topics:
                if t not in existing:
                    catalogue.append(TopicSpec(t, 1, 7 * DAY_MS))
        ensure_topics(self.admin, catalogue)

    async def publish(
        self,
        topic: str,
        key: str,
        value: Any,
        driver_id: Any = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        await self.producer.publish_async(topic, value, key=key, driver_id=driver_id, headers=headers)

    def publish_sync(
        self,
        topic: str,
        key: str,
        value: Any,
        driver_id: Any = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        self.producer.publish(topic, value, key=key, driver_id=driver_id, headers=headers)

    async def stop(self) -> None:
        try:
            self.producer.flush(15.0)
        except Exception as e:
            logger.debug("Error flushing producer on stop: %s", e)
        self._is_connected = False
        logger.info("Kafka broker transport stopped.")


_unified_broker: UnifiedKafkaBroker | None = None


def get_unified_broker() -> UnifiedKafkaBroker:
    global _unified_broker
    if _unified_broker is None:
        _unified_broker = UnifiedKafkaBroker()
    return _unified_broker


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="CALIBRE Kafka Topic & Broker Manager")
    parser.add_argument("--verify", action="store_true", help="Verify live broker matches topic catalogue")
    parser.add_argument("--ensure", action="store_true", help="Ensure all topics exist from catalogue")
    parser.add_argument("--driver-partitions", type=int, default=11, help="Driver tier partition count")
    args = parser.parse_args()

    settings = get_settings()
    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})
    catalogue = build_topic_catalogue(driver_partitions=args.driver_partitions)

    if args.ensure or (not args.verify):
        ensure_topics(admin, catalogue)
        print(f"[OK] Ensured {len(catalogue)} topics from catalogue on {settings.kafka_bootstrap_servers}")

    if args.verify or (not args.ensure):
        problems = verify_topics(admin, catalogue)
        if problems:
            print(f"[FAIL] Topic verification detected {len(problems)} drift issue(s):")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        else:
            print(f"[OK] All {len(catalogue)} topics verified against live broker with zero drift.")
            sys.exit(0)
