# PULSE — Canonical Architecture Decision Log (`ADR-01` – `PULSE-ADR-016`)

**Status:** Canonical Living Registry (Migrated & Updated Phase I)  
**Policy:** Historical CALIBRE decisions (`ADR-01`–`ADR-12`) are preserved with their original rationale while supersession tags link directly to reconstructed Phase H/I decisions (`PULSE-ADR-009`–`PULSE-ADR-016`). Rejected alternatives are explicitly recorded so abandoned refactors are not repeated.

---

## Part 1 — Historical CALIBRE Foundation Decisions (`ADR-01`–`ADR-12`)

| ID | Title | Original Status | Current PULSE Status & Traceability |
|---|---|---|---|
| **`ADR-01`** | Zero Kernel Dependencies Preservation (`sia_core_v3` pure Python stdlib) | Enforced | **Preserved & Enforced** (`PULSE-ADR-011`; verified by `sia_core_v3/tests`) |
| **`ADR-02`** | RFC 8785 Canonical JSON & `sha256:` Algorithm-Tagged Digests (`CR-L2`) | Enforced | **Preserved & Enforced** (`canon.py` regex+key-cache micro-optimized in Phase I; zero hash drift) |
| **`ADR-03`** | Legitimate Absence Decision Voiding (`CR-1`) via `void_decision()` | Enforced | **Preserved & Enforced** (emits full `calibre.sia.assessment/3.0` structure) |
| **`ADR-04`** | `LATE_REFERENCE_FACT` Witness for Late Reference Facts (`CR-2`) | Enforced | **Preserved & Enforced** |
| **`ADR-05`** | Formal Witness Code Registry (`INFO` / `WARNING` / `DEFECT`) (`CR-6`) | Enforced | **Preserved & Enforced** (`sia_core_v3/sia_core/witnesses.py`) |
| **`ADR-06`** | `ScopeClass.ZONE` Sub-Scope Support (`CR-10`) | Enforced | **Preserved** (with documented `SCOPE_FIELDS` key dependency in `SCIENTIFIC_FOUNDATIONS.md`) |
| **`ADR-07`** | Pattern P3 Guard-Banded Threshold Uncertainty (`CR-L6`) | Enforced | **Preserved & Enforced** (steward neutrality invariant: reports indeterminacy, never penalties) |
| **`ADR-08`** | Five Specialist Archetypes (`A1–A5`) & Agent Rules `AR-1..AR-10` | Enforced (target) | **Superseded for Runtime Execution** by `PULSE-ADR-001..008` (`EventControl`, `TrackState`, `VehicleResponse`, `TyreStrategy`, `Fusion`, `Integrity` in `backend/pulse/`) |
| **`ADR-09`** | Complete F1 Contract Catalogue (`C01–C13`) | Enforced | **Preserved** (13 catalogue specs + 5 runtime contracts mapped cleanly via `LIB_TO_RUNTIME_CONTRACT`) |
| **`ADR-10`** | Multi-Race Acquisition Pipeline & Jolpica-F1 Ergast Fallback | Enforced | **Preserved** (offline cache & honest `LAB` provenance segregation) |
| **`ADR-11`** | Content-Addressed Admission Log Engine (`LOG v1.0`) | Enforced | **Preserved** (`calibre_core/admission.py` + `SIAWALStore`) |
| **`ADR-12`** | Radical Provenance Honesty Across Four Data Regimes | Enforced | **Preserved & Hardened** (extended across `SYNTHETIC`, `LAB`, `PREVIEW`, `PUBLIC`, `LICENSED`, `INSTITUTIONAL`) |

---

## Part 2 — PULSE Reconstruction & Phase H/I Architecture Decisions

### `PULSE-ADR-009` — Manual Kafka Offset Commits Gated by SIA WAL & Idempotent Verdict Sink
- **Status:** Accepted (Phase H, `PULSE-ADR-009`)
- **Context:** Running `enable_auto_commit=True` with in-memory `wal_path=None` lost unpersisted offsets and SIA state on consumer crash or Flink restart.
- **Decision:** Wire `settings.sia_wal_path` into live runtime, configure Kafka consumers with `enable_auto_commit=False` over `getmany` micro-batches, execute `_route_normalized()` -> `SIAWALStore.sync_engine()` -> `IdempotentVerdictSink`, and commit offsets only after durable persistence succeeds.
- **Consequence:** Crash/restart recovery verified in live `SIGKILL` and TaskManager restart tests; `T1–T10` confirms `0` duplicate verdict persistence.

### `PULSE-ADR-010` — Retain Scalar Four-State Lattice + Orthogonal Evidence Vectors (Reject Product-Lattice Rewrite)
- **Status:** Accepted (Phase I · **Alternative Rejected**)
- **Context:** Phase I formally analyzed whether `DEGRADED < UNKNOWN < SUSPECT < HEALTHY` (`sia_core_v3/sia_core/algebra.py`) should be replaced with a 4D product lattice to avoid scalar collapse (`and_state(UNKNOWN, SUSPECT) == UNKNOWN`, `or_state(DEGRADED, UNKNOWN) == UNKNOWN`).
- **Decision:** **Keep** the scalar lattice in `algebra.py` and reject a breaking kernel rewrite, documenting the collapse boundaries explicitly in [`SCIENTIFIC_FOUNDATIONS.md`](../research/SCIENTIFIC_FOUNDATIONS.md).
- **Rationale:** `IntegrityEngine.evaluate_decision()` already exposes availability (`roles`), reliability/indeterminacy (`witnesses`), possibility bounds (`envelope`), provenance (`OriginRegistry`), and finality (`finality_status`) orthogonally; rewriting `algebra.py` would risk kernel compatibility without adding missing runtime observables.

