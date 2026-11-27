# PULSE Baseline Validation Report (Phase 0)

**Date:** 2026-11-25  
**Repository:** `E:\Caliberv2`  
**Checkpoint Branch:** `pulse-reconstruction` (branched from pre-reconstruction baseline `9f1af40`; upstream `kafka-v2` preserved untouched at `1297a09`)  
**Scope:** Independent reproduction and verification of active code, runtime services (3-broker Kafka KRaft cluster & Apache Flink 1.18.1), historical datasets, test suites, benchmarks, and UI/API behavior prior to reconstruction.

---

## 1. Executive Summary

Independent inspection and execution against the active `E:\Caliberv2` codebase confirm the core structural diagnoses raised in prior audits (`docs/COMPREHENSIVE_SYSTEM_AUDIT_2026.md`, `docs/AUDIT.md`), while sharpening root-cause precision on runtime behavior, Flink SQL failure semantics, benchmark bottlenecks, and frontend/backend mismatches.

| Baseline Check | Measured Result (2026-11-25) | Status |
|---|---|---|
| Docker Kafka KRaft 3-broker cluster (`kafka-1/2/3`, `cp-kafka:7.7.0`) | Healthy on ports `19092-19094` | Live / Operational |
| `test_kafka_integration_t1_t10.py` (`T1-T10`) | **10/10 PASSED** in `20.08s` (`kafka_io.py` verified against live cluster) | Verified (`kafka_io.py` unused by `main.py`) |
| Mainline runtime Kafka client (`kafka_client.py`) | Publishes to 1-partition `RF=1` topics; lacks EOS/DLQ/driver affinity | Split-brain architecture confirmed |
| Apache Flink `1.18.1` (`calibre-flink-jobmanager/taskmanager`) | Online (`:8081`), **missing `flink-sql-connector-kafka` JAR** (`ValidationException`) | Broken Kafka SQL connector |
| Non-integration test suites (`backend`, `sia_core_v3`, `calibre_core`) | **403 passed, 3 failed, 1 skipped** in `57.10s` | 3 Flink/replay reliability failures |
| Mid-race seek benchmark (`f1-2023-silverstone-race`, `target_index=25000` / `72642`) | **141,183.6 ms (141.2 s)** | Severe interactive bottleneck |
| Snapshot latency at idle vs mid-race (`target_index=25000`) | `2.3 ms` idle -> **6,776.7 ms (`199.4 KB`)** mid-race | Severe polling bottleneck |
| Baseline F1 lap model (`VehicleResponseAgent`) vs real FastF1 accurate green laps | MAE **10.49 s** (Monaco 2022) to **38.24 s** (Japan 2022) / **122.67 s** (Belgium 2021) | Hardcoded `76.0 s` baseline invalid |
| Uncompensated raw stint OLS slopes across dry FastF1 races | Median slopes negative (`-0.031` to `-0.352 s/lap`) | Fuel burn & track evolution confound raw OLS |

---

## 2. Environment & Test Suite Reproduction

### 2.1 Live Cluster & Flink Probe
- Docker Compose (`docker-compose.kafka.yml`) brings up `kafka-1`, `kafka-2`, `kafka-3`, `kafka-ui` (`:8080`), `calibre-flink-jobmanager` (`:8081`), and `calibre-flink-taskmanager`.
- Inspecting `/opt/flink/lib` inside `calibre-flink-jobmanager` confirms Flink `1.18.1` ships only `flink-cep`, `flink-connector-files`, `flink-csv`, `flink-dist`, `flink-json`, `flink-scala_2.12`, `flink-table-api-java-uber`, `flink-table-planner-loader`, and `flink-table-runtime`. No `flink-sql-connector-kafka` JAR exists.
- Executing `FlinkStreamManager.ensure_normalizer_job_running()` reproduces:
  - `org.apache.flink.table.api.ValidationException: Could not find any factory for identifier 'kafka' that implements 'org.apache.flink.table.factories.DynamicTableFactory' in the classpath. Available factory identifiers are: blackhole, datagen, filesystem, print, python-input-format`.

### 2.2 Baseline Test Suite Outcomes
1. **`pytest backend\tests\test_kafka_integration_t1_t10.py -v --tb=short`** -> **10 passed in 20.08s** (proving the unused `pulse/stream/kafka_io.py` stack passes `T1-T10`: driver affinity, single-broker failover, 2-broker ISR safety, cooperative rebalance, EOS `read_committed`, idempotent SQLite sink, DLQ, watermark isolation, static membership, partition invariance).
2. **`pytest backend\tests sia_core_v3\tests calibre_core\tests -k "not test_kafka_integration_t1_t10" -q --tb=short`** -> **403 passed, 3 failed, 1 skipped, 10 deselected in 57.10s**:
   - `FAILED backend/tests/test_fault_injection.py::test_duplicate_race_control_event` -> `RuntimeError` from Flink `'kafka'` `ValidationException`.
   - `FAILED backend/tests/test_phase4_reliability.py::test_01_normal_complete_historical_replay` -> `RuntimeError` from Flink `'kafka'` `ValidationException`.
   - `FAILED backend/tests/test_phase4_reliability.py::test_07_flink_checkpoint_recovery` -> `assert metrics is not None` (job failed to start due to missing connector).

