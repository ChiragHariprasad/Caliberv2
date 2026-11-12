# CALIBRE / PULSE

> **Durable Evidence Verification Platform & Formula 1 Real-Time Streaming Intelligence**

CALIBRE is a high-assurance evidence verification platform. PULSE is its reference application: a deterministic Formula 1 race intelligence engine that turns asynchronous telemetry, timing transponders, track state, weather, and race-control feeds into evidence-linked tactical consequence assessments with deterministic integrity verification.

PULSE provides tactical decision support. It does not issue official sporting penalties, manufacture race control rulings, diagnose mechanical breakdowns, or use generic LLM commentary to decide outcomes.

---

## Key Capabilities

- **6 Specialist Intelligence Agents:** Decoupled single-concern agents for Race Control (`agent-01`), Vehicle Response & Dirty Air (`agent-02`), Track State (`agent-03`), Tyre Strategy (`agent-04`), Consequence Fusion (`agent-05`), and SIA Integrity Verification (`agent-06`).
- **Deterministic Consequence Fusion:** Multi-agent revision DAG supporting immediate provisional alerts (`v1`) and superseding confirmed assessments (`v2`) with out-of-order arrival resilience.
- **Dual-Transport Architecture:** Identical execution across a distributed **Apache Kafka / Flink** cluster and a zero-dependency high-speed **Local In-Memory Bus** (`SIMULATOR`).
- **Deterministic Historical Replay & Seeking:** Rebuilds active state instantaneously via canonical pipelines without publishing duplicate records to external brokers.
- **CALIBRE v4 Durable Evidence Core:** Domain-separated cryptographic hashes (`BLAKE3`/`SHA-256`), effective-dated reference registries, continuous uncertainty witnesses with guard bands, portable archive bundles (`.tar.zst`), and a standalone offline verifier CLI.
- **Real-Time Tactical Cockpit:** React 18 / Vite interface featuring live SVG track maps, multi-channel CAN-bus telemetry meters, race control notices, agent transparency metrics, and cryptographic evidence audit drawers.

---

## High-Level Architecture

```text
[Telemetry / Transponders / Race Control]
                   │
                   ▼
       [Stream Normalizer Gate]
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
[Apache Kafka / Flink]   [Local Memory Bus]
       │                       │
       └───────────┬───────────┘
                   ▼
     [6 Specialist Agents (01-06)]
                   │
                   ▼
     [Agent 05: Consequence Fusion] ──► [v1 Provisional -> v2 Confirmed DAG]
                   │
                   ▼
          [Active StateStore] ─────────► [CALIBRE v4 Offline Verifier]
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
[FastAPI REST / SSE API]   [React 18 Cockpit UI]
```

---

## Prerequisites

- **Python:** 3.11, 3.12, or 3.13 (64-bit)
- **Node.js:** 18.x or 20.x LTS with npm
- **OS:** Windows 10/11, Linux, or macOS
- **Optional:** Docker Desktop 4.28+ (only required for clustered Kafka mode)

---

## Quick Start (Local Simulator Mode)

The recommended local execution mode requires zero external broker or database dependencies.

### 1. Start Backend API Server
```powershell
# Set Python path to include all core modules
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
$env:PULSE_TRANSPORT_MODE="SIMULATOR"

# Launch Uvicorn ASGI server
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

### 3. Distributed Kafka Mode (Optional)
To run with an external Kafka cluster:
```powershell
docker compose -f docker-compose.kafka.yml up -d
$env:PULSE_TRANSPORT_MODE="KAFKA"
$env:KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
python -m uvicorn pulse.main:app --host 127.0.0.1 --port 8000
```

---

## Test Execution & Validation

### Automated Unit, Property & Integration Tests
```powershell
pytest calibre_core/tests sia_core_v3/tests backend/tests
```
*Current test suite status:* **380 passed**, 17 skipped (Docker integration tests skipped when container engine is offline), 0 failed.

### Browser System Validation
Execute the automated 12-journey Playwright Chromium test suite:
```powershell
python scripts/run_browser_system_validation.py
```
Validation captures are written to `reports/browser-validation/screenshots/`.

### Offline Evidence Bundle Verification
```powershell
python -m calibre_core.verifier.cli verify --bundle ./captures/monaco_audit_bundle.tar.zst --strict
```

---

## Canonical Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):** Detailed technical architecture, stream topologies, agent specifications, epistemic contracts, and CALIBRE v4 durable archive specification.
- **[docs/HISTORY.md](docs/HISTORY.md):** Chronological project evolution from `E:\CALIBER` (SIA v2.2) to PULSE and CALIBRE v4, including 20 Architecture Decision Records (ADRs).
