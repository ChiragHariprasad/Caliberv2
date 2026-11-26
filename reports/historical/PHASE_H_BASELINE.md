# PULSE — Phase H Independent Baseline Verification Freeze

**Freeze Timestamp:** 2026-11-26 (`pulse-reconstruction` branch)  
**Git HEAD Commit:** `9f1af40b38e39f9484b5852f6f05e08d88518d46` (`checkpoint: pre-reconstruction Phase X audit baseline on pulse-reconstruction`)  
**Frozen Artifacts Preserved:**
- [baselines/git_status.baseline.txt](baselines/git_status.baseline.txt)
- [baselines/pipeline_latency_report.baseline.json](baselines/pipeline_latency_report.baseline.json)
- [baselines/f1_scientific_eval.baseline.json](baselines/f1_scientific_eval.baseline.json)

---

## 1. Environment & Infrastructure Observed at Freeze

- **Python / Runtime:** Python `3.13.12` (Windows 11 `amd64`), `pytest 9.1.1`, `confluent_kafka 2.16.1`, Node/Vite (`vite 6.4.5`).
- **Docker Services Running:** `kafka-1`, `kafka-2`, `kafka-3` (`confluentinc/cp-kafka:7.7.0`, healthy), `kafka-ui`, `calibre-flink-jobmanager`, `calibre-flink-taskmanager` (`flink:1.18.1-scala_2.12-java11`).
- **Live Flink Job Verified (`http://localhost:8081/jobs/overview`):** `f0b58c7e2477ea5651e0f226c2034a5d` (`pulse-canonical-normalizer-v2`, `RUNNING`, `28` running subtasks across `14` vertices).
- **Topic Catalogue Verification (`PYTHONPATH=backend python -m pulse.stream.kafka_io --verify`):** Exited `0` — `[OK] All 70 topics verified against live broker with zero drift.` *(Note: emits Python `runpy` RuntimeWarning because `pulse/stream` eagerly imports `kafka_io` during package init.)*

---

## 2. Pre-Edit Automated Test Reproduction

Executed untouched on the incoming `pulse-reconstruction` working tree before any Phase H code modifications:

| Suite / Build | Exact Scope | Observed Outcome | Runtime | Warnings |
|---|---|---|---:|---|
| `pytest sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | `421` non-T2 tests (`sia_core_v3`, `calibre_core`, `backend` including live Flink/Kafka replay `test_01`) | **`421 passed, 0 failed, 0 skipped`** | `166.50s` | `2` deprecation (`starlette` `multipart`, `fastf1` `.enable_cache`) |
| `pytest backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | `10` live 3-broker KRaft integration & chaos tests | **`10 passed, 0 failed, 0 skipped`** | `19.16s` | `0` |
| `cd frontend && npm run build` | TypeScript compilation (`tsc -b`) + Vite bundle | **`59 modules transformed`** | `1.42s` | `0` |

---

## 3. Initial Critical Findings Identified Prior to Phase H Remediation

1. **Apache Flink Blind Spot & `telemetry.car` Drop in Active Pipeline (`backend/pulse/testing/orchestrator.py`, `backend/pulse/stream/flink/jobs/normalizer_job.sql`, `backend/pulse/main.py`):**
   - `VerticalSliceVerifier._stage_verify_flink_streams()` constructs `expected_map = {env.event_id: env}` in memory rather than consuming from `pulse.norm.*` Kafka topics.
   - `orchestrator.py` routes Silverstone `POSITION_UPDATE` events (`71,960 / 72,642` = `99.06%`) into `pulse.raw.telemetry.car.v1`, which is absent from `normalizer_job.sql` (resulting in `432,517` unread raw messages stranded on `pulse.raw.telemetry.car.v1`).
   - `orchestrator.py` reuses identical `event_id` values across repeated runs (`benchmark_run_1..3`), causing Flink `ROW_NUMBER() OVER (PARTITION BY event_id)` to filter subsequent runs within its `300s` TTL while Stage 3 still reports `72,642` normalized.
   - `main.py` checks only `flink_mgr.client.is_cluster_online()`, never calling `ensure_normalizer_job_running()` on startup if Flink restarts clean.
