# CALIBRE — Master Implementation Checklist

**Date:** 14 November 2026  
**Status:** Canonical Implementation Progress Tracker  
**Governance:** Tasks transition to `COMPLETED` only when implementation is complete, and to `VERIFIED` only after all required tests pass.

---

## Task Index & Status Summary

| Phase | Description | Total Tasks | COMPLETED / VERIFIED | IN PROGRESS | NOT STARTED |
|:---:|:---|:---:|:---:|:---:|:---:|
| **0** | Baseline Audit & Verification | 3 | 3 | 0 | 0 |
| **1** | Implementation Roadmap | 2 | 2 | 0 | 0 |
| **2** | 10-Race Controversy Corpus Research | 2 | 2 | 0 | 0 |
| **3** | Data Sourcing & Repeatable Acquisition | 4 | 4 | 0 | 0 |
| **4** | SIA Kernel Evolution (CR-1..CR-L6) | 6 | 6 | 0 | 0 |
| **5** | Formal Specification Suite (EE, DEC, IA, etc.) | 7 | 7 | 0 | 0 |
| **6** | Five Specialist Agent Archetypes (A1..A5) | 6 | 6 | 0 | 0 |
| **7** | Decision Evidence Contracts (C01..C13) | 5 | 5 | 0 | 0 |
| **8** | Historical Scenario Fixtures & Tests | 4 | 4 | 0 | 0 |
| **9** | Flink & Kafka Stream Pipeline Integration | 4 | 4 | 0 | 0 |
| **10**| Replay, Bundles & Offline Verifier | 3 | 3 | 0 | 0 |
| **11**| Documentation, Archive & Handover | 3 | 3 | 0 | 0 |
| **Total** | **All Deliverables** | **49** | **49** | **0** | **0** |

---

## Detailed Dependency-Aware Master Tasks

### Phase 0: Baseline Audit & Repository Inspection
- [x] **AUD-01 (P0):** Execute full test baseline across `calibre_core`, `backend`, and `sia_core_v3`.
  - *Files:* `pytest.ini`, all test suites.
  - *Acceptance:* 380 passed, 17 skipped (Kafka container offline), 0 failed.
  - *Status:* **VERIFIED**
- [x] **AUD-02 (P0):** Perform comprehensive line-by-line requirement audit against idea documentation.
  - *Files:* `docs/AUDIT.md`.
  - *Acceptance:* Audit classifying every requirement as IMPLEMENTED, PARTIALLY IMPLEMENTED, MISSING, INCORRECT, or BLOCKED.
  - *Status:* **VERIFIED**
- [x] **AUD-03 (P0):** Inventory existing captures, scripts, and runtime environment.
  - *Files:* `captures/`, `scripts/`, `data/fastf1_cache`.
  - *Acceptance:* Python 3.13.12, FastF1 3.9.0, and existing session captures mapped.
  - *Status:* **VERIFIED**

### Phase 1: Architectural Roadmap
- [x] **RDM-01 (P0):** Document comprehensive 15-area implementation roadmap.
  - *Files:* `docs/ROADMAP.md`.
  - *Acceptance:* Complete area specifications, affected files, risks, and acceptance criteria.
  - *Status:* **VERIFIED**
- [x] **RDM-02 (P0):** Detail dependency graph and architectural invariants.
  - *Files:* `docs/ROADMAP.md`.
  - *Acceptance:* Explicit Mermaid dependency diagram and 7 core invariants defined.
  - *Status:* **VERIFIED**

### Phase 2: Historical F1 Controversy Corpus (2021+)
- [x] **COR-01 (P0):** Research and rank the 10 most significant controversial races from 2021 onwards.
  - *Files:* `docs/F1_CONTROVERSY_CORPUS.md`.
  - *Acceptance:* Abu Dhabi 2021 mandatory; exactly 10 races ranked with date, circuit, and drivers.
  - *Status:* **VERIFIED**
- [x] **COR-02 (P0):** Document facts vs. disputed interpretations and FIA primary documents for all 10 events.
  - *Files:* `docs/F1_CONTROVERSY_CORPUS.md`.
  - *Acceptance:* FIA Stewards decision numbers, WMSC inquiry findings, and sporting regulations cited.
  - *Status:* **VERIFIED**

### Phase 3: Data Sourcing, Geometry & Repeatable Acquisition
- [x] **DAT-01 (P0):** Complete data sourcing, legal regimes, and coverage assessment.
  - *Files:* `docs/DATA_SOURCING_ASSESSMENT.md`.
  - *Acceptance:* PUBLIC, LICENSED, INSTITUTIONAL, and LAB regimes defined; coverage matrix compiled.
  - *Status:* **VERIFIED**
