# CALIBRE / PULSE

> **Evidence-integrity and tactical-streaming prototype for Formula 1, built around SIA (Scoped Integrity Algebra)**

CALIBRE contains a deterministic SIA kernel, reusable evidence and archival prototypes, and PULSE, a Formula 1 tactical-streaming reference application. The kernel is designed to evaluate evidence adequacy, provenance and consistency; the end-to-end application does not yet provide durable, production-grade integrity guarantees. See [docs/README.md](docs/README.md) for the static audit and proposed remediation.

CALIBRE asks one question for every decision:
> **Is the evidence available right now adequate for this particular decision, and how do we know?**

CALIBRE never decides sporting penalties and never computes "the right value". It decides whether evidence **may legitimately be used** for an evaluation, leaving sporting authority to human officials.

---

## Implemented components (not a production claim)

- **SIA Core v3 (Scoped Integrity Algebra):** Standard-library deterministic evaluator with total order `DEGRADED < UNKNOWN < SUSPECT < HEALTHY`, validity timelines, witnesses and in-memory hash-chained revisions.
- **5 Specialist Agent Archetype prototypes (A1–A5):** Evidence producer modules under `calibre_core/agents/`; these are separate from, and currently not wired into, the PULSE runtime:
  - **A1 Measurement (Timing Agent):** Official transponder loops, speed traps, sector times, numbering regression detection.
  - **A2 Asset Telemetry (Vehicle Telemetry Agent):** High-frequency ECU speed, throttle/brake pedal exclusivity, kinematic anomaly detection (>2.0g deceleration check).
  - **A3 Spatial & Geometry (Spatial Agent):** Gate crossing interpolation, path length integration, effective-dated circuit geometry references.
  - **A4 Context (Session Context Agent):** Race control flag lifecycles (Green, Yellow, VSC, SC, Red), driver retirement tracking, rule limits.
  - **A5 Feed Supervisor (Independent Path):** Monotonic clock ticks, `STALLED` and `RESUMED` guards, stream cadence heartbeat analysis.
- **Two contract catalogues:** a C01–C13 prototype catalogue in `calibre_core/contracts/` and five active PULSE contracts. They require consolidation before operational use.
- **Corpus, specifications and archival utilities:** research/capture files, JSON schema artifacts, a standalone admission-log utility, data-regime types and archive/verifier prototypes. Their end-to-end integration and source coverage are unverified.

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

## Test execution and verification

### Automated Test Suite
Run the entire comprehensive test suite across `calibre_core`, `sia_core_v3`, and `backend`:
```powershell
pytest calibre_core/tests sia_core_v3/tests backend/tests
```
The audit intentionally did not execute these commands. Do not treat historical test counts in repository documents as current verification results.

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

## Documentation

See [docs/README.md](docs/README.md) for the current documentation hierarchy.

- [UI Visual Reference & Screenshots Catalogue](screenshots/README.md) (`docs/UI_SCREENSHOTS.md`)
- [Current-system architecture](docs/ARCHITECTURE.md)
- [Static engineering audit and findings register](docs/AUDIT.md)
- [Proposed remediation roadmap](docs/ROADMAP.md)

Historical reports, corpus research and decision records remain in `docs/` for traceability. They are not evidence that a feature is currently implemented or runtime-verified.
