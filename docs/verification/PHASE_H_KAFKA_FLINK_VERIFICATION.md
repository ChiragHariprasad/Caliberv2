# PULSE — Phase H Distributed Streaming Verification Report (Apache Kafka & Apache Flink)

**Audit Date:** 2026-11-26  
**Scope:** Independent runtime verification of the 3-broker Kafka KRaft cluster (`kafka-1`, `kafka-2`, `kafka-3`), Apache Flink `1.18.1` (`pulse-canonical-normalizer-v3`), topic catalogue (`70` topics), consumer offset commit coupling (`main.py`), and `T1`–`T10` integration/chaos test fidelity.

---

## 1. Critical Defects Discovered & Remediated in Phase H

Direct execution and code inspection uncovered five genuine distributed-streaming defects behind the earlier passing test checks:

| # | Defect Identified | Root Cause & Impact | Phase H Repair & File | Verified Result |
|---:|---|---|---|---|
| **1** | **Flink SQL omitted 2 of 9 `RAW_TOPICS` (`telemetry.car`, `session_status`) & Stage 3 stubbed verification** | `normalizer_job.sql` had `7` source tables instead of `9`; `orchestrator.py` routed `POSITION_UPDATE` (`71,960 / 72,642` events/run) to `telemetry.car` (`432k+` orphaned records) and returned an in-memory `expected_map` in Stage 3 without consuming `pulse.norm.*`. | Added `kafka_raw_telemetry_car` and `kafka_raw_session_status` to [`normalizer_job.sql`](../../backend/pulse/stream/flink/jobs/normalizer_job.sql) (`v3`), routed capture envelopes via `raw_topic_for_event()`, scoped `event_id`s per `run_id`, and rewrote Stage 3 (`_stage_verify_flink_streams`) in [`orchestrator.py`](../../backend/pulse/testing/orchestrator.py) to consume actual normalized records from `pulse.norm.*` watermarked before Stage 2. | **`10 / 10` full `72,642`-event runs (`726,420` events) normalized & consumed back with `0` drops** (`task-2455`); `test_flink_v3_normalizes_telemetry_car_and_session_status` **PASSED**. |
| **2** | **`CalibreProducer` `zstd` default crashed Flink `1.18.1` (`NoClassDefFoundError`)** | Although `kafka_client.py` switched to `gzip`, [`CalibreProducer.__init__`](../../backend/pulse/stream/kafka_io.py) still defaulted to `compression_type="zstd"`. Any direct caller writing to Flink-consumed topics crashed Flink's `Source` reader (`com/github/luben/zstd/ZstdInputStream`). | Switched `CalibreProducer` default `compression_type` from `"zstd"` to `"gzip"` cleanly in [`kafka_io.py`](../../backend/pulse/stream/kafka_io.py) and purged the legacy pre-fix `zstd` range (`0..417`) on `pulse.raw.race_control.v1`. | `race_control` Flink normalization confirmed **`14 / 14`** (`task-2370`). |
| **3** | **Flink job stacking exhausted TaskManager slots after transient broker faults** | `FlinkStreamManager.ensure_normalizer_job_running()` only checked `state == "RUNNING"`, so a job transiently `RESTARTING` during `T2`/`T3` broker outages triggered duplicate job submissions until all 4 slots ran out. | Updated [`manager.py`](../../backend/pulse/stream/flink/manager.py) to wait up to `20s` for recovering `v3` jobs (`RESTARTING`/`INITIALIZING`/`RECONCILING`), cancel superseded versions (`v2`/stalled), and poll up to `25s`. | `test_07_flink_checkpoint_recovery` & post-`T3` `test_01` E2E replay both **PASSED** (`18 / 18` vertices `RUNNING`, `checkpoints >= 1`). |
| **4** | **Auto-commit Kafka consumer lost durability parity & stalled behind offline benchmark runs** | `kafka_consumer_loop()` in [`main.py`](../../backend/pulse/main.py) used `enable_auto_commit=True` with volatile SIA RAM; initial manual per-message SQLite commit also stalled behind `726k` offline `e2e-session-*`/`bench-*` records. | Converted `kafka_consumer_loop()` to `enable_auto_commit=False` with `getmany(max_records=250)` micro-batches, pre-filtering foreign test runs before Pydantic validation, persistent WAL connection in `IdempotentVerdictSink`, and committing Kafka offsets strictly **after** `_route_normalized` + SIA WAL persist + `insert_verdict()`. | Live `uvicorn` `SIGKILL` drill (`task-2518`) recovered all `21` chains cleanly and delivered uncommitted in-flight atom (`28 -> 29` atoms). |
| **5** | **`main.py` omitted startup Flink normalizer ensure** | Lifespan in `KAFKA` mode checked `is_cluster_online()` without ensuring `normalizer_job` was running. | Wired `flink_mgr.ensure_normalizer_job_running()` cleanly in [`main.py`](../../backend/pulse/main.py) respecting `settings.flink_required` fallback policy. | Observed live `Reusing existing RUNNING Flink job [7a8d209f2e3bbaa5faff6e9656654096]`. |

