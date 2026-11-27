# PULSE — Phase H Benchmark Reconciliation Report

**Audit Date:** 2026-11-26  
**Benchmark Script:** [`scripts/benchmark_pipeline_latency.py`](../../scripts/benchmark_pipeline_latency.py)  
**Machine-Readable Evidence:** [`reports/pipeline_latency_report.json`](../../reports/pipeline_latency_report.json)  
**Pre-Edit Baseline Snapshot:** [`docs/verification/baselines/pipeline_latency_report.baseline.json`](baselines/pipeline_latency_report.baseline.json)

---

## 1. Executive Summary of Methodological Corrections

The prior benchmark report (`pipeline_latency_report.baseline.json` / `docs/VALIDATION_AND_BENCHMARKS.md`) contained four structural methodology issues. Phase H corrected the benchmark harness cleanly without distorting production behavior:

1. **Layer 1 vs. Stage 2 Ingest Discrepancy Explained:**
   - **Previous observation:** Layer 1 per-event Kafka ingest averaged **`42.93 ms`** (`~23.3 evt/s`), whereas Stage 2 across `72,642` events completed in **`95.25 s`** (`~762.6 evt/s`).
   - **Verified cause:** `KafkaBroker.publish()` awaits broker ISR acknowledgement (`acks="all"`, `RF=3`, `MIN_ISR=2`) on every call. Layer 1 awaited sequentially (`concurrency = 1`), whereas `orchestrator.py` awaited `50` concurrent futures per batch (`asyncio.gather`).
   - **Measured separated metrics (`n=250` serial / `20x50` batched / `5,000` bulk):**
     - `layer_1a_kafka_serial_rtt_ms` (`concurrency=1`): median **`15.76 ms`**, avg **`18.24 ms`**, P95 **`21.91 ms`**, max **`527.58 ms`** (`n=250`)
     - `layer_1b_kafka_batch50_ms` (`20` batches of `50` = `1,000` events): **`31.24 ms`** median/batch, **`1,517.68 evt/s`** sustained (`0.6589 s` total)
     - `layer_1c_kafka_enqueue_flush_5000` (`CalibreProducer` bulk enqueue + `flush`): **`0.1804 s`** total = **`0.0361 ms/evt`** (**`27,719.75 evt/s`**)
2. **Agent CPU Compute vs. Kafka Finding Publish Separated:**
   - **Previous observation:** Benchmark 1 reported Agent 1/3/4 averages of **`0.229 ms` / `0.216 ms` / `0.023 ms`**, whereas Benchmark 2 Stages 4–8 spent **`814 ms` / `7,642 ms` / `2,536 ms` / `7,530 ms`**.
   - **Verified cause:** Benchmark 1 ran agents attached to a disconnected `PulseEventBus()` (`broker.is_connected == False`, pure CPU), while `orchestrator.py` left `self.broker` connected, causing every emitted `Finding` / `Assessment` to block serially awaiting Kafka `acks="all"` delivery confirmation.
   - **Measured comparison:** Agent 1 pure compute = **`0.0861 ms`** median (`avg 0.1561 ms`, `n=13`); Agent 1 with live Kafka finding publish = **`17.31 ms`** median (`avg 63.16 ms`, `~201x` median difference). Agent 4 pure compute = **`0.0118 ms`** median (`avg 0.0895 ms`); with Kafka publish = **`avg 6.40 ms`** (`p95 64.47 ms`).
3. **Real Stage 3 Flink Consumption vs. Prior In-Memory Stub:**
   - **Previous defect:** `orchestrator.py` Stage 3 (`3.FLINK_STREAM_NORMALIZATION`) reported `458.85 ms` (`0` drops) by returning an in-memory copy of input events without consuming from `pulse.norm.*` Kafka topics. It also routed `71,960` `POSITION_UPDATE` events per run into unsubscribed `pulse.raw.telemetry.car.v1` while reusing identical `event_id`s across repeated runs.
   - **Phase H fix & measurement (`n=10` complete runs):** Routing fixed (`timing_positions`), `normalizer_job.sql` upgraded to `v3` covering all `9` `RAW_TOPICS`, run-scoped `event_id`s applied, and Stage 3 now consumes actual Flink-emitted canonical records from `pulse.norm.*`: median **`10,642.89 ms` (`10.64 s`)**, avg **`10,372.66 ms`**, min **`8,222.40 ms`**, max **`12,032.47 ms`**, **`0` drops across `10 / 10` full `72,642`-event runs** (`726,420` total events reconciled).
