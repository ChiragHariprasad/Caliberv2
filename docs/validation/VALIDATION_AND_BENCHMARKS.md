# PULSE — Validation, Scientific Benchmarks & UI Audit Ledger

**Status:** Canonical Authoritative Benchmark Ledger (Phase I Reproducible)  
**Machine-Readable Evidence:** [`baseline_comparison.json`](../../reports/benchmarks/baseline_comparison.json) · [`ablation_study.json`](../../reports/benchmarks/ablation_study.json) · [`phase_i_replay_benchmarks.json`](../../reports/benchmarks/phase_i_replay_benchmarks.json) · [`phase_i_kafka_sustained.json`](../../reports/benchmarks/phase_i_kafka_sustained.json)

---

## 1. Automated Verification Summary (Stage 9 Post-Final Edit)

All commands below were executed against the live 3-broker KRaft + Apache Flink 1.18.1 cluster after all code/test changes completed (`kafka-1/2/3`, `calibre-flink-jobmanager/taskmanager`, zero lingering dev servers on ports `:8000`/`:5173`):

| Verification Command | Scope | Observed Result | Duration |
|---|---|---|---|
| `npm run build` (`frontend/`) | TypeScript compilation (`tsc -b`) + Vite production bundle | **`60 modules transformed`**, zero warnings (`dist/index.html` `0.88 kB`, CSS `93.11 kB`, JS `479.10 kB`) | `2.69s` |
| `python -m pulse.stream.kafka_io --verify` | Live 3-broker Kafka 70-topic verification | **`70 / 70` topics verified (`0` drift)** | `< 2s` |
| Non-T2 `pytest sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py` | SIA formal invariants, contracts, scientific baselines, API/security, durability, keyframe replay | **`450 passed, 0 failed, 0 skipped`** (`2` upstream lib deprecation warnings) | `322.16s` |
| Live Kafka chaos `pytest backend/tests/test_kafka_integration_t1_t10.py` | Live 3-broker failover, ISR, EOS `read_committed`, static standby, `SHA-256` partition invariance (`T1–T10`) | **`10 passed, 0 failed, 0 skipped`** | `56.92s` |
| `python scripts/check_docs.py` | `12`-doc canonical structure, link resolution, zero stale claims | **PASS** (`12 / 12` docs verified, `0` errors) | `< 1s` |

**Combined Stage 9 Python Automated Pass Count:** **`460 passed, 0 failed, 0 skipped`**.

---

## 2. Scientific F1 Evaluation — 6-Baseline LORO, Holdout & Ablation (`baseline_comparison.json`)

**Script:** [`scripts/run_baseline_comparison.py`](../../scripts/run_baseline_comparison.py) · **Module:** [`backend/pulse/analytics/baseline_comparison.py`](../../backend/pulse/analytics/baseline_comparison.py)  
**Protocol:** Causal crossing-order evaluation (`predict_baseline()` strictly before `observe_lap()`, `LapStartTime`-derived inter-car intervals using same-lap prior cars only, regression fits strictly inside calibration/LORO folds).  
**Splits:** Calibration (`2021 British`, `2021 Saudi Arabian`, `2022 Monaco`), Held-out Test (`2021 Abu Dhabi`, `2022 Japanese`), Disruption Edge Case (`2021 Belgian` SC).

### 2.1 Five-Race Leave-One-Race-Out (LORO) Aggregate Comparison

| Model Baseline | Predicted Laps (`n`) | Weighted MAE (`s`) | Weighted RMSE (`s`) | Empirical 95% PI Coverage | Mean PI95 Width (`s`) | Gap from 95% Target | Calibrated (`±2%`)? |
|---|---:|---:|---:|---:|---:|---:|:---:|
| **`previous_lap`** | `1,866` | `0.8046` | `3.6967` | `93.46%` | `13.78` | `-1.54%` | Yes *(wide)* |
| **`rolling_5_median`** | `1,778` | `0.9414` | `3.1020` | `89.15%` | `4.22` | `-5.85%` | **No** |
| **`rolling_clean_air_median`** | `1,610` | `1.2644` | `4.0527` | `89.50%` | `7.78` | `-5.50%` | **No** |
| **`circuit_normalized_regression`** | `1,610` | `1.6991` | `4.2975` | `86.46%` | `7.53` | `-8.54%` | **No** |
| **`existing_fuel_compensated`** | `1,610` | `1.5057` | `5.1145` | `92.48%` | `17.54` | `-2.52%` | **No** |
| **`revised_pulse` (Phase I)** | **`1,560`** | **`0.5094`** | **`0.9043`** | **`93.91%`** | **`3.28`** | **`-1.09%`** | **Yes** |

