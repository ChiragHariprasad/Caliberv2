# PULSE — Phase H Scientific F1, Frontend UI & Patentability Verification

**Audit Date:** 2026-11-26  
**Repository:** `E:\Caliberv2` (branch `pulse-reconstruction`)  
**Evaluation Basis:** Fresh execution of `scripts/run_f1_scientific_eval.py` against offline FastF1 v3.9.0 cache (`data/fastf1_cache/`), direct code inspection of `backend/pulse/analytics/pace_and_tyre.py`, `backend/pulse/agents/`, `backend/pulse/sessions/registry.py`, `backend/pulse/integrity/contracts.py`, `frontend/src/`, live Chrome DevTools verification against active 3-broker Kafka KRaft + Flink v3 (`http://127.0.0.1:5173/` -> `http://127.0.0.1:8000/`), and primary-source prior-art synthesis from `docs/RESEARCH_AND_PRIOR_ART.md`.

---

## 1. Scientific Formula 1 Analytics Validation & Methodological Critique

### 1.1 Causal Walk-Forward Empirical Results (Reproduced `2026-11-26 19:08–19:09`)

Executing `python E:\Caliberv2\scripts\run_f1_scientific_eval.py` cleanly (exit code `0`) against offline cached FastF1 race sessions produced exact bit-for-bit reproducibility with `reports/f1_scientific_eval.json` across all 5 Grands Prix:

| Race (FastF1 Cache) | Legacy `76.0s` MAE | PULSE v2 Causal MAE | MAE Reduction | Empirical 95% PI Coverage | Calibrated Green Pit Loss (`n`) | Status |
|---|---:|---:|---:|---:|---:|---|
| **2021 British Grand Prix** | `17.343s` | **`0.358s`** | `-97.9%` | `92.6%` | `18.26s` (`n=20`) | `EMPIRICAL_PIT_CALIBRATED` |
| **2021 Saudi Arabian Grand Prix** | `19.475s` | **`1.976s`** | `-89.9%` | `93.7%` | `19.63s` (`n=1`) | `EMPIRICAL_PIT_CALIBRATED` |
| **2021 Abu Dhabi Grand Prix** | `13.627s` | **`0.352s`** | `-97.4%` | `92.2%` | `22.88s` (`n=17`) | `EMPIRICAL_PIT_CALIBRATED` |
| **2022 Monaco Grand Prix** | `9.745s` | **`1.484s`** | `-84.8%` | `92.1%` | `14.79s` (`n=9`) | `EMPIRICAL_PIT_CALIBRATED` |
| **2022 Japanese Grand Prix** (`29` laps, `323` eval) | `38.224s` | **`3.701s`** (`RMSE 12.931s`) | `-90.3%` (`90.32%`) | `83.3%` (`83.28%`) | `27.62s` (`n=11`, VSC `14.13s`) | `EMPIRICAL_PIT_CALIBRATED` |

**Fuel-Compensated Degradation Verification (`FuelCompensatedDegradationModel`):**

Raw chronological stint OLS frequently yields spurious *negative* slopes (cars appear to get faster per lap because ~100 kg fuel burn outweighs thermal tyre wear). Fuel-burn compensation recovers physically coherent positive degradation in dry races while exposing uncompensated noise honestly:
- **2021 British GP:** Hard (`n=19`) flips from `-0.0370` (`2/19` positive) to **`+0.0303 s/lap` (`15/19` positive)**; Medium (`n=20`) shifts `-0.1025` (`2/20`) -> `-0.0352` (`6/20`).
- **2021 Abu Dhabi GP:** Hard (`n=19`) flips `-0.0427` (`2/19`) -> **`+0.0176` (`12/19` pos)**; Soft (`n=8`) flips `-0.0313` (`2/8`) -> **`+0.0290` (`7/8` pos)**; Medium (`n=12`) shifts `-0.0871` (`1/12`) -> `-0.0268` (`3/12` pos).
- **2021 Saudi Arabia (`S 1/1 +0.0051`, `M 8/24`, `H 4/13`) & 2022 Monaco (`S 1/1 +0.1264`, `M 5/11`, `H 2/9`):** Track evolution, street-circuit evolution, and SC interruptions keep several raw/compensated slopes slightly negative, and precision-weighted Bayesian pooling regularizes volatile short stints without fabricating monotonicity.
- **2022 Japanese GP:** Heavy rain / red-flag truncation yields `compound_degradation = {}` (insufficient >=5-lap green stints) and drops 95% conformal coverage transparently to `83.28%` (`MAE 3.701s`, `RMSE 12.931s`) rather than fabricating tight confidence intervals.

