# API and dashboard specification

## Serving objectives

The serving layer gives analysts an evidence-first view of a run. It prioritises current race state, chronology, impact assessments, supporting findings, and data quality. It must show whether the run is `SIMULATED`, `REPLAY`, or `LIVE` in every main view.

## Backend service

### Technology boundary

The initial API is FastAPI with Pydantic contracts and PostgreSQL persistence. It reads materialised state and intelligence topics through a repository/service layer; dashboard requests must not query Kafka directly. SSE is preferred for v0.1 live updates because it is easy to observe and recover; WebSocket support can be added when client commands or multiplexed streams are justified.

### Endpoint inventory

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness/readiness, service version, dependencies. |
| `GET` | `/api/runs` | Available simulated/replay/live run list. |
| `POST` | `/api/runs` | Create a simulator/replay run from authorised configuration. |
| `GET` | `/api/runs/{run_id}` | Run metadata, mode, state, provenance summary. |
| `POST` | `/api/runs/{run_id}/controls` | Pause, resume, restart, change permitted replay speed, stop. |
| `GET` | `/api/sessions/{session_instance_id}` | Session header, race state summary, mode/coverage. |
| `GET` | `/api/sessions/{session_instance_id}/drivers` | Latest driver state ordered by position. |
| `GET` | `/api/sessions/{session_instance_id}/drivers/{driver_number}` | Driver state, stint history, impacts, evidence links. |
| `GET` | `/api/sessions/{session_instance_id}/timeline` | Unified chronological race-event / impact timeline. |
| `GET` | `/api/sessions/{session_instance_id}/track` | Segment/session track state and observations. |
| `GET` | `/api/sessions/{session_instance_id}/strategy` | Stint/strategy findings and alternatives. |
| `GET` | `/api/sessions/{session_instance_id}/assessments` | Latest or revisioned fused driver impact assessments. |
| `GET` | `/api/findings/{finding_id}` | A specific finding and its evidence/revision chain. |
| `GET` | `/api/assessments/{assessment_id}` | A specific assessment and revisions. |
| `GET` | `/api/operations` | Kafka/Flink/agent/replay health summary. |
| `GET` | `/api/stream?run_id=...` | Server-sent state/timeline/finding/health updates. |

### Query conventions

- Collection endpoints accept `run_id`, `as_of_event_time`, `latest`, `limit`, and cursor pagination where appropriate.
- `latest=true` returns a materialised current view. `latest=false` returns revision history.
- Time filtering always uses original event time by default; an explicit `time_axis=replay_clock` is permitted for replay UI navigation.
- Every payload includes `mode`, `run_id`, `session_instance_id`, source/capture summary, and a data coverage indicator.

### Core response models

#### Run response

```json
{
  "run_id": "pulse-sim-vsc-001",
  "session_instance_id": "sim-2026-demo-001",
  "mode": "SIMULATED",
  "status": "RUNNING",
  "replay_speed": 1.0,
  "created_at_utc": "2026-11-04T10:00:00Z",
  "source_summary": {
    "capture_id": "pulse-sim-v1",
    "provider": "PULSE_SIMULATOR",
    "provenance_status": "APPROVED"
  }
}
```

#### Session overview response

```json
{
  "session_instance_id": "sim-2026-demo-001",
  "mode": "SIMULATED",
  "session": {
    "season": 2026,
    "meeting_name": "PULSE Demonstration",
    "session_type": "RACE",
    "lap": 24,
    "laps_scheduled": 57,
    "status": "ACTIVE"
  },
  "race_control": {
    "active_event": "VSC",
    "lifecycle_state": "ACTIVE",
    "event_id": "race-event-00821"
  },
  "data_coverage": "PARTIAL",
  "last_event_time_utc": "2026-06-07T14:30:10Z"
}
```

#### API error envelope

