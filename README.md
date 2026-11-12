# CALIBRE / PULSE: Durable Evidence Verification Platform & Formula 1 Real-Time Intelligence

CALIBRE is a high-assurance, durable evidence verification platform engineered for mission-critical, high-throughput streaming environments. PULSE is its reference implementation: a deterministic Formula 1 race intelligence engine that consumes asynchronous telemetry, timing transponders, track state, weather, and race-control feeds, turning them into evidence-linked tactical consequence assessments with deterministic integrity verification.

---

## System Overview & Architecture Pillars

```
+---------------------------------------------------------------------------------------------------+
|                                  CALIBRE / PULSE STREAM TOPOLOGY                                  |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [Ingestion / Capture Feeds] (FastF1 / Official FIA Timing / Real-time CAN-bus Transponders)      |
|       |                                                                                           |
|       v                                                                                           |
|  [Stream Normalizer / Deduplication] <---> [Dual-Transport: Local Memory Bus / Apache Kafka]     |
|       |                                                                                           |
|       +-------------------+-------------------+-------------------+-------------------+       |
|       |                   |                   |                   |                   |       |
|       v                   v                   v                   v                   v       |
|  [Agent 01: Event]   [Agent 02: Vehicle]  [Agent 03: Track]   [Agent 04: Tyre]    [Agent 06: SIA] |
|   Race Control &       Dirty Air, Pace     Sectors & Surface   Stints & Window     Integrity &    |
|   Neutralisations      Degradation Delta   Grip / Weather      Undercut Model      Bitemporal Fact|
|       \                   |                   /                   |                   /       |
|        \                  |                  /                    |                  /        |
|         +-----------------+-----------------+---------------------+-----------------+         |
|                                           |                                                       |
|                                           v                                                       |
|                        [Agent 05: Consequence Fusion Engine]                                      |
|                             * Epistemic Classification (Observed vs Inferred vs Derived)          |
|                             * Consequence Revision Chains (v1 Provisional -> v2 Confirmed DAG)    |
|                             * Out-of-Order Multi-Agent Reconciliation                             |
|                                           |                                                       |
|                                           v                                                       |
|                                 [Active State Store]                                              |
|                                           |                                                       |
|                     +---------------------+---------------------+                                 |
|                     |                                           |                                 |
|                     v                                           v                                 |
|          [FastAPI Streaming Engine]                 [CALIBRE v4 Durable Core]                     |
|          * Server-Sent Events (SSE)                 * Domain-Tagged Hashes (BLAKE3/SHA-256)       |
|          * REST State & Control Endpoints           * Effective-Dated Reference Registry          |
|          * Seeking & Scrubbing Controller           * Continuous Uncertainty Witness              |
|                     |                               * Offline Standalone Verifier                 |
|                     v                                                                             |
|          [React 18 Cockpit UI]                                                                    |
|          * SVG Circuit Map & Live Delta                                                           |
|          * 6-Agent Transparency Dashboard                                                         |
|          * Real-Time Telemetry Modal & Canvases                                                   |
|          * Evidence Audit Drawer & Hash Lineage                                                   |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

CALIBRE operates on three foundational principles:
1. **Decision Support, Not Autocracy:** PULSE does not issue sporting penalties, manufacture race control rulings, diagnose hypothetical mechanical breakdowns, or use hallucinating LLMs to dictate strategy. It produces bounded, evidence-linked tactical intelligence with explicit uncertainty declarations.
2. **Deterministic Dual-Transport:** The platform executes identically over **Apache Kafka & Apache Flink** in clustered environments and a **Zero-Dependency High-Speed Local Bus** for edge deployment, testing, and deterministic replay.
3. **Multi-Agent Epistemic Rigour:** Raw events are classified strictly into canonical streams. Findings are categorized as `OBSERVED`, `INFERRED`, or `DERIVED`. Assessments follow an auditable revision Directed Acyclic Graph (DAG) where provisional early findings (v1) are deterministically superseded by confirmed tactical forecasts (v2).

---

## Project Structure & Authoritative Documentation

| Document | Purpose |
| :--- | :--- |
| **[README.md](file:///E:/Caliberv2/README.md)** | This document. System overview, quick start, test execution, and architecture summary. |
| **[ARCHITECTURE.md](file:///E:/Caliberv2/ARCHITECTURE.md)** | Comprehensive technical architecture: stream topologies, agent specifications, epistemic contracts, bitemporal ledger, and CALIBRE v4 durable archive specification. |
| **[OPERATIONS.md](file:///E:/Caliberv2/OPERATIONS.md)** | Operational runbook: environment variables, dual-transport modes, port mappings, API endpoints, and verification procedures. |
| **[PROJECT_HISTORY_AND_ENGINEERING_DECISIONS.md](file:///E:/Caliberv2/PROJECT_HISTORY_AND_ENGINEERING_DECISIONS.md)** | Deep architectural archaeology and engineering rationale tracing the project evolution from `E:\CALIBER` (SIA v2.2) to PULSE and CALIBRE v4, including 20 Architecture Decision Records (ADRs). |

```text
E:\Caliberv2
├── backend/                 # FastAPI REST/SSE server, replay controller, 6 specialist agents, StateStore
│   ├── pulse/
│   │   ├── agents/          # Specialist intelligence agents (01-05)
│   │   ├── api/             # FastAPI REST endpoints and SSE streams
│   │   ├── integrity/       # Agent 06: SIA integrity verification bridge
│   │   ├── replay/          # Deterministic replay and seek-reconstruction engine
│   │   ├── state/           # Bitemporal thread-safe in-memory state store
│   │   └── stream/          # Stream normalizer and deduplication engine
│   └── tests/               # Backend unit, integration, and reliability test suites
├── frontend/                # React 18 + Vite tactical race cockpit dashboard
│   ├── src/
│   │   ├── components/      # Cockpit, Race Control, Agent Ops, Pipeline Lab, Telemetry Modal, Evidence Drawer
│   │   ├── services/        # EventSource SSE and REST client API
│   │   └── types/           # Canonical TypeScript interfaces matching backend contracts
├── calibre_core/            # CALIBRE v4 durable platform primitives
│   ├── archive/             # Self-contained portable archive bundles (.tar.zst)
│   ├── hashing/             # Domain-separated BLAKE3 / SHA-256 tagged hash engine
│   ├── references/          # Effective-dated immutable reference registry
│   ├── timescale/           # UTC, TAI, GPS explicit time scale declarations
│   ├── verifier/            # Standalone offline zero-dependency verifier CLI
│   └── witness/             # Continuous uncertainty witness with guard bands
├── sia_core_v3/             # Deterministic evidence integrity evaluation engine
├── captures/                # High-fidelity historical telemetry captures (Monaco, Silverstone, Suzuka)
├── docs/                    # Architectural specifications and visual test screenshots
│   ├── screenshots/         # Automated browser validation screenshots (12 user journeys)
│   └── archive/             # Archived intermediate reports and telemetry benchmarks
├── scripts/                 # Operational automation and Playwright browser validation scripts
└── pytest.ini               # Pytest configuration and test runner definitions
```

---

## Quick Start & Local Execution

### 1. Prerequisites
- **Python 3.11+** (Python 3.13 recommended)
- **Node.js 18+** & npm
- Modern Chromium-based browser

### 2. Backend Startup (Deterministic Local Mode)
To launch the backend in high-speed, zero-dependency simulator mode:
```powershell
# Set Python path to include backend, calibre_core, and sia_core_v3
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
$env:PULSE_TRANSPORT_MODE="SIMULATOR"