### 1.2 Verified Architectural Strengths in Pillar 2

1. **Zero Data Leakage in Baseline Prediction (`RollingCleanAirPaceEstimator`):** Both `run_f1_scientific_eval.py` and `VehicleResponseAgent.on_event()` call `predict_baseline()` strictly **before** `observe_lap()`. Circuit-agnostic adaptation (`35s < lap_sec < 300s`), stint transition resets, and two-lap regime-shift adaptation (`pending_shift_laps`) eliminate the pre-reconstruction `76.0s` baseline bug.
2. **Domain-Accurate Re-Entry & Pit Calibration (`PitWindowStrategySimulator`):** Empirical pit-loss learning `(in_sec - baseline) + (out_sec - baseline)` bounded in `[10.0, 45.0]s` and explicit fallback tagging (`UNMEASURED_NO_FIELD_GAPS`, `~P{pos}+ (GAPS_PARTIAL)`) permanently eliminate legacy impossible labels (`P-1-P0`, hardcoded `21.5s` without provenance).
3. **Dataset Provenance Honesty (`backend/pulse/sessions/registry.py`):** `_apply_honest_session_provenance()` classifies all 12 catalogued sessions strictly into `SYNTHETIC` (`f1-2026-monaco-sim`, `f1-2026-suzuka-race` -> `PULSE_SYNTHETIC_SIMULATOR`), `LAB` (`f1-2023-silverstone-race` -> `JOLPICA_OPEN_AND_SYNTHETIC_TELEMETRY`, historical replays -> `PULSE_LAB_REPLAY_CAPTURE`), and `PREVIEW` (`PREVIEW_GEOMETRY_CATALOGUE`). Official FIA/FOM feeds are explicitly neither claimed nor scraped (`docs/DATA_SOURCING_ASSESSMENT.md`).

### 1.3 Remaining Scientific & Multi-Agent Weaknesses (Independent Critique)

1. **Epistemic Over-Claiming in Agent 05 V2 Convergence (`backend/pulse/agents/fusion.py:274-278`):** Even when `TyreStrategyAgent` flags a pit-window finding as `FindingStatus.PROVISIONAL` (`PRIOR_UNMEASURED`), `ConsequenceFusionEngine._publish_superseding_v2()` sets `is_confirmed = not blocking_integrity` — meaning uncalibrated priors remain marked `status=CONFIRMED` unless a `SIA_INTEGRITY_*` alert fires (legacy contract compatibility fallback; `uncertainty.calibration_status` still preserves `PRIOR_UNMEASURED`).
2. **Heuristic Horizon Benefit vs True Strategy Rollout:** `PitWindowStrategySimulator.evaluate_pit_window()` (`pace_and_tyre.py:779-782`) estimates stint age benefit with a linear cap `min(4.0, max(0.0, slope * min(stint_age, 12) * 0.25))` and assumes static opponent `gap_to_leader_sec` at re-entry rather than simulating tyre-compound crossover curves, fuel burn differences, or stochastic SC probability via Monte Carlo rollouts (as in Heilmeier et al., 2020).
3. **Uniform Fuel & Clean-Air Assumptions:** `estimate_fuel_burn_rate()` distributes a uniform `100.0 kg` fuel load at fixed `0.035 s/kg` (`[0.045, 0.095]` s/lap) across circuits; additionally, `run_f1_scientific_eval.py:114` sets `clean_air=not is_pit` without FastF1 inter-car interval reconstruction, and `TyreStrategyAgent` (`tyre_strategy.py:219`) treats missing `interval_val` (`None`) as clean air.
4. **Uneven Intelligence Across Agents 01–05:** `EventControlAgent` (`agent-01-event-control`) and `TrackStateAgent` (`agent-02-track-state`) remain deterministic event/threshold state machines (`abs(rain_risk_diff) > 15.0`, `abs(track_temp_diff) > 2.0`), whereas genuine statistical modeling resides in `VehicleResponseAgent` (`2.0.0`), `TyreStrategyAgent` (`2.0.0`), `ConsequenceFusionEngine` (`3.0.0`), and `IntegrityAgent` (`3.0.0`).