```json
{
  "error": {
    "code": "RUN_NOT_CONTROLLABLE",
    "message": "The completed replay cannot be resumed.",
    "trace_id": "...",
    "retryable": false
  }
}
```

### Control endpoint

`POST /api/runs/{run_id}/controls` accepts a narrow whitelist:

```json
{ "action": "PAUSE" }
```

Allowed actions: `START`, `PAUSE`, `RESUME`, `STOP`, `RESTART`, `SET_SPEED`. `SET_SPEED` takes a validated multiplier configured for the current mode. Live runs cannot be replay-seeked or speed-adjusted. Every control action creates an audit event.

## Dashboard information architecture

### Global shell

| Area | Contents |
| --- | --- |
| Top bar | PULSE wordmark, session/run selector, current mode badge, run state, last-event age, operator menu. |
| Primary navigation | Race State, Track Intelligence, Strategy, Consequences, Operations. |
| Global time control | Original event-time selector; replay controls when the mode is `REPLAY` or `SIMULATED`. |
| Evidence drawer | Opens from any finding/assessment; shows raw/canonical evidence, interpretation class, coverage, and revision chain. |

Every primary view has an unmissable data-mode badge: violet for `SIMULATED`, blue for `REPLAY`, green for `LIVE`. The label is text, not colour alone.

### 1. Race State view

**Goal:** Understand the live/replayed competitive state before reading interpretations.

| Module | Content |
| --- | --- |
| Session header | Lap, status, active control event, mode, data freshness. |
| Leaderboard | Position, driver/team, gap, interval, last lap, compound, stint age, pit indicator, impact badge. |
| Event strip | Chronological race-control/session/pit events with lifecycle state. |
| Race pace chart | Driver gaps/position evolution over selected event-time window. |
| Data-quality panel | Stream freshness, missing telemetry flag, active source/capture. |

### 2. Track Intelligence view

**Goal:** Show observable conditions and declared inferences at segment level.

| Module | Content |
| --- | --- |
| Circuit/segment view | Segment colour and status, with `UNKNOWN` visibly distinct. |
| Condition cards | Rain, track/air temperature, wind, source freshness, direct vs inferred label. |
| Transition timeline | Condition changes aligned to flags and lap/sector activity. |
| Evidence panel | Weather/track-status source records and any inconsistency finding. |

Never label a segment's “grip” unless a valid direct measurement exists. Use “condition state” and mark inference clearly.

### 3. Strategy Intelligence view

**Goal:** Compare stint context and modelled pit opportunities without presenting commands as facts.

| Module | Content |
| --- | --- |
| Stint table | Driver, compound sequence, age, pace trend, pit-cycle status, data coverage. |
| Pit window panel | Candidate windows, estimated cost range, assumptions, active event context. |
| Scenario comparator | “Pit now”, “hold”, and alternative timing scenarios with a range and evidence. |
| Strategy alerts | Revisioned opportunities including status and uncertainty. |

### 4. Event Consequences view

**Goal:** Explain who is affected and why.

| Module | Content |
| --- | --- |
| Active assessment stack | Latest driver-specific impact assessments ordered by materiality and event time. |
| Impact card | Trigger, observed changes, inferred effects, forecast range, alternatives, status, uncertainty. |
| Affected-driver matrix | Drivers × active events with impact direction/coverage. |
| Revision view | Timeline of provisional/confirmed/superseded assessments. |
| Evidence trail | Links to source events and specialist findings. |

The page must be able to say “insufficient evidence” clearly. It must not manufacture a green/red conclusion merely to fill the layout.

### 5. Operations view

**Goal:** Prove system behaviour and make operational failures visible.

| Module | Content |
| --- | --- |
| Pipeline health | Kafka lag, Flink checkpoints/watermark age, DLQ rate, input accounting. |
| Agent matrix | Agent status, input freshness, p95 processing latency, finding rate, current model version. |
| Replay controls | Mode-gated controls, source/capture manifest, current clock and speed. |
| Failure timeline | Agent restarts, late/duplicate events, DLQ records, replay checkpoints. |
| Data coverage | Per-stream completeness and known limitations for the active run. |