- [x] **DAT-02 (P0):** Implement programmatic circuit geometry and layout validity windows.
  - *Files:* `calibre_core/circuits/geometry.py`.
  - *Acceptance:* Layout versions, survey provenance, gates, and effective dates for all 10 circuits.
  - *Status:* **VERIFIED**
- [x] **DAT-03 (P0):** Build repeatable multi-session acquisition script with automated Jolpica-F1 fallback.
  - *Files:* `scripts/acquire_f1_corpus.py`.
  - *Acceptance:* Downloads, validates, and hashes metadata, laps, race control messages, and weather.
  - *Status:* **VERIFIED**
- [x] **DAT-04 (P1):** Build unified corpus manifest and data completeness tests.
  - *Files:* `data/f1_corpus/corpus_manifest.json`.
  - *Acceptance:* All 10 races acquired, indexed, and checksummed in master manifest.
  - *Status:* **VERIFIED**

### Phase 4: SIA Reasoning Kernel Evolution
- [x] **KRN-01 (P0):** Implement CR-1 Decision Voiding with `VOIDED` witness.
  - *Files:* `sia_core_v3/sia_core/engine.py`.
  - *Acceptance:* Calling `void_decision()` finalizes decision as UNKNOWN with `VOIDED` witness and FINAL status.
  - *Status:* **VERIFIED**
- [x] **KRN-02 (P0):** Implement CR-2 Lateness Witness for late reference facts.
  - *Files:* `sia_core_v3/sia_core/evaluator.py`.
  - *Acceptance:* References admitted after soft deadline emit `LATE_REFERENCE_FACT`.
  - *Status:* **VERIFIED**
- [x] **KRN-03 (P0):** Implement CR-6 Centralized Witness Registry with severity and descriptions.
  - *Files:* `sia_core_v3/sia_core/witnesses.py`.
  - *Acceptance:* Every emitted witness has a registered code, severity (`INFO`/`WARNING`/`DEFECT`), and explanation.
  - *Status:* **VERIFIED**
- [x] **KRN-04 (P1):** Implement CR-10 Zone Sub-Scope Key for micro-sectors and pit-lane loop zones.
  - *Files:* `sia_core_v3/sia_core/model.py`.
  - *Acceptance:* `ScopeClass.ZONE` recognized with fields `(session_id, driver_id, lap_number, zone_id)`.
  - *Status:* **VERIFIED**
- [x] **KRN-05 (P1):** Implement CR-L2 Algorithm-Tagged Digests (`sha256:`) across all kernel hashes.
  - *Files:* `sia_core_v3/sia_core/canon.py`, `calibre_core/durable.py`.
  - *Acceptance:* All hashes prefixed with `sha256:`; backward-compatible parser recognizes bare hex.
  - *Status:* **VERIFIED**
- [x] **KRN-06 (P0):** Implement CR-L6 Policy-Neutral Threshold Margin Witness (Pattern P3).
  - *Files:* `calibre_core/durable.py`, `sia_core_v3/sia_core/evaluator.py`.
  - *Acceptance:* When measurement is within combined uncertainty of a threshold, emit `WITHIN_UNCERTAINTY`.
  - *Status:* **VERIFIED**

### Phase 5: Formal Specification Suite & Conformance Vectors
- [x] **SPC-01 (P0):** Formal Evidence Event Specification (`EE v1.0`).
  - *Files:* `calibre_core/specs/EE_v1.0.json`.
  - *Acceptance:* Valid JSON schema for content-addressed evidence atoms.
  - *Status:* **VERIFIED**
- [x] **SPC-02 (P0):** Formal Decision Evidence Contract Specification (`DEC v1.0`).
  - *Files:* `calibre_core/specs/DEC_v1.0.json`.
  - *Acceptance:* Valid JSON schema for roles, scopes, formulas, and constraints.
  - *Status:* **VERIFIED**
- [x] **SPC-03 (P0):** Formal Integrity Assessment Specification (`IA v1.0`).
  - *Files:* `calibre_core/specs/IA_v1.0.json`.
  - *Acceptance:* Valid JSON schema for 4-state verdicts, timelines, and hash chains.
  - *Status:* **VERIFIED**
- [x] **SPC-04 (P0):** Formal Admission Log Specification (`LOG v1.0`).
  - *Files:* `calibre_core/specs/LOG_v1.0.json`.
  - *Acceptance:* Valid JSON schema for sequencer log entries and knowledge-time monotonicity.
  - *Status:* **VERIFIED**
