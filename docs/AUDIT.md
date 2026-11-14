# CALIBRE — Codebase Audit & Architectural Assessment

**Date:** 13 November 2026  
**Auditor:** Principal Software Architect & QA Lead  
**Reference Document:** CALIBRE — Complete Idea Documentation (12 November 2026)  
**Baseline Test Status:** 380 passed, 17 skipped (Kafka container offline), 1 warning in 94.75s

---

## 1. Executive Summary

A comprehensive, line-by-line inspection of the repository (`E:\Caliberv2`) was performed against the attached CALIBRE Complete Idea Documentation. The repository represents an advanced, highly capable codebase containing:
1. **SIA Core v3 (`sia_core_v3/`):** A mathematically rigorous, zero-dependency, pure Python implementation of Scoped Integrity Algebra (SIA) with 259 passing unit, property, and scenario tests.
2. **CALIBRE v4 Core (`calibre_core/`):** Durable archive bundles (`.tar.zst`), effective-dated reference registries, policy-neutral threshold witnesses with guard bands, algorithm-tagged digests, source pack lineage models, and a standalone zero-dependency verifier CLI.
3. **PULSE Backend (`backend/pulse/`):** A dual-transport streaming engine (in-memory bus & Kafka) with 6 tactical agents, session replay controller, and REST/SSE APIs.

However, critical gaps exist between the current codebase and the target 10-year CALIBRE architecture:
- Several **Kernel Change Requests (CR-1, CR-2, CR-6, CR-10, CR-L2, CR-L6)** specified in the core plan are not yet integrated into the SIA kernel.
- The **Five Specialist Agent Archetypes (A1–A5)** are currently conflated with PULSE's tactical strategy agents (dirty air, tyre degradation, consequence fusion). They must be implemented as distinct, pure evidence producers strictly governed by rules AR-1 through AR-10.
- The **Contract Catalogue (C01–C13)** is only partially populated (only 5 contracts exist, missing C04–C08, C10–C13).
- **Formal Specifications (EE, DEC, IA, LOG, SEM, BUN, PACK)** are not yet extracted as versioned documents with conformance test vectors.
- The **Historical Race Corpus** contains only one real historical session (Silverstone 2023) and synthetic simulations. The mandatory **10-race controversy corpus (2021 onwards, featuring Abu Dhabi 2021)**, along with repeatable data acquisition and scenario evaluation, is missing.

---

## 2. Requirement-by-Requirement Implementation Audit

Every core requirement is classified below with concrete repository evidence:
- **IMPLEMENTED** — present, fully conforming, and tested.
- **PARTIALLY IMPLEMENTED** — present but incomplete or lacking full verification.
- **MISSING** — not implemented.
- **INCORRECT** — present but violates intended architecture or semantics.
- **BLOCKED** — cannot be completed due to hard external constraints.

### 2.1 SIA Reasoning Kernel (`sia_core_v3/sia_core/`)

| Component / Requirement | Status | Evidence / Files | Notes |
|---|---|---|---|
| RFC 8785 Canonical JSON & SHA-256 | **IMPLEMENTED** | `sia_core/canon.py`, `tests/test_core.py:TestCanon` | Strict integer-microsecond time representation; no float time comparisons. |
| Four-State Lattice Algebra | **IMPLEMENTED** | `sia_core/algebra.py`, `tests/test_core.py:TestAlgebra` | DEGRADED < UNKNOWN < SUSPECT < HEALTHY. Composable AND/OR/k-of-n. |
| Typed Time & Conversion Graph | **IMPLEMENTED** | `sia_core/timeclass.py`, `tests/test_core.py:TestTimeClass` | Reference-gated conversions; uncertainty propagation. |
| Evidence Atoms & Content Addressing | **IMPLEMENTED** | `sia_core/model.py:EvidenceAtom`, `make_atom()` | Content-addressed by SHA-256 of canonical JSON payload. |
| Two-Axis Origin Independence | **IMPLEMENTED** | `sia_core/model.py:OriginRegistry` | Source and processing axis closures; disjoint check. |
| Constraints (Bounds, Diff, Ratio, Linear, Interval) | **IMPLEMENTED** | `sia_core/contract.py`, `sia_core/evaluator.py` | Cross-role validation and physical consistency. |
| Minimal Fault Diagnosis | **IMPLEMENTED** | `sia_core/evaluator.py:_diagnose()` | Hitting-set enumeration over minimal hypotheses up to budget $f$. |
| Possible-World Resilience Analysis | **IMPLEMENTED** | `sia_core/evaluator.py:_resilience()` | Origin loss analysis for $k \in \{1, 2\}$; critical origin reporting. |
| Superposition Envelope & Maturity | **IMPLEMENTED** | `sia_core/evaluator.py:_envelope()`, `algebra.py:envelope()` | OPEN, STATE_RESOLVED, TUPLE_RESOLVED, FINAL. Lower/upper bounds. |
| Hash-Chained Bitemporal History | **IMPLEMENTED** | `sia_core/verdict.py:Assessment`, `sia_core/ledger.py` | `content_hash` excludes eval instant; `record_hash` commits to previous link. |
| Population Calibration Monitor | **IMPLEMENTED** | `sia_core/calibration.py` | Median bias estimator across populations. |
| **CR-1: Decision Voiding with Witness** | **MISSING** | `sia_core/engine.py`, `sia_core/evaluator.py` | Voiding for retirements/red flags with `VOIDED` witness is absent. |
| **CR-2: Lateness Witness for Late References** | **MISSING** | `sia_core/evaluator.py` | Late references do not emit `LATE_REFERENCE_FACT`. |
| **CR-6: Witness Code Registry** | **MISSING** | `sia_core/verdict.py` | Witnesses are tuples/strings; lacks central registry with severity. |
| **CR-10: Zone Sub-Scope Key** | **PARTIALLY IMPLEMENTED** | `sia_core/model.py:ScopeClass` | Only SESSION, DRIVER_SESSION, DRIVER_LAP, SECTOR. Lacks ZONE sub-scope. |
| **CR-L2: Algorithm-Tagged Digests in Kernel** | **PARTIALLY IMPLEMENTED** | `calibre_core/durable.py` vs `sia_core/canon.py` | Kernel produces bare 64-char hex; `calibre_core` expects `sha256:` prefix. |
| **CR-L6: Margin Report as Witness (P3)** | **PARTIALLY IMPLEMENTED** | `calibre_core/durable.py:threshold_witness` | Exists in `calibre_core`, but not integrated into `sia_core/evaluator.py`. |