---

## 3. Confirmed Phase 0 Findings by Subsystem

### 3.1 Provenance Misrepresentation & Synthetic Contamination (P0)
- **Confirmed across session registry, capture manifests, and JSONL envelopes:**
  - `backend/pulse/sessions/registry.py` (`SESSION_REGISTRY`, lines 24-287) labels **all 10 sessions**, including synthetic `f1-2026-monaco-sim` and `f1-2026-suzuka-race`, with `source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY"`.
  - `captures/f1-2026-monaco-sim/capture_manifest.json` (`72,926` envelopes), `captures/f1-2026-suzuka-race/capture_manifest.json` (`72,617` envelopes), and aliases `pulse-sim-monaco-v1`, `pulse-sim-v1` declare `provider: "FIA_OFFICIAL_TIMING_AND_TELEMETRY"`.
  - Sampled envelopes across `f1-2026-monaco-sim`, `f1-2023-silverstone-race`, and `f1-2021-abu-dhabi` embed `source.provider = "FIA_OFFICIAL_TIMING"` and fabricated `licence_reference = "FIA-F1-DATA-ACQUISITION-V1"`.
  - `captures/f1-2026-monaco-sim` (`[77, 78, ...]`) and `captures/f1-2023-silverstone-race` (`[110, 111, 112, ...]`) contain integer synthetic lap durations and identical synthetic weather blocks (`air_temp_c: 22.4, track_temp_c: 34.2, rain_risk_percent: 10.0`); `f1-2021-abu-dhabi`..`f1-2024-united-states` captures each span only `~24,500` records (`duration_seconds: 600` in manifests).
  - `backend/pulse/stream/projections.py` synthesizes driver telemetry histories via `_generate_synthetic_telemetry_history`, pre-populates fake future `2026-05-24` FIA notices in `_init_official_notices`, and hardcodes `PIT_ENTRY` speed `60.0`.

### 3.2 SIA Core v3 (`sia_core_v3`) & Integrity Integration Defects (P0/P1)
- **Temporal wall-clock leakage on historical events:** Sending a historical `2021-12-12T13:00:00Z` `WEATHER_OBSERVATION` into `IntegrityAgent` with omitted `ingest_time_utc` falls back to `utc_now()` and immediately forces the verdict into `DEGRADED FINAL` (`resilience={'required_k': 0, 'profile': {}, 'critical_origins': []}`).
- **Schema mismatch in `void_decision` (`sia_core_v3/sia_core/engine.py:128-175`):** Emits `"maturity_status": "TUPLE_RESOLVED"` and enum `.value` objects rather than the standard `"resolution_maturity"` / structured `Assessment` shape produced by `evaluate_decision` (`evaluator.py:584-680`).
- **Pre-admission finality ordering (`sia_core_v3/sia_core/engine.py:78-105`):** `_check_finality` executes *after* `self.ledger.admit_*`, recording late/quarantined evidence inside the main ledger instead of quarantining prior to ledger mutation.
- **No durable SIA persistence:** `sia_core_v3/sia_core/ledger.py` holds atoms, facts, guards, assessments, and hash-chains solely in RAM (`calibre_core/admission.py` exists separately and is unintegrated into `pulse/main.py` / `IntegrityAgent`).
- **False source independence & passive contracts:**
  - `backend/pulse/integrity/bridge.py:45-56, 252-268` maps disparate strings (`FIA_OFFICIAL_TIMING`, `JOLPICA_F1_AND_FIA_OFFICIAL`, `F1_TIMING`, `LIVE_TIMING`) into `"PITWALL"` -> `["F1_FOM_TIMING"]`, failing to distinguish genuinely independent origins vs derived open feeds vs synthetic feeds.
  - `backend/pulse/integrity/contracts.py:27-231` configures `"corroboration": {"mode": "INFORMATIONAL"}` on every role and `resilience_requirement: 0` on 4 of 5 runtime contracts (`lap_time`, `sector_time`, `driver_position`, `weather_observation`).

### 3.3 Scientific Defects in F1 Domain Agents (P1)
Reproducible evaluation on real historical races from `data/f1_corpus/` and `data/fastf1_cache/` (`FastF1 v3.9.0`):

