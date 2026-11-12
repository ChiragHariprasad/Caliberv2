# Phase 0: Baseline Inventory and Repository Audit

**Date:** 2026-11-05  
**Branch:** `kafka-v2`  
**Execution Environment:** Windows / Python 3.13 / Docker 27.x  

---

## 1. Discrepancy Matrix: Prompt Assumptions vs. Repository Reality

Per Hard Rule 1 (*"If the repo contradicts this prompt, the repo wins; list every discrepancy in your report"*), the table below reconciles the briefing specifications with the actual repository state:

| Subsystem / Area | Prompt Briefing Assumption | Repository Reality (`Caliberv2`) | Resolution & Strategy |
| :--- | :--- | :--- | :--- |
| **Client Library** | `kafka-python` in `flink/job.py`, ingestion, processors | Uses `aiokafka` in `backend/pulse/stream/kafka_client.py` and `bus.py`; no `kafka-python` or `flink/job.py` present. | Migrate centralized client to `confluent-kafka` (v2.16.1 installed) in `backend/pulse/stream/kafka_io.py`. |
| **Test Suite Baseline** | 741/741 tests passing; 20 golden hash parity; 30 adversarial | Test suite contains **90/90 passing tests** in `backend/tests` (including 20 streaming replay tests in `test_phase4_2_streaming.py`, 8 reliability tests in `test_phase4_reliability.py`). Baseline runtime: 72.48 s. | Maintain 100% pass rate (90/90 green) across all phases, plus new T1-T10 integration and chaos tests. |
| **Topic Namespace** | `calibre.*` (`calibre.raw.*`, `calibre.evidence.*`, `calibre.out.*`, `calibre.dlq`, etc.) in `calibre_core/topics.py` | Topics are defined in `backend/pulse/topics.py` as `pulse.*` (`pulse.raw.*`, `pulse.norm.*`, `pulse.agent.*`, `pulse.intelligence.*`, `pulse.ops.*`). | Standardize in `backend/pulse/topics.py` to support both the complete `calibre.*` production specification (catalogue, partitioning, retention) and legacy `pulse.*` aliases for zero breakage. |
| **Central Client Module** | `calibre_core/kafka_io.py` | Existing wrapper is `pulse/stream/kafka_client.py`. | Create `backend/pulse/stream/kafka_io.py` as the single authoritative Kafka client factory and broker manager. |
| **Cluster Topology** | 1 x Confluent `cp-kafka:7.7.0` + ZooKeeper (container `calibre-kafka` on port 9092) | Single-broker Kafka 7.7.0 with ZooKeeper running from external CALIBRE v1 compose. | Replace with 3-broker KRaft cluster (`kafka-1`, `kafka-2`, `kafka-3`) on host ports `19092`, `19093`, `19094` in `docker-compose.kafka.yml` with RF=3, min.isr=2. |
| **Persistence Engine** | SQLite (WAL), INSERT OR IGNORE, content-hashed verdicts | `StateStore` in `backend/pulse/state/store.py` manages in-memory projections and SHA-256 finding/assessment hashes. | Add SQLite WAL persistence sink module with `(topic, partition, offset)` primary key and idempotent writes. |

---

## 2. Inventory of Producers and Consumers

Every Kafka touchpoint in the codebase is indexed below:

| File | Class / Function | Topic(s) | Role | Client / Mode | Acks / Commit Mode | Serializer |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `backend/pulse/stream/kafka_client.py` | `KafkaBroker.publish` | All configured topics | Producer | `aiokafka.AIOKafkaProducer` | `acks="all"` | JSON UTF-8 via Pydantic |
| `backend/pulse/stream/kafka_client.py` | `KafkaBroker.create_consumer` | Dynamic topic list | Consumer | `aiokafka.AIOKafkaConsumer` | Auto-commit `true` / `latest` | JSON UTF-8 deserializer |
| `backend/pulse/stream/bus.py` | `PulseEventBus.publish` | Dynamic routing | Dispatcher / Producer | Calls `KafkaBroker.publish` + local dispatch | Synchronous broker ack | Object / JSON |
| `backend/pulse/main.py` | `lifespan.kafka_consumer_loop` | `pulse.norm.*` | Background Consumer | Group: `pulse-backend-normalised-consumer-v2` | Auto-commit `true` / `latest` | EventEnvelope model parse |
| `backend/pulse/testing/orchestrator.py` | `_stage_publish_historical_capture_to_kafka` | `pulse.raw.*` | Replay Producer | Calls `broker.publish` | `acks="all"`, batch size 50 | EventEnvelope JSON |
| `backend/tests/test_fault_injection.py` | `test_03_crash_restart_recovery` | `pulse.raw.race_control.v1` | Test Consumer | Group: `pulse-crash-restart-group-*` | Manual commit (`enable_auto_commit=False`) | JSON UTF-8 |
| `backend/tests/test_phase4_reliability.py` | `test_06_broker_reconnect_durability` | Test topic | Test Consumer | Groups: `pulse-test-restart-*` | Auto-commit `true` / `earliest` | JSON UTF-8 |

