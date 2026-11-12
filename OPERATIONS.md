# CALIBRE / PULSE: Operations Runbook & Deployment Guide

This document is the authoritative operations guide for deploying, configuring, monitoring, and troubleshooting the CALIBRE / PULSE platform.

---

## 1. System Requirements & Environment Configuration

### Software Requirements
- **Operating System:** Windows 10/11, macOS 13+, or Linux (Ubuntu 22.04 LTS recommended)
- **Python Runtime:** Python 3.11, 3.12, or 3.13 (64-bit)
- **Node.js Runtime:** Node.js 18.x or 20.x LTS with npm 9+
- **Container Engine (Optional for Clustered Mode):** Docker Desktop 4.28+ with Compose v2
- **Hardware Minimums:** 4 CPU cores, 8 GB RAM, 20 GB free disk space

### Environment Variables
Configure the system via `.env` or system environment variables:

| Variable | Default Value | Allowed Values | Purpose |
| :--- | :--- | :--- | :--- |
| `PULSE_TRANSPORT_MODE` | `SIMULATOR` | `SIMULATOR`, `KAFKA` | Switches between deterministic local in-memory bus and distributed Apache Kafka broker. |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Host:Port comma list | Kafka broker bootstrap string (used when `PULSE_TRANSPORT_MODE=KAFKA`). |
| `FLINK_REST_URL` | `http://localhost:8081`| HTTP URL | Apache Flink JobManager REST endpoint for distributed normalization jobs. |
| `PULSE_DEFAULT_SESSION` | `f1-2026-monaco-sim` | Registered session ID| Default session to mount on initial startup. |
| `PULSE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Application logging verbosity. |

---

## 2. Operating Modes & Startup Procedures

### Mode A: Standalone Deterministic Simulator Mode (Recommended for Development & Demos)
In this mode, CALIBRE executes entirely in-memory with zero external broker dependencies, utilizing the high-speed `PulseEventBus` and bundled historical telemetry captures.

#### Step 1: Start Backend ASGI Server
```powershell
# Windows PowerShell
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
$env:PULSE_TRANSPORT_MODE="SIMULATOR"
python -m uvicorn pulse.main:app --host 127.0.0.1 --port 8000 --log-level info
```
*Expected log output:*
```text
INFO:     Started server process [PID]
INFO:     Initializing PULSE Race Intelligence Engine...
INFO:     Operating in SIMULATOR transport mode. Local deterministic bus active.
INFO:     pulse.integrity.agent: Registered integrity contracts (lap_time, pit_speed, sector_time...)
INFO:     pulse.replay.controller: ReplayController loaded 72926 envelopes for session [f1-2026-monaco-sim]
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

#### Step 2: Build & Start Frontend Cockpit
```powershell
cd E:\Caliberv2\frontend
npm install
npm run build
npm run preview
```
*Access URLs:*
- **Tactical Cockpit UI:** `http://localhost:5173/`
- **Backend Health Check:** `http://127.0.0.1:8000/api/health`
- **Interactive OpenAPI Docs:** `http://127.0.0.1:8000/docs`

---

### Mode B: Clustered Distributed Mode (Apache Kafka & Apache Flink)
In this mode, CALIBRE deploys a Kafka KRaft broker, schema registry, and Flink streaming job manager for distributed streaming.

```powershell
# 1. Start Docker Compose infrastructure
docker compose -f docker-compose.kafka.yml up -d

# 2. Verify containers are healthy
docker compose -f docker-compose.kafka.yml ps

# 3. Launch backend pointing to Kafka broker
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
$env:PULSE_TRANSPORT_MODE="KAFKA"
$env:KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
$env:FLINK_REST_URL="http://localhost:8081"
python -m uvicorn pulse.main:app --host 127.0.0.1 --port 8000
```

---

## 3. Comprehensive REST & SSE API Reference

All REST endpoints are prefixed with `/api`.

### Active Session & Telemetry Endpoints
- **`GET /api/health`**: Returns service health status, active transport mode, and version.
- **`GET /api/snapshot`**: Returns the complete composite state snapshot:
  - Active session metadata, circuit ID, current lap, elapsed time.
  - 20-driver leaderboard with positions, gaps, tyre compound/age, and status.
  - Active tactical consequence assessments (fused by Agent 05).
  - Recent race events timeline.
- **`GET /api/sessions`**: Enumerates all available sessions in the session registry (`f1-2026-monaco-sim`, `f1-2023-silverstone-race`, `f1-2026-suzuka-race`).
- **`POST /api/sessions/select`**: Dynamically switches the active session:
  - Payload: `{"sessionId": "f1-2023-silverstone-race"}`
- **`GET /api/circuit/{circuit_id}`**: Retrieves SVG track coordinates, sector demarcations, and speed trap locations.
- **`GET /api/telemetry/{driver_number}`**: Retrieves high-frequency CAN-bus channels (speed, throttle, brake, RPM, DRS) and historical time-series curves for a specific car.
- **`GET /api/stream`**: Server-Sent Events (SSE) streaming endpoint delivering real-time state snapshots, telemetry ticks, and agent findings to connected browser clients.

