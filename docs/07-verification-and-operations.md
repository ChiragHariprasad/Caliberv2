# Verification, evaluation, and operations

## Verification philosophy

PULSE is only reliable if it behaves correctly when the input is messy and agents finish at different times. A clean replay demonstration is insufficient. Verification covers contract integrity, temporal correctness, analytical validity, fusion consistency, operational recovery, and user-visible explanation.

## Test layers

| Layer | Scope | Examples |
| --- | --- | --- |
| Contract unit tests | Model parsing and serialization | invalid time, missing provenance, enum rejection, revision-chain ordering. |
| Deterministic simulator tests | Scenario events and expected outputs | VSC becomes active, strategy finding is delayed, partial assessment revises. |
| State/projection tests | Normalisation and reconstruction | duplicate event, late sector time, corrected pit exit, source idleness. |
| Agent unit tests | Agent-specific deterministic rules/baselines | lifecycle transition, condition transition, pace baseline, pit cost. |
| Integration tests | Multi-service Kafka/in-memory pathways | independent producer order, finding correlation, restart/recovery. |
| API tests | Service contract | latest/history queries, evidence lookup, run controls, SSE replay. |
| UI/component tests | Transparent presentation | mode badge, partial coverage state, evidence drawer, revision diff. |
| End-to-end tests | Docker Compose simulator run | source event through dashboard assessment. |
| Evaluation tests | Real/replay predictive validity | held-out metrics and ablation study. |

## Simulator acceptance scenarios

### S1: Dry baseline

**Input:** green session, stable weather, ordinary positions, two planned pit cycles, complete timing/stint input.

**Expected:**

- State projection produces ordered driver/stint/pit timelines.
- No unsupported track/vehicle claims are emitted.
- Strategy agent can generate a bounded degradation estimate only after its minimum evidence threshold.
- Fusion outputs `UNRESOLVED` or no material consequence rather than forcing alerts.

### S2: VSC pit window

**Input:** VSC deployment at a defined session time, drivers with differing stint ages and gaps, pit event(s), delayed tyre-strategy finding.

**Expected:**

- Agent 1 publishes an active VSC lifecycle finding.
- Agent 5 creates correlation groups by affected driver and emits a preliminary/partial assessment at deadline.
- Agent 4 publishes a strategy/pit-window finding later.
- Agent 5 emits a superseding assessment with evidence links; the UI renders a revision marker.
- Different agent finding arrival orders result in equal final materialised assessment content.

### S3: Changing conditions

**Input:** rain/track-status changes with segment scope, partial weather coverage, sector timing shifts, tyre changes.

**Expected:**

- Track agent separates direct weather/status observation from inferred condition changes.
- Vehicle agent reports timing-based deviation only if baseline is adequate.
- Every dashboard panel exposes `PARTIAL` coverage when observations are incomplete.
- No output calls an inferred state a directly measured grip value.

### S4: Fault injection bundle

**Input:** S2 plus duplicate pit record, out-of-order withdrawal, delayed weather, telemetry gap, Agent 4 outage/restart.

**Expected:**

- One terminal accounting outcome per input record.
- Duplicate records do not create duplicate state transitions or final assessments.
- Valid late input causes a documented revision or late-review outcome.
- Agent outage becomes explicit input coverage/unresolved state.
- Replay recovery preserves revision chain and idempotent sink behaviour.

## Acceptance tests by system concern

### Input accounting

For all admitted source event IDs in a run:

```text
accepted + duplicate + dead_letter + pending_late_window == admitted
```

This is a reconciliation invariant, not merely a dashboard count. Run it after every replay, restart, and fault experiment.

### Event lifecycle

Test all legal and illegal state transitions. Assert that an event end references the active canonical event rather than creating an unrelated event. Include source correction and ambiguous provider message cases.

### Event-time correctness

- Validate `event_time_utc` is unchanged from ingestion through persistence.
- Simulate two partitions with one idle; assert idleness prevents watermark starvation.
- Introduce events inside and outside the correction window; assert different explicit outcomes.
- Pause/resume replay and assert event-time ordering stays source-derived.

### Fusion consistency

For a fixed set of specialist findings, run every meaningful permutation of arrival order. The final assessment should be semantically equivalent; only intermediate revision timing may differ. Property-based tests are recommended once the base suite is stable.

### Explainability

For each assessment returned by the API, assert:

- it has a trigger or declared non-event trigger;
- `supporting_finding_refs` resolve;
- `evidence_refs` resolve or have an explicit unavailable reason;
- coverage exists for each specialist domain;
- forecast status and uncertainty are present;
- predecessor reference is valid when version > 1.

## Agent evaluation protocol

### Dataset protocol

For every approved session:

- retain an immutable raw capture and manifest;
- create a source completeness report;
- write an event/pit/session timeline;
- define ground-truth labels from legitimate independent evidence;
- reserve held-out time or sessions before tuning;
- record configuration/model/rule version and hardware/environment.

### Metrics

