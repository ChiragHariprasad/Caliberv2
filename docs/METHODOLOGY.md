# PULSE Scientific, Data & Evaluation Methodology

---

## 1. Data Sourcing, Provenance & Anti-Fabrication Policy

PULSE strictly enforces empirical provenance tracking across every stored dataset and emitted API response:

| Source Class | Actual Repository Contents | Allowed Analytical Use | Explicit Restrictions |
| :--- | :--- | :--- | :--- |
| **Offline Cached FastF1 Sessions** (`data/fastf1_cache/`) | **6 complete race datasets** with lap times, timestamps, sectors, pit in/out, tyre compounds & track status: `2021 Britain` (949 valid laps), `2021 Belgium` (58 laps), `2021 Saudi Arabia` (802 laps), `2021 Abu Dhabi` (998 laps), `2022 Monaco` (1,158 laps), `2022 Japan` (485 laps) | Pace validation, LORO cross-validation, holdout evaluation, ablation studies, causal interval reconstruction | Reconstructed intervals from `LapStartTime`; never labeled as live official FIA feeds |
| **Summary Historical Metadata** (`data/f1_corpus/2023_*`, `2024_*`) | 4 directories (`Australia`, `Austria`, `Las Vegas`, `United States 2024`) containing Jolpica summary metadata (`0` per-lap `lap_time_seconds` rows) | Metadata & incident cross-reference only | Excluded from lap-time pace modeling (`valid_lt = 0`) |
| **Replay Capture Archives** (`captures/*/envelopes.jsonl`) | Pre-recorded race & stress-test streams (`f1-2023-silverstone-race` `72,642` events, `f1-2026-monaco-sim` `72,926` events, `f1-2026-suzuka-race` `72,617` events, etc.) | Pipeline throughput, deterministic replay, SIA chain & UI testing | Explicitly marked `SYNTHETIC` / `REPLAY` / `LAB` via [registry.py](../backend/pulse/sessions/registry.py) |

**Epistemic Output Taxonomy ([contracts.py](../backend/pulse/contracts.py)):**
- `OBSERVED`: Raw timing/telemetry measurement verified as received (`Interpretation.OBSERVED`, `FindingStatus.OBSERVED`).
- `CALCULATED / DERIVED`: Mathematical transformation of observed inputs with explicit sample count and standard error (`Interpretation.DERIVED`).
- `INFERRED`: Latent classification such as dirty-air traffic impedance (`Interpretation.INFERRED`).
- `PREDICTED`: Causal forward projection with finite-sample 95% prediction bounds (`Interpretation.PREDICTED`).
- `RECOMMENDED` *(Bounded Advisory)*: Pit-window comparisons explicitly flagged `strategy_scope="ADVISORY_LOCAL_PIT_WINDOW_ONLY"` and `is_globally_optimal=False` alongside missing-input warnings (`model_limitations`).

---

## 2. Clean-Air Tri-State Methodology (`CleanAirStatus`)

Clean-air baseline estimation cannot assume missing interval telemetry equals free air:

- **`CLEAN_AIR_CONFIRMED`:** Either `interval_to_ahead >= 1.8s` (measured) OR `position == 1` (race leader on track), AND not a pit-in/pit-out lap. Eligible to train clean baseline & residual tracking.
- **`TRAFFIC_AFFECTED`:** Measured `interval_to_ahead < 1.8s` OR pit-in/pit-out lap (`is_pit=True`). Excluded from baseline updates and surfaces traffic-impeded warning.
- **`CLEAN_AIR_UNKNOWN`:** Neither `interval_to_ahead` nor `position == 1` is available (`CleanAirStatus.CLEAN_AIR_UNKNOWN`, boolean flag `None`). **Strictly excluded** from updating clean-air pace baselines (`test_phase_i_scientific_semantics.py`) and blocks `CONFIRMED` status promotion.

---

## 3. Causal Pace, Fuel Degradation & Strategy Modeling Scope

