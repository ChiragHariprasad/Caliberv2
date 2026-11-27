# CHANGELOG — PULSE (`pulse-reconstruction` & `pulse-phase-j-rc`)

All notable architectural, scientific, security, optimization, and documentation changes are recorded chronologically below with direct Git commit traceability. Preserved Phase I checkpoint: `f5fbc6a` on `pulse-reconstruction`; Release Candidate branch: `pulse-phase-j-rc`.

---

## Phase J — Release Candidate, Independent Validation & Academic Readiness (`pulse-phase-j-rc`)

- **`security(api,config,store)` (`148a6b5`):**
  - Enforced fail-closed startup and runtime security posture in `backend/pulse/{config.py,main.py,api/security.py}`: default `host="127.0.0.1"`, `PULSE_REQUIRE_CONTROL_AUTH` support, mandatory non-placeholder `>=16`-char `PULSE_API_KEY` whenever auth is enabled or `PULSE_ENV` is non-development (`shared-demo`, `production`, `staging`, `external`) or `host` is non-loopback, strict rejection of wildcard `*` CORS and unmodified local CORS defaults in external environments, and HTTP `503` fail-closed guard inside `require_control_api_key`.
  - Replaced non-atomic SSE listener checks in `backend/pulse/state/store.py` & `router.py` with atomic `store.try_add_listener()`, updated `.env.example`, and added `backend/tests/test_phase_j_security.py` (`3/3` passing across all `10` `POST` mutators, CORS allowlist, session isolation `404`/`409`/`422`, and HTTP `429` SSE capacity + cleanup).

- **`feat(science,sia)` (`31a323b`):**
  - Cached **11 additional real 2023–2024 Grands Prix** via the free public historical OpenF1 REST API under `data/openf1_cache/` (`7.02 MB`: `2023` Austria/Britain/Netherlands/Singapore/Japan, `2024` Saudi Arabia/Monaco/Canada/Britain/Monza/Brazil), expanding offline validation to **17 real races across 4 seasons (`2021–2024`)**.
  - Added `backend/pulse/analytics/generalization_phase_j.py` & `scripts/run_phase_j_generalization.py` (`reports/benchmarks/phase_j_generalization.json`): fixed silent dead-code skip in `test_baseline_comparison.py`, reconciled LORO-5 (`n=1,560` paired delta `-0.4651s [-0.6343, -0.3159]`, `50` abstentions where legacy baseline had `MAE 18.0788s`), computed within-stint lag-1 residual autocorrelation (`+0.38`–`+0.40`) and `2,000`-replicate stint/session block bootstrap CIs, unseen external `2023–2024` holdout (`MAE 0.5288s [0.4855, 0.5740]`, `PI95 94.41%`), 15-fold walk-forward (`MAE 0.5327s`, `PI95 94.34%`), LORO-16 (`MAE 0.5239s`, `PI95 94.28%`), strict 6-way common support, and 7-dimension stratification (documenting wet `91.28%` under-coverage and 2024 delta narrowing).
  - Added `sia_core_v3/tests/test_phase_j_sia_semantics.py` comparing four-state scalar rollup masking against orthogonal multidimensional projections extracted from `EvalOutput.content`, transitive common-cause closure, unauthorized supersession rejection, pre-admission finality quarantine, and bitemporal `as_of` immutability (`311` core/scientific tests passing).

- **`perf(replay),fix(ui)` (`c28c88f`):**
  - Built `scripts/benchmark_phase_j_replay.py` (`reports/benchmarks/phase_j_replay_benchmarks.json`) decomposing all 7 replay boundaries on `f1-2023-silverstone-race` (`36,321`): import `0.66s`, default Monaco load `2.19s`, Silverstone switch `2.21s`, domain replay without SIA `1.64s` vs full SIA+WAL sync `14.98s` (`std=0.25s`, `89.04%` SIA cost), warm seeks `0.33s–1.16s`, SQLite WAL process restart recovery `0.75s` (`625/625` exact hashes, `0` mismatches), and live Uvicorn HTTP round-trips; explained Phase I `14.69s` vs `70.88s` discrepancy via CPU/thermal contention under back-to-back subprocess execution (`32s–81s`).
  - Raised `frontend/src/api.ts` `seekReplay` timeout `45s -> 120s` and fixed stale topic labels in `frontend/src/components/agents/AgentsPipelineView.tsx` (`npm run build` clean in `1.62s`).

- **`perf(kafka,flink)` (`232f9a3`):**
  - Built `scripts/benchmark_phase_j_kafka_sustained.py` (`reports/benchmarks/phase_j_kafka_sustained.json`) separating **Tier 1** raw broker/consumer capacity (`73.7k–83.8k msg/s` batch sweep, `30.6k msg/s` concurrent fan-in, `18.5k msg/s` batched SQLite drain) from **Tier 2** sustained `110.86s` E2E pipeline (`Kafka -> Flink v3 -> 6 Agents -> unpaused SIA WAL -> per-event SQLite VerdictSink`): **`9.67 ev/s`**, `24` Flink checkpoints (`0` failed, `0` backpressure), `+39.53 MB` Python RSS, and mid-stream consumer restart preserving `978/978` SIA WAL hashes (`0` mismatches); `test_kafka_integration_t1_t10.py` `10/10` passing (`61.00s`).

- **`docs,verify` (Phase J Consolidation & Live Demo):**
  - Audited all `12` canonical documents against code (`pulse.norm.*`, `kafka-1..3:29092`, `4` Flink TaskManager slots / `36` subtasks, Python contracts instead of YAML, SIA formal contribution statement, Academic Demonstration Package, and Phase J prior-art confirmation).
  - Executed the complete 13-step live Chrome demo walkthrough in `KAFKA` + Flink v3 (`36/36` tasks, `6,686` Flink checkpoints, `0` failed/`0` backpressure, `0` console errors, `0` console warnings, `0` HTTP `>=400` responses, `541/541` verified SHA-256 chains, `Seek Lap` `L10`/`L15`, `As-Of (K)` query, and fault-injector drills `monaco_pit_bias`/`late_reference_fact`/`silent_feed_guard`).
  - Completed clean-environment final Phase J verification: **`467 passed, 0 failed, 0 skipped`** (`457` non-T2 in `192.01s` + `10` live `T1–T10` failover in `56.26s`), `npm run build` (`60` modules in `1.38s`), `70/70` Kafka topic verification (`0` drift), and `check_docs.py` (`12/12` canonical docs clean).

---

## Phase I — Research Validation, Optimization, Hardening & Consolidation (`f5fbc6a`)

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
  - Added `backend/pulse/api/security.py` (optional control-plane guard using `PULSE_API_KEY` via `X-PULSE-API-Key` / `Bearer`, later hardened fail-closed in Phase J `148a6b5`), restricted FastAPI CORS origins to `settings.cors_origin_list`, enforced strict `session_id` path regex, and bounded SSE listeners (`max_sse_listeners=64`, HTTP `429`).
  - Verified raw broker 3-broker KRaft + Flink v3 (`36/36` subtasks) ingestion/drain metrics via `scripts/benchmark_kafka_sustained.py` (`12,320.9 msg/s` batch sweep, `10,585.9 msg/s` 3-session concurrent fan-in, `18,000` lag drained to `0` at `3,791 msg/s`, `0` dedup violations, `+18.63 MB` RSS; separated from E2E analytics throughput in Phase J `232f9a3`) and `10/10` live `T1–T10` failover tests.

- **`docs` (`f5fbc6a` Stage 8/10 Consolidation):**
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