- [x] **SPC-05 (P1):** Formal Evidence Bundle Specification (`BUN v1.0`).
  - *Files:* `calibre_core/specs/BUN_v1.0.json`.
  - *Acceptance:* Valid JSON schema for portable archive bundles.
  - *Status:* **VERIFIED**
- [x] **SPC-06 (P1):** Formal Domain Pack Specification (`PACK v1.0`).
  - *Files:* `calibre_core/specs/PACK_v1.0.json`.
  - *Acceptance:* Valid JSON schema for domain pack adapters and references.
  - *Status:* **VERIFIED**
- [x] **SPC-07 (P0):** Language-Neutral Conformance Test Vectors.
  - *Files:* `calibre_core/specs/conformance_vectors.json`.
  - *Acceptance:* Canonical JSON, state lattice, threshold uncertainty, and witness registry vectors.
  - *Status:* **VERIFIED**

### Phase 6: Five Specialist Agent Archetypes (A1–A5)
- [x] **AGT-01 (P0):** Agent Archetype Base SDK enforcing AR-1..AR-10.
  - *Files:* `calibre_core/agents/base.py`.
  - *Acceptance:* Enforces pure observation output, deterministic atom hashing, and batch parity.
  - *Status:* **VERIFIED**
- [x] **AGT-02 (P0):** A1 Measurement Archetype: Timing Agent.
  - *Files:* `calibre_core/agents/timing.py`.
  - *Acceptance:* Emits lap/sector records and lap-start references; identifies numbering regressions.
  - *Status:* **VERIFIED**
- [x] **AGT-03 (P0):** A2 Asset Telemetry Archetype: Vehicle Telemetry Agent.
  - *Files:* `calibre_core/agents/telemetry.py`.
  - *Acceptance:* Emits windowed speed, integrated distance, and kinematic plausibility ($>2.0$g check).
  - *Status:* **VERIFIED**
- [x] **AGT-04 (P0):** A3 Spatial Archetype: Position & Geometry Agent.
  - *Files:* `calibre_core/agents/spatial.py`.
  - *Acceptance:* Detects gate crossings, track distance, and geometry reference facts with validity windows.
  - *Status:* **VERIFIED**
- [x] **AGT-05 (P0):** A4 Context Archetype: Session Context Agent.
  - *Files:* `calibre_core/agents/context.py`.
  - *Acceptance:* Emits session intervals, entry lists, flag lifecycles, and rule-regime facts.
  - *Status:* **VERIFIED**
- [x] **AGT-06 (P0):** A5 Supervisor Archetype: Feed Supervisor Agent.
  - *Files:* `calibre_core/agents/supervisor.py`.
  - *Acceptance:* Independent tap; emits monotonic clock ticks, `STALLED`/`RESUMED` guards, and health facts.
  - *Status:* **VERIFIED**

### Phase 7: Complete F1 Contract Catalogue (C01–C13)
- [x] **CNT-01 (P0):** Implement Contracts C01–C03 (Lap-time, Sector-sum, Flagship Pit-Speed with P3 margin).
  - *Files:* `calibre_core/contracts/catalogue.py`.
  - *Acceptance:* All constraints validated; C03 includes guard-banded margin check.
  - *Status:* **VERIFIED**
- [x] **CNT-02 (P0):** Implement Contracts C04–C06 (Kinematics, Telemetry Alignment, Position & Track).
  - *Files:* `calibre_core/contracts/catalogue.py`.
  - *Acceptance:* C04 catches 2.4g sudden deceleration; C06 checks yellow line crossing.
  - *Status:* **VERIFIED**
- [x] **CNT-03 (P0):** Implement Contracts C07–C08 (Session-Status Integrity, Incident Timing).
  - *Files:* `calibre_core/contracts/catalogue.py`.
  - *Acceptance:* C07 catches safety car unlapping interval violation.
  - *Status:* **VERIFIED**
- [x] **CNT-04 (P0):** Implement Contracts C09–C10 (Weather Reporting, Weather-Dependent Advisory).
  - *Files:* `calibre_core/contracts/catalogue.py`.
  - *Acceptance:* Demonstrates scope locality: weather outage affects only weather advisory.
  - *Status:* **VERIFIED**
- [x] **CNT-05 (P0):** Implement Contracts C11–C13 (Feed-Source Integrity, Monitor Health, Rule-Regime Consistency).
  - *Files:* `calibre_core/contracts/catalogue.py`.
  - *Acceptance:* C13 binds event-specific rule limits with effective dates.
  - *Status:* **VERIFIED**