2. **Kafka Offset Commit vs SIA WAL Durability Gap (`backend/pulse/main.py`, `backend/pulse/config.py`, `backend/pulse/stream/kafka_client.py`):**
   - `config.py` defines `sia_wal_path = "data/sia_ledger.sqlite"`, yet `settings.sia_wal_path` is never read anywhere in the runtime. `main.py` constructs `IntegrityAgent(bus=bus)` with `wal_path=None` (volatile RAM only).
   - `KafkaBroker.create_consumer()` in `kafka_client.py` instantiates `AIOKafkaConsumer(..., enable_auto_commit=True)` instead of `kafka_io.CalibreConsumer` (`cooperative-sticky`, `enable.auto.offset.store=False`), allowing Kafka offsets & `IdempotentVerdictSink` to commit consumption even though SIA state vanishes on process crash/restart.
3. **Cross-Partition SIA `session_t0` Ordering Race (`backend/pulse/integrity/agent.py`):**
   - `_maybe_admit_session_t0()` treats the very first arriving event as `session_t0` and ignores later `SESSION_STARTED` events if an out-of-order partition lap event arrives before `SESSION_STARTED`.
4. **Methodology Discrepancies in `reports/pipeline_latency_report.json` (`scripts/benchmark_pipeline_latency.py`):**
   - Layer 1 (`42.93ms`) runs sequential `concurrency=1` `await fut` per message, while full-run Stage 2 (`95.25s` = `762.4 evt/s`) runs `batch_size=50` `asyncio.gather` batches.
   - Benchmark 1 agent timings (`0.229ms` / `0.0225ms` / `0.0478ms`) run with `broker.is_connected == False` (zero Kafka I/O), whereas Benchmark 2 Stages 4–8 run with `self.broker.is_connected == True`, adding serial 1-by-1 `await fut` Kafka publish latency to every emitted `Finding` (`7.64s` / `2.54s` / `7.53s`).
   - Full-pipeline benchmark runs `num_runs=3` and feeds that into `compute_stats()`, labeling the sample maximum as `p95`/`p99`. Seek speedup tables compared Baseline `target_index=25000` (`141.2s`) against post-fix `target_index=36321` (`20.8s`).
5. **Test Suite Assertion & Fidelity Gaps (e.g. `test_kafka_integration_t1_t10.py`, `test_phase4_reliability.py`, `test_browser_cockpit.py`):**
   - `test_t3` never stops 2 brokers or calls `produce()`, `test_t8` sends 1 JSON tick without isolation checks, `test_t9` never restarts a second static-member consumer, `test_t10` ignores its partition variables and hashes identical dicts twice, `test_06` switches consumer `group_id`, `test_07` asserts `checkpoints_completed >= 0`, and `test_browser_cockpit.py` asserts static PNG screenshot sizes rather than live browser behavior.
6. **Residual Frontend Hardcodings (`frontend/src/App.tsx`, `PipelineLabView.tsx`):**
   - `App.tsx:239` `onImpactAssessmentUpdate` hardcodes `dn === 16 ? 'positive' : dn === 44 ? 'negative' : 'neutral'`.
   - `PipelineLabView.tsx` still displays static fallbacks (`10/10 STAGES RECONCILED`, `localhost:9092`, `14 active`, `193` checkpoints) and reads non-existent fields `inputs_expected` / `outputs_actual` / `drops` instead of `input_count` / `output_count` / `drop_count`.

---

## 4. What Could Not Be Verified Without External Licensing

- **Live Institutional F1 Transponder / ECU Feeds:** Official F1 SignalR and F1TV streams remain prohibited under Formula 1 Terms of Use without institutional licensing (`DATA_SOURCING_ASSESSMENT.md`); telemetry integrity cross-checks on hardware-disjoint loops rely on `LAB` test injections and offline `data/fastf1_cache/` archives.
