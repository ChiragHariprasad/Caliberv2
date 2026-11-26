# PULSE — Scientific Foundations, SIA Formal Model & Controversy Corpus

**Status:** Canonical Authoritative Reference (Phase I Validated)  
**Scope:** Epistemic Foundations of `sia_core_v3`, Statistical F1 Domain Semantics, Historical Controversy Corpus (`2021–2024`), and Evidence Classification Matrix  
**Modules:** [`sia_core_v3/sia_core/`](../../sia_core_v3/sia_core/engine.py), [`backend/pulse/agents/`](../../backend/pulse/agents/fusion.py), [`backend/pulse/analytics/pace_and_tyre.py`](../../backend/pulse/analytics/pace_and_tyre.py)

---

## 1. Scoped Integrity Algebra (`sia_core_v3`) Formal Model

`sia_core_v3` depends strictly on the Python 3.10+ Standard Library (`ADR-01` / `PULSE-ADR-011`) and separates **epistemic integrity verification** (what evidence exists, whether sources share an upstream dependency, whether an observation arrived before finality, and whether cryptographic chains are unbroken) from motorsport domain analytics and regulatory penalties.

### 1.1 Four-State Lattice Semantics & Scalar Collapse Analysis

`sia_core_v3/sia_core/algebra.py` implements a bounded distributive four-state total order lattice:

```text
DEGRADED (0)  <  UNKNOWN (1)  <  SUSPECT (2)  <  HEALTHY (3)
```

| State | Rank | Epistemic Meaning | Meet (`AND`, `min`) / Join (`OR`, `max`) Behavior |
|---|---:|---|---|
| **`DEGRADED`** | `0` | Verified integrity defect, hard invariant breach, kinematic anomaly beyond tolerance, or broken provenance | Absorbing element under `and_state` (`MEET`); least element |
| **`UNKNOWN`** | `1` | Absence of required evidence, unscheduled/voided slot, or unresolved corroboration needed to grade integrity | Dominates `SUSPECT` under `and_state(UNKNOWN, SUSPECT) == UNKNOWN` and dominates `DEGRADED` under `or_state(DEGRADED, UNKNOWN) == UNKNOWN` |
| **`SUSPECT`** | `2` | Evidence present but exposed to guard-band indeterminacy (`WITHIN_UNCERTAINTY`), partial corroboration depth (`COMMON_CAUSE_EXPOSURE`), or unverified warning condition | Lies strictly below `HEALTHY` and above `UNKNOWN` |
| **`HEALTHY`** | `3` | All mandatory roles present within tolerance, non-defective witnesses, and valid provenance closure | Identity element under `and_state`; greatest element (`max`) |

**Formal Investigation of Scalar Collapse (Phase I Finding):**
Property-based verification in [`sia_core_v3/tests/test_formal_invariants.py`](../../sia_core_v3/tests/test_formal_invariants.py) proves that `algebra.py` satisfies bounded distributive lattice axioms (commutativity, associativity, idempotency, absorption, distributivity, and monotonicity for `and_state`, `or_state`, and `k_of_n_state`) **within** its scalar rank space, while highlighting two intrinsic scalar epistemic trade-offs:
1. **Conjunction Collapse (`and_state(UNKNOWN, SUSPECT) == UNKNOWN`):** Combining a suspect warning with a missing observation reduces the scalar summary to `UNKNOWN`, losing the active suspicion flag at the scalar rank alone.
2. **Disjunction Masking (`or_state(DEGRADED, UNKNOWN) == UNKNOWN`):** Under an `OR` quorum where one channel is `DEGRADED` and another is `UNKNOWN`, `or_state` promotes the scalar verdict to `UNKNOWN` rather than flagging `DEGRADED`.
3. **Absent Evidence Floor:** Missing observations yield `UNKNOWN` (or `DEGRADED` when a mandatory role expires without voiding) and **never** emit an optimistic `HEALTHY` grade.

**Architectural Verdict (`PULSE-ADR-010`):** Refactoring `algebra.py` into a multidimensional product lattice was evaluated and **rejected** because `IntegrityEngine.evaluate_decision()` already preserves the orthogonal dimensions alongside `verdict_state`:
- **Evidence Availability:** `roles[role].timeline` & `resolution_maturity` (`OPEN`, `TUPLE_RESOLVED`).
- **Evidence Reliability & Indeterminacy:** Typed `witnesses` (`INFO`, `WARNING`, `DEFECT`; e.g., `WITHIN_UNCERTAINTY`, `COMMON_CAUSE_EXPOSURE`, `LOW_QUALITY_EVIDENCE`).
- **Possibility Interval:** `envelope` (`lower`, `upper` bounds via `SuperpositionView`).
- **Finality State:** `finality_status` (`OPEN`, `FINAL`).