## UI states

| State | Required behaviour |
| --- | --- |
| Loading | Skeleton matching final layout; retains mode badge and selected run context. |
| No run selected | Explain how to choose/start a permitted simulator or replay run. |
| Empty finding set | Say no current assessment has met evidence criteria; do not render a fake all-clear. |
| Source unavailable | Show affected stream, stale age, agent impact, and whether fusion can still update. |
| Partial coverage | Display precise missing fields/streams and constrain claims. |
| Error | Actionable service error with trace ID; do not erase last known state unless stale. |
| Late/revision | Highlight that an assessment was revised and provide a one-click diff. |

## Accessibility and interaction requirements

- Do not rely on colour as the only indication of status/impact.
- All charts have textual summary and accessible data table alternative.
- Keyboard navigation supports view switching, driver selection, timeline focus, and evidence drawer.
- Timestamps display in a selected user time zone while tooltips preserve raw UTC.
- All numerical estimates show units and whether they are measured, derived, inferred, or predicted.

## Frontend data strategy

1. The dashboard starts with contract-valid fixture data from a deterministic simulator scenario.
2. A typed API client supplies the same view models from the backend.
3. SSE messages carry an event type, sequence cursor, run/session ID, and data payload. The client reconnects with the last event ID.
4. Server updates merge only if their revision/time is newer than the current view model.
5. The frontend never recomputes a strategic conclusion; it renders backend findings and their declared evidence.

## API acceptance examples

- A VSC deployment shows up in Race State within the current state/event strip and produces an Agent 1 finding before strategy findings arrive.
- The Consequences view shows a `PROVISIONAL` driver impact after minimum evidence, then a visibly superseded revision when Agent 4 adds a pit-window finding.
- If telemetry is missing, the Vehicle Response module says unavailable/partial rather than showing fabricated charts.
- A user can select an older assessment version and retrieve its evidence references through the API.

---

## Phase 3 Implementation Updates (Cockpit, Telemetry & Multi-View Operations)

### Extended Endpoint Inventory (Phase 3 Verified)