### 2.2 Five Specialist Agent Archetypes

| Agent Archetype | Status | Evidence / Files | Notes |
|---|---|---|---|
| Shared Agent SDK (AR-1..AR-10) | **PARTIALLY IMPLEMENTED** | `backend/pulse/agents/base.py` | Has metrics & transparency, but oriented towards tactical findings, not evidence atoms. |
| **A1: Timing Agent** | **PARTIALLY IMPLEMENTED** | `pulse/integrity/bridge.py`, `scripts/acquire_historical_race.py` | Emits lap/sector timings into pulse events, but lacks standalone pure archetype with failure catalogue. |
| **A2: Vehicle Telemetry Agent** | **PARTIALLY IMPLEMENTED** | `pulse/agents/vehicle_response.py` | Computes tactical dirty air / pace deviation; does not emit windowed speed, integrated distance, or kinematic flags atoms. |
| **A3: Spatial & Geometry Agent** | **MISSING** | N/A | No agent currently computes gate crossings, trajectory path lengths, or geometry references with layout validity windows. |
| **A4: Session Context Agent** | **PARTIALLY IMPLEMENTED** | `pulse/agents/event_control.py` | Tracks safety cars for tactical exposure, but does not emit structured session intervals, entry lists, or rule-regime facts. |
| **A5: Feed Supervisor Agent** | **PARTIALLY IMPLEMENTED** | `pulse/stream/bus.py`, `pulse/main.py` | Basic heartbeat and drift tracking, but shares execution paths and does not emit independent clock ticks or STALLED/RESUMED guards. |

### 2.3 Decision Evidence Contracts (C01 – C13)

| Contract ID & Name | Status | Evidence / Files | Notes |
|---|---|---|---|
| C01 Lap-Time Consistency | **IMPLEMENTED** | `backend/pulse/integrity/contracts.py:_lap_time_contract` | Verifies lap timing against session T0 and lap start references. |
| C02 Sector-Sum Consistency | **PARTIALLY IMPLEMENTED** | `backend/pulse/integrity/contracts.py:_sector_time_contract` | Verifies individual sector bounds; missing interval constraint $\sum S_i = \text{Lap}$. |
| C03 Pit-Lane Speed Integrity (Flagship) | **PARTIALLY IMPLEMENTED** | `backend/pulse/integrity/contracts.py:_pit_speed_contract` | Ratio check exists; lacks P3 guard band uncertainty witness and P4 population tie-in. |
| C04 Vehicle Kinematic Plausibility | **MISSING** | N/A | Bounded acceleration, brake/throttle exclusivity, gear/RPM plausibility. |
| C05 Telemetry Time Alignment | **MISSING** | N/A | Lap-relative telemetry alignment against lap start reference. |
| C06 Position and Track Consistency | **MISSING** | N/A | Track-position mapping and gate-crossing geometry checks. |
| C07 Session-Status Integrity | **MISSING** | N/A | Consistency across race control messages, track status, and flags. |
| C08 Incident Timing | **MISSING** | N/A | Incident interval bounding and participant exposure. |
| C09 Weather Reporting | **IMPLEMENTED** | `backend/pulse/integrity/contracts.py:_weather_contract` | Validates ambient weather readings. |
| C10 Weather-Dependent Advisory | **MISSING** | N/A | Demonstrates scope locality (weather outage does not degrade dry decisions). |
| C11 Feed-Source Integrity | **MISSING** | N/A | Evaluates supervisor health facts, cadence, and schema drift. |
| C12 Monitor Health | **MISSING** | N/A | Population monitor positive status facts and expiry. |
| C13 Rule-Regime Consistency | **MISSING** | N/A | Event-specific rule limit parameter bindings with effective dates. |