---

### 1.2 Verified Formal Invariants (`sia_core_v3/tests/test_formal_invariants.py`)

All nine core SIA invariants are mechanically exercised across unit, adversarial, and property tests:

| # | Formal Invariant | Verification Scope & Empirical Check | Status |
|---:|---|---|---|
| 1 | **Knowledge-Time (`K`) Monotonicity** | Strictly non-decreasing ledger clock across atoms, facts, guards, voids, and re-evaluations; adversarial clock-skew inputs blocked or handled deterministically | **PASS** |
| 2 | **Valid-Time (`V`) Consistency** | Effective-date interval alignment (`effective_from_utc` / `effective_to_utc`), retroactive rule switches, and `LATE_REFERENCE_FACT` witness generation | **PASS** |
| 3 | **Finality Irreversibility** | Once `finality_status == FINAL` (including legitimate-absence `void_decision()`), status remains permanently `FINAL` across subsequent arrivals | **PASS** |
| 4 | **Pre-Admission Quarantine Isolation** | `_check_finality` executes **before** `Ledger.admit_*`; late atoms/facts go to `quarantined_items` and WAL `quarantine` table without altering prior sealed verdicts or chains | **PASS** |
| 5 | **Source-Independence Correctness** | Disparate adapters feeding from a shared physical sensor or feed (e.g., `F1_FOM_TIMING`) collapse to effective corroboration depth `1` | **PASS** |
| 6 | **Common-Cause Transitive Closure** | Verified `OriginRegistry` transitive propagation across 4-hop origin graphs and adversarial dependency cycles without infinite recursion | **PASS** |
| 7 | **Deterministic Replay** | Replaying identical admission logs (tested up to `500` adversarial interleaved atoms/facts/clock skews) yields bit-identical RFC 8785 (`jcs()`) JSON and SHA-256 `verdict_hash` / `record_hash` | **PASS** |
| 8 | **Hash-Chain Continuity** | Strictly linked `previous_digest` -> `record_hash` sequence using `sha256:<hex>` digests across `SIAWALStore` & JSON checkpoints | **PASS** |
| 9 | **Incremental vs. Full Verification Equivalence** | `verify_incremental()` produces identical boolean verification results and detects injected ledger tampering equivalently to full `verify()` | **PASS** |

**Domain Independence Boundary:**  
`sia_core_v3` passes an isolated Clinical ICU haemodynamic & sepsis fixture (`ScopeClass.SESSION`) with zero motorsport imports. However, direct inspection of `SCOPE_FIELDS` in [`sia_core_v3/sia_core/model.py`](../../sia_core_v3/sia_core/model.py) confirms that sub-session scope bindings (`DRIVER_SESSION`, `DRIVER_LAP`, `SECTOR`, `ZONE`) currently hardcode F1 key names (`driver_id`, `lap_number`, `sector_number`, `zone_id`). Arbitrary non-motorsport sub-session domains require either `ScopeClass.SESSION` or generalizing `SCOPE_FIELDS`.

---

## 2. Scientific F1 Semantics & Uncertainty Rules

### 2.1 Finding Status Lifecycle (`backend/pulse/contracts.py`, `backend/pulse/agents/fusion.py`)

Downstream multi-agent intelligence distinguishes **epistemic certainty** from **integrity alerts**. Under Phase I strict evidence semantics (`PULSE-ADR-012`), Agent 05 (`ConsequenceFusionEngine`) enforces a five-state lifecycle persisted atomically across [`backend/pulse/state/store.py`](../../backend/pulse/state/store.py) and rendered identically in [`frontend/src/types.ts`](../../frontend/src/types.ts):

- **`OBSERVED`**: Direct normalized measurement event with zero inferred model claims.
- **`PROVISIONAL`**: Analytical output carrying uncalibrated priors (`PRIOR_UNMEASURED`), missing telemetry channels, insufficient sample count (`n < 5` or stint span `< 3` laps), or SIA `UNKNOWN` / `SUSPECT` evidence. **A missing SIA integrity alert is never treated as positive corroboration.**
- **`CONFIRMED`**: Reserved exclusively for analytical outputs backed by `CALIBRATED` evidence, sufficient sample support, no missing mandatory telemetry, independent/corroborated lineage (or `CONFIRMED` SIA state), and zero blocking `SIA_INTEGRITY_*` defects.
- **`REJECTED`**: Suppressed or invalidated finding (e.g., SIA `DEGRADED`, conflicting contradictory evidence, or invalid prerequisite checks).
- **`SUPERSEDED`**: Earlier provisional or active revision replaced monotonically in `assessment_history` by a newer `supersedes_assessment_id`.

