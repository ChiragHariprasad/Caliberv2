# Event and finding contracts

## Contract principles

- JSON is acceptable for v0.1 and human-readable APIs. The operational schema should later move to Avro or Protobuf with a schema registry.
- Every producer validates before publishing; every consumer tolerates additive fields and rejects incompatible major versions.
- All messages carry event-time, ingest-time, run mode, source provenance, and interpretation semantics.
- Topic names, event types, and contract enums are versioned. A breaking semantic change requires a new major topic/schema version.
- A field absent because the source does not provide it is `null` or listed in `missing_fields`; it is never silently invented.

## Identifiers

| Identifier | Generation rule | Stability |
| --- | --- | --- |
| `event_id` | UUIDv7 or deterministic namespace UUID derived from provider/capture/source-record ID. | Immutable and globally unique within PULSE. |
| `source_record_id` | Provider's immutable identifier. If absent, use documented fingerprint of source identity + event time + payload. | Stable per capture. |
| `capture_id` | Immutable raw-capture manifest ID. | Immutable. |
| `run_id` | New ID for each replay/simulation/live execution. | Immutable per run. |
| `session_instance_id` | Distinguishes concurrent/restarted run instances for the same sporting session. | Immutable per run instance. |
| `finding_id` | Stable entity ID across revisions. | Stable. |
| `finding_version` | Integer starting at 1. | Strictly increasing per finding ID. |
| `assessment_id` / `assessment_version` | Stable assessment entity plus revision counter. | Strictly increasing version. |

## Common event envelope

Every raw and canonical event uses this shape. Domain-specific fields belong in `payload`.

```json
{
  "event_id": "018f8b3c-2a3a-7f01-94fa-5f9ced4c822f",
  "event_type": "CAR_TELEMETRY_SAMPLE",
  "schema_version": 1,
  "source": {
    "provider": "PULSE_SIMULATOR",
    "adapter": "simulator_adapter",
    "source_record_id": "sim-7-341",
    "capture_id": "pulse-sim-v1",
    "licence_reference": "internal-simulator"
  },
  "run": {
    "run_id": "pulse-replay-001",
    "session_instance_id": "2026-R05-RACE-SIM-001",
    "mode": "SIMULATED"
  },
  "session": {
    "season": 2026,
    "meeting_id": "meeting-identifier",
    "session_id": "session-identifier",
    "session_type": "RACE"
  },
  "time": {
    "event_time_utc": "2026-06-07T14:30:10.250Z",
    "session_elapsed_ms": 5430000,
    "ingest_time_utc": "2026-11-04T10:00:00.000Z",
    "replay_clock_ms": 5430000,
    "time_domain": "EVENT_TIME"
  },
  "subject": {
    "driver_number": 16,
    "segment_id": null
  },
  "payload": {
    "speed_kph": 285,
    "throttle_pct": 100,
    "brake": false,
    "rpm": 10500,
    "gear": 8
  },
  "quality": {
    "interpretation": "OBSERVED",
    "completeness": "COMPLETE",
    "missing_fields": [],
    "unit_validation": "PASSED"
  }
}
```

### Required enums

| Field | Allowed values |
| --- | --- |
| `run.mode` | `SIMULATED`, `REPLAY`, `LIVE` |
| `session.session_type` | `PRACTICE`, `QUALIFYING`, `SPRINT`, `RACE`, `UNKNOWN` |
| `time.time_domain` | `EVENT_TIME`, `SOURCE_SEQUENCE`, `UNKNOWN` |
| `quality.interpretation` | `OBSERVED`, `DERIVED`, `INFERRED`, `PREDICTED` |
| `quality.completeness` | `COMPLETE`, `PARTIAL`, `MISSING`, `UNKNOWN` |
| `quality.unit_validation` | `PASSED`, `FAILED`, `NOT_APPLICABLE` |

### Time semantics

| Field | Meaning | Must never be used as |
| --- | --- | --- |
| `event_time_utc` | Timestamp assigned to the original sporting/source event. | A local process receipt time. |
| `ingest_time_utc` | When PULSE received the record. | A substitute for historical event time. |
| `session_elapsed_ms` | Source-relative elapsed session coordinate, if known. | A globally comparable wall-clock value without session context. |
| `replay_clock_ms` | Position on a replay/simulation clock. | A replacement for event time. |