### 2.4 Streaming Architecture & Execution Infrastructure

| Component | Status | Evidence / Files | Notes |
|---|---|---|---|
| Admission Log Engine | **PARTIALLY IMPLEMENTED** | `calibre_core/capture_archive.py`, `sia_core/ledger.py` | Ledger admits atoms/facts, but standalone serialized admission log format (LOG spec) is not formalized. |
| Dual-Transport (Bus / Kafka) | **IMPLEMENTED** | `pulse/stream/bus.py`, `pulse/stream/kafka_io.py`, `calibre_core/kafka_io.py` | Transparent switching via `PULSE_TRANSPORT_MODE=SIMULATOR|KAFKA`. |
| Flink Job Execution | **PARTIALLY IMPLEMENTED** | `pulse/stream/flink/jobs/normalizer_job.sql`, `pulse/stream/flink/client.py` | SQL scripts exist; local simulator runs in-process equivalent. J1 Sequencer and J2 Evaluator Flink host wrappers need formalization. |
| Population Calibration Monitor (J3) | **PARTIALLY IMPLEMENTED** | `sia_core/calibration.py` | Calculation logic exists; continuous stream feedback loop needs wiring. |
| Standalone Verifier (J4) | **IMPLEMENTED** | `calibre_core/standalone_verifier.py`, `calibre_core/batch.py` | Standard-library-only offline verification CLI for archive bundles. |
| Replay & Clean State Reconstruction | **IMPLEMENTED** | `pulse/replay/controller.py`, `backend/tests/test_replay_processing.py` | Deterministic scrubbing, reset hooks, zero duplicate records published to sinks. |
| Portable Evidence Bundles | **IMPLEMENTED** | `calibre_core/archive.py:create_bundle()` | Self-contained `.tar.zst` packages with manifests, anchors, and raw data slices. |

### 2.5 Historical F1 Data & Controversies

| Item | Status | Evidence / Files | Notes |
|---|---|---|---|
| FastF1 Integration | **IMPLEMENTED** | `scripts/check_fastf1_coverage.py`, `data/fastf1_cache` | FastF1 3.9.0 configured with SQLite cache; loads laps, telemetry, weather. |
| Jolpica-F1 Ergast API Integration | **IMPLEMENTED** | `scripts/acquire_historical_race.py`, `scripts/test_jolpica.py` | Open data client for classification, pit stops, and lap timing. |
| Existing Captured Races | **PARTIALLY IMPLEMENTED** | `captures/f1-2023-silverstone-race` | Silverstone 2023 complete (72,642 records). Monaco and Suzuka are synthetic. |
| **10-Race Controversy Corpus (2021+)** | **MISSING** | N/A | Ranked list of 10 controversial races (with Abu Dhabi 2021 mandatory) not yet built into corpus. |
| Repeatable Multi-Race Acquisition Pipeline | **MISSING** | `scripts/acquire_historical_race.py` (Silverstone only) | Needs multi-race adapter acquiring metadata, timing, telemetry, position, track geometry, and race control. |
| Programmatic Track Geometry Maps | **PARTIALLY IMPLEMENTED** | `backend/pulse/circuits/` (SVG layouts) | SVG maps exist for rendering, but programmatic gate-crossing coordinates and sector boundaries are missing. |

---

## 3. Immediate Action Plan

Based on this audit, implementation proceeds across the following phases:
1. **Phase 1:** Document the comprehensive, dependency-aware Implementation Roadmap (`docs/ROADMAP.md`).
2. **Phase 2:** Research, curate, and document the 10-Race Controversy Corpus (`docs/F1_CONTROVERSY_CORPUS.md`).
3. **Phase 3:** Build the repeatable F1 data acquisition and normalization pipeline (`scripts/acquire_f1_corpus.py` and `calibre_core/source_pack.py`).
4. **Phase 4 & 6:** Implement the SIA kernel enhancements (CR-1, CR-2, CR-6, CR-10, CR-L2, CR-L6), formal specifications, the 5 specialist agent archetypes, and contracts C01–C13.
5. **Phase 5:** Maintain the master checklist (`docs/IMPLEMENTATION_CHECKLIST.md`).
6. **Phase 7 & 8:** Clean documentation, update decision log (`docs/DECISION_LOG.md`), run full validation test suite, and deliver final handover report.