### 2.2 Tri-State Clean-Air Estimation (`CleanAirStatus`)

Previously, missing `interval_val` telemetry could silently fall through into clean-air lap training. Phase I enforces explicit tri-state classification via `resolve_clean_air_status()` in [`backend/pulse/analytics/pace_and_tyre.py`](../../backend/pulse/analytics/pace_and_tyre.py):
- **`CLEAN_AIR_CONFIRMED`**: Explicit positive interval telemetry satisfies the clean-air threshold (`interval >= threshold`). Only confirmed clean-air laps update `RollingCleanAirPaceEstimator` baselines and clean degradation fits.
- **`TRAFFIC_AFFECTED`**: Positive interval below threshold indicates aerodynamic wake / traffic interaction.
- **`CLEAN_AIR_UNKNOWN`**: Missing, null, or corrupted `interval_val`. Explicitly excluded from clean-air baseline training and marked uncertain in downstream stint diagnostics.

### 2.3 Fuel-Compensated Tyre Degradation & Pit-Window Strategy Boundaries

- **Fuel Model Sufficiency (`FuelCompensatedDegradationModel`):** Standard F1 runs assume a nominal `100 kg` start fuel load linearly burned at circuit-length rates scaled by a `0.035 s/kg` mass sensitivity (`0.045–0.095 s/lap`). In clean dry races (`2021 British GP`, `2021 Abu Dhabi GP`), this linear fuel approximation suffices to invert raw negative chronological slopes into coherent positive tyre wear, and precision-weighted Empirical-Bayes shrinkage reduces out-of-sample stint slope MAE by **`-0.2079 s`** (`0.6851 s -> 0.4772 s` on `n = 277` laps). Crucially, it requires minimum **`n >= 5` inliers** and **stint span `>= 3` laps** (emitting `INSUFFICIENT_SAMPLES` for `1–4` lap stints). Replacing linear fuel burn with proprietary fuel-flow maps is **unjustified** without public fuel-mass ground truth and violates Rule 4 (no speculative complexity).
- **Advisory Scope of `PitWindowStrategySimulator`:** `evaluate_pit_window()` is explicitly scoped (`strategy_scope = "ADVISORY_LOCAL_PIT_WINDOW_ONLY"`, `is_globally_optimal = False`) and guarded (`pit_window_viable = False` within `<= 2` laps remaining). Explicit `model_limitations` document static opponent gap assumptions, single-stint linear age proxy, unmodeled stochastic Safety Car probability, and absent compound-crossover curves — ensuring deterministic pit advisories are never misrepresented as globally optimal race strategies.

---

## 3. Historical F1 Controversy Corpus (`2021–2024`)

PULSE evaluates integrity patterns against ten real-world Formula 1 incidents strictly separating **documented FIA/timing facts** from **disputed interpretations**. Full narrative dossiers and FIA document citations are archived in [`reports/historical/F1_CONTROVERSY_CORPUS.md`](../../reports/historical/F1_CONTROVERSY_CORPUS.md).

