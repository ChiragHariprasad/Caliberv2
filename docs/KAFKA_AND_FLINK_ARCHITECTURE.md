# Kafka & Apache Flink Stream Processing Architecture

**Modules:** [`backend/pulse/stream/kafka_client.py`](../backend/pulse/stream/kafka_client.py), [`backend/pulse/stream/kafka_io.py`](../backend/pulse/stream/kafka_io.py), [`backend/pulse/topics.py`](../backend/pulse/topics.py), [`backend/pulse/stream/flink/`](../backend/pulse/stream/flink/jobs/normalizer_job.sql), [`backend/pulse/main.py`](../backend/pulse/main.py), [`docker-compose.kafka.yml`](../docker-compose.kafka.yml)

---

## 1. Broker Cluster & Topic Catalogue

PULSE uses a 3-broker Confluent Kafka (`cp-kafka:7.7.0`) KRaft ensemble exposed on `localhost:19092,localhost:19093,localhost:19094` (internal `kafka-1/2/3:9092`), paired with `kafka-ui` (`:8080`) and Apache Flink `1.18.1-scala_2.12-java11`.

- **Catalogue Verification:** `python -m pulse.stream.kafka_io --ensure --verify` enforces **`70` catalogued topics** with zero configuration drift.
- **Durability Defaults:** All streaming topics enforce `replication_factor=3` and `min.insync.replicas=2` (`auto_create_topics_enable=false` on brokers).
- **Partitioning Strategy (`DriverSlots`):** High-volume per-driver topics (`pulse.f1.raw.*`, `pulse.f1.canonical.*`, etc.) use **`11` partitions** keyed deterministically via `routing_key(session_instance_id, driver_number, segment_id)` mapped through `DriverSlots` so events for any individual car retain strict per-partition causal ordering without cross-driver head-of-line blocking, while session-global topics retain single-partition total order where appropriate.

---

## 2. Producer, Consumer, Compression & Sink Guarantees

`KafkaBroker` (`kafka_client.py`) now builds directly atop the production `kafka_io` primitives rather than separate `RF=1`/`num_partitions=1` legacy code:

| Property | Setting / Implementation | Rationale |
|---|---|---|
| Producer delivery | `acks="all"`, `enable.idempotence=True`, retry backoff | Eliminates silent broker loss on single-node crash (`T2`) and prevents duplicate sequence commits under retries. |
| Compression codec | `compression_type="gzip"` | Universally supported across `confluent-kafka`/librdkafka AND Flink `1.18.1` (`flink-sql-connector-kafka-3.1.0-1.18.jar`), which omits native `zstd-jni` JNI binaries (`NoClassDefFoundError` root cause resolved). |
| Async publish bridge | Delivery Future polling (`poll_interval=0`) | Bridges synchronous `confluent_kafka.Producer.produce()` callbacks cleanly into FastAPI/Replay asyncio loops. |
| Consumer isolation | `isolation.level="read_committed"`, cooperative-sticky rebalance (`CooperativeStickyAssignor`), static membership | Aborted/uncommitted transactional batches never leak downstream (`T5`); consumer failover finishes cleanly without full-group stop-the-world stalls (`T4`, `T9`). |
| Consumer-side EOS | `IdempotentVerdictSink` (`data/pulse_verdicts.sqlite`) keyed by `(topic, partition, offset, key, event_id)` + Flink `upsert-kafka` tombstone skip | Guarantees at-least-once broker delivery collapses to idempotent single-application effect inside `kafka_consumer_loop`. |
| Poison-pill handling | `broker.publish_dlq(...)` to Dead-Letter Queue | Unparseable/schema-corrupt records route with `(topic, partition, offset, raw_key, raw_bytes, error)` instead of crashing the consumer loop (`T7`). |
| Pause & Seek Isolation | `store.retire_run(run_id)` + bounded `paused_replay_buffer` (`deque(maxlen=5000)`) | Consumer keeps heartbeating continuously (no `max.poll.interval.ms` rebalance), while late broker packets from prior runs are dropped and paused run packets wait cleanly without advancing race lap/elapsed state. |

---

## 3. Apache Flink `1.18.1` SQL Normalization (`normalizer_job.sql`)

Three structural defects were diagnosed and repaired so Flink runs live against Kafka:

1. **Connector Deployment:** Downloaded and mounted `docker/flink/lib/flink-sql-connector-kafka-3.1.0-1.18.jar` (`5,596,853` bytes) into `/opt/flink/lib/` across both `calibre-flink-jobmanager` and `calibre-flink-taskmanager` in `docker-compose.kafka.yml`.
2. **Janino Watermark Fix:** Replaced complex inline `COALESCE(TRY_CAST(...), CURRENT_TIMESTAMP)` inside DDL `WATERMARK` clauses (which threw `org.codehaus.commons.compiler.CompileException` in Flink 1.18 `WatermarkGenerator` and type-mismatched `TIMESTAMP(3)` vs `TIMESTAMP_LTZ(3)`) with Kafka broker metadata timestamps:
   - `kafka_ts TIMESTAMP_LTZ(3) METADATA FROM 'timestamp' VIRTUAL`
   - `WATERMARK FOR kafka_ts AS kafka_ts - INTERVAL '2' SECOND`
3. **Append-Only First-Row Deduplication:** Deduplicates across all `7` raw input topics using `ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY proc_time ASC) WHERE row_num = 1`, backed by `execution.checkpointing.interval = 5000` (`5s` checkpoints) and `table.exec.state.ttl = 300000 ms` (`5 min` idle TTL).

---

## 4. Verified Chaos & Reliability Suite (`T1`–`T10`)

Executed directly against the live 3-broker Docker cluster in `backend/tests/test_kafka_integration_t1_t10.py`:
- **`T1`:** Driver-affine partitioning & strict per-driver sequence ordering.
- **`T2`:** Live `docker stop kafka-2` failover with zero data loss and full ISR catch-up on restart.
- **`T3`:** Two-broker failure (`< 2` ISR remaining) fails closed safely rather than losing durability.
- **`T4` / `T9`:** Cooperative-sticky rebalance & static membership quick-restart stability.
- **`T5`:** Producer abort isolation (`read_committed` hides uncommitted transactions).
- **`T6`:** `IdempotentVerdictSink` SQLite replay invariance across repeated offset sweeps.
- **`T7`:** Poison-record DLQ capture with exact partition/offset provenance.
- **`T8`:** Bitemporal watermark & multi-run replay isolation.
- **`T10`:** Topic partition count invariance across verification passes.
