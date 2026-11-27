# PULSE — Scientific Foundations, SIA Formal Model & Controversy Corpus

**Status:** Canonical Authoritative Reference (Phase J Release-Candidate Validated)  
**Scope:** SIA Research Contribution, Epistemic Lattice vs Multidimensional Projections, Statistical F1 Domain Semantics, Expanded Corpus (`2021–2024`), and Evidence Matrix  
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

**Technical Research Contribution Statement (Beyond Event Sourcing, Temporal DBs, and Hash-Chained Logs):**  
Ordinary **event sourcing** reproduces application state by replaying append logs, **bitemporal databases** (`valid time` / `transaction time`, e.g., `US8713073B2`) version rows across `V`/`K`, and **cryptographically chained journals** (e.g., Amazon QLDB / `US10614239B2`) authenticate committed revisions. None of those primitives natively distinguish *missing telemetry* from *contradictory telemetry* or *illicit common-cause source reuse* during open-window evaluation. SIA (`sia_core_v3`) contributes four coupled invariants executed deterministically in one lightweight kernel (`stdlib`-only):
1. **Bounded-Uncertainty & Common-Cause Origin Collapse:** Physical-tolerance guards (`Pattern P3` guard bands -> `SUSPECT`) plus transitive DAG closure across `OriginRegistry` (`Atom.origin_id`) collapsing multiple adapters sharing a physical timing feed (e.g., `F1_FOM_TIMING`) to effective corroboration depth `1`. *(Implemented caveat verified in Phase J: `ReferenceFact.src` provenance is checked on agreement/lateness, whereas graph resilience closure operates over `Atom` origins).*
2. **Pre-Admission Finality Quarantine:** Slot deadlines (`deadline_s + allowed_lateness_s`) seal `finality_status = FINAL` monotonically; late/conflicting arrivals execute `_check_finality()` *prior* to `Ledger.admit_*`, diverting payloads to a separate quarantine ledger so prior verdicts and SHA-256 chains remain strictly invariant (unlike post-hoc compensating events).
3. **Scalar Lattice Coupled to Orthogonal Structured Content:** Fast distributive `DEGRADED < UNKNOWN < SUSPECT < HEALTHY` verdict aggregation paired deterministically with structured witnesses, role timelines, possibility envelopes, and finality flags inside `EvalOutput.content`.
4. **Cross-Boundary Replay Equivalence:** Coupling RFC 8785 (`jcs()`) canonicalization and SQLite WAL checkpoints with Kafka/Flink manual offset commits preserves exact bit-identical `verdict_hash` continuity across crash recovery and deterministic replay.

**Formal & Comparative Review of Scalar Collapse vs Multidimensional Lattices (Phase I/J):**
Property-based verification in [`test_formal_invariants.py`](../../sia_core_v3/tests/test_formal_invariants.py) and Phase J's comparative projection tests in [`test_phase_j_sia_semantics.py`](../../sia_core_v3/tests/test_phase_j_sia_semantics.py) prove bounded distributive lattice axioms across all `and_state`, `or_state`, and `k_of_n_state` combinations while explicitly testing the two scalar masking boundaries:
1. **Missing vs Contradictory Evidence & Conjunction Masking:** Within single-slot evaluation, absent required roles yield `UNKNOWN` (`STALLED`/`DEGRADED` on hard expiration without voiding), whereas conflicting evidence yields `DEGRADED` (`CONSTRAINT_VIOLATION` / `UNRESOLVED_CONFLICT`). However, under `and_state(SUSPECT, UNKNOWN) == UNKNOWN` (occurring on compound contracts like `lap_time` `AND(lap_record, lap_start, session_t0)` when `lap_record` is `SUSPECT` and `session_t0` is missing), the scalar grade collapses to `UNKNOWN`.
2. **Disjunction Masking (`or_state(DEGRADED, UNKNOWN) == UNKNOWN`):** A `DEGRADED` branch combined via `OR` with an `UNKNOWN` branch elevates to scalar `UNKNOWN` rather than flagging `DEGRADED`.
3. **Multidimensional Fidelity Comparison (`_project_multidim`):** [`test_phase_j_sia_semantics.py`](../../sia_core_v3/tests/test_phase_j_sia_semantics.py) reconstructs `(availability, consistency, corroboration, finality)` vectors directly from `EvalOutput.content` (distinguishing `COMPLETE/PARTIAL/MISSING` availability, `AGREED/QUESTIONABLE/CONFLICTED` consistency, `INDEPENDENT/DEPENDENT_OR_SINGLE_POINT/UNCORROBORATED` depth, and `OPEN/FINAL` finality) without changing `algebra.py`. Updating downstream consumers (`ConsequenceFusionEngine`) to inspect `content` fields alongside scalar `integrity_state` captures full multidimensional precision without breaking kernel compatibility (`PULSE-ADR-010`).

**Architectural Verdict (`PULSE-ADR-010` Retained):** Replacing `algebra.py` with a 4D product lattice has **no genuine engineering advantage** because `EvalOutput.content` already exposes the complete orthogonal vector lossless of scalar rank (`roles`, `witnesses`, `envelope`, `resilience`, `finality_status`). Only `SCOPE_FIELDS` (`model.py`) retains F1 key names (`driver_id`, `lap_number`, `sector_number`, `zone_id`) for sub-session scopes; arbitrary non-F1 domains currently execute cleanly at `ScopeClass.SESSION` unless `SCOPE_FIELDS` is generalized.

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