## Supported raw event types

| Topic | Event types | Required payload highlights |
| --- | --- | --- |
| `race_control` | `SAFETY_CAR_DEPLOYED`, `SAFETY_CAR_ENDING`, `SAFETY_CAR_ENDED`, `VSC_DEPLOYED`, `VSC_ENDING`, `VSC_ENDED`, `RED_FLAG`, `YELLOW_FLAG`, `INCIDENT_NOTICE` | source message, scope, affected segments if supported. |
| `track_status` | `TRACK_STATUS_UPDATE`, `SEGMENT_STATUS_UPDATE` | status, segment, status source. |
| `timing.laps` | `LAP_COMPLETED`, `SECTOR_COMPLETED` | lap number, lap time, sector times, validity. |
| `timing.positions` | `POSITION_UPDATE`, `INTERVAL_UPDATE` | position, interval/gap, lap context. |
| `telemetry.car` | `CAR_TELEMETRY_SAMPLE` | available measured signals with declared units. |
| `weather` | `WEATHER_OBSERVATION` | air/track temp, wind, rain, humidity where available. |
| `tyres.stints` | `TYRE_FITTED`, `STINT_UPDATE` | compound, tyre age, stint number. |
| `pit.events` | `PIT_ENTRY`, `PIT_STOP`, `PIT_EXIT` | pit visit ID where known, duration/tyre change if known. |
| `session_status` | `SESSION_STARTED`, `SESSION_SUSPENDED`, `SESSION_RESUMED`, `SESSION_ENDED` | source status. |

## Canonical race event

Job 1 turns raw race-control messages into an explicit lifecycle entity.

```json
{
  "event_id": "race-event-00821",
  "event_type": "VSC_DEPLOYED",
  "session_id": "2026-R05-RACE",
  "event_time_utc": "2026-06-07T14:30:10Z",
  "race_event": {
    "event_category": "NEUTRALISATION",
    "control_type": "VSC",
    "lifecycle_state": "ACTIVE",
    "scope": "SESSION",
    "affected_segments": [],
    "source_message": "VSC DEPLOYED"
  },
  "source_record_ids": ["record-102", "record-103"]
}
```

`lifecycle_state` is one of `DETECTED`, `ACTIVE`, `ENDING`, `ENDED`, `CANCELLED`, or `UNKNOWN`. State transitions must be legal and versioned. For example, a withdrawal message updates the existing VSC event; it does not create an unrelated event entity.

## Agent finding contract

All specialist agents publish a common wrapper with a typed agent-specific `result`.

```json
{
  "finding_id": "finding-7d4c",
  "finding_version": 1,
  "agent_id": "tyre_strategy_agent",
  "finding_type": "PIT_WINDOW_OPPORTUNITY",
  "session_id": "2026-R05-RACE",
  "run_id": "pulse-replay-001",
  "subject": { "driver_number": 16, "segment_id": null },
  "trigger_event_id": "race-event-00821",
  "as_of_event_time": "2026-06-07T14:30:10Z",
  "interpretation": "PREDICTED",
  "result": {
    "opportunity": "EARLIER_PIT_WINDOW",
    "forecast_horizon_laps": 2,
    "estimated_gap_effect_seconds": null
  },
  "uncertainty": {
    "calibration_version": null,
    "probability": null,
    "interval": null,
    "coverage": "PARTIAL"
  },
  "evidence_refs": ["record-102", "record-103", "tyre-state-221"],
  "model_version": "1.0.0",
  "assessment_status": "PROVISIONAL",
  "supersedes_finding_id": null,
  "reason_codes": ["VSC_ACTIVE", "STINT_AGE_HIGH"]
}
```

### Finding rules

- `finding_version` advances when the same analytical entity is revised. A new unrelated event gets a new `finding_id`.
- `assessment_status` is `PROVISIONAL`, `CONFIRMED`, `SUPERSEDED`, `UNRESOLVED`, or `WITHDRAWN`.
- `evidence_refs` must refer to source event IDs, canonical state IDs, or prior findings that can be retrieved.
- `probability` is null until calibration exists for that task. A score is not a probability.
- A finding can explicitly declare unavailable input through `reason_codes` and uncertainty coverage.

## Agent-specific finding types