---

## 2. Frontend Completeness, Honesty & Live Chrome DevTools Verification

### 2.1 Phase H Defects Discovered & Repaired

During Phase H UI auditing against live Apache Kafka + Apache Flink v3 (`PULSE_TRANSPORT_MODE=KAFKA`), four concrete frontend integrity defects were identified, patched, built (`npm run build`: `✓ 60 modules transformed`, `1.57s`), and re-verified:

1. **Hardcoded Driver-Specific SSE Sentiment Removed (`frontend/src/App.tsx:239`):** Pre-Phase-H SSE handler assigned `#16` `'positive'` and `#44` `'negative'` tones mechanically; replaced with dynamic impact tone derived strictly from payload telemetry/assessment deltas.
2. **Orphaned & Misaligned `PipelineLabView` Re-Wired & Sanitized (`frontend/src/components/PipelineLabView.tsx`, `frontend/src/types.ts`, `frontend/src/components/agents/AgentsPipelineView.tsx`):**
   - Audit #1 discovered that `PipelineLabView.tsx` was unmounted in the active navigation shell while holding static placeholders (`10/10 STAGES RECONCILED`, `Kafka 3.6`, `localhost:9092`, `193` checkpoints, `~2.1ms`) and referencing non-existent response keys (`inputs_expected`, `outputs_actual`, `drops`). Meanwhile, `AgentsPipelineView.tsx` displayed hardcoded `"5 Active"` / `"0.0%"` KPI cards.
   - Repaired `PipelineLabView.tsx` + `types.ts` to map actual backend `input_count`, `output_count`, and `drop_count` fields, wired `PipelineLabView` into `AgentsPipelineView.tsx` as the 4th subtab (`Verification & Lineage Lab`), and connected `TOPOLOGY` & KPI cards to live `/api/agents/metrics` and `/api/pipeline/status`.
3. **Hard-Reload Session Dropdown Desync Fixed (`frontend/src/App.tsx`):** Browser reload previously reverted the header `<select>` visually to Monaco while backend telemetry/canvas rendered the active session (e.g., Silverstone). Synchronized `sessionId` and `circuitId` from initial `loadSnapshot()` and SSE `onSnapshot`.
4. **Card Overflow Wrapping Fixed (`frontend/src/components/PipelineLabView.tsx:108`):** Added `overflowWrap: 'anywhere', wordBreak: 'break-word'` on the `.node-kafka` Cluster `<strong>` element so `localhost:19092,localhost:19093,localhost:19094` wraps cleanly inside the card container.

### 2.2 Live Chrome DevTools Evidence (`http://127.0.0.1:5173/` -> Live `KAFKA` + `Flink v3`)

