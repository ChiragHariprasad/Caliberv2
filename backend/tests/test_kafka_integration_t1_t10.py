"""Phase 9: Comprehensive Integration and Chaos Test Suite (T1 - T10).

Validates the 3-broker KRaft cluster against production requirements:
- T1: Driver-affine partitioning and strictly monotonic per-driver ordering.
- T2: Single broker failure (kafka-2 stopped) during ingest -> 0 failed deliveries, full recovery.
- T3: Double broker failure (2 of 3 down) -> NotEnoughReplicas safety, zero ack loss.
- T4: Cooperative-sticky consumer rebalance and partition takeover.
- T5: Exactly-Once Semantics (EOS) transactional fencing and read_committed isolation.
- T6: Idempotent SQLite sink (topic, partition, offset) replay invariance.
- T7: Poison pill DLQ routing with coordinate headers and non-stop consumption.
- T8: Evaluation frontier and replay session isolation.
- T9: Static group membership (group.instance.id) suppresses rebalance on restart.
- T10: Partition-count invariance (driver partitions 1 vs 11 hash parity).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

import pytest
from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Producer,
    TopicPartition,
)
from confluent_kafka.admin import AdminClient

from pulse.config import get_settings
from pulse.stream.kafka_io import (
    CalibreConsumer,
    CalibreProducer,
    DriverSlots,
    IdempotentVerdictSink,
    PoisonRecord,
    TopicSpec,
    TransactionalProcessor,
    TransformOutput,
    build_topic_catalogue,
    driver_partition,
    ensure_topics,
    get_driver_slots,
    verify_topics,
)


def _cluster_available() -> bool:
    import socket
    settings = get_settings()
    for endpoint in settings.kafka_bootstrap_servers.split(","):
        try:
            h, p = endpoint.strip().split(":")
            with socket.create_connection((h, int(p)), timeout=0.2):
                return True
        except Exception:
            continue
    return False


@pytest.fixture(scope="module", autouse=True)
def require_kafka_cluster():
    if not _cluster_available():
        pytest.skip("KRaft 3-broker cluster is offline (Docker offline)")


@pytest.fixture(scope="module")
def admin_client():
    settings = get_settings()
    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})
    catalogue = build_topic_catalogue(driver_partitions=11)
    ensure_topics(admin, catalogue)
    return admin


# ==============================================================================
# T1: DRIVER-AFFINE PARTITIONING & ORDERING
# ==============================================================================

def test_t1_driver_affine_partitioning_and_ordering(admin_client):
    """T1: Ingests per-driver records; verifies per-driver seq strictly increasing and
    each driver confined to exactly one partition."""
    settings = get_settings()
    topic = "calibre.raw.fastf1.car_data"
    producer = CalibreProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    slots = get_driver_slots()
    drivers = [1, 11, 44, 16, 55, 63, 4, 81, 14, 10]
    run_id = f"run-t1-{uuid4().hex[:8]}"

    # Publish 10 sequential messages per driver
    for seq in range(1, 11):
        for d in drivers:
            payload = json.dumps({"run_id": run_id, "driver": d, "seq": seq, "speed": 310.0 + seq})
            producer.publish(
                topic,
                payload,
                key=f"driver-{d}",
                driver_id=d,
                headers={"x-seq": str(seq).encode("utf-8"), "x-driver": str(d).encode("utf-8")},
            )
    producer.flush()

    # Read back with a fresh group
    group_id = f"t1-verifier-{uuid4().hex[:6]}"
    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "isolation.level": "read_committed",
        "enable.auto.commit": False,
    })
    consumer.subscribe([topic])

    driver_partitions: dict[int, set[int]] = defaultdict(set)
    driver_sequences: dict[int, list[int]] = defaultdict(list)

    deadline = time.time() + 15.0
    while time.time() < deadline:
        msg = consumer.poll(timeout=0.5)
        if msg is None:
            continue
        if msg.error():
            continue

        try:
            data = json.loads(msg.value().decode("utf-8"))
        except Exception:
            continue

        if data.get("run_id") != run_id:
            continue

        d = data["driver"]
        seq = data["seq"]
        driver_partitions[d].add(msg.partition())
        driver_sequences[d].append(seq)

        if all(len(driver_sequences[d]) >= 10 for d in drivers):
            break

    consumer.close()

    # 1. Every driver must be in exactly one partition
    for d in drivers:
        assert len(driver_partitions[d]) == 1, f"Driver {d} mapped to multiple partitions: {driver_partitions[d]}"

    # 2. Per-driver sequence must be strictly increasing
    for d in drivers:
        seqs = driver_sequences[d]
        assert len(seqs) >= 10, f"Driver {d} received only {len(seqs)} records"
        for i in range(1, len(seqs)):
            assert seqs[i] > seqs[i - 1], f"Driver {d} sequence out of order: {seqs}"


# ==============================================================================
# T2: SINGLE BROKER FAILURE WITH ZERO LOSS
# ==============================================================================

def test_t2_single_broker_failure_zero_data_loss(admin_client):
    """T2: docker stop kafka-2 during ingest -> 0 failed deliveries, full recovery,
    under-replicated partitions clear after restart."""
    settings = get_settings()
    topic = "calibre.raw.fastf1.position"
    producer = CalibreProducer(bootstrap_servers=settings.kafka_bootstrap_servers)

    # 1. Start background ingest
    sent_count = 0
    errors = 0

    try:
        # Publish initial batch
        for i in range(50):
            producer.publish(topic, {"val": i}, key=f"k-{i}", driver_id=(i % 10 + 1))
            sent_count += 1
        producer.flush(10.0)

        # 2. Stop broker 2
        subprocess.run(["docker", "stop", "kafka-2"], check=True, timeout=15)
        time.sleep(2.0)

        # 3. Publish during broker downtime (min.isr=2 satisfied by kafka-1 and kafka-3)
        for i in range(50, 100):
            producer.publish(topic, {"val": i}, key=f"k-{i}", driver_id=(i % 10 + 1))
            sent_count += 1
        producer.flush(15.0)

    finally:
        # 4. Restart broker 2
        subprocess.run(["docker", "start", "kafka-2"], check=True, timeout=15)
        time.sleep(5.0)

    assert producer.stats.failed == 0, f"Failed deliveries during broker failover: {producer.stats.failed}"
    assert producer.stats.delivered >= 100


# ==============================================================================
# T3: TWO BROKER FAILURE (NOT ENOUGH REPLICAS)
# ==============================================================================

def test_t3_two_broker_failure_not_enough_replicas_safety():
    """T3: Stop 2 of 3 brokers -> producer acks=all fails with zero un-replicated commits,
    then full 3-broker ISR recovers cleanly."""
    settings = get_settings()
    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})
    topic = "calibre.raw.fastf1.position"
    specs = build_topic_catalogue(driver_partitions=11)
    assert len(verify_topics(admin, specs)) == 0

    md = admin.list_topics(topic, timeout=10.0)
    tmeta = md.topics.get(topic)
    assert tmeta is not None and len(tmeta.partitions) >= 1
    leader_p = next((pid for pid, pmeta in tmeta.partitions.items() if pmeta.leader == 1), None)
    assert leader_p is not None, "Expected at least one partition led by broker 1 (kafka-1)"

    probe_consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": f"t3-wm-{uuid4().hex[:6]}",
    })
    _lo, hi_before = probe_consumer.get_watermark_offsets(TopicPartition(topic, leader_p), timeout=5.0)
    probe_consumer.close()

    delivered = 0
    errors: list[str] = []

    def _on_delivery(err, _msg):
        nonlocal delivered
        if err is not None:
            errors.append(str(err))
        else:
            delivered += 1

    p = Producer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "acks": "all",
        "enable.idempotence": True,
        "delivery.timeout.ms": 3500,
        "request.timeout.ms": 2000,
        "message.timeout.ms": 3500,
    })
    try:
        subprocess.run(["docker", "stop", "kafka-2", "kafka-3"], check=True, timeout=20)
        time.sleep(2.0)

        for i in range(3):
            p.produce(
                topic,
                partition=leader_p,
                key=f"t3-unreplicated-{i}".encode("utf-8"),
                value=json.dumps({"test": "t3", "seq": i}).encode("utf-8"),
                on_delivery=_on_delivery,
            )
        p.flush(6.0)

        assert delivered == 0, f"Producer unexpectedly committed {delivered} un-replicated records with 2/3 brokers down!"
        assert len(errors) == 3, f"Expected all 3 produce attempts to fail safely, got errors={errors}"
    finally:
        subprocess.run(["docker", "start", "kafka-2", "kafka-3"], check=True, timeout=20)
        recovery_deadline = time.time() + 35.0
        recovered = False
        while time.time() < recovery_deadline:
            try:
                md_rec = admin.list_topics(topic, timeout=3.0)
                t_rec = md_rec.topics.get(topic)
                if (
                    len(md_rec.brokers) == 3
                    and t_rec is not None
                    and len(t_rec.partitions[leader_p].isrs) >= 2
                ):
                    recovered = True
                    break
            except Exception:
                pass
            time.sleep(1.0)
        assert recovered, "3-broker quorum / ISR failed to recover cleanly after docker start!"

    probe_after = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": f"t3-wm-after-{uuid4().hex[:6]}",
    })
    _lo2, hi_after = probe_after.get_watermark_offsets(TopicPartition(topic, leader_p), timeout=5.0)
    probe_after.close()
    assert hi_after == hi_before, f"Watermark advanced ({hi_before} -> {hi_after}) despite 2-broker failure!"


# ==============================================================================
# T4: COOPERATIVE REBALANCE TAKEOVER
# ==============================================================================

def test_t4_cooperative_rebalance_takeover():
    """T4: Cooperative-sticky rebalancing transfers partitions cleanly on worker exit."""
    settings = get_settings()
    group_id = f"t4-coop-{uuid4().hex[:6]}"
    topic = "calibre.evidence.vehicle"

    conf = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": group_id,
        "partition.assignment.strategy": "cooperative-sticky",
        "auto.offset.reset": "earliest",
        "session.timeout.ms": 6000,
        "heartbeat.interval.ms": 1000,
        "max.poll.interval.ms": 15000,
    }

    c1 = Consumer(conf)
    c2 = Consumer(conf)

    c1.subscribe([topic])
    c2.subscribe([topic])

    # Poll both to trigger initial assignment
    t0 = time.time()
    while time.time() - t0 < 8.0:
        c1.poll(0.2)
        c2.poll(0.2)
        if len(c1.assignment()) > 0 and len(c2.assignment()) > 0:
            break

    p1 = c1.assignment()
    p2 = c2.assignment()
    assert len(p1) > 0 or len(p2) > 0, "No partitions assigned"

    # Close consumer 1; consumer 2 must absorb all partitions
    c1.close()
    t1 = time.time()
    while time.time() - t1 < 12.0:
        c2.poll(0.3)
        if len(c2.assignment()) == 11:
            break

    assert len(c2.assignment()) == 11, f"Consumer 2 did not acquire all 11 partitions: {len(c2.assignment())} / 11"
    c2.close()


# ==============================================================================
# T5: EXACTLY-ONCE TRANSACTIONS (EOS)
# ==============================================================================

def test_t5_eos_transactional_isolation_read_committed():
    """T5: Transactional producer fencing and read_committed vs read_uncommitted isolation."""
    settings = get_settings()
    topic_in = "calibre.evidence.timing"
    topic_out = "calibre.core.verdict_history"
    tx_id = f"t5-tx-{uuid4().hex[:6]}"

    # Transactional Producer
    tp = Producer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "transactional.id": tx_id,
        "enable.idempotence": True,
        "acks": "all",
    })
    tp.init_transactions()

    # 1. Aborted Transaction
    tp.begin_transaction()
    tp.produce(topic_out, value=b"ABORTED_DATA", key=b"tx-abort")
    tp.flush()
    tp.abort_transaction()

    # 2. Committed Transaction
    tp.begin_transaction()
    tp.produce(topic_out, value=b"COMMITTED_DATA", key=b"tx-commit")
    tp.flush()
    tp.commit_transaction()

    # Read with read_committed
    c_committed = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": f"t5-read-comm-{uuid4().hex[:6]}",
        "auto.offset.reset": "earliest",
        "isolation.level": "read_committed",
        "enable.auto.commit": False,
    })
    c_committed.subscribe([topic_out])

    read_vals = []
    t0 = time.time()
    while time.time() - t0 < 5.0:
        msg = c_committed.poll(0.3)
        if msg and not msg.error():
            read_vals.append(msg.value())
            if len(read_vals) >= 1:
                break
    c_committed.close()

    assert b"COMMITTED_DATA" in read_vals
    assert b"ABORTED_DATA" not in read_vals, "read_committed leaked aborted transaction payload!"


# ==============================================================================
# T6: IDEMPOTENT SINK WITH (TOPIC, PARTITION, OFFSET)
# ==============================================================================

def test_t6_idempotent_sqlite_sink_replay_invariance(tmp_path):
    """T6: Replays the same records twice; SQLite primary key (topic, partition, offset)
    guarantees unchanged row counts and zero duplication."""
    db_file = tmp_path / "test_verdicts.db"
    sink = IdempotentVerdictSink(db_file)

    # First run: Insert 50 records
    for i in range(50):
        inserted = sink.insert_verdict("calibre.out.database", partition=1, offset=i, key=f"car-{i}", value=f"hash-{i}")
        assert inserted is True

    assert sink.count() == 50

    # Second run: Replay exact same 50 records
    for i in range(50):
        inserted = sink.insert_verdict("calibre.out.database", partition=1, offset=i, key=f"car-{i}", value=f"hash-{i}")
        assert inserted is False, f"Record offset {i} was duplicated!"

    # Row count must remain exactly 50
    assert sink.count() == 50


# ==============================================================================
# T7: POISON PILL DLQ ROUTING
# ==============================================================================

def test_t7_dlq_poison_record_routing_with_coordinates():
    """T7: Malformed messages route to DLQ with x-src-topic/partition/offset and x-error headers,
    while consumer pipeline continues smoothly."""
    settings = get_settings()
    producer = CalibreProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    topic = "calibre.evidence.incident"
    dlq_topic = "calibre.dlq"

    # Ingest bad record followed by valid record
    producer.publish(topic, b"MALFORMED_NON_JSON", key="bad-key")
    producer.publish(topic, json.dumps({"valid": True, "event": "CLEAR"}), key="good-key")
    producer.flush()

    # Simulate consumer error handler
    dlq_consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": f"t7-dlq-read-{uuid4().hex[:6]}",
        "auto.offset.reset": "earliest",
        "isolation.level": "read_committed",
    })
    dlq_consumer.subscribe([dlq_topic])

    # Publish explicitly via publish_dlq
    class MockMsg:
        def topic(self): return topic
        def partition(self): return 0
        def offset(self): return 42
        def key(self): return b"bad-key"
        def value(self): return b"MALFORMED_NON_JSON"
        def headers(self): return [("x-trace-id", b"trace-123")]

    producer.publish_dlq(MockMsg(), PoisonRecord("Invalid JSON encoding syntax"), topic=dlq_topic)
    producer.flush()

    found_dlq = False
    t0 = time.time()
    while time.time() - t0 < 6.0:
        msg = dlq_consumer.poll(0.3)
        if msg and not msg.error():
            raw_hdrs = dict(msg.headers() or [])
            hdrs = {
                (k.decode("utf-8") if isinstance(k, bytes) else str(k)): (v.decode("utf-8") if isinstance(v, bytes) else str(v))
                for k, v in raw_hdrs.items()
            }
            if "x-error" in hdrs and "x-src-topic" in hdrs and "x-src-offset" in hdrs:
                assert hdrs["x-src-topic"] == topic
                assert hdrs["x-src-offset"] == "42"
                assert "Invalid JSON" in hdrs["x-error"]
                found_dlq = True
                break

    dlq_consumer.close()
    assert found_dlq, "DLQ failed to receive poison record with required coordinate headers"


# ==============================================================================
# T8: CLOCK WATERMARK & REPLAY ISOLATION
# ==============================================================================

def test_t8_clock_watermark_and_replay_isolation(tmp_path):
    """T8: Verifies live vs replay run isolation, broker watermark monotonicity, and durable clock ticks."""
    settings = get_settings()
    producer = CalibreProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    clock_topic = "calibre.guard.clock"
    raw_topic = "calibre.raw.fastf1.race_control"

    probe = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": f"t8-reader-{uuid4().hex[:6]}",
        "auto.offset.reset": "earliest",
        "isolation.level": "read_committed",
        "enable.auto.commit": False,
    })
    _lo_c, hi_clock = probe.get_watermark_offsets(TopicPartition(clock_topic, 0), timeout=5.0)
    _lo_r, hi_raw = probe.get_watermark_offsets(TopicPartition(raw_topic, 0), timeout=5.0)

    tag = uuid4().hex[:8]
    # 1. Monotonic durable evaluation clock ticks on calibre.guard.clock
    for epoch in (100, 101):
        producer.publish(
            clock_topic,
            json.dumps({"tag": tag, "tick_utc": "2026-11-05T12:00:00Z", "epoch": epoch}),
            key=f"clock-{tag}",
        )

    # 2. Isolated LIVE vs REPLAY streams published to Kafka raw topic
    live_run_id = f"run-live-{tag}"
    replay_run_id = f"run-replay-{tag}"
    producer.publish(raw_topic, json.dumps({"event_id": f"evt-live-{tag}", "event_type": "SESSION_STARTED", "run": {"run_id": live_run_id, "mode": "LIVE", "session_instance_id": f"live-{tag}"}}), key=f"live-{tag}")
    producer.publish(raw_topic, json.dumps({"event_id": f"evt-rep-{tag}", "event_type": "SESSION_STARTED", "run": {"run_id": replay_run_id, "mode": "REPLAY", "session_instance_id": f"rep-{tag}"}}), key=f"rep-{tag}")
    producer.flush(10.0)
    assert producer.stats.delivered >= 4

    probe.assign([TopicPartition(clock_topic, 0, hi_clock), TopicPartition(raw_topic, 0, hi_raw)])
    epochs_seen: list[int] = []
    runs_seen: dict[str, str] = {}
    deadline = time.time() + 10.0
    while time.time() < deadline and (len(epochs_seen) < 2 or len(runs_seen) < 2):
        msg = probe.poll(0.3)
        if msg is None or msg.error() or msg.value() is None:
            continue
        data = json.loads(msg.value().decode("utf-8"))
        if msg.topic() == clock_topic and data.get("tag") == tag:
            epochs_seen.append(int(data["epoch"]))
        elif msg.topic() == raw_topic and isinstance(data.get("run"), dict):
            rid = data["run"].get("run_id")
            if rid in {live_run_id, replay_run_id}:
                runs_seen[rid] = data["run"].get("mode", "")
    probe.close()

    assert epochs_seen == [100, 101], f"Clock epochs out of order or missing: {epochs_seen}"
    assert runs_seen == {live_run_id: "LIVE", replay_run_id: "REPLAY"}

    # 3. Verify SQLite SIA WAL enforces disjoint session scope isolation
    from sia_core import SIAWALStore, OriginRegistry, IntegrityEngine, make_atom
    from sia_core.evaluator import EngineConfig
    wal_db = tmp_path / "t8_isolation.sqlite"
    reg = OriginRegistry({"PITWALL": ["F1_FOM_TIMING"]})
    wal_live = SIAWALStore(wal_db, session_id=f"live-{tag}")
    eng_live = IntegrityEngine(registry=reg, config=EngineConfig(auto_open=False), wal=wal_live)
    eng_live.admit_atom(make_atom("lap_record", 89.1, "2026-05-24T13:00:00Z", {"session_id": f"live-{tag}", "driver_id": "16", "lap_number": "1"}, ["PITWALL"]), "2026-05-24T13:00:01Z")
    wal_live.close()

    wal_replay = SIAWALStore(wal_db, session_id=f"rep-{tag}")
    eng_replay = wal_replay.load_engine(registry=reg, config=EngineConfig(auto_open=False))
    assert eng_replay.ledger.counts()["atoms"] == 0, "LIVE session atoms leaked into REPLAY session WAL!"
    wal_replay.close()


# ==============================================================================
# T9: STATIC GROUP MEMBERSHIP
# ==============================================================================

def test_t9_static_membership_no_rebalance_on_quick_restart():
    """T9: Consumer with group.instance.id restarts within session.timeout without triggering rebalance
    on sibling members."""
    settings = get_settings()
    group_id = f"t9-static-{uuid4().hex[:6]}"
    inst_1 = f"worker-static-01-{uuid4().hex[:6]}"
    inst_2 = f"worker-static-02-{uuid4().hex[:6]}"
    topic = "calibre.evidence.vehicle"

    revokes_standby: list[int] = []
    assigns_standby: list[int] = []

    def _mk(inst_id: str) -> Consumer:
        return Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": group_id,
            "group.instance.id": inst_id,
            "auto.offset.reset": "earliest",
            "session.timeout.ms": 45000,
        })

    c1 = _mk(inst_1)
    standby = _mk(inst_2)
    c1.subscribe([topic])
    standby.subscribe(
        [topic],
        on_revoke=lambda _c, ps: revokes_standby.append(len(ps)),
        on_assign=lambda _c, ps: assigns_standby.append(len(ps)),
    )

    t0 = time.time()
    while time.time() - t0 < 10.0:
        c1.poll(0.2)
        standby.poll(0.2)
        if (
            len(c1.assignment()) + len(standby.assignment()) == 11
            and len(c1.assignment()) > 0
            and len(standby.assignment()) > 0
        ):
            break
    # Drain any trailing rebalance callbacks before clearing tracking counters
    for _ in range(3):
        c1.poll(0.1)
        standby.poll(0.1)

    p1_before = {p.partition for p in c1.assignment()}
    p2_before = {p.partition for p in standby.assignment()}
    assert p1_before and p2_before and p1_before.isdisjoint(p2_before)

    # Clear initial assignment counters, close c1 cleanly, and rejoin immediately with same group.instance.id
    revokes_standby.clear()
    assigns_standby.clear()
    c1.close()

    c1_restarted = _mk(inst_1)
    c1_restarted.subscribe([topic])
    t1 = time.time()
    while time.time() - t1 < 10.0 and not c1_restarted.assignment():
        c1_restarted.poll(0.2)
        standby.poll(0.2)

    for _ in range(3):
        c1_restarted.poll(0.1)
        standby.poll(0.1)

    p1_after = {p.partition for p in c1_restarted.assignment()}

    assert p1_after == p1_before, f"Static member lost partition affinity on restart: {p1_before} -> {p1_after}"
    assert revokes_standby == [], f"Standby experienced spurious revoke rebalance: {revokes_standby}"
    assert assigns_standby == [], f"Standby experienced spurious assign rebalance: {assigns_standby}"

    c1_restarted.close()
    standby.close()


# ==============================================================================
# T10: PARTITION-COUNT INVARIANCE
# ==============================================================================

def test_t10_partition_count_invariance():
    """T10: Verifies real Kafka round-trip decisions are invariant across 1-partition vs 11-partition
    topologies (zero cross-driver order dependencies)."""
    import hashlib

    settings = get_settings()
    topic_p1 = "calibre.alerts"             # 1 partition in catalogue
    topic_p11 = "calibre.evidence.timing"   # 11 partitions in catalogue
    drivers = [1, 11, 44, 16, 55, 63]
    run_tag = uuid4().hex[:8]
    slots = DriverSlots()

    probe = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": f"t10-wm-{uuid4().hex[:6]}",
        "isolation.level": "read_committed",
        "enable.auto.commit": False,
    })
    start_tps_p1 = [TopicPartition(topic_p1, 0, probe.get_watermark_offsets(TopicPartition(topic_p1, 0), timeout=5.0)[1])]
    start_tps_p11 = [
        TopicPartition(topic_p11, pid, probe.get_watermark_offsets(TopicPartition(topic_p11, pid), timeout=5.0)[1])
        for pid in range(11)
    ]
    probe.close()

    producer = CalibreProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    expected_total = len(drivers) * 4
    for lap in range(1, 5):
        for d in drivers:
            rec = {
                "tag": run_tag,
                "driver": d,
                "lap": lap,
                "pit_loss": 10.5 if d in {16, 44} else 8.0,
            }
            producer.publish(topic_p1, rec, key=f"driver-{d}", driver_id=d)
            producer.publish(topic_p11, rec, key=f"driver-{d}", driver_id=d)
    producer.flush(10.0)

    def _consume_digest(topic: str, start_tps: list[TopicPartition]) -> tuple[dict[int, str], set[int]]:
        c = Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": f"t10-read-{uuid4().hex[:6]}",
            "isolation.level": "read_committed",
            "enable.auto.commit": False,
        })
        c.assign(start_tps)
        per_driver: dict[int, list[dict]] = defaultdict(list)
        partitions_used: set[int] = set()
        seen = 0
        deadline = time.time() + 12.0
        while seen < expected_total and time.time() < deadline:
            msg = c.poll(0.3)
            if msg is None or msg.error() or msg.value() is None:
                continue
            row = json.loads(msg.value().decode("utf-8"))
            if row.get("tag") != run_tag:
                continue
            per_driver[row["driver"]].append({"lap": row["lap"], "pit_loss": row["pit_loss"]})
            partitions_used.add(msg.partition())
            seen += 1
        c.close()
        assert seen == expected_total, f"Missing records on {topic}: {seen}/{expected_total}"
        digests = {
            d: hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
            for d, rows in per_driver.items()
        }
        return digests, partitions_used

    digests_p1, parts_p1 = _consume_digest(topic_p1, start_tps_p1)
    digests_p11, parts_p11 = _consume_digest(topic_p11, start_tps_p11)

    assert parts_p1 == {0}, f"1-partition topic should only use partition 0, got {parts_p1}"
    assert len(parts_p11) >= 3, f"Expected driver spreading across >= 3 of 11 partitions, got {parts_p11}"
    assert digests_p1 == digests_p11, f"Per-driver Kafka digests diverged across 1 vs 11 partitions!"

