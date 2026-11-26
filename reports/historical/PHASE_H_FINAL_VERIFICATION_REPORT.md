# PULSE — Phase H Master Independent Verification Report

**Project:** PULSE (formerly CALIBRE) — Real-Time Sports Event Stream Analytics & Integrity Platform  
**Repository:** `E:\Caliberv2`  
**Active Branch / Checkpoint:** `pulse-reconstruction` (preserved pre-Phase-H baseline commit `9f1af40b38e39f9484b5852f6f05e08d88518d46`)  
**Audit Date:** 2026-11-26  

> [!NOTE]
> **Prompt Input Boundary:** The Phase H prompt truncated mid-sentence in Section 7.4 (`- Duplicate verdict`). All preceding Sections (Baseline Reproduction, Distributed Kafka/Flink Verification, SIA WAL/Temporal/Origin Verification, `n=10` Benchmark Reconciliation, Scientific F1 Validation, Live Chrome DevTools Audit, and Patentability / Section 3(k) Readiness) were independently executed, repaired where defective, and verified end-to-end.

---

## 1. Executive Summary & System-Level Verdicts

| Evaluation Dimension | Independent Verdict | Key Measured Evidence |
|---|---|---|
| **1. Pre-Phase-H Claims vs. Actual Reality** | **PARTIALLY OVERSTATED AT BASELINE; NOW REMEDIATED** | Baseline `421 + 10 = 431` tests, `70/70` topics, and Vite build reproduced identically, but independent audit caught a stubbed Stage 3 Flink check, `2/9` unsubscribed raw topics, `zstd` producer crash bug, disconnected runtime SIA WAL (`wal_path=None`), `enable_auto_commit=True` Kafka loop, `4` tautological `T1-T10` / `2` weak reliability tests, methodology skew in benchmarks (`20.8s` vs `83.8s` seek), and an orphaned `PipelineLabView` + SSE sentiment bias in the UI. All were fixed and re-verified. |
| **2. Systems Architecture & Distributed Streaming** | **GENUINE & LIVE-VERIFIED** | 3-broker Kafka KRaft (`RF=3`, `MIN_ISR=2`) + Apache Flink `1.18.1` (`pulse-canonical-normalizer-v3`, `18` RUNNING vertices across all `9` `RAW_TOPICS`) + manual offset commit gated after SIA WAL + `IdempotentVerdictSink` (`436 / 436` total post-edit tests passing, including `10/10` full `72,642`-event E2E Flink runs = `726,420` events with `0` drops). |
| **3. SIA Core v3 Integrity Engine** | **STRONGEST SUBSYSTEM (DURABILITY FIXED)** | Strictly non-decreasing `K`, RFC 8785 + SHA-256 hash chaining (`637` Silverstone chains verified), transitive common-cause origin collapse (`F1_FOM_TIMING`), pre-admission finality quarantine, historical clock invariance, out-of-order `session_t0` supersession invariance, and live `SIGKILL` SQLite WAL recovery (`task-2518`: `21` chains, `28 -> 29` atoms intact). |
| **4. Scientific Formula 1 Methodology** | **DEFENSIBLE IN DRY RACES; HONEST UNDER DISRUPTION** | Strictly causal walk-forward baselines cut `76.0s` MAE from `17.34s` -> **`0.358s`** (British GP, `-97.9%`) and `13.63s` -> **`0.352s`** (Abu Dhabi, `-97.4%`), recover positive fuel-compensated Hard tyre wear (`15/19` British, `12/19` Abu Dhabi), and surface wider errors under red-flag/wet disruption (`3.701s`, `PI95 83.28%` Japan). Telemetry gaps stay `UNAVAILABLE`; provenance separates `SYNTHETIC`/`LAB`/`PREVIEW`. |
| **5. Benchmark Reconciliation (`n=10`)** | **HONEST & REPRODUCIBLE** | Replaced `n=3` P95-equals-max math, `tracemalloc` overhead, and stubbed Stage 3 with `n=10` trials: real Flink Stage 3 consume = `10.64s` med (`10/10` E2E med `184.87s`); cold `seek(36321)` = `83.80s` (`WAL OFF`) / `87.49s` (`WAL ON`); cached keyframe `seek(36500)` = `3.72s` (`23.55x` faster, `0` hash mismatches); `/api/snapshot` (`113.05 KB`) = `10.28ms` med (`12.81ms` P95); `/api/integrity/verify` (`637` chains) = `2,003.7ms` med. |
| **6. Frontend Completeness & UX** | **FUNCTIONAL & HONEST LIVE UI** | Wired `PipelineLabView` into `AgentsPipelineView`, replaced hardcoded `"5 Active"`/`"0.0%"`/`#16/#44` SSE biases, synced header session dropdown across hard reloads, and fixed `.node-kafka` Cluster wrapping. Live Chrome DevTools audit across `Monaco [Sim]` & `Silverstone [Historical]` on `KAFKA` + `Flink v3` passed with `0` console errors, `0` warnings, and `0` failed HTTP requests. |
| **7. Patentability & Section 3(k) Readiness** | **NOT READY TO FILE (`1.5–4.0 / 10`)** | Broad platform (`1.5/10`) and standalone SIA (`2.5/10`) are barred by Section 3(k) / 2025 CRI Guidelines and anticipating art (`US6020851A`, `US8713073B2`, `US10614239B2`, `US11567823B2`, `US20180089328A1`). Narrowest `4.0/10` hardware/network actuator interlock angle lacks physical actuation wiring today and requires formal FTO clearance. |