### 2.2 Per-Race Performance & Held-Out Generalization (`revised_pulse` vs `existing_fuel_compensated`)

| Split | Grand Prix | `existing_fuel_compensated` (`n` / MAE / RMSE / PI95) | `revised_pulse` (`n` / MAE / RMSE / PI95 / Width) | Root Cause / Domain Insight |
|---|---|---|---|---|
| Calibration | **2021 British** | `390` / `2.2449s` / `6.9970s` / `95.64%` | `373` / **`0.3872s`** / **`0.7685s`** / `93.30%` / `2.20s` | Eliminated Lap 4 standing-restart contamination (`160.13s` mixing with `92.81s` flying lap). |
| Calibration | **2021 Saudi Arabia** | `234` / `2.5475s` / `7.3042s` / `92.74%` | `223` / **`0.4578s`** / **`0.8117s`** / `93.72%` / `2.80s` | Restart fast-recovery reset stopped post-red-flag RMSE explosion. |
| Calibration | **2022 Monaco** | `386` / `1.6642s` / `4.0221s` / `90.93%` | `365` / **`0.8265s`** / **`1.3507s`** / `93.42%` / `5.48s` | Wet-to-dry crossover transitions (e.g., Inter->Hard outlier `+8.22s`) remain primary failure mode. |
| **Holdout** | **2021 Abu Dhabi** | `433` / `0.3495s` / `0.5721s` / `92.61%` | `433` / **`0.3495s`** / **`0.5721s`** / **`94.46%`** / `2.43s` | Stable dry race; calibrated conformal quantile tightens PI gap to `-0.54%`. |
| **Holdout** | **2022 Japan** | `167` / `0.9507s` / `4.9857s` / `88.02%` | `166` / **`0.5730s`** / **`0.7791s`** / **`95.18%`** / `3.72s` | Resolved Phase H `83.28%` under-coverage root cause (`fast_restart_recovery=True` + causal scaling). |
| Edge Case | **2021 Belgium** | `0` predicted (`13` target laps) | `0` predicted (`13` target laps) | SC-only rain session correctly refuses invalid green-flag extrapolation. |

### 2.3 Seven-Component Ablation Study (`ablation_study.json`)

| Variant / Component Tested | Sample Size | Key Metric Effect | Ablation Conclusion |
|---|---:|---|---|
| **`full_revised` *(standalone default)*** | `1,560` | MAE `0.5094s`, RMSE `0.9043s`, PI95 `89.94%` | Minimal calibrated conformal adjustment in full pipeline restores `PI95 = 93.91%`. |
| **Remove Clean-Air Filtering** | `1,758` | MAE `0.5452s`, **RMSE `1.4542s`** (`+60.8%`) | Clean-air filter strongly suppresses traffic tail outliers. |
| **Remove Fuel Compensation** | `1,560` | MAE `0.5141s`, RMSE `0.8968s` | Small short-window pace impact; essential inside stint degradation slope sign recovery (`+0.0303 s/lap` British Hard). |
| **Remove Track Evolution** | `1,560` | **MAE `0.6418s`** (`+26.0%`), RMSE `1.1256s` | Track-evolution Kalman term meaningfully reduces systematic session drift. |
| **Remove Compound Effects** | `1,742` | **MAE `0.9829s`** (`+93.0%`), **RMSE `3.8053s`**, PI95 `86.68%` | Largest single contributor: cross-compound resets prevent multi-second tyre transition spikes. |
| **Empirical-Bayes Shrinkage** | `277` stint laps | OLS MAE `0.6851s` -> Shrinkage **`0.4772s`** (**`-0.2079s`**) | Pooling noisy short stints substantially stabilizes slope estimation. |
| **SIA & Agent 05 Gate** | `10` scenarios | Pre-Phase I `Precision 0.2222`, **`FPR 0.875`** -> Phase I **`Precision 1.000`, `Recall 1.000`, `FPR 0.000`** | Enforcing calibration & SIA corroboration eliminates uncalibrated false confirmations on controlled probes. |

---

## 3. Cold Replay Optimization & Determinism (`phase_i_replay_benchmarks.json`)

**Session:** `f1-2023-silverstone-race` (`72,642` events, target mid-race index `36,321`) · **Scripts:** [`scripts/profile_cold_seek.py`](../../scripts/profile_cold_seek.py), [`scripts/benchmark_phase_i_replay.py`](../../scripts/benchmark_phase_i_replay.py)

1. **Profiling Root Cause (`cProfile`, `51.28s` traced run):**
   - `sia_core/model.py::scope_in`: `7,695,405` calls (`8.188s`) driven by unindexed scans across `Ledger.facts` in `evaluator.py`.
   - `sia_core/canon.py::jcs`: `3,261,806` `json.dumps` invocations (`9.340s`) on ASCII dictionary keys.
   - `replay/controller.py::_for_current_run`: `4,282,193` Pydantic `deepcopy` calls (`7.213s`).