| Agent | Primary metrics | Valid ground truth |
| --- | --- | --- |
| Race Event | Precision, recall, F1, event-boundary timing error. | Recorded race-control/session events. |
| Track State | Classification accuracy, macro F1, transition latency. | Explicit track-status/weather observations; direct surface labels only where available. |
| Vehicle Response | Precision, recall, false-positive rate, lead time. | Independently reviewed response episodes; not raw speed decrease alone. |
| Tyre & Strategy | Degradation MAE/RMSE, pit-window estimation error. | Observed stints, pace, pit events. |
| Race Consequence | Gap-change MAE, position-change accuracy, impact classification F1. | Subsequent actual race progression. |

Metrics that lack suitable ground truth must be named as proxy or inference metrics. Do not report them as validated predictive accuracy.

## Ablation study

The project must test whether agent separation improves a relevant result:

| Experiment | Configuration |
| --- | --- |
| E1 | Race-state rules and simple baseline calculations. |
| E2 | One combined analytical model using all available features. |
| E3 | Agents 1–4 present, no Agent 5 fusion. |
| E4 | Full five-agent PULSE architecture. |

Pre-register one primary predictive task (for example, short-horizon gap/position impact around a neutralisation) before interpretation. Retain an agent only when it provides measurable value or necessary safety/traceability behaviour.

## System performance targets

| Measurement | Target | Measurement method |
| --- | --- | --- |
| Input accounting | 100% | Reconciliation query at run completion/recovery. |
| Event detection F1 | >= 0.90 | Held-out labelled evaluation, supported event types only. |
| Normalised event to first finding | p95 < 2 seconds | Trace event ID from canonical write to first finding at 1x replay. |
| Finding to impact fusion | p95 < 3 seconds | Trace finding arrival to assessment revision. |
| Final duplicate persistence | 0 | Restart/fault-injection reconciliation. |
| Broken revision links | 0 | Database/API consistency check. |
| Provenance coverage | 100% | Query all intelligence records. |

Record input rate, host resources, partition count, replay speed, and mode beside every performance report. A number without its workload is not a useful benchmark.

## Observability design

### Logs

Emit structured JSON logs with `run_id`, `session_instance_id`, `event_id`, `finding_id`, `assessment_id`, `topic`, `partition`, `offset`, and `trace_id` where available. Avoid raw credentials/provider authentication details.

### Metrics

| Metric family | Examples |
| --- | --- |
| Ingestion | accepted/duplicate/DLQ counts, validation failure rate, ingest lag. |
| Flink | watermark age, checkpoint duration/success, late event count, backpressure. |
| Agents | consumer lag, processing p50/p95/p99, finding rate, error/retry counts, input coverage. |
| Fusion | open correlation groups, timeout rate, assessment revisions, unresolved rate. |
| Persistence/API | write conflicts, idempotent conflict count, API latency/error rate, SSE connections. |
| Simulator/replay | current clock, speed, pause count, restart count, event accounting. |

### Tracing

Propagate a trace or correlation ID derived from `event_id` when handling a source event. A fused assessment has its own trace that links all supporting finding traces. Use OpenTelemetry once the local service boundaries exist.

## Operational runbooks

### Start a simulator run

1. Confirm the scenario name, generator seed, and expected mode are shown in the run configuration.
2. Start the local stack or in-memory development pipeline.
3. Create a run with `mode=SIMULATED`.
4. Verify source manifest, heartbeat, and input accounting become visible.
5. Watch Race State and Operations; record trace IDs for any failure.
6. On completion, run reconciliation and compare golden assertions.

### Start an approved historical replay

1. Confirm capture manifest hash, licence/approval, session mapping, and completeness scope.
2. Create a new `run_id` and `session_instance_id`; do not reuse an old run state.
3. Select replay speed and source-specific lateness config; persist them with the run.
4. Start at the first source event time and track watermark/data coverage.
5. If a source gap is encountered, display it and let agents declare unavailable input.
6. On completion, run accounting/revision/evidence reconciliation and archive metrics.

### Agent unhealthy

1. Check agent heartbeat, consumer lag, error log, and deployed model/rule version.
2. Keep other agents and fusion running; Agent 5 must mark that input unavailable after its deadline.
3. Restart the agent from its consumer offset/checkpoint.
4. Confirm it does not duplicate persisted findings.
5. Review any revised/unresolved assessments before declaring recovery complete.

### Late or duplicate event spike

1. Identify source, topic/partition, capture/run, time window, and mapping version.
2. Inspect input accounting and watermark configuration.
3. Do not delete DLQ records to clear the dashboard.
4. Fix adapter/configuration, replay in a new run, and compare revision/final state with the previous run.

### Replay restart

1. Persist/inspect replay checkpoint, consumer offsets, run status, and current clock.
2. Restart from a valid checkpoint with the same run only if idempotent state restoration is confirmed; otherwise start a new run and link it to the failed attempt.
3. Reconcile source events, findings, and assessments to ensure no final duplicate.

## Operational incident record template

```markdown
## Incident title
- Date/time and operator:
- Run/session/mode:
- Affected component/topic:
- Data/provenance impact:
- User-visible impact:
- Detection signal:
- Timeline:
- Immediate mitigation:
- Reconciliation result:
- Root cause:
- Follow-up change and test:
```

