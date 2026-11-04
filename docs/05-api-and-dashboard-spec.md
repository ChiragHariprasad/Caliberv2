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