---

## 2. Final Post-All-Edits Regression & Build Evidence (`2026-11-26 19:21–19:25`)

All checks below were executed strictly **after** the final code/test edit (`wal.py`, `agent.py`, `main.py`, `App.tsx`, `PipelineLabView.tsx`, `AgentsPipelineView.tsx`):

1. **Kafka Topic Catalogue Verification:**
   - `PYTHONPATH=backend python -m pulse.stream.kafka_io --verify` -> Exit `0`: **`[OK] All 70 topics verified against live broker with zero drift.`**
2. **Complete Non-T2 Pytest Suite (`sia_core_v3`, `calibre_core`, `backend`):**
   - `pytest sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` -> **`426 passed, 0 failed, 0 skipped`** (`190.24s`, `2` deprecation warnings: `starlette` `multipart`, `fastf1` `.enable_cache`). Includes live Flink v3 `72,642`-event `test_01_normal_complete_historical_replay`, strengthened `test_06`/`test_07`, and `5` Phase H regression tests (`test_phase_h_verification.py`).
3. **Live 3-Broker Kafka KRaft & Chaos Integration Suite (`T1–T10`):**
   - `pytest backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` -> **`10 passed, 0 failed, 0 skipped`** (`44.17s`, `0` warnings), including hardened live multi-broker container stop/start `T2`/`T3`, readback `T8`, static-member standby `T9`, and real multi-partition SHA-256 invariance `T10`.
4. **Combined Post-Edit Automated Pass Count:** **`436 passed, 0 failed, 0 skipped`** across all Python suites.
5. **Frontend Production Build:**
   - `cd frontend && npm run build` -> Exit `0`, **`✓ 60 modules transformed`**, **`✓ built in 1.41s`**, `0` warnings.
6. **Live Dev Servers Cleanliness:** Stopped both background `uvicorn` (`:8000`) and `vite` (`:5173`) daemons cleanly and confirmed `0` lingering listeners via `Get-NetTCPConnection`.

---

## 3. Summary of Critical Defects Caught & Fixed During Phase H

1. **Flink Normalizer Coverage & Stage 3 Verification (`normalizer_job.sql`, `topics.py`, `kafka_io.py`, `orchestrator.py`, `manager.py`, `main.py`):**
   - Added missing `kafka_raw_telemetry_car` (`71,960` Silverstone `POSITION_UPDATE` events/run) and `kafka_raw_session_status` tables to SQL `pulse-canonical-normalizer-v3` (now `18` vertices over all `9` `RAW_TOPICS`).
   - Switched `CalibreProducer` default compression from `"zstd"` -> `"gzip"` cleanly preventing Flink `NoClassDefFoundError` on `ZstdInputStream`.
   - Rewrote Stage 3 in `orchestrator.py` to consume real Flink outputs from `pulse.norm.*` using per-run `event_id`s and pre-Stage-2 partition watermarks (`10/10` `72,642`-event runs reconciled with `0` drops).
   - Fixed Flink job slot stacking under broker restarts (`manager.py`) and auto-ensured the Flink job in `main.py` startup.
2. **Kafka Offset Commit <-> SIA WAL Durability Coupling (`main.py`, `store.py`, `agent.py`, `wal.py`):**
   - Wired `settings.sia_wal_path` cleanly into live runtime, switched `kafka_consumer_loop()` to `enable_auto_commit=False` + `getmany` micro-batches committing offsets strictly after `_route_normalized` + SIA WAL persist + `IdempotentVerdictSink`, and verified recovery across live `SIGKILL` (`task-2518`) and Flink TaskManager restart (`task-2524`).
   - Fixed 5 crash bugs in `SIAWALStore.sync_engine()`, added SQLite WAL lifecycle cleanup across teardown/reset (caught directly during full-suite `test_replay_processing.py` run), and added authoritative `session_t0` supersession invariance in `IntegrityAgent`.