---

## 3. Raw Feed Payload Shapes and Driver Attribution

Based on analysis of `captures/f1-2023-silverstone-race/envelopes.jsonl` (72,642 canonical records):

| Raw Feed / Event Type | Total Records in Replay | Drivers per Message | Driver Field Location | Routing Strategy |
| :--- | :--- | :--- | :--- | :--- |
| `POSITION_UPDATE` | 71,960 | Exactly 1 driver | `subject.driver_number` (int) | **Driver-affine**: `driver_partition(driver_id, 11)` |
| `LAP_COMPLETED` | 600 | Exactly 1 driver | `subject.driver_number` (int) | **Driver-affine**: `driver_partition(driver_id, 11)` |
| `PIT_ENTRY` / `PIT_EXIT` | 40 | Exactly 1 driver | `subject.driver_number` (int) | **Driver-affine**: `driver_partition(driver_id, 11)` |
| `TYRE_FITTED` | 20 | Exactly 1 driver | `subject.driver_number` (int) | **Driver-affine**: `driver_partition(driver_id, 11)` |
| `WEATHER_OBSERVATION` | 8 | Multi-car / Session-level | `None` (`subject.segment_id`) | **Single partition** (1 partition, key hash) |
| `TRACK_STATUS_GREEN` / `UPDATE`| 3 | Session-level | `None` (`subject.segment_id`) | **Single partition** (1 partition, key hash) |
| `RACE_CONTROL_NOTICE` / `VSC_*` | 11 | Session-level | `None` or single (retirement) | **Single partition** (1 partition, global order) |

### Driver Identification Fields
1. **Raw Ingest**: `envelope.subject.driver_number` (integer `1..99`).
2. **Evidence / Specialist Finding**: `finding.subject.driver_number` (integer `1..99`).
3. **Fused Assessment Key**: `routing_key(session_id, driver_number)` $\rightarrow$ `"{session_instance_id}:{driver_number}"`.

---

## 4. Audit of Global Order Assumptions

Single-partition topics guaranteed strict total ordering across all messages. In multi-partition topics (11 driver partitions), order is guaranteed **only per-driver**. The following subsystems were audited:

1. **Agent 1 (`EventControlAgent`)**: Tracks Safety Car, VSC, and Green Flag lifecycles.
   - *Requirement*: Race control notices must preserve chronological event-time order.
   - *Status*: Kept on **1-partition topics** (`calibre.raw.f1_signalr.race_control`, `calibre.evidence.incident`). No cross-driver interleaving issues.
2. **Agent 3 (`VehicleResponseAgent`)**: Analyzes per-driver lap pace and tyre degradation.
   - *Requirement*: Lap progressions must arrive in order for each car.
   - *Status*: **Co-partitioned per driver**. Per-driver sequence is strictly preserved within the driver's partition.
3. **Agent 5 (`ConsequenceFusionEngine`)**: Synthesizes impact assessments.
   - *Requirement*: Correlation depends on event timestamp (`as_of_event_time`), not Kafka arrival order.
   - *Status*: Validated. Fusion engine correlates via driver-keyed buffers.
4. **`StateStore` Projector**:
   - *Requirement*: Monotonic sequence numbers for SSE delivery (`sse_sequence_counter`).
   - *Status*: Assigned at store insertion time; independent of Kafka partition concurrency.

---

## 5. Baseline Benchmark Methodology and Results

### Methodology
- Harness: `scripts/benchmark_pipeline_latency.py` running against 2023 British GP replay (`captures/f1-2023-silverstone-race`, 72,642 envelopes).
- Ingest Throughput: Time to publish 72,642 messages in batches of 50 to Kafka broker with `acks="all"`.
- Kafka Transport Latency: Per-message duration measured between producer dispatch and broker acknowledgment callback (`time.perf_counter_ns()`).
- End-to-End Latency: Synchronous traversal time from raw ingest publish through Flink canonical normalization, Specialist Agent reasoning, Consequence Fusion, to StateStore persistence.

### Baseline Numbers (Single-Broker Setup)
- **Baseline Test Suite**: 90 passed, 0 failed in 72.48 s.
- **Kafka Transport Latency (Per Event)**:
  - Min: `0.78 ms`
  - Avg: `1.86 ms`
  - P95: `2.68 ms`
  - Max: `14.81 ms`
- **Replay Ingest Throughput**: 72,642 messages in 26.81 s avg $\rightarrow$ **2,710 msg/s** (Kafka ingest represents 69.0% of total replay time).
- **Full Replay Duration**: `38.86 s` average across 3 complete runs.
- **End-to-End Per-Event Latency**: `8.08 ms` avg (Min: `4.16 ms`, Max: `33.29 ms`).
- Raw baseline artifact: [`docs/kafka/results/baseline_benchmark.json`](file:///e:/Caliberv2/docs/kafka/results/baseline_benchmark.json).