2. **Paired Standalone & Subprocess Benchmarks (`0` SIA hash mismatches across `637` / `451` verified decisions):**
   - **Clean Paired Standalone Unthrottled Cold `seek(36321)`:** **`21.0772 s -> 14.6917 s`** (**`-30.3%`** speedup; cached backward seek **`0.2861 s`**, cached forward seek **`1.2081 s`**, `637` decisions verified, `0` mismatches).
   - **5-Trial Full Subprocess Cold `seek(36321)` Benchmark:** **`mean = 70.8831 s`**, `std = 1.0337 s`, `min = 69.6203 s`, `p50 = 71.2150 s`, `max = 72.2208 s` (down from Phase H legacy subprocess baseline `[83.8 s, 87.5 s]`).
   - **Warm Cache & Navigation Suite (`phase_i_replay_benchmarks.json`):** Warm build (`seek 48,000`): `94.2067 s`; Cached random seeks (`n=6`): **`mean = 1.6507 s`**, `p50 = 1.5628 s`; Sequential step seeks (`n=5`): **`mean = 2.6895 s`**, `p50 = 2.2373 s`; Session switch + `seek(4500)` (`n=3`): `mean = 13.0321 s`; **`sia_hash_mismatches = 0`**.

---

## 4. Sustained 3-Broker Kafka & Flink Streaming (`phase_i_kafka_sustained.json`)

**Script:** [`scripts/benchmark_kafka_sustained.py`](../../scripts/benchmark_kafka_sustained.py)  
**Historical Phase H Baseline Reference:** Archived in [`reports/historical/PHASE_H_BENCHMARK_RECONCILIATION.md`](../../reports/historical/PHASE_H_BENCHMARK_RECONCILIATION.md) (`10 / 10` full `72,642`-event E2E Flink runs = `726,420` events, `0` drops, Stage 3 Flink consume median `10.64 s`, E2E median `184.87 s`).

| Stress / Endurance Probe | Observed Phase I Measurement | Integrity / Drop Verification |
|---|---|---|
| **Cluster & Flink Health** | `3` brokers (`localhost:19092..19094`), `30` PULSE topics, `438` partitions (`0` under-replicated); Flink `pulse-canonical-normalizer-v3` (`18` vertices, **`36 / 36` tasks RUNNING**) | Zero broker degradation across run |
| **Rising Ingestion Sweep** | `2,000` batch -> **`2,799.1 msg/s`** (`696.52ms` P95); `5,000` -> **`7,984.4 msg/s`** (`561.98ms`); `8,000` -> **`12,320.9 msg/s`** (`13.03 MB/s`, `550.50ms` P95) | **`0` failed deliveries** across all batches |
| **3-Session Concurrent Fan-In (`3 × 6,000`)** | `conc-silverstone`, `conc-monaco`, `conc-suzuka` (`18,000` msgs) completed in **`1.70 s`** aggregate = **`10,585.9 msg/s`**, `11`-partition skew **`1.102`** | Isolated `6,000` per session, `0` failed |
| **Peak Lag Drain & Idempotency** | Drained **`18,000` queued messages** to **`remaining_lag = 0`** in `4.748 s` (`3,791.0 msg/s`); re-consumption across `18,000` sink verdicts -> **`0` dedup violations** | `unique_sink_verdicts = 18,000`, RSS delta **`+18.63 MB`** (`50.71 -> 69.34 MB`) |

---

## 5. Browser UI Reference & Visual Verification Showcase

Live Chrome DevTools verification against `KAFKA` + Flink v3 (`0` console errors, `0` console warnings, `0` `4xx`/`5xx` responses across Monaco `[Sim]` & Silverstone `[Historical]`) confirms full parity across Trackside, Integrity Board, SIA Logic Lab, Agents & Pipeline, and Replay Audit views.

![Trackside Mission Control](../screenshots/01_trackside_mission_control.png)
![Integrity Board Matrix](../screenshots/06_integrity_board_matrix.png)
![SIA Logic Lab Superposition](../screenshots/09_sia_logic_lab_superposition.png)
![Agents Pipeline Topology](../screenshots/16_agents_pipeline_topology.png)

- **Full 22-Screen Gallery & Top-10 Highlights:** Stored under [`docs/screenshots/`](../screenshots/) and [`docs/screenshots/top10/`](../screenshots/top10/), with live browser validation screenshots preserved under [`reports/browser-validation/screenshots/`](../../reports/browser-validation/screenshots/).