4. **Statistical Validity (`n=10` Runs, Cold vs. Warm Segregation, No Small-Sample `P95`):**
   - Prior report ran `num_runs=3` and equated `P95`/`P99` directly to the sample maximum (`123.37 s`). Phase H executes `n=10` full E2E runs (`Benchmark 3`) and `n=10` identical-index seek trials (`Benchmark 2`), reporting `min`, `median`, `avg`, `max`, `range`, and `stdev` while suppressing `p95`/`p99` (`null`) whenever `n < 20` / `n < 100`.
   - Note also: Python `tracemalloc` instrumentation inflates `seek(36321)` by `~6x` (`509.7 s` vs `83.8 s` clean); all reported timings were measured strictly with `tracemalloc` disabled.

---

## 2. Separated Layer & Throughput Metrics (`Benchmark 1`)

| Layer / Operation | Metric / Mode | Count | Min | Median | Mean (Avg) | P95 | Max | StdDev |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Layer 1a:** Kafka Ingest (serial `acks=all`, `concurrency=1`) | Per-message RTT (`ms`) | `250` | `9.18` | **`15.76`** | `18.24` | `21.91` | `527.58` | `32.53` |
| **Layer 1b:** Kafka Ingest (`batch_size=50` `asyncio.gather`) | Batch RTT (`ms`) · Throughput **`1,517.68 evt/s`** | `20` (`1,000` evt) | `27.38` | **`31.24`** | `32.94` | `38.49` | `62.35` | `7.49` |
| **Layer 1c:** `CalibreProducer` Enqueue + `flush()` (`5,000` evt) | Amortized (`ms/evt`) · Throughput **`27,719.75 evt/s`** | `5,000` | — | — | **`0.0361`** | — | — | — |
| **Layer 2:** `StreamNormalizer` Schema Parse (`CPU`) | Per-event (`ms`) | `1,000` | `0.0079` | **`0.0234`** | `0.0195` | `0.0250` | `0.1261` | `0.0085` |
| **Layer 3:** Agent 1 `EventControl` (`compute-only`) | Per-event (`ms`) | `13` | `0.0689` | **`0.0861`** | `0.1561` | `n/a (n<20)` | `0.6550` | `0.1726` |
| **Layer 3:** Agent 1 `EventControl` (`+ Kafka publish`) | Per-event (`ms`) | `13` | `11.7146` | **`17.3112`** | `63.1614` | `n/a (n<20)` | `545.2929` | `145.9433` |
| **Layer 3:** Agent 2 `TrackState` (`compute-only`) | Per-event (`ms`) | `8` | `0.0810` | **`0.0872`** | `0.0943` | `n/a (n<20)` | `0.1349` | `0.0189` |
| **Layer 3:** Agent 3 `VehicleResponse` (`compute-only`) | Per-event (`ms`) | `600` | `0.0219` | **`0.6441`** | `0.6147` | `1.1539` | `1.7476` | `0.3401` |
| **Layer 3:** Agent 4 `TyreStrategy` (`compute-only`) | Per-event (`ms`) | `22` | `0.0099` | **`0.0118`** | `0.0895` | `0.7292` | `0.9621` | `0.2474` |
| **Layer 3:** Agent 4 `TyreStrategy` (`+ Kafka publish`) | Per-event (`ms`) | `22` | `0.0070` | `0.0083` | **`6.4046`** | `64.4735` | `76.2262` | `20.7764` |
| **Layer 3 (Aggregated Compute):** Agents 01–04 | Per-event (`ms`) | `643` | `0.0099` | **`0.6206`** | `0.5810` | `1.1434` | `1.7476` | `0.3556` |
| **Layer 4:** `ConsequenceFusionEngine` (`compute-only`) | Per-finding (`ms`) | `315` | `0.0031` | **`0.1600`** | `0.2630` | `0.6537` | `5.8706` | `0.4919` |
| **Layer 5:** `StateStore` Record Persistence | Per-item (`ms`) | `100` | `0.0408` | **`0.0474`** | `0.0811` | `0.1311` | `2.3274` | `0.2334` |
| **Layer 6:** API Query Serving (`TestClient`, 6 endpoints) | Per-request (`ms`) | `120` | `0.5668` | **`1.8855`** | `2.2195` | `3.8830` | `6.5332` | `0.9694` |
| **Layer 7:** SSE Queue Delivery (`StateStore.record_finding -> queue`) | Per-event (`ms`) | `100` | `0.0434` | **`0.0502`** | `0.0846` | `0.1390` | `2.3380` | `0.2343` |

Live Apache Flink snapshot during Benchmark 1 (`pulse-canonical-normalizer-v3`, `7a8d209f2e3bbaa5faff6e9656654096`): `state = RUNNING`, `read_records = 662,038`, `write_records = 662,038`, `checkpoints_completed = 346`, `checkpoints_failed = 0`.

---

## 3. Identical-Index Seek, Keyframe Cache, WAL Recovery & Mid-Race API (`Benchmark 2`, `n=10`)