| Check Area | Observed Live Chrome Result | Verdict |
|---|---|---|
| **Console & Network Cleanliness** | Audit #2 & Final Reload Check (`ignoreCache: true`): **`0` console errors**, **`0` console warnings**, **`0` failed HTTP requests** (`78/78` `200 OK` on initial load; `/api/snapshot`, `/api/replay/status`, `/api/integrity/*`, `/api/agents/metrics`, `/api/pipeline/status`, `/api/pipeline/verification-runs`, `/api/pipeline/lineage` all `200 OK`). | **PASS** |
| **Hard-Reload Session Sync & `.node-kafka` Wrap** | On hard reload while backend held `f1-2023-silverstone-race`, `<select>` immediately stayed synced to `British Grand Prix 2023 · Silverstone (5.891 km) [Historical]` (`LAB ARCHIVE`, `COMMON-CAUSE EXP`, `Event 20346 / 72642 (28%)`, `LAP 9/52`). `.node-kafka` Cluster `<strong>` (`48.96px` height, `3 × 16.32px` lines) wrapped cleanly within `176.7px`. | **PASS** |
| **Live Kafka Playback, Pause & Multi-Resolution Seek** | `5x` playback advanced Monaco smoothly (`Event 60 -> 1898 / 72926`), `Pause` held exact state (`2249 / 72926`, `3.1%`) stationary across `18s`. Switching to Silverstone + `Seek(36321)` -> `LAP 17/52 · 00:30:02`; `Seek Lap: L10` -> `20346 / 72642`, `LAP 9/52`. | **PASS** |
| **Telemetry Modals & Provenance Honesty** | Drivers `#55`, `#11`, `#31`, `#1` rendered live `AVAILABLE` channels (`high_frequency_track_adapter · 120ms freshness`) with honest footer: *"Missing channels are reported as UNAVAILABLE and are strictly never synthetic."* | **PASS** |
| **SIA Integrity Matrix, Inspector & Replay Audit** | Inspected `#55 Carlos Sainz` (`lap_time@f1-2023-silverstone-race|55|9`): `DEGRADED`, `TUPLE_RESOLVED`, `FINAL`, `CHAIN OK (SHA-256)`. `Re-verify All Chains` returned **`625 Active Instances`**, **`625 / 625 Verified SHA-256 Chain`**, **`0 Zero Chain Breaks`**. | **PASS** |
| **Agents & Pipeline / Verification Lab Honesty** | Live KPIs displayed **`REGISTERED AGENTS: 6 Active`**, **`PROCESSED INPUTS: 22,994`**, **`FINDINGS EMITTED: 2,539`**, **`LATENCY P95: 0.5ms`**, **`SYSTEM ERROR RATE: 0.00%`**. Topology & Lab showed real Flink checkpoints incrementing dynamically (`1922 -> 2003`) and honestly displayed prior failed vs passing runs (`run-bb6d949f 3/4 PASSED`, `run-5eca8f5c 10/10 PASSED`) plus 18 live lineage trace events. | **PASS** |

**Residual Frontend Caveats:**
- `IntegrityMatrix.tsx` includes a static `LIBRARY_CONTRACTS` reference catalog (`C01`–`C13`) accessible via toggle alongside live `ACTIVE` contracts (`LIB_TO_RUNTIME_CONTRACT` maps `5` active contracts cleanly). `AssumptionsBar.tsx` retains component prop defaults (`Monaco-2025-v2.1`) that are overridden whenever live session metadata is loaded.

---

## 3. Patentability, Prior-Art Audit & Indian Section 3(k) Readiness

### 3.1 Primary-Source Prior-Art Audit (Google Patents Corrections)

Prior internal documentation (`docs/COMPREHENSIVE_SYSTEM_AUDIT_2026.md`) contained misattributed patent numbers; primary verification in `docs/RESEARCH_AND_PRIOR_ART.md` establishes the real prior-art landscape:

- **Corrected False Positives from Early Audit:**
  - `US7578182B2` actually covers *Detection of prepped tires* (chemical vapor sniffing), not motorsport tracking/gaps.
  - `US20030117275A1` covers general vehicle tire-failure detection, not motorsport strategy telemetry.
  - `US11069450B2` and `US9997265B2` (Mitsubishi Electric) belong to nuclear reactor protection I&C safety voting, not motorsport event analytics.
  - Bare `US10502806` has no matching sensor-fusion/guard-band utility patent.