# Start the Uvicorn ASGI server on port 8000
python -m uvicorn pulse.main:app --host 127.0.0.1 --port 8000 --log-level info
```
The backend initializes the in-memory bus, registers all 6 specialist agents, mounts the Monaco Grand Prix simulation capture (72,926 events), and serves the API at `http://127.0.0.1:8000`.

### 3. Frontend Tactical Cockpit Startup
In a separate terminal:
```powershell
cd E:\Caliberv2\frontend

# Install dependencies (first time only)
npm install

# Build production bundle
npm run build

# Serve high-performance preview server
npm run preview
```
Open **`http://localhost:5173/`** in your browser.

---

## Automated Test Verification

The platform features an extensive test suite verifying mathematical purity, stream ordering, agent convergence, fault injection, and API contracts.

```powershell
# Run the complete test suite across all modules
pytest calibre_core/tests sia_core_v3/tests backend/tests
```

### Test Suite Execution Status
- **Total Tests Collected:** 397
- **Passed:** 380 (100% of runnable tests)
- **Skipped:** 17 (Distributed Kafka/Docker integration tests gracefully skipped when Docker broker is offline)
- **Failed:** 0
- **Execution Time:** ~62 seconds

---

## Browser Visual Validation & User Journeys

The platform includes a fully automated Playwright browser test suite ([`scripts/run_browser_system_validation.py`](file:///E:/Caliberv2/scripts/run_browser_system_validation.py)) that validates all user journeys against the running application in Chromium (1600x1000 viewport), logging 0 console errors and 0 page errors.

Visual evidence captures are stored in [`docs/screenshots/`](file:///E:/Caliberv2/docs/screenshots/):

| Journey | Target View | Verification Screenshot | Validation Description |
| :--- | :--- | :--- | :--- |
| **01** | Cockpit Overview | [`01_cockpit_overview.png`](file:///E:/Caliberv2/docs/screenshots/01_cockpit_overview.png) | 20 driver leaderboard, track layout SVG, session header, and timing ticker. |
| **02** | Replay Playback | [`02_replay_running.png`](file:///E:/Caliberv2/docs/screenshots/02_replay_running.png) | Real-time event streaming, advancing elapsed time, and car positions. |
| **03** | Speed & Pause | [`03_replay_paused.png`](file:///E:/Caliberv2/docs/screenshots/03_replay_paused.png) | 5.0x playback speed adjustment and pause freeze-frame verification. |
| **04** | Timeline Seeking | [`04_replay_seek.png`](file:///E:/Caliberv2/docs/screenshots/04_replay_seek.png) | Scrubbing timeline slider forward, instantaneous state reconstruction without broker duplicate emission. |
| **05** | Race Control View | [`06_race_control_view.png`](file:///E:/Caliberv2/docs/screenshots/06_race_control_view.png) | Official FIA race control flags, incident notices, and safety car neutralisations. |
| **06** | Agent Operations | [`07_agent_operations_view.png`](file:///E:/Caliberv2/docs/screenshots/07_agent_operations_view.png) | 6 specialist agent cards active (`6/6 AGENTS ACTIVE`), latency metrics, and execution trace inspection modal. |
| **07** | Pipeline Lab | [`08_pipeline_lab_view.png`](file:///E:/Caliberv2/docs/screenshots/08_pipeline_lab_view.png) | 6 streaming pipeline nodes, verification run history, and cryptographic lineage inspection. |
| **08** | Telemetry Modal | [`09_driver_telemetry_modal.png`](file:///E:/Caliberv2/docs/screenshots/09_driver_telemetry_modal.png) | Multi-channel CAN-bus inspection for Car #16 (Leclerc): Speed, Throttle, Brake, Gear/RPM, DRS, Tyre, and SVG time series. |
| **09** | Evidence Drawer | [`10_evidence_drawer.png`](file:///E:/Caliberv2/docs/screenshots/10_evidence_drawer.png) | Audit rationale drawer: tactical narrative, forecast horizon, calibration warning, supporting finding refs, and SHA-256 evidence hashes. |
| **10** | Replay Reset | [`05_replay_reset.png`](file:///E:/Caliberv2/docs/screenshots/05_replay_reset.png) | Replay reset to cursor 0 under fresh run ID, state store re-indexed to `READY`. |
| **11** | Session Switch 1 | [`11_silverstone_session.png`](file:///E:/Caliberv2/docs/screenshots/11_silverstone_session.png) | Dynamic session switch to British Grand Prix (Silverstone), updating circuit geometry and drivers. |
| **12** | Session Switch 2 | [`12_monaco_restored.png`](file:///E:/Caliberv2/docs/screenshots/12_monaco_restored.png) | Dynamic session switch restored to Monaco Grand Prix simulation with full telemetry envelopes. |

---

## Specialist Agents

CALIBRE / PULSE avoids monolithic prediction models in favour of 6 isolated, deterministic specialist agents:

1. **`agent-01-event-control` (Event Context & Neutralisation Agent):** Tracks track-wide flag lifecycles (VSC, Safety Car, Red Flag, Green Flag) and calculates spatial driver exposure.
2. **`agent-02-vehicle-response` (Vehicle Response & Dirty Air Agent):** Monitors telemetry intervals and micro-sector lap deltas; identifies dirty air aerodynamic losses vs thermal tyre degradation.
3. **`agent-03-track-state` (Track Sector & Environmental Agent):** Evaluates track condition transitions (Dry -> Damp -> Wet) and localized micro-sector grip indices.
4. **`agent-04-tyre-strategy` (Tyre Strategy & Pit Window Agent):** Calculates pit loss Deltas, undercut/overcut windows, and safety car delta advantages.
5. **`agent-05-fusion` (Consequence Fusion Engine):** Fuses multi-agent findings into coherent driver impact assessments; resolves out-of-order findings; emits v1 provisional and v2 confirmed revision chains.
6. **`agent-06-integrity` (SIA Evidence Verification Agent):** Runs embedded SIA v3 verification rules over incoming telemetry and timing facts, checking mathematical bitemporal consistency and cryptographic integrity.

---

## Standalone Verifier CLI (CALIBRE v4)

CALIBRE v4 includes a zero-dependency offline verifier capable of validating portable archive bundles (`.tar.zst`) without access to live Kafka brokers, databases, or runtime dependencies:

```powershell
python -m calibre_core.verifier.cli verify --bundle ./captures/monaco_audit_bundle.tar.zst --strict
```
The verifier performs:
- Cryptographic signature check against the effective-dated Reference Registry.
- Merkle leaf hash recomputation using domain-separated tagged hashes.
- Mathematical verification of continuous uncertainty witness boundaries.
- Bit-identical reproduction of state projections.

---

## License & Operational Scope
This software is designed strictly for research, decision support, and tactical demonstration. It does not replace official FIA timing transponders, steward adjudications, or manufacturer telemetry telemetry loggers.