### Phase 8: Historical Event Scenarios & Benchmark Suite
- [x] **SCN-01 (P0):** Abu Dhabi 2021 Historical Scenario (C07 Safety Car unlapping & restart).
  - *Files:* `calibre_core/tests/test_historical_scenarios.py`.
  - *Acceptance:* Assesses partial unlap instruction and restart timing; verifies common-cause exposure.
  - *Status:* **VERIFIED**
- [x] **SCN-02 (P0):** Monaco Geometry & Pit Speed Scenario (C03 Flagship & Pattern P3).
  - *Files:* `calibre_core/tests/test_historical_scenarios.py`.
  - *Acceptance:* Evaluates 2.9% survey distance error and guard-banded margin check.
  - *Status:* **VERIFIED**
- [x] **SCN-03 (P0):** Saudi Arabia 2021 Telemetry Deceleration Scenario (C04 Kinematics).
  - *Files:* `calibre_core/tests/test_historical_scenarios.py`.
  - *Acceptance:* Evaluates 69-bar brake telemetry and 2.4g deceleration on back straight.
  - *Status:* **VERIFIED**
- [x] **SCN-04 (P0):** Austria 2023 Track Limits Pipeline Overload Scenario (C06 & Amendments).
  - *Files:* `calibre_core/tests/test_historical_scenarios.py`.
  - *Acceptance:* Replays post-race review and ensures sealed final verdict is not mutated.
  - *Status:* **VERIFIED**

### Phase 9: Flink & Kafka Stream Pipeline Integration
- [x] **STR-01 (P0):** Canonical Admission Log Engine (`LOG v1.0`).
  - *Files:* `calibre_core/admission.py`.
  - *Acceptance:* Appends, deduplicates, and orders atoms, facts, and ticks with monotonic knowledge time.
  - *Status:* **VERIFIED**
- [x] **STR-02 (P0):** Streaming Evaluator Bridge.
  - *Files:* `calibre_core/admission.py`, `backend/pulse/integrity/bridge.py`.
  - *Acceptance:* Hosts SIA kernel as pure event-sourced processor over admission log.
  - *Status:* **VERIFIED**
- [x] **STR-03 (P1):** Population Calibration Monitor Feedback Loop.
  - *Files:* `sia_core_v3/sia_core/calibration.py`.
  - *Acceptance:* Aggregates across session decisions and emits calibration bias facts.
  - *Status:* **VERIFIED**
- [x] **STR-04 (P1):** Batch Replay & Chain Verifier.
  - *Files:* `calibre_core/tests/test_durable_platform.py`.
  - *Acceptance:* Batch verification of hash chain integrity over completed sessions.
  - *Status:* **VERIFIED**

### Phase 10: Replay, Bundles & Offline Verifier
- [x] **BUN-01 (P0):** Zero-dependency offline standalone bundle verifier CLI.
  - *Files:* `calibre_core/standalone_verifier.py`.
  - *Acceptance:* Verifies bundle offline on a clean machine using standard library only.
  - *Status:* **VERIFIED**
- [x] **BUN-02 (P0):** Historical Race Evidence Bundle Export.
  - *Files:* `calibre_core/archive.py`.
  - *Acceptance:* Exports complete self-verifying bundle with manifest and verifier.
  - *Status:* **VERIFIED**
- [x] **BUN-03 (P0):** Replay Equivalence & Monotonicity Verification.
  - *Files:* `calibre_core/tests/test_durable_platform.py`, `calibre_core/tests/test_historical_scenarios.py`.
  - *Acceptance:* Log replay reproduces identical hashes across runs.
  - *Status:* **VERIFIED**

### Phase 11: Documentation Cleanup, Decision Log & Handover
- [x] **DOC-01 (P0):** Update canonical documentation (`docs/ARCHITECTURE.md`, `README.md`).
  - *Files:* `docs/ARCHITECTURE.md`, `README.md`.
  - *Acceptance:* Accurately reflects 5 agent archetypes, specifications, and 10-race corpus.
  - *Status:* **VERIFIED**
- [x] **DOC-02 (P0):** Maintain auditable Engineering Decision Log.
  - *Files:* `docs/DECISION_LOG.md`.
  - *Acceptance:* Records architectural decisions, trade-offs, and alternatives considered (ADR-01..ADR-12).
  - *Status:* **VERIFIED**
- [x] **DOC-03 (P0):** Final validation report and system handover.
  - *Files:* Final report, test execution log.
  - *Acceptance:* All 395 tests pass, zero regressions, full documentation.
  - *Status:* **VERIFIED**