- **Genuinely Relevant Anticipating / Crowding Prior Art:**
  - **Live Motorsport Telemetry & Tracking:** `US6020851A` (*Auto race monitoring system*, Busack) & `US20080036587A1` (*Race tracking system and method*, Meinzen); commercial operational benchmark **Catapult RaceWatch** and academic strategy models (Heilmeier et al., 2020; Piccinotti MDP).
  - **Bitemporal Canonical Data & Contracts:** `US8713073B2` (*Management of temporal data by means of a canonical schema*) & `US10445698B2` (*System and method for forming, storing, managing, and executing contracts*).
  - **Hash-Chained Immutable Ledgers:** `US10614239B2` & `US11418345B2` (Amazon / QLDB cryptographic hash-chained journals & digest proofs).
  - **Common-Cause Failure & Analytical Redundancy:** `US11567823B2` (Siemens AG closed-loop automated fault-tree common-cause resolution) & `US11747360B2` (cross-modality analytical redundancy).
  - **Out-of-Order Watermark Quarantine:** `US20180089328A1` (Splunk metrics ingestion quarantine) & `US11943123B1` (timeline state spans).

### 3.2 Indian Patent Act Section 3(k) & CRI Guidelines (2025) Verdict

Under **Section 3(k)** of the Indian Patents Act (excluding *"mathematical or business method or a computer programme per se or algorithms"*) as interpreted under the **2025 CRI Guidelines** (*Ferid Allani*, *Microsoft* **Technical Effect / Technical Contribution** standard):

1. **Broad PULSE Platform ("Kafka + Flink + Multi-Agent F1 Analytics + Dashboard"): `1.5 / 10` — UNPATENTABLE.** Anticipatable over `US6020851A`, `US20080036587A1`, Heilmeier et al. (2020), and squarely barred under Section 3(k) as software orchestration and mathematical modeling without technical effect beyond standard computing.
2. **Standalone SIA Features ("Bitemporal `K`/`V` + SHA-256 Chain + Quarantine + Lineage DAG"): `2.5 / 10` — WEAK.** Each building block is well-covered in crowded prior art (`US8713073B2`, `US10614239B2`, `US10445698B2`, `US20180089328A1`, `US11567823B2`).
3. **Narrowest Arguable Direction (Not Yet Filing-Ready): `4.0 / 10`.** Only a **fail-closed admission & hardware/network actuator interlock** tying pre-admission finality quarantine (`quarantine_before_admit`) + bounded clock-skew (`session_t0` supersession invariance) + shared-lineage common-cause graph collapse directly into physical/network actuation or deterministic distributed state-machine replication (guaranteeing identical `verdict_hash` under partition failover while physically gating downstream controllers) offers plausible technical effect.

### 3.3 Concrete Engineering Gaps Blocking Any Immediate Filing

Inspecting the actual codebase (`backend/pulse/integrity/contracts.py`, `sia_core_v3/sia_core/`) confirms why PULSE is **not ready for patent filing today**:
- **No Physical / Protocol Actuation Interlock:** PULSE currently operates solely as an offline/replay analytical observability UI (`FastAPI` + `SQLite WAL` + React); neither SIA verdicts nor `HOLD_VERIFY_INTEGRITY` findings physically gate real vehicle ECUs, pit-lane limiters, or broadcast timing hardware.
- **Permissive Default Contract Corroboration:** In `backend/pulse/integrity/contracts.py:56`, `_lap_time_contract()` sets `"corroboration": {"mode": "INFORMATIONAL", "min_source_depth": 0, "min_processing_depth": 0}` and `fault_model.resilience_requirement = 0` so single-source FastF1/synthetic streams run without blocking.
- **Pending Counsel Freedom-to-Operate (FTO) Search:** Formal Espacenet/PATENTSCOPE/USPTO clearance over `US11567823B2`, `US10614239B2`, and `US20180089328A1` has not been performed.