| Agent | Minimum finding types | Result fields |
| --- | --- | --- |
| Race Event & Control | `RACE_EVENT_LIFECYCLE`, `DRIVER_EVENT_EXPOSURE`, `PIT_EVENT_ASSOCIATION` | control type, lifecycle, scope, affected drivers/segments, association window. |
| Track State | `TRACK_CONDITION_STATE`, `TRACK_TRANSITION`, `OBSERVATION_INCONSISTENCY` | segment, observed/inferred condition, trend, confidence/coverage, observed measurements. |
| Vehicle Response | `PACE_DEVIATION`, `TELEMETRY_RESPONSE_DEVIATION`, `RESPONSE_REQUIRES_REVIEW` | baseline, observed delta, context factors, evidence; no failure diagnosis. |
| Tyre & Strategy | `STINT_DEGRADATION_ESTIMATE`, `PIT_WINDOW_OPPORTUNITY`, `STRATEGY_SCENARIO` | degradation estimate, feasible window, estimated cost/risk, scenario assumptions. |
| Race Consequence | `DRIVER_RACE_IMPACT`, `RACE_IMPACT_REVISION`, `UNRESOLVED_IMPACT` | affected driver, gap/position/strategy forecast, supporting findings, alternatives. |

## Race impact assessment contract

```json
{
  "assessment_id": "impact-vsc-821-driver-16",
  "assessment_version": 2,
  "session_id": "2026-R05-RACE",
  "run_id": "pulse-replay-001",
  "as_of_event_time": "2026-06-07T14:30:45Z",
  "trigger": {
    "event_id": "race-event-00821",
    "control_type": "VSC",
    "lifecycle_state": "ACTIVE"
  },
  "subject": { "driver_number": 16 },
  "impact": {
    "summary": "Potential pit-window advantage while VSC remains active.",
    "affected_segments": [],
    "observed_changes": ["stint age and neutralisation state"],
    "inferred_effects": ["reduced relative pit-loss exposure"],
    "forecast": {
      "horizon_laps": 2,
      "position_delta_range": [-1, 2],
      "gap_delta_seconds_range": [-3.0, 1.5],
      "status": "PROVISIONAL"
    },
    "alternatives": ["stay out until next green-lap timing update"]
  },
  "supporting_finding_refs": ["finding-event-821", "finding-strategy-16-14"],
  "data_coverage": {
    "race_event": "COMPLETE",
    "track_state": "PARTIAL",
    "vehicle_response": "UNAVAILABLE",
    "strategy": "COMPLETE"
  },
  "uncertainty": {
    "level": "MEDIUM",
    "explanation": "Track-state observation is partial and the VSC duration is unknown."
  },
  "status": "PROVISIONAL",
  "supersedes_assessment_id": "impact-vsc-821-driver-16@1",
  "evidence_refs": ["record-102", "finding-event-821", "finding-strategy-16-14"]
}
```

## Idempotency, late data, and revisions

### Deduplication

1. Reject exact repeat `event_id` as `DUPLICATE` without re-emitting a canonical event.
2. For a new adapter record with a previously seen source identity, retain the earliest accepted source event and emit an operational duplicate metric.
3. Use a TTL appropriate to capture/replay retention; do not assume in-memory duplicate cache is sufficient for recovery.

### Late data

1. Flink assigns bounded watermarks by source, with per-source idleness.
2. A late record inside the declared correction window updates state and may cause a new finding/assessment revision.
3. A record beyond the correction window goes to `PENDING_LATE_WINDOW` and a late-data topic or DLQ for explicit review; it is never silently discarded.

### Revisions

1. Derived entities are append-only revisions.
2. The API offers `latest=true` materialised views and a full revision history.
3. Fusion may publish partial assessment v1 before all agents contribute, then supersede it with v2+ as bounded late findings arrive.
4. A revision references its predecessor and its complete evidence set.

## Error envelope

Dead-letter messages use the source envelope plus:

```json
{
  "failure": {
    "stage": "normalisation",
    "code": "INVALID_EVENT_TIME",
    "message": "event_time_utc is not parseable",
    "retryable": false,
    "first_failed_at_utc": "2026-11-04T10:00:00Z",
    "attempt_count": 1
  }
}
```

Never put secrets, raw access tokens, or unnecessary personal data in a dead-letter payload.