### `PULSE-ADR-011` — Pre-Admission Finality Quarantine & Unindexed Scan Elimination
- **Status:** Accepted (Phase H/I, Commit `b836b8b`)
- **Context:** Late arriving records could mutate sealed history unless gated before admission; additionally, `scope_in()` linear ledger scans (`7.69M` calls), repeated `json.dumps` calls (`3.26M`), and deepcopies (`4.28M`) made cold seek expensive (`~21.1s` standalone, `~84s` full-stack).
- **Decision:** Enforce `_check_finality()` strictly before `Ledger.admit_*`; maintain indexed `facts_for` lookups in `Ledger`/`Evaluator`, `scope_in` tuple fast path, RFC 8785 safe-key caching in `canon.py`, shallow `model_copy()` cloning during keyframe replay, and corrupted-checkpoint fallback while preserving `run_id` isolation.
- **Consequence:** Standalone cold `seek(36321)` fell `-30.3%` (`21.08s -> 14.69s`) with `0` hash mismatches across `637` SIA chains.

### `PULSE-ADR-012` — Strict Evidence-Status Promotion Policy & Tri-State Clean-Air Classification
- **Status:** Accepted (Phase I, Commit `a130ef7`)
- **Context:** `Agent 05` (`ConsequenceFusionEngine._publish_superseding_v2`) promoted uncalibrated `PROVISIONAL` findings (`PRIOR_UNMEASURED`) to `CONFIRMED` merely when no blocking SIA integrity alert occurred; simultaneously, `TyreStrategyAgent` treated missing `interval_val` telemetry as clean air.
- **Decision:** Introduce five distinct statuses (`OBSERVED`, `PROVISIONAL`, `CONFIRMED`, `REJECTED`, `SUPERSEDED`) where missing SIA alerts never constitute positive confirmation; introduce `CleanAirStatus` (`CLEAN_AIR_CONFIRMED`, `TRAFFIC_AFFECTED`, `CLEAN_AIR_UNKNOWN`) excluding `CLEAN_AIR_UNKNOWN` from clean baseline updates; enforce `>= 5` inliers / span `>= 3` laps on tyre models and explicit `strategy_scope="ADVISORY_LOCAL_PIT_WINDOW_ONLY"` / `is_globally_optimal=False` on pit advisories.

### `PULSE-ADR-013` — Fast-Restart Recovery in Causal Clean-Air Pace Estimation
- **Status:** Accepted (Phase I, Commit `5afd7b9`)
- **Context:** 6-baseline LORO evaluation revealed why Phase H Japan `PI95` fell to `83.28%` and standing-restart laps spiked rolling averages: `RollingCleanAirPaceEstimator` averaged `len==1` standing-restart laps (e.g., Silverstone Lap 4 `160.13s`) with flying pace (`92.805s`), while `_advance_track_evo` drifted on `>5s` restart gaps.
- **Decision:** Guard fast restart transitions cleanly without future leakage (`fast_restart_recovery=True`), lifting LORO 5-race `PI95` to `93.91%` (`MAE 0.5094s`) and held-out 2022 Japan `PI95` to `95.18%` (`MAE 0.5730s`).

### `PULSE-ADR-014` — Optional Control-Plane Auth, Restricted CORS & Bounded SSE Listeners
- **Status:** Accepted (Phase I, Commit `a24ff6c`)
- **Context:** FastAPI originally exposed `allow_origins=["*"]`, unauthenticated control routes (`start`, `pause`, `seek`, `reset`, `lab-scenario`), unvalidated `session_id` path strings, and unbounded SSE subscriber queues.
- **Decision:** Add [`backend/pulse/api/security.py`](../../backend/pulse/api/security.py) (`require_control_api_key` via `X-PULSE-API-Key` or `Authorization: Bearer <token>` when `PULSE_CONTROL_API_KEY` is configured), restrict CORS to `settings.cors_origin_list`, enforce `[a-zA-Z0-9._-]+` `session_id` validation, and enforce `max_sse_listeners=64` (returning HTTP `429` above capacity).

### `PULSE-ADR-015` — Unified Three-Broker KRaft + Flink `v3` Pipeline Across All 9 Raw Topics
- **Status:** Accepted (Phase H/I)
- **Context:** Legacy Flink `v2` dropped `71,960` car-telemetry position events and Stage 3 in `orchestrator.py` stubbed normalization instead of consuming `pulse.norm.*`; `zstd` encoding crashed Flink container deserializers.
- **Decision:** Standardize on `pulse-canonical-normalizer-v3` (`18` RUNNING vertices / `36` subtasks covering all `9` `RAW_TOPICS`), default `CalibreProducer` compression to `gzip`, run real Flink Stage 3 consumption/watermarks, and keep host clients exclusively on external listeners (`localhost:19092..19094`).

### `PULSE-ADR-016` — Defer Patent Filing & Reject Uncorroborated Commercial Data Claims
- **Status:** Accepted (Phase I · **Action Deferred / Rejected**)
- **Context:** Claim-level review of verified Google Patents (`US6020851A`, `US8713073B2`, `US10614239B2`, `US11567823B2`, `US11747360B2`, `US20180089328A1`, `US10445698B2`, `US11943123B1`) and Indian Patents Act Section 3(k) + 2025 CRI Guidelines.
- **Decision:** **Do not file** broad PULSE (`1.5/10`) or standalone SIA software (`2.5/10`) claims; defer any filing until/unless a physical hardware/network interlock architecture (`~4.0/10`) receives formal FTO clearance from patent counsel. Continue strict `SYNTHETIC`/`LAB`/`PREVIEW` separation without F1TV scraping.