---

## 2. Live Cluster, Topic Catalogue & Architecture Verification

1. **Docker 3-Broker KRaft + Flink `1.18.1` Cluster:**
   - Verified healthy `kafka-1`, `kafka-2`, `kafka-3` (`confluentinc/cp-kafka:7.7.0`, combined `broker,controller` KRaft quorum), `kafka-ui`, `calibre-flink-jobmanager`, and `calibre-flink-taskmanager` (`4` task slots, `parallelism.default = 2`). *(Note correction to prior docs: internal Docker listener port in [`docker-compose.kafka.yml`](../../docker-compose.kafka.yml) is `:29092`, external host ports are `localhost:19092,19093,19094`; Flink mounts `flink-sql-connector-kafka-3.1.0-1.18.jar`, which excludes native `zstd-jni`.)*
2. **Topic Catalogue (`70` Topics):**
   - `python -m pulse.stream.kafka_io --verify`: `[OK] All 70 topics verified against live broker with zero drift.` (`RF=3`, `min.insync.replicas=2`, `unclean.leader.election.enable=false`, `11` partitions via `DriverSlots` for per-driver telemetry/timing/verdict topics).
3. **Active Runtime Flink Topology (`pulse-canonical-normalizer-v3`, `7a8d209f2e3bbaa5faff6e9656654096`):**
   - `18` pipeline vertices (`9` `RAW_TOPICS` Kafka sources -> `ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY proc_time ASC) WHERE row_num = 1` deduplicators -> `5` `NORMALISED_TOPICS` `upsert-kafka` sinks), `table.exec.state.ttl = 300000 ms`, `execution.checkpointing.interval = 5000 ms`.
   - Observed `346` completed checkpoints (`0` failed) processing `662,038` records cleanly during Benchmark 1 and `1,078+` completed checkpoints prior to TaskManager fault injection.

---

## 3. Chaos, Fault-Injection & Hardened `T1`–`T10` / Reliability Evidence

All four previously tautological/weak `T1`–`T10` tests and two reliability tests were hardened to execute genuine distributed assertions against live Docker containers:

| Check | Live Failure / Invariant Exercised | Direct Observed Outcome |
|---|---|---|
| **`T1`** `driver_affine_partitioning` | `10` drivers x `10` monotonic sequence messages | **PASSED** (`1` unique partition per driver; strict monotonic seq) |
| **`T2`** `single_broker_failure` | Live `docker stop kafka-2` mid-ingest -> publish -> `docker start kafka-2` | **PASSED** (`0` failed deliveries; ISR recovers cleanly under `MIN_ISR=2`) |
| **`T3`** *(Hardened)* `two_broker_failure` | Live `docker stop kafka-2 kafka-3` on `kafka-1`-led partition -> `acks="all"` produce -> restart & await 3-broker ISR | **PASSED** (`delivered == 0`, `3/3` errors rejected, `hi_after == hi_before`, quorum healed) |
| **`T4`** `cooperative_rebalance_takeover` | Two `cooperative-sticky` consumers over 11 partitions; close worker 1 | **PASSED** (Worker 2 cleanly absorbs `11 / 11` partitions) |
| **`T5`** `eos_transactional_isolation` | Transactional `abort_transaction()` vs `commit_transaction()` under `isolation.level="read_committed"` | **PASSED** (`COMMITTED_DATA` read; `ABORTED_DATA` suppressed) |
| **`T6`** `idempotent_sqlite_sink` | Replay same `(topic, partition, offset)` batch twice | **PASSED** (`50` unique rows unchanged; `has_verdict` + `insert_verdict` safe) |
| **`T7`** `dlq_poison_routing` | Malformed payload routed to `calibre.dlq` with `x-src-topic/partition/offset` headers | **PASSED** (Consumer reads DLQ with exact headers cleanly) |
| **`T8`** *(Hardened)* `clock_watermark_isolation` | Monotonic epochs on `calibre.guard.clock` + concurrent `LIVE`/`REPLAY` streams + SIA WAL disjoint session check | **PASSED** (`[100, 101]` readback; `eng_replay` atom count `== 0`) |
| **`T9`** *(Hardened)* `static_membership_no_rebalance` | Co-member `standby` + `c1` static `group.instance.id`; close `c1`, immediately rejoin `c1_restarted` with same ID | **PASSED** in `9.14s` (`p1_after == p1_before`, `revokes_standby == []`, `assigns_standby == []`) |
| **`T10`** *(Hardened)* `partition_count_invariance` | Live Kafka publish & consume of same driver lap batch across `calibre.alerts` (`1` part.) vs `calibre.evidence.timing` (`11` parts.) | **PASSED** (`{0}` vs `>=3` partitions used; identical per-driver SHA-256 digests) |
| **`test_06`** *(Hardened)* `same_group_restart` | Manual `c1.commit({tp: offset+1})`, close `c1`, publish `env_2`, restart `c2` under **identical `group_id`** | **PASSED** (`env_1` never redelivered; `env_2` received cleanly) |
| **`test_07`** *(Hardened)* `flink_checkpoint_recovery` | Live check of Flink `v3` `checkpoints_completed >= 1` & all `>=18` vertices `RUNNING` | **PASSED** |
| **Flink TaskManager Container Restart (`task-2524`)** | Live `docker restart calibre-flink-taskmanager` while `pulse-canonical-normalizer-v3` running (`ckpt=1078`) | **PASSED** — job recovered autonomously to `RUNNING` within `~6–8s`, advancing checkpoint `1078 -> 1079` |
| **10x `72,642`-Event E2E Stress Pass (`task-2455`)** | `10` sequential full-race runs through Kafka `RF=3` -> Flink `v3` -> Stage 3 real `pulse.norm.*` consumption | **`10 / 10 PASSED` (`726,420 / 726,420` events, `0` drops)** |

---

## 4. Honest Architectural Justification & Boundaries

- **Why Kafka & Flink are genuinely exercised now (not theater):** In `KAFKA` mode, `CalibreProducer` (`acks="all"`, `enable.idempotence=True`, `RF=3`, `MIN_ISR=2`, `DriverSlots` 11-way driver partitioning) genuinely survives single-node failure (`T2`), rejects un-replicated commits under 2-broker failure (`T3`), supports cooperative sticky / static rebalance (`T4`/`T9`), isolates uncommitted transactions (`T5`), and feeds live Apache Flink `1.18.1` SQL `ROW_NUMBER()` deduplication across all `9` raw topics back into `main.py`'s `IdempotentVerdictSink` + manual offset commit loop.
- **Pragmatic operational boundary:** At single-race live playback (`~10–62 evt/s`), Kafka+Flink are heavier than strictly required (`MEMORY` / `SIMULATOR` modes handle single-node replay cleanly); their architectural justification lies in multi-session fan-out, durable log retention/replay, partitioned fault isolation, and proving real-time distributed telemetry transport semantics cleanly. Notice also that in [`orchestrator.py`](../../backend/pulse/testing/orchestrator.py), Stage 2 `batch_size=50` sequential barrier awaits (`126.95 s` avg) remain the dominant wall-clock bottleneck during full-capture bulk tests vs raw sustained producer enqueue (`27,719 evt/s`).