**Domain Independence & Supersession Boundaries:**  
`sia_core_v3` passes an isolated Clinical ICU haemodynamic & sepsis fixture (`ScopeClass.SESSION`) with zero motorsport imports, and `test_phase_j_sia_semantics.py` verifies bitemporal `as_of(k)` read-only fidelity plus rejection of unauthorized/lower-priority contract supersession. However, direct inspection of `SCOPE_FIELDS` in [`sia_core_v3/sia_core/model.py`](../../sia_core_v3/sia_core/model.py) confirms that sub-session scope bindings (`DRIVER_SESSION`, `DRIVER_LAP`, `SECTOR`, `ZONE`) currently hardcode F1 key names (`driver_id`, `lap_number`, `sector_number`, `zone_id`). Arbitrary non-motorsport sub-session domains require either `ScopeClass.SESSION` or parameterizing `SCOPE_FIELDS`.

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
| 05 | **2023 Austria** (Red Bull Ring) | 02 Jul 2023 | `1,200+` track-limit events overwhelming live review & post-finality penalties (`Docs 71`/`73`) | `C06`, `C11`, `C12` | OpenF1 cache (`1,351` valid laps) — External `2023–2024` generalization set + finality tests |
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
| Bounded distributive lattice axioms (`and`, `or`, `k_of_n`), scalar masking vs multidimensional `EvalOutput.content` fidelity, unauthorized supersession block, `verify_incremental` equivalence, transitive origin closure, and pre-finality quarantine | **Experimentally Demonstrated** | [`test_formal_invariants.py`](../../sia_core_v3/tests/test_formal_invariants.py), [`test_phase_j_sia_semantics.py`](../../sia_core_v3/tests/test_phase_j_sia_semantics.py) |
| Expanded **17-race `2021–2024` generalization** (zero-tuning unseen `2023–2024` `MAE = 0.5288s [0.4855, 0.5740]`, `PI95 = 94.41% [93.69%, 95.12%]`; LORO-16 `0.5239s [0.4882, 0.5595]`, `PI95 = 94.28%`; dry `94.72%`, post-restart `0.7616s vs 2.2101s` legacy) with `2,000`-rep stint/session block bootstrap (`lag-1 resid ACF = +0.38..+0.40`) | **Experimentally Demonstrated** *(with explicit limits on steady dry green laps vs `previous_lap` MAE & wet `PI95 91.28%` under-coverage)* | [`phase_j_generalization.json`](../../reports/benchmarks/phase_j_generalization.json), [`baseline_comparison.json`](../../reports/benchmarks/baseline_comparison.json) |
| Empirical-Bayes shrinkage improves stint degradation MAE (`0.6851s -> 0.4772s`, `n=277` laps), and compound + track-evolution + clean-air filtering each contribute measurable RMSE/MAE reduction | **Experimentally Demonstrated** | [`ablation_study.json`](../../reports/benchmarks/ablation_study.json) |
| Uncontended cold replay `seek(36321)` averages `14.98s` (`std=0.25s`, `89.04%` SIA+WAL sync, `1.64s` without SIA), `0.33s–1.16s` warm seek, `0.75s` SQLite WAL restart (`625/625` exact hashes); reconciles `14.69s` vs `70.88s` contended throttling | **Experimentally Demonstrated** | [`phase_j_replay_benchmarks.json`](../../reports/benchmarks/phase_j_replay_benchmarks.json), [`phase_i_replay_benchmarks.json`](../../reports/benchmarks/phase_i_replay_benchmarks.json) |
| Tier 1 raw broker (`73.7k–83.8k msg/s` batch, `30.6k msg/s` fan-in, `18.5k msg/s` drain) vs Tier 2 sustained `110.86s` E2E (`Kafka -> Flink v3 -> 6 Agents -> unpaused SIA WAL -> SQLite sink`): `9.67 ev/s`, `24` checkpoints (`0` failed), `978/978` WAL hashes post-restart, `T1–T10` `10/10` | **Experimentally Demonstrated** | [`phase_j_kafka_sustained.json`](../../reports/benchmarks/phase_j_kafka_sustained.json), `test_kafka_integration_t1_t10.py` |
| Fuel burn (`~100 kg`, `0.035 s/kg`), wet/dry crossover mechanics, and SC/VSC strategic Monte Carlo rollouts shape real pit strategy | **Supported by Published Literature** | Heilmeier et al. (2020, *Applied Sciences* Vol. 10 & Art. 7805); Piccinotti (Politecnico di Milano) |
| Strict `FindingStatus` promotion rules & SIA common-cause origin collapse prevent premature false confirmations on uncalibrated priors or shared-upstream feeds | **Theoretical / Model-Derived** *(and partially Experimentally Demonstrated on controlled/ablated probes)* | `backend/pulse/agents/fusion.py`, `ablation_study.json` (`FPR 0.875 -> 0.0` on test harness) |
| Global multi-stint race optimality, real-time F1 official feed integration, sub-second distributed scale beyond single-host Docker cluster, multi-tenant OIDC/TLS/mTLS production readiness, and physical hardware actuation | **Not Yet Validated** | Explicitly excluded from production & patent claims; documented as open engineering/research boundaries |