| Method | Path | Response Type | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/circuits` | `list[CircuitGeometrySummary]` | List available circuit geometry models (Monaco, Silverstone, Suzuka) with metadata and SHA-256 checksums. |
| `GET` | `/api/circuit/{circuit_id}` | `CircuitGeometry` | Retrieve complete circuit asset: centreline, boundary offsets, corners, DRS zones, pit lane, start/finish line. |
| `GET` | `/api/telemetry/{driver_number}` | `DriverTelemetryPayload` | Rich per-driver telemetry (speed, throttle, brake, gear, rpm, drs, tyre, stint) with quality states and 20-point time-series history. |
| `GET` | `/api/race-control` | `list[OfficialNotice]` | Verbatim FIA official race notices with regulatory article references (e.g. Art 56.4), flag statuses, and timestamps. |
| `GET` | `/api/pipeline/status` | `PipelineStatusData` | Real-time health, Kafka broker transport, Flink JobManager checkpoint/record metrics, and 5-agent registration counts. |
| `GET` | `/api/pipeline/verification-runs` | `list[VerificationRun]` | Historical verification runs with stage-by-stage reconciliation status (10/10 stages passed). |
| `GET` | `/api/pipeline/verification-runs/{run_id}` | `VerificationRunDetail` | Complete execution audit report and latency profiles for a verification run. |
| `GET` | `/api/pipeline/lineage` | `list[LineageTraceEvent]` | End-to-end event lineage tracing from raw Kafka ingestion through Flink normalization, agent findings, and fusion. |

### Visual Architecture & Views

The upgraded PULSE frontend cockpit delivers a cohesive dark Formula 1 operational layout across four primary operational modules:

1. **🏁 Cockpit View (`Cockpit`)**:
   - **Dynamic SVG Circuit Map**: Renders exact circuit geometry centreline and track boundaries for Monaco (3.337 km), Silverstone (5.891 km), and Suzuka (5.807 km).
   - **Full-Grid Driver Tracking**: Spatially tracks all 20+ active cars with team-colored pulsing nodes, positions, and hover preview cards.
   - **Interactive Telemetry Modal**: Clicking any driver displays real-time gauges, time-series SVG line chart (speed, throttle, brake), explicit `UNAVAILABLE` channel handling, and provenance lineage footer.
   - **Full 20-Driver Leaderboard**: Complete timing grid with status filters (All, Active, Pit Lane, Out), tyre compound badges (Soft, Medium, Hard, Inter, Wet), stint age, gaps, and tactical consequence tags.
   - **Live Tactical Consequence Feed & Strategy Card**: Displays fused multi-agent consequences and VSC pit window saving calculation with explicit arithmetic assumptions (e.g., 10.5s neutralised saving).

2. **🏛️ Race Control & Stewarding View (`RaceControlView`)**:
   - **Strict Domain Separation**: Segregates official FIA communications from PULSE AI analytical predictions.
   - **Official Domain**: Chronological notices table with notice ID, UTC timestamp, flag severity, driver references, and formal regulatory citations (e.g. FIA Sporting Regulations Art 56.4).
   - **PULSE Domain**: Multi-agent consequence synthesis, provisional vs confirmed assessments, and superseding revision audit cards.

3. **🤖 Agent Operations View (`AgentOperationsView`)**:
   - **Live Specialist Agent Cards**: 5 dedicated cards for Event Control, Track State, Vehicle Response, Tyre Strategy, and Consequence Fusion.
   - **13 Operational Telemetry Metrics**: Exposes events received, eligible inputs, processed inputs, emitted findings, dropped inputs, invalid payloads, p50/p95/max latency, memory, uptime, and last active timestamp.
   - **Clickable Execution Trace Modal**: Opens complete deterministic audit log of findings emitted by each specialist agent with causal parent references.

4. **🔬 Pipeline Lab View (`PipelineLabView`)**:
   - **Live Streaming Topology Flow**: Node-by-node execution diagram (Raw Ingestion ➔ Normalization ➔ Kafka Stream ➔ Multi-Agent Processing ➔ Consequence Fusion ➔ State & API).
   - **Real-Time Engine Metrics**: Real-time Kafka broker transport state and Flink JobManager checkpoint accounting.
   - **Verification Run Selector**: Interactive selector over automated verification test runs with full 10-stage reconciliation accounting table.
   - **Lineage Explorer**: Detailed event-to-finding trace breakdown.

### Verified Visual Baseline (Playwright High-Resolution Captures)

All modules have been verified via automated Playwright browser tests and captured into `docs/screenshots/`:

| Screenshot | File | Description |
| --- | --- | --- |
| **01** | `docs/screenshots/01_cockpit_monaco.png` | Monaco cockpit view with dynamic centreline, 20 drivers, leaderboard, and VSC tactical feed. |
| **02** | `docs/screenshots/02_driver_telemetry_modal.png` | Real-time telemetry inspector for Car #16 (Leclerc) with gauges and SVG time-series chart. |
| **03** | `docs/screenshots/03_race_control_stewarding.png` | Race Control view separating Official FIA regulatory notices (Art 56.4) from PULSE AI predictions. |
| **04** | `docs/screenshots/04_agent_operations.png` | Agent Operations view with 13 live execution metrics across all 5 agents and trace modal. |
| **05** | `docs/screenshots/05_pipeline_lab.png` | Streaming pipeline topology diagram, Flink/Kafka metrics, and 10-stage reconciliation table. |
| **06** | `docs/screenshots/06_cockpit_silverstone.png` | Dynamically switched Silverstone circuit geometry with 18 corners and 2 DRS zones. |


