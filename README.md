# CALIBRE / PULSE

> **Independent Evidence-Integrity Platform for Timing and Telemetry Decisions, built on SIA (Scoped Integrity Algebra)**

CALIBRE is an independent, deterministic evidence-integrity platform. It continuously evaluates the adequacy, provenance, physical plausibility, and independence of measurements and references before decisions are made. PULSE is its real-time tactical streaming reference application for Formula 1.

CALIBRE asks one question for every decision:
> **Is the evidence available right now adequate for this particular decision, and how do we know?**

CALIBRE never decides sporting penalties and never computes "the right value". It decides whether evidence **may legitimately be used** for an evaluation, leaving sporting authority to human officials.

---

## Key Capabilities

- **SIA Core v3 (Scoped Integrity Algebra):** Pure standard-library deterministic reasoning kernel with total order `DEGRADED < UNKNOWN < SUSPECT < HEALTHY`, 4-state validity timelines, named witnesses, and hash-chained bitemporal records.
- **5 Specialist Agent Archetypes (A1–A5):** Decoupled evidence producers enforcing rules AR-1 through AR-10:
  - **A1 Measurement (Timing Agent):** Official transponder loops, speed traps, sector times, numbering regression detection.
  - **A2 Asset Telemetry (Vehicle Telemetry Agent):** High-frequency ECU speed, throttle/brake pedal exclusivity, kinematic anomaly detection (>2.0g deceleration check).
  - **A3 Spatial & Geometry (Spatial Agent):** Gate crossing interpolation, path length integration, effective-dated circuit geometry references.
  - **A4 Context (Session Context Agent):** Race control flag lifecycles (Green, Yellow, VSC, SC, Red), driver retirement tracking, rule limits.
  - **A5 Feed Supervisor (Independent Path):** Monotonic clock ticks, `STALLED` and `RESUMED` guards, stream cadence heartbeat analysis.
- **Complete F1 Contract Catalogue (C01–C13):** Formal contracts covering lap times, sector sums, pit-lane speed (flagship with Pattern P3 margin check), vehicle kinematics, position/track boundaries, session status, and rule regimes.
- **10-Race Historical F1 Controversy Corpus (2021+):** Comprehensive research and automated acquisition across the 10 most controversial Grands Prix from 2021 onwards (Abu Dhabi 2021 mandatory, Monaco, Saudi Arabia, Belgium, Austria, Great Britain, Japan, Australia, COTA, Las Vegas) with automated Jolpica-F1 open Ergast fallback.
- **Formal Specification Suite:** JSON schemas for Evidence Events (`EE v1.0`), Decision Contracts (`DEC v1.0`), Integrity Assessments (`IA v1.0`), Admission Logs (`LOG v1.0`), Portable Bundles (`BUN v1.0`), Domain Packs (`PACK v1.0`), and language-neutral Conformance Vectors.
- **Content-Addressed Admission Log Engine:** Monotonic sequencing, hash chaining, and deterministic replay bridge to SIA Core.
- **Four Data Governance Regimes:** Radical provenance honesty distinguishing `PUBLIC` (source depth 1, `COMMON_CAUSE_EXPOSURE`), `LICENSED`, `INSTITUTIONAL`, and `LAB` (synthetic twins).
- **Portable Evidence Bundles & Standalone Verifier:** Self-verifying offline archive bundles verifiable on a clean machine using Python standard library only.

---

## High-Level Architecture

```text
 EXTERNAL WORLD (untrusted): FOM timing, telemetry, race control, survey registries
        │
 SOURCE PACKS: adapters + raw recorder (sanitized RFC 8785 canonical JSON, sha256)
        │
 KAFKA RAW / LOCAL MEMORY BUS: calibre.<pack>.raw.<provider>.<stream>
        │
 AGENT ARCHETYPES (evidence producers only; never grade, never declare health)
   A1 Measurement   A2 Telemetry   A3 Spatial   A4 Context  ──► calibre.<pack>.evidence.*
   A5 Supervisor (independent failure domain)               ──► calibre.<pack>.guard.*
        │
 ADMISSION LOG ENGINE (J1 Sequencer): monotonic seq, knowledge time ──► core.admission_log
        │
 SIA KERNEL EVALUATOR (J2 Evaluator): bitemporal index, voiding, P3 margin ──► core.verdicts
        │
 SERVING & ARCHIVE: FastAPI REST / SSE, React 18 UI, portable bundles, standalone verifier
```

---

## Test Execution & Verification

### Automated Test Suite
Run the entire comprehensive test suite across `calibre_core`, `sia_core_v3`, and `backend`:
```powershell
pytest calibre_core/tests sia_core_v3/tests backend/tests
```
*Current test suite status:* **395 passed**, 17 skipped (Docker integration tests skipped when container engine is offline), 0 failed in ~90s.

### Run Specialized Test Suites
```powershell
# 1. Agent archetypes & Contract catalogue conformance (AR-1..AR-10, C01..C13)
pytest calibre_core/tests/test_agents_and_contracts.py -v

# 2. Historical controversy scenarios (Abu Dhabi, Monaco, Saudi Arabia, Austria, Belgium)
pytest calibre_core/tests/test_historical_scenarios.py -v

# 3. SIA reasoning kernel property and mutation tests (259 tests, 0 dependencies)
pytest sia_core_v3/tests -v

# 4. Durable bundles and standalone offline verifier
pytest calibre_core/tests/test_durable_platform.py -v
```

### Acquire Historical Race Corpus
Acquire or re-index the 10-race controversy corpus (with automatic Jolpica-F1 fallback):
```powershell
python scripts/acquire_f1_corpus.py
```
Master corpus manifest is written to `data/f1_corpus/corpus_manifest.json`.

---

## Quick Start (Local Simulator Mode)

The recommended local execution mode requires zero external broker or database dependencies.

### 1. Start Backend API Server
```powershell
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
$env:PULSE_TRANSPORT_MODE="SIMULATOR"

python -m uvicorn pulse.main:app --host 127.0.0.1 --port 8000 --log-level info
```
- API Root & Health: `http://127.0.0.1:8000/api/health`
- OpenAPI Documentation: `http://127.0.0.1:8000/docs`

### 2. Start Frontend Cockpit
In a separate terminal:
```powershell
cd E:\Caliberv2\frontend
npm install
npm run build
npm run preview
```
- Tactical Cockpit UI: `http://localhost:5173/`

---

## Canonical Documentation Index

- **[docs/AUDIT.md](docs/AUDIT.md):** Complete line-by-line implementation audit of the repository against the CALIBRE idea documentation.
- **[docs/ROADMAP.md](docs/ROADMAP.md):** 15-area dependency-aware engineering roadmap with Mermaid dependency graphs.
- **[docs/IMPLEMENTATION_CHECKLIST.md](docs/IMPLEMENTATION_CHECKLIST.md):** 49 master implementation tasks with status tracking and acceptance criteria.
- **[docs/F1_CONTROVERSY_CORPUS.md](docs/F1_CONTROVERSY_CORPUS.md):** In-depth research of the 10 most controversial F1 races (2021+) citing official FIA Stewards decisions and sporting regulations.
- **[docs/DATA_SOURCING_ASSESSMENT.md](docs/DATA_SOURCING_ASSESSMENT.md):** Data sourcing, legal regimes (PUBLIC, LICENSED, INSTITUTIONAL, LAB), and channel coverage matrix.
- **[docs/DECISION_LOG.md](docs/DECISION_LOG.md):** Architecture Decision Records (ADR-01 through ADR-12) documenting trade-offs and rationale.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):** Technical architecture, stream topologies, agent specifications, and epistemic contracts.