Prior report (`VALIDATION_AND_BENCHMARKS.md`) compared uncached baseline `target_index=25000` (`141.2 s`) against `target_index=36321` (`20.8 s`, reporting `11.1x` vs an intermediate `230.4 s` run) and cited `1.1 ms` `/api/snapshot` and `480.3 ms` `verify`. Direct Phase H re-measurement across `n=10` independent trials with **`PULSE_SIA_WAL_PATH` enabled** (plus isolated clean-room `WAL_OFF` check) reveals important discrepancies:

| Operation | Scope & Trial Count | Measured Result | Prior Claimed Value | Reconciliation Finding |
|---|---|---|---|---|
| Cold `seek(36321)` (`WAL OFF`, clean `prof_seek.py`) | `n=1` (`72,642`-evt Silverstone) | **`83,801.1 ms` (`83.80 s`)** | `20,785.1 ms` (`20.8 s`) | **Discrepancy identified:** Current full-stack seek reconstruction (`36,321` events through normalizer, 5 agents, SIA `IntegrityEngine`, and `18` `export_checkpoint` captures) takes `~84s`, not `20.8s`. |
| Cold `seek(36321)` (`WAL ON`, Run 1 cold / Runs 2–10 warm) | `n=10` via `POST /api/replay/seek` | Run 1: `88,449.2 ms`; Warm 2–10 median: **`86,538.9 ms`** (All 10: min `79,210.5`, med **`87,494.1`**, avg `93,985.0`, max `125,345.2`, stdev `15,350.8 ms`) | `20,785.1 ms` (`WAL` inactive) | Isolated `wal_sync` adds only **`~1.28 s`** (`1,281.6 ms` measured); remaining cost is sequential Python agent/SIA reconstruction across `36,321` events + `18` pickle checkpoints. |
| Cached Keyframe `seek(36500)` (`ckpt=36000 -> +500 events + wal_sync`) | `n=10` via `POST /api/replay/seek` | Min `2,827.1 ms`, med **`3,715.5 ms`**, avg `3,816.5 ms`, max `5,676.1 ms`, stdev `798.8 ms` | `487.4 ms` (`WAL` inactive) | **`23.55x` median speedup** vs cold `seek(36321)` under durable WAL mode, with **`0` SIA `record_hash` mismatches (`sia_hash_mismatches = 0`)**. |
| Mid-Race SQLite WAL Crash Restore (`IntegrityAgent.restore_from_wal()`) | `n=10` after `seek(36321)` sync | Min `919.1 ms`, med **`1,400.2 ms`**, avg `1,553.4 ms`, max `2,961.7 ms`, stdev `592.1 ms` | `N/A` (WAL unwired at runtime) | Full mid-race SIA ledger + `637` hash chains restore cleanly in `~1.4s`. |
| Mid-Race `GET /api/snapshot` (`113.05 KB`) | `n=50` after `seek(36500)` | Min `7.55 ms`, med **`10.28 ms`**, P95 **`12.81 ms`**, avg `51.99 ms`, max `2,092.81 ms` (cold 1st call outlier) | `1.1 ms` (in-proc) / `34.2 ms` (HTTP) | Sub-`13 ms` P95 in-process steady state after first warm verification cache build (`13.51 ms` `WAL_OFF`, `12.03 ms` `WAL_ON` in `prof_seek`). |
| Full `GET /api/integrity/verify` (`637` chains) | `n=10` | Min `1,760.1 ms`, med **`2,003.7 ms`**, avg `1,970.0 ms`, max `2,062.9 ms`, stdev `90.7 ms` | `480.3 ms` | Clean `verified=true` across all `637` chains in `~2.0s` (`1.89s` `WAL_OFF`, `2.20s` `WAL_ON` in `prof_seek`). |

---

## 4. Full `72,642`-Event Kafka + Apache Flink `v3` E2E Benchmark (`Benchmark 3`, `n=10` Complete Runs)

All `10 / 10` runs executed cleanly (`726,420` events streamed to 3-broker KRaft RF=3, normalized through live Apache Flink `pulse-canonical-normalizer-v3`, consumed and verified back from `pulse.norm.*` in Stage 3, processed by Agents 01–05, and persisted to `StateStore` with **`0` drops** across every stage):

