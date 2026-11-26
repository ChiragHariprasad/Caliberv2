# CHANGELOG — PULSE (`pulse-reconstruction` Branch)

All notable architectural, scientific, security, optimization, and documentation changes are recorded chronologically below with direct Git commit traceability.

---

## Phase I — Research Validation, Optimization, Hardening & Consolidation

- **`fix(fusion,analytics)` (`a130ef7`):**
  - Enforced strict five-state evidence confirmation policy (`OBSERVED`, `PROVISIONAL`, `CONFIRMED`, `REJECTED`, `SUPERSEDED`) in `backend/pulse/contracts.py`, `backend/pulse/agents/fusion.py`, `backend/pulse/state/store.py`, and `frontend/src/{types.ts,styles.css}`. Uncalibrated priors (`PRIOR_UNMEASURED`), missing telemetry, or absent SIA alerts are never promoted to `CONFIRMED`.
  - Implemented explicit `CleanAirStatus` tri-state (`CLEAN_AIR_CONFIRMED`, `TRAFFIC_AFFECTED`, `CLEAN_AIR_UNKNOWN`) in `pace_and_tyre.py`, `vehicle_response.py`, and `tyre_strategy.py` so missing intervals no longer contaminate clean-air baselines.
  - Enforced `>= 5` inlier / `>= 3` lap span guards on `FuelCompensatedDegradationModel` and explicit advisory-scope / limitation metadata (`strategy_scope="ADVISORY_LOCAL_PIT_WINDOW_ONLY"`, `is_globally_optimal=False`) on `PitWindowStrategySimulator`.

- **`test(sia)` (`e9dadbb`):**
  - Added `sia_core_v3/tests/test_formal_invariants.py` verifying bounded distributive lattice axioms, documenting scalar epistemic collapse cases (`and_state(UNKNOWN, SUSPECT) == UNKNOWN`, `or_state(DEGRADED, UNKNOWN) == UNKNOWN`), proving orthogonal preservation across timelines/witnesses/finality, and verifying all `9` formal SIA invariants including 4-hop transitive `OriginRegistry` cycles, `verify_incremental()` equivalence, WAL quarantine isolation, and 500-atom adversarial determinism (`273` SIA tests passing).

- **`feat(evaluation)` (`5afd7b9`):**
  - Fixed standing-restart pace contamination (`fast_restart_recovery=True`) in `pace_and_tyre.py` and added causal ablation toggles (`enable_fuel_comp`, `enable_track_evo`, `enable_compound_effects`).
  - Added 6-baseline LORO + holdout comparison framework (`backend/pulse/analytics/baseline_comparison.py`, `scripts/run_baseline_comparison.py`), confirming `revised_pulse` (`MAE=0.5094s`, `PI95=93.91%`, held-out Japan `0.5730s` / `PI95=95.18%`, resolved Phase H `83.28%` under-coverage) and measuring 7 component ablations.

- **`perf(replay,sia)` (`b836b8b`):**
  - Profiled cold mid-race seek (`cProfile`) and eliminated `Ledger.facts` linear scans (`scope_in` / `facts_for` driver-lap index), repeated `json.dumps` in RFC 8785 canonicalization (`canon.py` regex & safe-key cache), and redundant `deepcopy` overhead during keyframe replay (`model_copy(update=...)`), while adding corrupted-checkpoint recovery with `run_id` isolation.
  - Reduced clean standalone cold `seek(36321)` by `-30.3%` (`21.08s -> 14.69s`) and subprocess mean cold seek to `70.88s` (`std=1.03s`, `0` hash mismatches).

- **`security,kafka` (`a24ff6c`):**
  - Added `backend/pulse/api/security.py` (`X-API-Key` optional control-plane guard via `PULSE_CONTROL_API_KEY`), restricted FastAPI CORS origins to `settings.cors_origin_list`, enforced strict `session_id` path regex, and bounded SSE listeners (`max_sse_listeners=64`, HTTP `429`).
  - Verified sustained 3-broker KRaft + Flink v3 (`36/36` tasks) throughput via `scripts/benchmark_kafka_sustained.py` (`12,320.9 msg/s` batch sweep, `10,585.9 msg/s` 3-session concurrent fan-in, `18,000` lag drained to `0` at `3,791 msg/s`, `0` dedup violations, `+18.63 MB` RSS) and `10/10` live `T1–T10` failover tests.

- **`docs` (Stage 8/10 Final Consolidation):**
  - Consolidated `24+` scattered Markdown files into a single canonical `12`-file documentation hierarchy indexed in [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md), preserving legacy records read-only in [`reports/historical/INDEX.md`](reports/historical/INDEX.md).
  - Documented claim-level Google Patents prior-art comparisons (`9` primary verified US patents + `US20080036587A1`) and Indian Section 3(k) / `2025` CRI Guidelines assessment in [`docs/research/RESEARCH_AND_PRIOR_ART.md`](docs/research/RESEARCH_AND_PRIOR_ART.md), enforced by [`scripts/check_docs.py`](scripts/check_docs.py).
  - Completed Stage 9 final verification: **`460 passed, 0 failed, 0 skipped`** (`450` non-T2 across `sia_core_v3`/`calibre_core`/`backend` in `322.16s` + `10` live 3-broker `T1–T10` failover tests in `56.92s`), Vite build (`60` modules in `2.69s`), `70/70` Kafka topic verification (`0` drift), and `check_docs.py` (`12/12` canonical docs clean).

---

## Phase H — Runtime Stabilization, Flink `v3`, WAL Coupling & Verification (`0017377`)

- Repaired `normalizer_job.sql` -> `pulse-canonical-normalizer-v3` covering all `9` raw topics (`18` vertices), switched `CalibreProducer` default compression to `gzip`, replaced stubbed Stage 3 Flink check with real `pulse.norm.*` consumption (`10/10` full `72,642`-event runs, `0` drops).
- Wired `SIAWALStore` runtime persistence (`wal_path`) with `enable_auto_commit=False` manual Kafka offset commits and `IdempotentVerdictSink`; passed live `SIGKILL` recovery drill (`436 / 436` post-edit tests).
- Repaired frontend SSE bias, wired `PipelineLabView`, synchronized session dropdown across hard reloads, and verified live Chrome DevTools cockpit cleanly (`0` console errors/warnings).

---

## Pre-Reconstruction Phase X Baseline (`9f1af40`)

- Initial repository snapshot preserved unmodified prior to reconstruction hardening (`calibre_core`, `sia_core_v3`, early `backend` / `frontend` prototypes).