3. **Frontend Integrity & Completeness (`App.tsx`, `PipelineLabView.tsx`, `AgentsPipelineView.tsx`, `types.ts`):**
   - Removed `#16/#44` driver sentiment bias, corrected `input_count`/`output_count`/`drop_count` bindings, removed fake placeholders, mounted orphaned `PipelineLabView` as 4th subtab in `AgentsPipelineView`, connected live KPI/topology telemetry, synced session `<select>` across hard browser reloads, and wrapped `.node-kafka` Cluster strings.

---

## 4. Honest Operational Weaknesses & Documentation Discrepancies Remaining

1. **Cold Full-Race Seek Overhead (~84–94 s vs Pre-Edit 20.8 s Claim):** Reconstructing `36,321` events sequentially through Python agents + SIA (`WAL OFF`: `83.80s`; `WAL ON`: `87.49s` median, `125.35s` max) remains slow whenever no cached keyframe exists (`3.72s` with keyframe). Initial warm integrity cache generation on `/api/snapshot` shows a first-call `2,092.81ms` outlier before settling to `10.28ms` median (`12.81ms` P95).
2. **Single-Host Bulk Ingest Variance & Missing API Auth:** `orchestrator.py`'s `batch_size=50` sequential barrier awaits cap ingest speed (`~127s` avg vs `27,719 evt/s` producer bulk enqueue) with `stdev = 28.16s` across 10 runs on shared Docker resources. Meanwhile, `FastAPI` still exposes `allow_origins=["*"]` with unauthenticated control endpoints (`start`, `seek`, `reset`).
3. **F1 Model & Agent Asymmetry:** `Agent 01` and `Agent 02` remain threshold/lifecycle state machines; `Agent 05` (`fusion.py:274–278`) leaves uncalibrated `PRIOR_UNMEASURED` v2 pit-window assessments marked `CONFIRMED` unless SIA conflicts trigger; `Pace/Tyre` uses uniform `100 kg` fuel assumptions, and `PitWindowStrategySimulator` lacks full multi-stint Monte Carlo rollover optimization. Live licensed F1 timing/telemetry streams are absent (strictly segregated behind `SYNTHETIC`/`LAB`/`PREVIEW` metadata).
4. **Residual Pre-Phase-H Doc Drift:** Earlier docs (`docs/KAFKA_AND_FLINK_ARCHITECTURE.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION_AND_BENCHMARKS.md`) still contain outdated pre-Phase-H references (`:9092` internal port vs `:29092`, `pulse.f1.*` topic prefix vs `pulse.raw.*/pulse.norm.*`, `7` raw topics / `-v2` vs `9` raw topics / `-v3`, and `20.8s`/`1.1ms`/`480.3ms` latency figures).

---

## 5. Complete Phase H Verification Deliverables

- [PHASE_H_BASELINE.md](file:///e:/Caliberv2/docs/verification/PHASE_H_BASELINE.md) — Pre-edit checkpoint `9f1af40b`, baseline reproduction & initial defect inventory.
- [PHASE_H_TEST_RESULTS.md](file:///e:/Caliberv2/docs/verification/PHASE_H_TEST_RESULTS.md) — Baseline test/coverage audit, assertion hardening matrix & final `436 / 436` post-edit results.
- [PHASE_H_BENCHMARK_RECONCILIATION.md](file:///e:/Caliberv2/docs/verification/PHASE_H_BENCHMARK_RECONCILIATION.md) — `n=10` benchmark reconciliation (`Benchmark 1/2/3`), Docker footprint & live `uvicorn` RSS (`586–641 MB`).
- [PHASE_H_KAFKA_FLINK_VERIFICATION.md](file:///e:/Caliberv2/docs/verification/PHASE_H_KAFKA_FLINK_VERIFICATION.md) — 3-broker KRaft, Flink v3 (`18` vertices), `T1–T10` chaos & TaskManager restart evidence.
- [PHASE_H_SIA_VERIFICATION.md](file:///e:/Caliberv2/docs/verification/PHASE_H_SIA_VERIFICATION.md) — SIA Core v3 formal properties, `session_t0` supersession, WAL durability & live `SIGKILL` drill.
- [PHASE_H_SCIENTIFIC_FRONTEND_PATENT.md](file:///e:/Caliberv2/docs/verification/PHASE_H_SCIENTIFIC_FRONTEND_PATENT.md) — Causal FastF1 evaluation, Chrome DevTools UI verification & Section 3(k) patentability audit.
- [PHASE_H_FINAL_VERIFICATION_REPORT.md](file:///e:/Caliberv2/docs/verification/PHASE_H_FINAL_VERIFICATION_REPORT.md) — Executive reconciliation & final technical verdict.
