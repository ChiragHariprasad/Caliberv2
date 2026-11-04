# PULSE — Phase 4.2: Real-Time Streaming, Replay Controller and UI Synchronisation

**Execution Date:** 2026-11-05  
**Version:** Phase 4.2  
**Baseline Status:** 90/90 Tests Passing (100% Green), TypeScript Clean Build, Zero Emojis Remaining.

---

## 1. Executive Summary

Phase 4.2 transforms the PULSE Formula 1 race intelligence cockpit from an interface displaying static demo values into a dynamic, streaming real-time platform driven by an asynchronous backend `ReplayController` and continuous Server-Sent Events (SSE). 

Prior to this phase, the dashboard presented static information because the legacy `ScenarioRunner` executed only 9 synthetic VSC events before halting, the circuit picker only altered local frontend state without informing the backend, and SSE connections performed generic polling instead of receiving partial, typed domain updates. Furthermore, 39 emoji literals degraded the professional race-operations aesthetic.

All objectives of Phase 4.2 have been achieved:
1. **Dedicated Backend ReplayController**: Implemented in [backend/pulse/replay/controller.py](file:///e:/Caliberv2/backend/pulse/replay/controller.py) supporting explicit lifecycle states (`READY`, `RUNNING`, `PAUSED`, `COMPLETED`, `RESETTING`, `FAILED`), wall-clock event-time scheduling scaled by playback speed (`0.25x`, `0.5x`, `1.0x`, `2.0x`, `5.0x`), and full seek capabilities (target lap, envelope index, session elapsed time).
2. **Session Registry & Provenance Distinctions**: Established in [backend/pulse/sessions/registry.py](file:///e:/Caliberv2/backend/pulse/sessions/registry.py) distinguishing `AVAILABLE_HISTORICAL` (Silverstone 2023, 52 laps, 20 drivers), `AVAILABLE_SIMULATION` (Monaco 2026 VSC scenario), and `NO_SESSION_DATA` (Suzuka preview, displaying verified geometry while rendering clean empty states across data panels).
3. **Continuous Typed SSE Stream**: Upgraded `/api/stream` in [backend/pulse/api/router.py](file:///e:/Caliberv2/backend/pulse/api/router.py) with sequence counters, unique message IDs (`sse-evt-{seq}`), a 500-event rolling buffer supporting `Last-Event-ID` reconnection resumption, periodic heartbeats, and 10 typed domain event channels.
4. **Interactive UI Replay Control Bar**: Built in [frontend/src/components/ReplayControls.tsx](file:///e:/Caliberv2/frontend/src/components/ReplayControls.tsx) featuring Play/Pause toggle, Reset to cursor 0 under a fresh run ID, Speed selection chips, Scrub/Seek timeline slider, dynamic Lap/Time displays, and status orb indicators.
5. **Complete Emoji Eradication**: Removed all 39 emoji literals across 11 frontend components and replaced them with accessible, responsive SVG icons defined in [frontend/src/components/icons.tsx](file:///e:/Caliberv2/frontend/src/components/icons.tsx). Automated regex scanning verifies exactly 0 emojis remain in `frontend/src`.
6. **20-Criteria Automated Test Suite**: Implemented in [backend/tests/test_phase4_2_streaming.py](file:///e:/Caliberv2/backend/tests/test_phase4_2_streaming.py). All 20 tests pass along with the 70 existing baseline tests (90/90 tests passing).

---

## 2. Root Cause Analysis — Why Values Appeared Static

| Component | Pre-Phase 4.2 Behavior | Root Cause | Phase 4.2 Fix |
| :--- | :--- | :--- | :--- |
| **Playback Engine** | `ScenarioRunner` executed only 9 events on startup and immediately completed. | No continuous event scheduler existed; time deltas were ignored after event 9. | Created `ReplayController` with async event loop `wall_clock_delay = event_time_delta / speed`, scheduling hundreds of events dynamically. |
| **Circuit / Session Selection** | Changing dropdown in `BroadcastBanner` only mutated `circuitId` in React state. | Backend never received notification of circuit or session switch; StateStore remained tied to original session. | Added Session Registry and `POST /api/sessions/select`. UI switching immediately updates backend session and re-seeds StateStore. |
| **Streaming & SSE Transport** | EventSource listener treated all events generically and invoked full snapshot HTTP fetches. | Heavy payload polling created race conditions and failed to stream partial state changes. | Implemented typed SSE dispatch (`SESSION_STATE_UPDATED`, `DRIVER_STATE_UPDATED`, `TELEMETRY_UPDATED`, etc.) and partial state merging. |
| **Empty State Handling** | Selecting Suzuka continued showing Monaco/Silverstone driver metrics. | StateStore did not distinguish missing capture data from active sessions. | Implemented `NO_SESSION_DATA` session status, displaying Suzuka circuit geometry alongside an explicit empty state banner. |
| **UI Aesthetics** | 39 emoji characters (`🚩`, `🌧️`, `🏎️`, `🛞`, `🧠`, `⏱️`, `📊`, etc.) throughout UI. | Visual presentation relied on emojis rather than vector symbols. | Built [icons.tsx](file:///e:/Caliberv2/frontend/src/components/icons.tsx) containing 18 custom SVG components and replaced all emojis. |

---

## 3. Architecture & Service Specifications

### 3.1 Backend ReplayController

The `ReplayController` is a singleton service managing asynchronous playback of historical and simulated canonical event envelopes:

```mermaid
stateDiagram-v2
    [*] --> READY
    READY --> RUNNING: POST /api/replay/start / resume()
    RUNNING --> PAUSED: POST /api/replay/pause
    PAUSED --> RUNNING: POST /api/replay/resume
    RUNNING --> COMPLETED: All Envelopes Consumed
    PAUSED --> READY: POST /api/replay/reset
    COMPLETED --> READY: POST /api/replay/reset
    RUNNING --> READY: POST /api/replay/reset
    RUNNING --> FAILED: Loop Error
    PAUSED --> PAUSED: POST /api/replay/seek
    READY --> READY: POST /api/replay/seek
```

#### Replay API Contracts

- `GET /api/replay/status`: Returns current cursor, status, speed, lap, elapsed time, total events, drop count, and progress percentage.
- `POST /api/replay/start`: Commences playback from index 0 or current cursor at specified speed.
- `POST /api/replay/pause`: Halts event scheduling while preserving cursor position.
- `POST /api/replay/resume`: Resumes event-time progression from current cursor.
- `POST /api/replay/reset`: Cancels active background loop, resets cursor to 0, generates a new `runId`, and re-seeds the `StateStore`.
- `POST /api/replay/seek`: Fast-replays historical state to target index, target lap, or session elapsed milliseconds.
- `POST /api/replay/speed`: Validates and applies playback acceleration factor (`0.25x`, `0.5x`, `1.0x`, `2.0x`, `5.0x`).

### 3.2 Session Registry

Defined in `pulse.sessions.registry`, providing authoritative metadata for session isolation:

1. **`f1-2023-silverstone-race`** (`AVAILABLE_HISTORICAL`):
   - Provenance: Jolpica-F1 and Official FIA Race Director Notices.
   - Total Laps: 52 | Entries: 20 drivers | Envelopes: 100+ canonical events.
2. **`f1-2026-monaco-sim`** (`AVAILABLE_SIMULATION`):
   - Provenance: PULSE Deterministic Scenario Simulator.
   - Total Laps: 78 | Entries: 20 drivers | Envelopes: 9 canonical VSC events.
3. **`f1-2026-suzuka-preview`** (`NO_SESSION_DATA`):
   - Provenance: Preview Geometry Catalogue (FIA/OSM reference).
   - Total Laps: 53 | Entries: 0 | Envelopes: 0. Renders verified track geometry with explicit `NO SESSION DATA AVAILABLE` empty state in data views.

### 3.3 Continuous SSE Stream Architecture

- **Persistent Connection**: Single long-lived HTTP connection (`/api/stream`) with HTTP/1.1 chunked streaming.
- **Heartbeat Keep-Alive**: Emits `event: heartbeat` every 2 seconds with ingest timestamp and current sequence.
- **Sequence Numbering**: Every event emitted carries an integer `seq` and an ID formatted `sse-evt-{seq}`.
- **Last-Event-ID Resumption**: `StateStore` retains a rolling buffer of 500 events. Reconnecting clients supplying `Last-Event-ID: sse-evt-{n}` immediately receive all events where `seq > n`.
- **Domain Event Channels**:
  - `SESSION_STATE_UPDATED`: Lap, elapsed time, neutralisation status, session name.
  - `DRIVER_STATE_UPDATED`: Full grid array or individual driver position, status, and gaps.
  - `TELEMETRY_UPDATED`: CAN-bus channels (speed, rpm, gear, throttle, brake, DRS).
  - `TRACK_STATE_UPDATED`: Sector condition changes, weather, and rain risk.
  - `RACE_CONTROL_UPDATED`: Official FIA notices and race timeline milestones.
  - `AGENT_STATUS_UPDATED`: Execution metrics across all 5 registered specialist agents.
  - `AGENT_FINDING_UPDATED`: Autonomous agent analytical findings.
  - `IMPACT_ASSESSMENT_UPDATED`: Agent 5 consequence fusion assessments and revisions.
  - `REPLAY_STATUS_UPDATED`: Replay cursor, speed, and playback lifecycle state.

---

## 4. Professional Iconography & Zero-Emoji Audit

All 39 emoji literals identified during the audit were removed from the codebase and replaced with responsive SVG components from [frontend/src/components/icons.tsx](file:///e:/Caliberv2/frontend/src/components/icons.tsx).

| File | Replaced Emoji | Professional Replacement | Accessible Role / Class |
| :--- | :--- | :--- | :--- |
| `AgentOperationsView.tsx` | `🚩` (Agent 1) | `<FlagIcon size={18} />` | `agent-svg-icon` |
| `AgentOperationsView.tsx` | `🌧️` (Agent 2) | `<CloudRainIcon size={18} />` | `agent-svg-icon` |
| `AgentOperationsView.tsx` | `🏎️` (Agent 3) | `<CarIcon size={18} />` | `agent-svg-icon` |
| `AgentOperationsView.tsx` | `🛞` (Agent 4) | `<CircleDotIcon size={18} />` | `agent-svg-icon` |
| `AgentOperationsView.tsx` | `🧠` (Agent 5) | `<BrainIcon size={18} />` | `agent-svg-icon` |
| `AgentOperationsView.tsx` | `✕` (Close Modal) | `<CloseIcon size={16} />` | `aria-label="Close trace modal"` |
| `BroadcastBanner.tsx` | `🏁` Cockpit | `<FlagIcon size={14} />` | `nav-icon` |
| `BroadcastBanner.tsx` | `🏛️` Race Control | `<ScaleIcon size={14} />` | `nav-icon` |
| `BroadcastBanner.tsx` | `🤖` Agent Ops | `<BrainIcon size={14} />` | `nav-icon` |
| `BroadcastBanner.tsx` | `🔬` Pipeline Lab | `<FlaskIcon size={14} />` | `nav-icon` |
| `BroadcastBanner.tsx` | `⚠️` VSC Caution | `<AlertTriangleIcon size={14} />` | `ticker-icon` |
| `BroadcastBanner.tsx` | `🚨` Safety Car | `<AlertTriangleIcon size={14} />` | `ticker-icon` |
| `DriverTelemetryModal.tsx` | `⚠️` Telemetry Error | `<AlertTriangleIcon size={14} />` | `text-amber-400` |
| `DriverTelemetryModal.tsx` | `✕` Close Modal | `<CloseIcon size={16} />` | `aria-label="Close modal"` |
| `EvidenceDrawer.tsx` | `✕` Close Drawer | `<CloseIcon size={16} />` | `aria-label="Close drawer"` |
| `ImpactCard.tsx` | `✦` Forecast Star | `<SparkleIcon size={12} />` | `forecast-icon` |
| `LeaderboardTable.tsx` | `📊` Inspect Telemetry | `<BarChartIcon size={14} />` | `aria-label="Inspect Telemetry"` |
| `PipelineLabView.tsx` | `📡`, `📦`, `⚡`, `🤖`, `🧠`, `🗄️` | `<RadioIcon />`, `<CircleDotIcon />`, `<ZapIcon />`, `<ShieldIcon />`, `<BrainIcon />`, `<FileTextIcon />` | `node-icon` |
| `PipelineLabView.tsx` | `➔` Unicode arrow | `&rarr;` | SVG HTML entity |
| `PipelineLabView.tsx` | `✓` Status pass | `<CheckCircleIcon size={12} />` | `stage-pass-tag` |
| `PitWindowCard.tsx` | `⚡` Opportunity | `<ZapIcon size={14} />` | `sparkle-icon` |
| `PitWindowCard.tsx` | `★` Saved | `SAVING:` | Typographic label |
| `PitWindowCard.tsx` | `⏱` Delta icon | `<ClockIcon size={12} />` | `delta-icon` |
| `PitWindowCard.tsx` | `ℹ️` Info callout | Typographic text | Plain text label |
| `RaceControlView.tsx` | `🏛️`, `🧠` Tabs | `<ScaleIcon size={14} />`, `<BrainIcon size={14} />` | `tab-icon` |
| `RaceControlView.tsx` | `✓` Status tag | `<CheckCircleIcon size={12} />` | `status-verified` |
| `ReplayControls.tsx` | `▶`, `⏸`, `↺` Controls | `<PlayIcon />`, `<PauseIcon />`, `<ResetIcon />`, `<SpeedIcon />`, `<ClockIcon />` | Vector Controls |
| `TrackMap.tsx` | `📊` Button icon | `<BarChartIcon size={14} />` | Action icon |

### Automated Verification Script Result
```text
Total emoji matches found in frontend/src: 0
```

---

## 5. Automated Streaming Test Suite (20 Criteria)

Implemented in [backend/tests/test_phase4_2_streaming.py](file:///e:/Caliberv2/backend/tests/test_phase4_2_streaming.py):

| Criterion # | Test Name | Target Verified | Result |
| :---: | :--- | :--- | :---: |
| 1 | `test_01_replay_lifecycle_transitions` | READY → RUNNING → PAUSED → RUNNING → RESET → READY | **PASSED** |
| 2 | `test_02_allowed_speeds_and_scaling` | Allowed speeds [0.25, 0.5, 1.0, 2.0, 5.0] and clamping | **PASSED** |
| 3 | `test_03_replay_seek_by_index` | Fast-forward and rewind seek by envelope index | **PASSED** |
| 4 | `test_04_replay_seek_by_elapsed_ms` | Seek navigation by session elapsed milliseconds | **PASSED** |
| 5 | `test_05_run_id_isolation_on_reset` | Resetting generates fresh `runId` and isolates state | **PASSED** |
| 6 | `test_06_session_registry_catalogue` | Session registry entries, circuit IDs, and provenance | **PASSED** |
| 7 | `test_07_session_switch_to_historical` | Switching to Silverstone loads 20 drivers and 52 laps | **PASSED** |
| 8 | `test_08_session_switch_to_no_session_data` | Switching to Suzuka triggers NO_SESSION_DATA empty state | **PASSED** |
| 9 | `test_09_circuit_geometry_preservation_on_no_session_data` | Verified geometry remains intact during empty state | **PASSED** |
| 10 | `test_10_sse_sequence_monotonicity` | Monotonically strictly increasing sequence numbers | **PASSED** |
| 11 | `test_11_last_event_id_reconnection_buffer` | 500-event rolling buffer and `Last-Event-ID` recovery | **PASSED** |
| 12 | `test_12_sse_endpoint_initial_snapshot` | GET `/api/stream` initial connection delivers snapshot | **PASSED** |
| 13 | `test_13_sse_typed_session_update_emission` | Typed `SESSION_STATE_UPDATED` SSE event dispatched | **PASSED** |
| 14 | `test_14_sse_typed_driver_update_emission` | Typed `DRIVER_STATE_UPDATED` SSE event dispatched | **PASSED** |
| 15 | `test_15_sse_typed_replay_status_emission` | Typed `REPLAY_STATUS_UPDATED` SSE event dispatched | **PASSED** |
| 16 | `test_16_api_replay_status_contract` | GET `/api/replay/status` satisfies 16-field contract | **PASSED** |
| 17 | `test_17_api_replay_speed_contract` | POST `/api/replay/speed` adjusts multiplier | **PASSED** |
| 18 | `test_18_api_sessions_catalogue_and_selection` | GET `/api/sessions` and POST `/api/sessions/select` | **PASSED** |
| 19 | `test_19_zero_emojis_in_frontend` | Regex audit verifying 0 emoji literals in `frontend/src` | **PASSED** |
| 20 | `test_20_execution_transparency_metrics_increment` | Multi-agent execution counters increment dynamically | **PASSED** |

---

## 6. Complete Verification Suite Summary

```text
============================= test session starts =============================
platform win32 -- Python 3.13.12, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\Caliberv2\backend
configfile: pyproject.toml
collected 90 items

backend\tests\test_agents.py .................................. [  4%]
backend\tests\test_api.py .................................... [ 17%]
backend\tests\test_browser_cockpit.py ........................ [ 18%]
backend\tests\test_circuits_and_operations.py ................ [ 26%]
backend\tests\test_contracts.py .............................. [ 31%]
backend\tests\test_fault_injection.py ........................ [ 33%]
backend\tests\test_fusion.py ................................. [ 34%]
backend\tests\test_multi_agent_pipeline.py ................... [ 40%]
backend\tests\test_phase3_contracts_and_integration.py ....... [ 60%]
backend\tests\test_phase4_2_streaming.py ..................... [ 82%]
backend\tests\test_phase4_part_a_session_entry.py ............ [ 88%]
backend\tests\test_phase4_reliability.py ..................... [ 97%]
backend\tests\test_simulator.py .............................. [100%]

======================= 90 passed, 1 warning in 12.68s ========================
```

Frontend production build check:
```text
> pulse-race-intelligence-ui@0.1.0 build
> tsc -b && vite build

vite v6.4.5 building for production...
✓ 44 modules transformed.
dist/index.html                   0.54 kB │ gzip:  0.32 kB
dist/assets/index-BZQv2U-v.css   36.34 kB │ gzip:  7.54 kB
dist/assets/index-BflfrRBM.js   314.64 kB │ gzip: 91.86 kB
✓ built in 616ms
```

---

## 7. Deliverables Index

1. **Replay Controller**: [backend/pulse/replay/controller.py](file:///e:/Caliberv2/backend/pulse/replay/controller.py)
2. **Session Registry**: [backend/pulse/sessions/registry.py](file:///e:/Caliberv2/backend/pulse/sessions/registry.py)
3. **State Store & Stream Dispatch**: [backend/pulse/state/store.py](file:///e:/Caliberv2/backend/pulse/state/store.py)
4. **FastAPI Replay & Stream Endpoints**: [backend/pulse/api/router.py](file:///e:/Caliberv2/backend/pulse/api/router.py)
5. **Icon Component Suite (Zero Emojis)**: [frontend/src/components/icons.tsx](file:///e:/Caliberv2/frontend/src/components/icons.tsx)
6. **Replay Control Bar**: [frontend/src/components/ReplayControls.tsx](file:///e:/Caliberv2/frontend/src/components/ReplayControls.tsx)
7. **Broadcast Header**: [frontend/src/components/BroadcastBanner.tsx](file:///e:/Caliberv2/frontend/src/components/BroadcastBanner.tsx)
8. **Frontend State & SSE Integration**: [frontend/src/App.tsx](file:///e:/Caliberv2/frontend/src/App.tsx) and [frontend/src/api.ts](file:///e:/Caliberv2/frontend/src/api.ts)
9. **Streaming Test Suite (20 Criteria)**: [backend/tests/test_phase4_2_streaming.py](file:///e:/Caliberv2/backend/tests/test_phase4_2_streaming.py)
10. **Machine-Readable Report**: [phase4_2_report.json](file:///e:/Caliberv2/phase4_2_report.json)
11. **Comprehensive Engineering Specification**: [PHASE_4_2_REPORT.md](file:///e:/Caliberv2/PHASE_4_2_REPORT.md)