### Replay & Seeking Control Endpoints
- **`GET /api/replay/status`**: Returns current replay cursor index, total events, speed, elapsed time, and status (`READY`, `RUNNING`, `PAUSED`, `RESETTING`).
- **`POST /api/replay/start`**: Begins or resumes replay playback.
- **`POST /api/replay/pause`**: Freezes replay playback at the current event cursor.
- **`POST /api/replay/speed`**: Sets playback multiplier:
  - Payload: `{"speed": 5.0}` (Allowed: `0.25`, `0.5`, `1.0`, `2.0`, `5.0`).
- **`POST /api/replay/reset`**: Resets cursor to event 0 under a fresh run ID, clearing state store.
- **`POST /api/replay/seek`**: Fast-forwards or rewinds state to an exact target index, lap, or elapsed time:
  - Payload: `{"targetIndex": 25000}` or `{"targetLap": 15}`.

### Agent Transparency & Audit Endpoints
- **`GET /api/agents`**: Lists all 6 registered specialist agents and their operational status.
- **`GET /api/agents/metrics`**: Returns run-scoped transparency metrics for all agents (inputs received, findings emitted, no-finding decisions, latency distributions).
- **`GET /api/findings`**: Returns the complete chronological log of agent findings.
- **`GET /api/findings/{finding_id}`**: Retrieves a specific finding with its complete upstream evidence reference chain.
- **`GET /api/assessments`**: Returns all fused tactical consequence assessments.
- **`GET /api/pipeline/status`**: Returns health and latency metrics across all 6 pipeline nodes.
- **`GET /api/pipeline/lineage`**: Returns the complete lineage graph from ingestion to state projection.

---

## 4. Verification & Testing Runbook

### Full Pytest Suite Execution
Execute the full test suite across the platform's 3 major test roots:
```powershell
pytest calibre_core/tests sia_core_v3/tests backend/tests -v
```
*Expected Result:*
- **380 tests passed**
- **17 skipped** (Docker integration tests skipped when container engine is offline)
- **0 failures**

### Automated Browser Visual Validation Suite
CALIBRE includes an automated Playwright Chromium test harness validating end-to-end browser workflows:
```powershell
# Ensure backend and frontend preview servers are running, then execute:
python scripts/run_browser_system_validation.py
```
This automated suite executes 12 continuous browser journeys:
1. Navigation and Cockpit overview inspection.
2. Replay start and live streaming verification.
3. Speed adjustment to 5.0x and pause verification.
4. Timeline slider scrubbing and seek reconstruction.
5. Race Control & Stewarding tab inspection.
6. Agent Operations tab and trace modal inspection.
7. Pipeline Lab tab and lineage inspection.
8. Driver Telemetry Modal multi-channel CAN-bus inspection.
9. Evidence Audit Drawer tactical rationale and hash verification.
10. Replay Reset to cursor 0.
11. Dynamic Session Switching to Silverstone Grand Prix.
12. Restoring session to Monaco Grand Prix simulation.

Screenshots are automatically captured and saved to [`docs/screenshots/`](file:///E:/Caliberv2/docs/screenshots/).

---

## 5. Troubleshooting & Operational Incidents

### Incident 1: Docker Service Unavailable on Windows
- **Symptom:** `error during connect: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.`
- **Root Cause:** Docker Desktop service is stopped or the shell lacks administrative privileges to access the Windows named pipe.
- **Remediation:**
  - If external Kafka is not strictly required, run the platform in **`PULSE_TRANSPORT_MODE=SIMULATOR`**. The local deterministic mode provides full agent fusion, replay, telemetry, and UI functionality without Docker.
  - To enable Docker, launch Docker Desktop as Administrator and verify `docker info` succeeds before starting the clustered mode.

### Incident 2: Seeking or Replay Reset Fails to Emit Events
- **Symptom:** After scrubbing the timeline slider or resetting playback, no new findings or assessments appear.
- **Root Cause:** Stream normalizer deduplication cache retained old event IDs.
- **Remediation:** Verified fixed via ADR-018. `ReplayController.seek()`, `reset()`, and `switch_session()` trigger the registered reset hook `StreamNormalizer.reset()`, clearing `_seen_events` whenever cursor lineage changes.

### Incident 3: Port Binding Conflicts
- **Symptom:** `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): only one usage of each socket address is normally permitted.`
- **Remediation:**
  - Find and terminate orphaned Python/Uvicorn processes:
    ```powershell
    Get-Process python | Where-Object { $_.MainWindowTitle -eq "" } | Stop-Process -Force
    ```
  - For frontend port 5173 conflicts:
    ```powershell
    Get-Process node | Stop-Process -Force
    ```