| Stage | Baseline Avg (`n=3`, Fake Stage 3) | Phase H Min (`n=10`) | Phase H Median (`n=10`) | Phase H Avg (`n=10`) | Phase H Max (`n=10`) | StdDev (`n=10`) |
|---|---:|---:|---:|---:|---:|---:|
| `0.VALIDATE_CAPTURE_MANIFEST` | `0.44 ms` | `0.84 ms` | `1.73 ms` | `4.58 ms` | `29.67 ms` | `8.84 ms` |
| `1.PREFLIGHT` | `1,227.10 ms` | `2,704.40 ms` | `3,690.16 ms` | `3,601.45 ms` | `4,067.28 ms` | `416.02 ms` |
| `2.HISTORICAL_CAPTURE_INGEST_KAFKA` | `95,252.65 ms` | `71,836.47 ms` | `132,718.38 ms` | `126,951.69 ms` | `141,441.60 ms` | `20,644.68 ms` |
| **`3.FLINK_STREAM_NORMALIZATION` *(Real Consume)*** | `458.85 ms` *(stub)* | `8,222.40 ms` | **`10,642.89 ms`** | `10,372.66 ms` | `12,032.47 ms` | `1,376.96 ms` |
| `4.AGENT_1_EVENT_CONTROL` | `814.36 ms` | `407.55 ms` | `1,120.89 ms` | `921.32 ms` | `1,147.51 ms` | `335.69 ms` |
| `5.AGENT_2_TRACK_STATE` | `386.58 ms` | `184.99 ms` | `561.27 ms` | `470.91 ms` | `592.38 ms` | `166.25 ms` |
| `6.AGENT_3_VEHICLE_RESPONSE` | `7,641.84 ms` | `6,059.80 ms` | `13,850.59 ms` | `12,858.60 ms` | `16,441.97 ms` | `3,496.42 ms` |
| `7.AGENT_4_TYRE_STRATEGY` | `2,536.32 ms` | `2,254.34 ms` | `4,145.42 ms` | `3,833.86 ms` | `4,646.29 ms` | `873.10 ms` |
| `8.AGENT_5_CONSEQUENCE_FUSION` | `7,529.79 ms` | `6,243.84 ms` | `13,500.03 ms` | `12,884.21 ms` | `17,689.65 ms` | `3,754.22 ms` |
| `9.FAULT_INJECTION_AND_DATA_QUALITY` | `46.34 ms` | `16.87 ms` | `64.16 ms` | `57.31 ms` | `78.23 ms` | `21.67 ms` |
| `10.RACE_INTELLIGENCE_EVALUATION` | `0.48 ms` | `0.90 ms` | `1.21 ms` | `5.96 ms` | `48.78 ms` | `15.05 ms` |
| `11.STATE_STORE_LINEAGE_AND_API` | `1,725.48 ms` | `2,053.30 ms` | `2,236.84 ms` | `2,243.46 ms` | `2,429.09 ms` | `97.58 ms` |
| **FULL PIPELINE E2E TOTAL (`n=10`)** | `117,807.91 ms` *(n=3)* | **`107,483.57 ms`** | **`184,871.29 ms`** | **`176,891.42 ms`** | **`200,675.16 ms`** | **`28,163.57 ms`** |

- **Cold vs. Warm Breakdown:** Run 1 (cold start): **`188,119.09 ms` (`188.12 s`)**. Runs 2–10 (`n=9`): min **`107,483.57 ms`**, median **`181,623.50 ms`**, avg **`175,643.90 ms`**, max **`200,675.16 ms`**, stdev **`29,577.47 ms`**.
- **Variance Note (`stdev = 28.16 s`):** Under concurrent `batch_size=50` ingestion while Flink `v3` deduplicates and compacts 72k events per run across the same 3-broker Docker host, broker I/O & Flink `5s` checkpoint pauses widen Stage 2 duration (`71.8 s` to `141.4 s`), making honest `n=10` dispersion reporting (`min / median / max / stdev`) critical vs. the prior `n=3` report.

---

## 5. Docker Container Resource Footprint (`docker stats --no-stream`)

Captured right at completion of the `10`-run E2E Kafka+Flink stress pass:

| Container | CPU % | Memory Usage / Limit | Memory % |
|---|---:|---|---:|
| `kafka-1` | `6.60%` | `2.207 GiB / 15.37 GiB` | `14.36%` |
| `kafka-2` | `5.33%` | `1.504 GiB / 15.37 GiB` | `9.79%` |
| `kafka-3` | `6.59%` | `1.558 GiB / 15.37 GiB` | `10.13%` |
| `calibre-flink-jobmanager` | `64.25%` | `1.456 GiB / 15.37 GiB` | `9.47%` |
| `calibre-flink-taskmanager` | `102.31%` | `1.034 GiB / 15.37 GiB` | `6.73%` |

*(Note: `get_process_rss_mb()` inside `pipeline_latency_report.json` returned `0.0` due to `psapi` handle lookup in `benchmark_pipeline_latency.py`; live backend `uvicorn` (`PULSE_TRANSPORT_MODE=KAFKA`) process RSS was measured directly via Windows process counters during the `task-2518` crash/recovery drill: **`586.03 MB`** pre-kill and **`640.84 MB`** post-restart recovery.)*