| Historical Race (FastF1 Cache) | Clean Green Accurate Laps | Median Clean Lap (s) | Hardcoded `VehicleResponseAgent` MAE (s) | Naive Prev-Lap MAE (s) | Uncompensated Stint OLS Median Slopes (`neg / total` stints) |
|---|---:|---:|---:|---:|---|
| 2021 Abu Dhabi | 785 (`818` corpus) | 89.59 | **13.65** (`818` corpus) | 0.400 | HARD `-0.0448` (`17/19`), MEDIUM `-0.0871` (`11/12`), SOFT `-0.0313` (`6/8`) |
| 2021 Belgium (SC-only) | `20` corpus | 198.66 | **122.67** | — | Insufficient green running |
| 2021 Great Britain | 827 (`867` corpus) | 93.25 | **18.27** (`867` corpus) | 1.250 | HARD `-0.0370` (`17/19`), MEDIUM `-0.1025` (`18/20`) |
| 2021 Saudi Arabia | 524 (`530` corpus) | 93.98 | **19.50** (`530` corpus) | 3.156 | HARD `-0.3519` (`13/13`), MEDIUM `-0.3154` (`21/24`) |
| 2022 Monaco | 844 (`967` corpus) | 80.38 (`81.62` corpus) | **10.49** (`967` corpus) | 2.006 | HARD `-0.3394` (`8/8`), MEDIUM `-0.2918` (`10/10`), WET `-0.8145` (`14/14`) |
| 2022 Japan | 403 (`403` corpus) | 109.26 | **38.24** (`403` corpus) | 3.908 | INTER `+0.1659` (`1/23` neg) |

*(Note: `2023_australia`, `2023_austria`, `2023_las_vegas`, `2024_united_states` in `data/f1_corpus/` originate from Ergast/Jolpica summary exports with `lap_time_seconds: None`.)*

- **`VehicleResponseAgent` (`backend/pulse/agents/vehicle_response.py:30-36, 117`):** Hardcodes 5 driver baselines (`75.80-76.35 s`) and falls back to `76.0 s`, producing `10.5-38.2 s` MAE across real dry F1 circuits.
- **`TyreStrategyAgent` (`backend/pulse/agents/tyre_strategy.py:30-43, 102-115`):** Uses fixed hardcoded slopes (`S: +0.12`, `M: +0.06`, `H: +0.03` s/lap) and fixed pit loss (`21.5s` green, `11.0s` VSC, `13.5s` SC) with zero fuel-burn adjustment or uncertainty quantification, whereas raw F1 stint OLS without fuel-mass & track-evolution separation yields predominantly negative slopes on dry races.
- **`ConsequenceFusionEngine` (`backend/pulse/agents/fusion.py:40-332`):** Produces templated narratives, string-format bugs such as `P{range[0]}-P{range[1]}` evaluating to `P-1-P0`, and retains unbounded correlation history buffers in RAM.

### 3.4 Kafka Split-Brain & Flink Architectural Findings (P1)
- Runtime (`pulse/main.py`, `PulseEventBus`, `ReplayController`, `testing/orchestrator.py`) imports **`pulse/stream/kafka_client.py`** (`1` partition, `RF=1`, no idempotence, no transactions, no DLQ, no driver affinity) instead of **`pulse/stream/kafka_io.py`** (`11` partitions, `RF=3`, `MIN_ISR=2`, `DriverSlots`, EOS transactional processor, idempotent SQLite sink, DLQ) which already passes `T1-T10` against the running KRaft cluster.
- Note on topic/broker mismatch: `docker-compose.kafka.yml` enforces `KAFKA_DEFAULT_REPLICATION_FACTOR=3`, `KAFKA_MIN_INSYNC_REPLICAS=2`, and `KAFKA_AUTO_CREATE_TOPICS_ENABLE=false`.
- Flink `normalizer_job.sql` cannot deploy without `flink-sql-connector-kafka` in `/opt/flink/lib`; additionally, Python runtime currently handles normalization/processing directly when in `SIMULATOR` mode rather than requiring Flink SQL jobs.

### 3.5 Replay Performance & API Isolation Defects (P1)
Reproduced via `TestClient(app)` on `f1-2023-silverstone-race`:
- **Mid-race seek (`POST /api/replay/seek {"target_index": 25000}`):** **`141,183.6 ms` (~141.2 s)** to replay 25,000 events (`34.4%` of race) from index `0` because every seek resets and synchronously replays every event through all 5 agents + Fusion + SIA without keyframes.
- **Snapshot serialization bottleneck (`GET /api/snapshot`):** `2.3 ms` (`65.7 KB`) at `currentIndex=0`, degrading to **`6,776.7 ms` (`199.4 KB`)** at `currentIndex=25000`.
- **Session path isolation bug:** `GET /api/sessions/bogus-session-id/drivers` returns **`200 OK` with 20 drivers** (ignoring `session_id`), whereas `POST /api/sessions/select` properly returns `404`.
- **Speed validation defect:** `POST /api/replay/speed {"speed": 99.0}` returns **`200 OK`** and silently resets speed to `1.0x` rather than rejecting unsupported speeds (`422`) or applying bounded validation cleanly.

