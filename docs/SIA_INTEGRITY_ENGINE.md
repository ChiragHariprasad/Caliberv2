# SIA Integrity Engine (`sia_core_v3`) Specification & Hardening

**Modules:** [`sia_core_v3/sia_core/`](../sia_core_v3/sia_core/engine.py), [`backend/pulse/integrity/`](../backend/pulse/integrity/agent.py)

---

## 1. Epistemic Core Semantics

`sia_core_v3` remains strictly Python-standard-library-only (`ADR-01`) and implements:

1. **Four-State Total Order Lattice (`algebra.py`):**
   `DEGRADED (0) < UNKNOWN (1) < SUSPECT (2) < HEALTHY (3)`
   Supports deterministic lattice operators `MEET (min / AND)`, `JOIN (max / OR)`, `k-of-n` order statistics, and open-world possibility intervals `[lower, upper]` over pending slots (`SuperpositionView`).
2. **Scoped Evidence & Common-Cause Origin Graph (`model.py`, `evaluator.py`):**
   - Strictly enforces scope compatibility (`SESSION`, `DRIVER_SESSION`, `DRIVER_LAP`, `SECTOR`, `ZONE`).
   - Models `OriginRegistry` transitive dependency closures: disparate adapters sharing a common upstream dependency (e.g., `PITWALL` and `TRACINGINSIGHTS` -> `F1_FOM_TIMING`) collapse to **source corroboration depth = 1**, emitting `COMMON_CAUSE_EXPOSURE` and `INSUFFICIENT_RESILIENCE` (`k >= 1`) rather than false corroboration.
3. **Bitemporal Indexing & Hash-Chained Ledger (`verdict.py`, `ledger.py`, `canon.py`):**
   - Separates valid time (`event_time_utc`, telemetry intervals) from strictly monotonic knowledge time (`K`, microsecond ledger clock).
   - Computes content hashes (`verdict_hash`) and previous-linked record hashes (`record_hash`) using strict RFC 8785 Canonical JSON (`jcs()`) + SHA-256 (`sha256_hex()`).

---

## 2. Hardening Implemented During Reconstruction

| Vulnerability Addressed | Reconstruction Fix | Verification |
|---|---|---|
| **Post-finality mutation leakage** | `_check_finality` now executes **pre-admission** before `self.ledger.admit_*`; late atoms/facts arriving after `FINAL` cutoff are quarantined in `quarantined_items` (and persisted in WAL `quarantine` table) without mutating normal ledger views or sealed `record_hash` chains. | `sia_core_v3/tests/test_core.py`, `backend/tests/test_phase2` / `test_integrity.py` |
| **Inconsistent `void_decision` schema** | `IntegrityEngine.void_decision()` now emits full `calibre.sia.assessment/3.0` structure (`envelope`, `validity_timeline`, `resolution_maturity="TUPLE_RESOLVED"`, `finality_status="FINAL"`, `witnesses`) matching `evaluate_decision()`. | `calibre_core/tests/test_historical_scenarios.py`, `sia_core_v3/tests/` |
| **Supersession cycles & authority hijacks** | Cycle detection + origin-authority enforcement prevent adversarial or malformed supersession links from overriding higher-authority observations or creating evaluation loops. | `sia_core_v3/tests/` (`265 passed`) |
| **Process-local volatility** | Added `SIAWALStore` (`sia_core_v3/sia_core/wal.py`, SQLite transactional store for contracts, instances, atoms, facts, guards, assessments, and quarantine) plus `sync_engine()` bulk commit and `export_state()`/`restore_state()` pickle checkpoints. | Tested via crash/reload & keyframe equivalence suites |
| **Historical clock wall-clock leakage** | Fixed `IntegrityAgent._event_knowledge_time()` so historical captures with omitted or far-future defaulted `ingest_time_utc` align deterministically to event time rather than leaking host 2026 clocks into 2021–2023 races (preserving explicit bitemporal delays within races). | Verified on 2021 Abu Dhabi / 2023 Silverstone historical runs |
| **`O(N^2)` `driver_position` blowup & 3.0s snapshot stall** | (a) Added deterministic `(session_id, driver_id, lap)` 12s position/telemetry heartbeat throttling in `IntegrityAgent.on_event()` (while admitting immediately on first sample, lap change, rank/status change, or non-healthy/anomalous observations); (b) added O(1) guard scan pointer (`_guard_scan_idx`); (c) added `IntegrityEngine.verify_incremental()` for `/api/snapshot` while preserving full `verify_chains()` on `/api/integrity/verify`. | Cold `seek(36321)` reduced `230.4s -> 20.8s`; steady `get_snapshot()` reduced `2,994ms -> 1.1ms`; `verify_chains(637)` `480.3ms` (`all_ok=True`) |

---

## 3. Domain Independence Proof (Clinical ICU Fixture)

To prove `sia_core_v3` has zero hidden motorsport coupling inside the kernel, an isolated unit test exercises `IntegrityEngine` against an independent **Clinical ICU Haemodynamic & Sepsis Monitoring** domain (validating MAP/lactate contracts, sensor common-upstream failures, late lab-result quarantine, and clinical `as_of(K)` verdict reconstruction). The clinical domain logic stays strictly confined inside the test suite (`sia_core_v3/tests`), keeping all runtime PULSE modules dedicated to Formula 1.
