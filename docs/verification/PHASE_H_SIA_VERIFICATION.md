# PULSE — Phase H SIA Core v3 Mathematical, Temporal, Origin & Durability Verification

**Audit Date:** 2026-11-26  
**Kernel & Integration Modules:** [`sia_core_v3/sia_core/`](../../sia_core_v3/sia_core/engine.py), [`backend/pulse/integrity/`](../../backend/pulse/integrity/agent.py)

---

## 1. Phase H Critical Defects Discovered & Fixed in SIA Runtime Integration

While `sia_core_v3` passed its standalone 265 unit tests at baseline freeze, Phase H end-to-end runtime testing exposed **three severe integration/durability gaps**:

| Defect Discovered | Root Cause | Phase H Fix | Verification Evidence |
|---|---|---|---|
| **1. `SIAWALStore` was disconnected in production `main.py` (`wal_path=None`)** | `config.py` defined `sia_wal_path = "data/sia_ledger.sqlite"`, yet `main.py` initialized `IntegrityAgent(bus=bus)` with `wal_path=None`, losing 100% of SIA state on restart while Kafka offsets still committed. | Wired `wal_path=(settings.sia_wal_path or "").strip() or None` + `session_id=replay_controller.session_id` into [`main.py`](../../backend/pulse/main.py), added `switch_session(..., preserve_wal=...)` in [`store.py`](../../backend/pulse/state/store.py), enhanced `restore_from_wal()` in [`agent.py`](../../backend/pulse/integrity/agent.py), and gated Kafka manual `consumer.commit()` strictly **after** WAL persistence. | **`task-2518`** live `SIGKILL` drill: pre-kill `21` chains (`28` atoms) -> post-kill `uvicorn` startup recovered all `21` chains (`verified=True`) and resumed uncommitted Kafka offset (`28 -> 29` atoms); **`test_lifespan_wal_preserved_on_restart_and_cleared_on_reset`** **PASSED**. |
| **2. Five latent crash bugs inside `SIAWALStore.sync_engine()`** | Whenever WAL pause/sync ran (e.g., after `/api/replay/seek` `set_wal_paused(False)`), [`wal.py::sync_engine()`](../../sia_core_v3/sia_core/wal.py) iterated dict keys (`_atoms`, `_facts`), treated `GuardRec` as `GuardFact`, accessed nonexistent `eng.index._records`, and read missing key `q["kt"]`. | Fixed all 5 loops in `SIAWALStore.sync_engine()` cleanly (`_atoms.values()`, `_facts.values()`, `rec.guard`, `eng.index.decisions()/chain()`, `q.get("kt") or parse_instant(q["knowledge_time"])`). | **`test_sia_wal_pause_sync_engine_and_crash_restart_recovery`** **PASSED**; `Benchmark 2` ran `10` full `seek(36321)` `sync_engine()` + `restore_from_wal()` cycles with **`0` errors** (`1.40 s` median restore). |
| **3. Cross-partition out-of-order `session_t0` race** | `_maybe_admit_session_t0()` locked `_session_t0_admitted = True` on whichever event arrived first (e.g. a partition-1 `LAP_COMPLETED`) and silently ignored the true Partition-0 `SESSION_STARTED`. | Added `_session_t0_official`, `_session_t0_fact_id`, and `_session_t0_value` state tracking + checkpoint/WAL persistence in [`agent.py`](../../backend/pulse/integrity/agent.py), allowing authoritative `SESSION_STARTED` to emit a superseding `session_t0` reference fact (`supersedes=...`). | **`test_cross_partition_out_of_order_session_t0_supersession_invariance`** **PASSED** (verifies final active `session_t0` matches sequential order identically). |

---

## 2. Independent Verification of Core Epistemic & Formal Properties

### 2.1 Four-State Lattice Algebra (`algebra.py`) & Conservativity
- **States:** Total order `DEGRADED (0) < UNKNOWN (1) < SUSPECT (2) < HEALTHY (3)` (`algebra.py`).
- **Operators:** `MEET` (`min`), `JOIN` (`max`), and deterministic `k-of-n` order statistics operate on discrete states and lifted open-world interval `[lower, upper]` projections over pending roles, guaranteeing monotonic narrowing (`SuperpositionView`) as evidence arrives without collapsing missing data into optimistic `HEALTHY`.

### 2.2 Source Independence & Common-Cause Closure (`model.py`, `evaluator.py`, `bridge.py`)
- **`OriginRegistry` Transitive Graph:** Verified across `DEFAULT_ORIGINS` (`PITWALL -> [F1_FOM_TIMING]`, `TRACINGINSIGHTS -> [F1_FOM_TIMING]`, `FASTF1_RESEARCH -> [F1_TIMING_ARCHIVE, F1_FOM_TIMING]`). Disjoint adapters sharing `F1_FOM_TIMING` collapse strictly to corroboration depth `1`, emitting `COMMON_CAUSE_EXPOSURE` and blocking `k >= 1` resilience claims unless physically/upstream disjoint origins (e.g., `LAB` twin loops) corroborate.

### 2.3 Bitemporal Semantics (`K` vs. `V`), Historical Clock Invariance & Pre-Admission Quarantine (`ledger.py`, `engine.py`)
- **Strict Knowledge-Time Monotonicity:** `Ledger._common()` fail-closes (`KNOWLEDGE_TIME_REGRESSION`) if any admission attempts to regress `kt < self.clock`.
- **Historical Replay Invariance (`agent.py`):** Confirmed in `test_historical_event_with_omitted_ingest_time_never_leaks_wall_clock` — historical captures (e.g. `2021-12-12` Yas Marina) preserve event-time `K` (`2021-12-12T13:00:00Z`) cleanly regardless of host wall-clock year, while preserving intra-race delayed delivery intervals.
- **Pre-Admission Finality Quarantine (`engine.py`):** Checked `admit_atom` (`lines 197–218`) and `admit_fact` (`lines 237–261`): checks matching sealed `FINAL` instances **before** `self.ledger.admit_*`, routing late arrivals directly into `quarantined_items` / `sia_quarantine` with `POST_FINALITY_QUARANTINED` so `ledger.counts()` and sealed `record_hash` chains remain strictly invariant.

### 2.4 Cryptographic Hash-Chain Determinism & Tamper Evidence (`canon.py`, `verdict.py`)
- **RFC 8785 Canonical JSON + `SHA-256`:** Every assessment computes separate `content_hash` (`verdict_hash`) and previous-linked `record_hash` over `jcs()` canonical JSON (removing prior misleading `"Blake3"` labels).
- **Tamper & Replay Verification:** Direct SQLite content modification is caught immediately (`test_sqlite_wal_durability_recovery_and_tamper_detection`); duplicate `save_atom` / `save_assessment` WAL calls are strictly idempotent (`INSERT OR IGNORE`, verified in `task-2518`); incremental snapshot verification matches full `/api/integrity/verify` across all `637` Silverstone chains (`verified: true`, `0` keyframe seek mismatches across `10` trials).

---

## 3. Domain Independence Verification

Verified cleanly in [`sia_core_v3/tests/test_sia_domain_independence.py`](../../sia_core_v3/tests/test_sia_domain_independence.py): an isolated **Clinical ICU Haemodynamic & Sepsis Monitoring** contract (`MAP`, `lactate` common-cause sensor collapse, late lab quarantine, bitemporal `as_of(K)`) executes directly on `IntegrityEngine` with zero Formula 1 code or runtime coupling, confirming the SIA kernel is domain-agnostic while keeping 100% of PULSE runtime code focused exclusively on Formula 1.