1. **Pace Prediction ([pace_and_tyre.py](../backend/pulse/analytics/pace_and_tyre.py)):**
   - **Strict Causality:** On every lap `t`, `predict_baseline(target_lap=t)` runs *strictly before* `observe_lap(lap_number=t)`. Future laps `> t` never influence predictions at `<= t` (`test_zero_future_leakage_across_all_6_baselines`).
   - **Fuel Assumption Boundaries:** Uses generic `100 kg` usable race fuel distributed uniformly over `total_laps` at fixed `0.035 s/kg` (`[0.045, 0.095] s/lap`), falling back to `0.060 s/lap` (`GENERIC_FUEL_PRIOR`) when race distance `< 15` or unknown. Exact car/engine lift-and-coast fuel maps are unavailable in public timing feeds and therefore modeled only via explicit uncertainty bounds rather than over-parameterized unidentifiable regressions.
   - **Fast Regime Recovery (Phase I):** When returning from slow standing restarts or Safety Car periods (`lap_sec < cur_med - 6.0s`), `stint_laps` resets cleanly rather than averaging a `160s` restart lap with a `92.8s` flying lap, and `_advance_track_evo` ignores >`5.0s` field discontinuities so unflagged restarts do not corrupt track-evolution state.
2. **Tyre Degradation:**
   - Resets across stint ID changes, tyre-age drops, compound switches, and wet/dry transitions. Filters SC/VSC and pit laps. Requires `>= 5` clean inliers AND `>= 3` lap span before emitting `DRIVER_STINT_CALIBRATED`; stints with `1..4` clean laps emit `INSUFFICIENT_SAMPLES` rather than silent prior confidence.
3. **Strategy Advisory Limits:**
   - Evaluated via live `PitIn`/`PitOut` calibrated transit losses (`[10s, 45s]`) + live field-gap re-entry rank projection. Never presented as a globally optimal Nash-equilibrium or full-race MILP solver; explicitly flags missing remaining distance (`<= 2` laps sets `pit_window_viable=False`), missing defender interval, partial field gaps, and unknown neutralisation end time.

---

## 4. Scientific Validation Protocol ([baseline_comparison.py](../backend/pulse/analytics/baseline_comparison.py))

All 6 pace baselines are compared over **identical green-flag, non-pit, `CLEAN_AIR_CONFIRMED` flying laps (`lap >= 2`)** across:
- **Calibration / Development Split:** `2021 British GP`, `2021 Saudi Arabian GP`, `2022 Monaco GP`.
- **Temporal Held-Out Test Split:** `2021 Abu Dhabi GP`, `2022 Japanese GP`.
- **Edge-Case Stress Check:** `2021 Belgian GP` (`3` total laps behind Safety Car -> `0` green targets predicted, zero spurious output).
- **Leave-One-Race-Out (LORO) Validation:** Cross-validated across all 5 full-distance races (`regression_params` refit solely on the 4 training races per fold).

| Model | Definition | Primary Role |
| :--- | :--- | :--- |
| `PreviousLapPredictor` | Immediately preceding green same-stint lap + trailing `q95` PI | High-adaptability naive autoregressive baseline |
| `RollingFiveLapMedian` | Unfiltered 5-lap median in current stint + `2.6*sigma` PI | Tests value of outlier & clean-air filtering |
| `RollingCleanAirMedian` | 5-lap median on `CLEAN_AIR_CONFIRMED` laps only | Tests value of fuel/evo adjustment over clean median |
| `CircuitNormalizedRegression` | Cross-race LORO OLS on `(tyre_age, race_progress)` + online intercept | Linear parametric regression baseline |
| `ExistingFuelCompensatedModel` | Pre-Phase-I estimator (`clean_air != False`, no restart guard, fixed `2.6*sigma`) | Measures pre-Phase-I regression baseline |
| `RevisedPULSEModel` | Phase I strict `CLEAN_AIR_CONFIRMED` + restart/evo guard + Student-t / trimmed conformal PI | Evaluates Phase I net improvement |