| # | Grand Prix & Circuit | Date | Primary Evidentiary Dimension | Contracts Tested | Acquisition / Cache Status |
|---:|---|---|---|---|---|
| 01 | **2021 Abu Dhabi** (Yas Marina) | 12 Dec 2021 | Selective SC unlapping & premature SC withdrawal (`Art. 48.12`, Docs `57`/`58`, WMSC Report) | `C07`, `C13`, `C01` | Local FastF1 cache (`58` laps) — Walk-forward holdout |
| 02 | **2021 Belgium** (Spa-Francorchamps) | 29 Aug 2021 | 2-lap wet SC race & Art. 6.5 countback classification (`Docs 18–23`) | `C07`, `C09`, `C10` | Local FastF1 cache (`1` official lap) — SC edge-case test |
| 03 | **2021 Saudi Arabia** (Jeddah) | 05 Dec 2021 | Lap 37 `69 bar` / `2.4g` deceleration kinematics (`Doc 43`) & restart negotiation (`Docs 34–35`) | `C04`, `C05`, `C08` | Local FastF1 cache (`50` laps) — Calibration set |
| 04 | **2021 Great Britain** (Silverstone) | 18 Jul 2021 | Lap 1 Copse collision (`Doc 34`); simulated trajectories vs raw data in Review (`Doc 49`) | `C04`, `C06` | Local FastF1 cache (`52` laps) — Calibration & E2E Lab Replay |
| 05 | **2023 Austria** (Red Bull Ring) | 02 Jul 2023 | `1,200+` track-limit events overwhelming live review & post-finality penalties (`Docs 71`/`73`) | `C06`, `C11`, `C12` | Research dossier & SIA post-finality amendment test scenarios |
| 06 | **2023 Australia** (Albert Park) | 02 Apr 2023 | Triple red flags, standing restart voiding & countback order (`Docs 45`/`52`) | `C01`, `C07`, `C08` | Research dossier & `void_decision()` CR-1 validation |
| 07 | **2022 Japan** (Suzuka) | 09 Oct 2022 | Recovery vehicle on track in heavy rain (`Doc 36`), Art. 6.5 full-points wording ambiguity | `C08`, `C11`, `C13` | Local FastF1 cache (`28` laps) — Extreme wet/RF holdout |
| 08 | **2022 Monaco** (Monte Carlo) | 29 May 2022 | Wet-to-dry pit-exit line interpretation (`Docs 56`/`57`, effective-dated ISC wording) & power fault | `C06`, `C13` | Local FastF1 cache (`64` laps) — Calibration + Lab scenario |
| 09 | **2024 United States** (COTA) | 20 Oct 2024 | Lap 52 T12 off-track overtake & corner-apex guidelines (`Docs 69`/`78`) | `C04`, `C06` | Research dossier |
| 10 | **2023 Las Vegas** (Las Vegas Strip) | 16 Nov 2023 | FP1 manhole valve cover infrastructure failure vs zero regulatory penalty discretion (`Doc 17`) | `C11`, `C13` | Research dossier |

---

## 4. Scientific Evidence Classification Matrix

Per Section 4.5 (Research Integrity), every analytical and formal claim in PULSE falls into one of four explicit evidential grades:

| Claim Statement | Evidence Classification | Direct Basis / Location |
|---|---|---|
| Bounded distributive lattice axioms (`and`, `or`, `k_of_n`), `verify_incremental` equivalence, transitive origin closure (`<=4` hops + cycle safety), and pre-finality quarantine isolation | **Experimentally Demonstrated** | `sia_core_v3/tests/test_formal_invariants.py` (`273` passing SIA tests) |
| Causal FastF1 pace estimation (`MAE = 0.5094s`, `PI95 = 93.91%` across `n=1,560` LORO laps; `0.5730s`, `PI95 = 95.18%` held-out Japan) outperforms previous-lap, 5-lap median, clean-air median, and linear regression baselines | **Experimentally Demonstrated** | `reports/benchmarks/baseline_comparison.json`, `scripts/run_baseline_comparison.py` |
| Empirical-Bayes shrinkage improves stint degradation MAE (`0.6851s -> 0.4772s`, `n=277` laps), and compound + track-evolution + clean-air filtering each contribute measurable RMSE/MAE reduction | **Experimentally Demonstrated** | `reports/benchmarks/ablation_study.json` |
| Cold replay seek latency cut `-30.3%` (`21.08s -> 14.69s`) via indexing/cloning optimization and `23.5x–43x` speedup under cached keyframe seek with `0` SIA hash mismatches | **Experimentally Demonstrated** | `reports/benchmarks/phase_i_replay_benchmarks.json` |
| 3-broker KRaft + Flink v3 (`36/36` tasks) + manual offset commit sustains `10.5k–12.3k msg/s` multi-session throughput, zero under-replicated partitions (`0/438`), and exact dedup under broker chaos (`T1–T10`) | **Experimentally Demonstrated** | `reports/benchmarks/phase_i_kafka_sustained.json`, `test_kafka_integration_t1_t10.py` |
| Fuel burn (`~100 kg`, `0.035 s/kg`), wet/dry crossover mechanics, and SC/VSC strategic Monte Carlo rollouts shape real pit strategy | **Supported by Published Literature** | Heilmeier et al. (2020, *Applied Sciences* Vol. 10 & Art. 7805); Piccinotti (Politecnico di Milano) |
| Strict `FindingStatus` promotion rules & SIA common-cause origin collapse prevent premature false confirmations on uncalibrated priors or shared-upstream feeds | **Theoretical / Model-Derived** *(and partially Experimentally Demonstrated on controlled/ablated probes)* | `backend/pulse/agents/fusion.py`, `ablation_study.json` (`FPR 0.875 -> 0.0` on test harness) |
| Global multi-stint race optimality, real-time F1 official feed integration, sub-second distributed scale beyond single-host Docker cluster, and physical hardware/actuation interlocks | **Not Yet Validated** | Explicitly excluded from production telemetry claims; documented as open research boundaries |