### 3.6 Frontend Honesty & Wiring Defects (P0/P1)
Confirmed directly in `frontend/src`:
- **`DecisionInspector.tsx:176-283`:** Reads `roleData?.atom` and `roleData?.state`, whereas SIA `evaluate_decision` returns `{kind, timeline, closed, deadline, cutoff, has_evidence, source_depth, processing_depth, support_atom_ids, reference_fact_ids, dependencies, latest_observed_at}` — causing admitted roles to render `Pending observation` / `UNKNOWN`; hardcodes `60.08 vs 60.0 km/h` `ThresholdMarginGauge` and static `FOM_OPTICAL_LOOP` / `D=2` / `Exposure 0.00` text.
- **`IntegrityMatrix.tsx:92, 669`:** `LIBRARY_CONTRACTS` keys (`C01_lap_time_consistency`, etc.) fail to match backend contract IDs (`lap_time`, `pit_speed`, `sector_time`, `driver_position`, `weather_observation`), dropping matrix active verdict counts under `ALL_13`; footer falsely claims calibrated optical loops & CAN-bus transponders.
- **`SiaLogicLabView.tsx:78` + `logic_lab/*`:** Passes hardcoded props (`corroborationDepth={2}`, `hasCommonCause={false}`, static `blake3:` hashes, `SAMPLE_ATOMS`) into `EntanglementGraph`, `ContextualityDag`, `SuperpositionView`, and `StateAlgebraTree` instead of real `activeVerdict` data.
- **`ReplayAuditView.tsx`:** Defaults instance selection to non-existent `'dec-pit_speed-d1'` (triggering `_ensure_decision_instance` side-effect in backend), defaults `K` to wall-clock `new Date().toISOString()`, hardcodes `'2023-04-02T05:00:00.000Z'` genesis button, and wires fault-injector buttons only to local UI text.
- **`AgentsPipelineView.tsx:38-114` & `App.tsx` / `AppHeader.tsx`:** Hardcodes legacy `f1.raw.*` topic names and `Blake3 hash chaining` (while backend uses SHA-256 RFC 8785); `App.tsx` hardcodes `dataRegime="PUBLIC"`, `timingSource="FOM Optical Loops & CAN Telemetry"`, and displays `IN-MEMORY EVENT BUS` or `DEGRADED / FALLBACK` strings inconsistently with active transport.
- **`PipelineLabView.tsx:53, 86-148` & `RaceControlView.tsx:34, 143`:** Hardcode `10/10 STAGES RECONCILED`, `localhost:9092`, `14 active`, `CHECKPOINTING`, and static stage table fallbacks when backend data is empty; `RaceControlView` still claims verbatim FIA Race Director notices while `projections.py` seeds fake 2026 notices.

---

## 4. Reconstruction Plan Reference

Subsequent work proceeds strictly through Stages B -> G:
1. **Stage B (Phase 1 & 2):** Provenance & regime honesty across manifests/registry/streams/UI, real source-independence/quorum policy in `contracts.py` & `bridge.py`, SIA schema & pre-admission finality quarantine fixes, deterministic historical clock semantics, SQLite WAL durability (`sia_core_v3` + `backend/pulse/integrity`), domain-independent schema verification, and full wiring of SIA frontend views (`IntegrityMatrix`, `DecisionInspector`, `SiaLogicLabView`, `ReplayAuditView`).
2. **Stage C (Phase 3):** Scientifically defensible F1 `VehicleResponseAgent`, fuel-compensated compound degradation `TyreStrategyAgent`, deterministic pit-window/undercut simulator, and ablation validation on real FastF1 temporal splits.
3. **Stage D (Phase 4 & 5):** Consolidate runtime Kafka on `kafka_io.py`, resolve Flink SQL Kafka connector (`flink-sql-connector-kafka` or justified simplification), and restructure Agents 01–05 + `ConsequenceFusionEngine`.
4. **Stage E (Phase 6 & 7):** Periodic keyframe checkpointing in `ReplayController` + O(1) `/api/snapshot` caching, API session isolation & `422` validation, and complete UI honesty & accessibility remediation verified in live Chrome.
5. **Stage F & G (Phase 8–12):** Online literature & primary patent claim verification, comprehensive regression/chaos/benchmark suite, consolidated `docs/` architecture documentation, and final audited scoring.
