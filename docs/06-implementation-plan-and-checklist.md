# Implementation plan and checklist

## Delivery rule

Build the simulator path first. It provides a deterministic, legally uncomplicated way to validate contracts, agent separation, fusion revisions, dashboard behaviour, replay semantics, and fault handling. Real historical replay may be enabled only after the feasibility gate in Phase 0 has a documented pass.

## Target repository layout

```text
.
├── backend/
│   ├── pulse/
│   │   ├── api/                 # FastAPI routers and response models
│   │   ├── contracts/           # Pydantic event/finding/assessment models
│   │   ├── adapters/            # simulator, replay, future authorised sources
│   │   ├── stream/              # producer/consumer abstractions and Flink jobs
│   │   ├── state/               # repositories, projections, idempotency
│   │   ├── agents/              # five independently runnable services
│   │   ├── fusion/              # correlation and revision engine
│   │   ├── simulator/           # deterministic scenarios and generator
│   │   ├── evaluation/          # metrics and ablation runner
│   │   └── observability/       # health, metrics, logging helpers
│   ├── tests/
│   ├── requirements.txt or pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   ├── fixtures/
│   │   └── routes/
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── compose/
│   ├── kafka/
│   ├── flink/
│   ├── postgres/
│   └── observability/
├── data/
│   ├── manifests/
│   ├── raw/                     # ignored from VCS except approved samples
│   └── scenarios/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Phase 0 — Feasibility and project bootstrap

**Goal:** Establish a lawful, reproducible data boundary and a repeatable local-development baseline.

### Data feasibility

- [ ] Read and preserve the source restrictions in [data provenance](02-data-provenance-and-feasibility.md).
- [ ] Inventory any existing local FastF1 captures without exposing credentials or copying cache blindly.
- [ ] Verify provenance, licence, capture integrity, and allowed use for each candidate capture.
- [ ] Query Jolpica only for metadata/result/lap/pit reference scope; record exact acquisition details.
- [ ] Create manifests for three candidate sessions using the audit matrix.
- [ ] Establish Dataset A (dry/conventional), Dataset B (neutralisations), and Dataset C (changing weather) only after coverage review.
- [ ] Define one held-out interval/session before tuning an agent.
- [ ] Record source gaps and outputs that must remain unavailable.
- [ ] Record Phase 0 decision: `REAL_REPLAY_APPROVED`, `SIMULATOR_ONLY`, or `BLOCKED`.

### Bootstrap

- [ ] Initialise Git repository if the user wants version control in this workspace.
- [ ] Create Python project/tooling and React/Vite/TypeScript project.
- [ ] Add `.gitignore` for environments, captures, caches, database volumes, and secrets.
- [ ] Add `.env.example` with non-secret connection/config keys.
- [ ] Add formatting, linting, type-checking, and test scripts.
- [ ] Add CI workflow only after local commands are stable.
- [ ] Add `make`/PowerShell task aliases or documented equivalent commands.

**Exit criteria:** A source decision is recorded and the empty project can install/lint/test a minimal contract package locally.

## Phase 1 — Contracts and deterministic simulator

**Goal:** Make the system executable without external race data.

### Shared contracts

- [ ] Implement Pydantic models for `EventEnvelope`, source/run/session/time/subject/quality submodels.
- [ ] Implement enums exactly as specified in [contracts](03-event-and-finding-contracts.md).
- [ ] Implement `Finding`, `RaceEvent`, `RaceImpactAssessment`, error envelope, and operation-health models.
- [ ] Add JSON Schema export/snapshots for contract review.
- [ ] Add deterministic ID helpers and validation of revision chains.
- [ ] Add tests for valid, invalid, incomplete, and additive-field payloads.
- [ ] Add serialization tests proving all timestamp fields persist unchanged.

### Simulator

- [ ] Define scenario DSL/config with seed, driver roster, circuit segments, event schedule, and expected assertions.
- [ ] Create `dry_baseline` scenario: conventional stints, positions, lap/sector timing, weather, pit events.
- [ ] Create `vsc_pit_window` scenario: VSC deployment/ending, affected drivers, strategy opportunity, delayed specialist finding.
- [ ] Create `changing_conditions` scenario: wet/drying segment status, partial coverage, pace effect without false grip claims.
- [ ] Add optional corrupted scenarios: duplicate event, late weather, missing telemetry, agent crash signal.
- [ ] Make simulator output immutable, seeded envelopes with `mode=SIMULATED` and capture ID.
- [ ] Add golden expected timeline and finding/assessment assertions.

### Local event-bus abstraction

- [ ] Define publisher/consumer interface shared by in-memory and Kafka implementations.
- [ ] Add per-topic key, envelope validation, duplicate handling, and offset/sequence metadata.
- [ ] Unit-test in-memory deterministic replay with pause/resume/restart semantics.
- [ ] Ensure unit tests do not require Docker/Kafka.

**Exit criteria:** The VSC scenario can publish contract-valid events in deterministic order and its golden assertions pass repeatedly with the same seed.

## Phase 2 — State reconstruction and stream foundation

**Goal:** Reconstruct a race faithfully despite duplicate, late, and out-of-order records.

### Normalisation

- [ ] Implement provider mapping configuration rather than hard-coding provider identities.
- [ ] Implement schema/unit/required-field validation.
- [ ] Implement terminal record accounting: accepted, duplicate, dead letter, pending late window.
- [ ] Add a durable/idempotent deduplication store interface.
- [ ] Add dead-letter contract, retention, and remediation metadata.
- [ ] Add per-source watermark/late-window configuration.

### State projections

- [ ] Implement driver state projection.
- [ ] Implement race-event lifecycle projection.
- [ ] Implement track-segment projection.
- [ ] Implement tyre/stint projection.
- [ ] Implement pit-cycle projection.
- [ ] Add source freshness and completeness to each materialised view.
- [ ] Add revision/retraction behaviour for valid late corrections.
- [ ] Create state-reconstruction fixtures from all simulator scenarios.

### Kafka/Flink infrastructure

- [ ] Define all topics, keys, retention, and compaction configuration in source-controlled infrastructure configuration.
- [ ] Start small with partitions; record benchmark-driven scaling changes later.
- [ ] Configure idempotent producer and durable consumer groups.
- [ ] Implement Flink Job 1 and Job 2 with checkpoints and source-specific watermarks.
- [ ] Emit operational metrics for counts, watermark age, late records, and DLQ volume.
- [ ] Test restart from checkpoint and reconciliation against event accounting.

**Exit criteria:** Every scenario input is accounted for, reconstructed state is correct after shuffled/duplicate input, and restart produces no duplicate canonical state transition.

## Phase 3 — Feature engineering and four specialist agents

**Goal:** Implement independently meaningful analysis services.

### Flink features

- [ ] Implement event-aligned context around neutralisations.
- [ ] Implement lap/sector rolling pace baseline features.
- [ ] Implement stint-age and stint-performance features.
- [ ] Implement pit entry/exit and traffic/gap-change features.
- [ ] Implement segment observation/track-transition features.
- [ ] Store calculation window/config version with each feature.

### Agent 1: Race Event & Control

- [ ] Implement lifecycle state machine and legal transition rules.
- [ ] Map simulator/provider messages to canonical control types.
- [ ] Associate nearby pit/incident records through event-time windows.
- [ ] Emit `RACE_EVENT_LIFECYCLE` and `DRIVER_EVENT_EXPOSURE` findings.
- [ ] Test deployment, ending, end, correction, duplicate, and out-of-order input.

### Agent 2: Track State

- [ ] Implement segment state model with direct observations, inferred labels, and coverage.
- [ ] Implement initial deterministic condition/transitions classifier.
- [ ] Implement observation inconsistency detection.
- [ ] Emit `TRACK_CONDITION_STATE` and `TRACK_TRANSITION` findings.
- [ ] Test missing weather, conflicting track status, and session-only (not segment) status.

### Agent 3: Vehicle Response

- [ ] Implement driver-context baseline store.
- [ ] Implement timing-only deviation finder.
- [ ] Add telemetry-feature path behind presence checks.
- [ ] Include traffic, tyre age, neutralisation, and track context as confounders.
- [ ] Emit no conclusion if baseline/support is insufficient.
- [ ] Test absence of telemetry and ensure no mechanical-failure language is generated.

### Agent 4: Tyre & Strategy

- [ ] Implement stint state and first deterministic degradation estimate.
- [ ] Implement pit cost model with neutralisation saving and traffic terms.
- [ ] Publish alternative scenarios/ranges with assumptions and coverage.
- [ ] Emit strategy/pit-window findings only when relevant state is available.
- [ ] Test green-flag versus VSC conditions and incomplete tyre data.

### Agent infrastructure

- [ ] Make each agent independently runnable with topic subscriptions, consumer group, heartbeat, health endpoints, and graceful shutdown.
- [ ] Version each rule/model configuration and include it in findings.
- [ ] Add agent-level unit/integration tests and health/lag metrics.
- [ ] Demonstrate Agents 1–4 can publish in different orders without direct calls.

**Exit criteria:** Each agent emits contract-valid findings from the simulator and has a clear metric/ground-truth plan described in [verification](07-verification-and-operations.md).

## Phase 4 — Fusion, persistence, and API

**Goal:** Turn asynchronous specialist output into explainable assessments.

### Fusion

- [ ] Implement correlation-group key: run/session + trigger event + subject driver/segment.
- [ ] Define required, optional, unavailable, and timeout rules per assessment class.
- [ ] Emit partial `PROVISIONAL` assessments after minimum evidence/deadline.
- [ ] Emit ordered revision chain when delayed specialist findings arrive.
- [ ] Emit `UNRESOLVED` when an important input is unavailable beyond deadline.
- [ ] Persist all evidence refs, uncertainty, data coverage, and alternative scenarios.
- [ ] Test different finding arrival orders produce equivalent final state.

### Persistence

- [ ] Create migrations for source events, runs, materialised state, findings, assessments, checkpoints, and evaluation runs.
- [ ] Implement idempotent upserts keyed by entity ID + revision.
- [ ] Add lookup of latest and full revision history.
- [ ] Store immutable source/capture manifest references, not credentials.

### API

- [ ] Implement all initial endpoints listed in [API spec](05-api-and-dashboard-spec.md).
- [ ] Add OpenAPI tags/descriptions, response models, cursor pagination, and consistent error envelope.
- [ ] Add run controls with mode-aware validation/audit events.
- [ ] Add SSE reconnect cursor and update sequence tests.
- [ ] Write API contract/integration tests against simulator data.

**Exit criteria:** A VSC scenario generates an assessment v1 before all findings arrive and a traceable v2 when a delayed strategy finding arrives; the API exposes both revisions and evidence.

## Phase 5 — Dashboard

**Goal:** Provide an analytical, evidence-forward interface.

- [ ] Create dashboard shell with mode badge, run selector, session context, and event-time control.
- [ ] Build Race State view and driver leaderboard.
- [ ] Build timeline with event lifecycles and impact revision markers.
- [ ] Build Track Intelligence view with direct/inferred condition labels.
- [ ] Build Strategy view with stints, opportunities, assumptions, and ranges.
- [ ] Build Consequences view with affected-driver matrix and evidence drawer.
- [ ] Build Operations view with health, lag, checkpoint, DLQ, and data-coverage widgets.
- [ ] Start with contract-valid fixture data then integrate typed API/SSE client.
- [ ] Implement all loading, empty, partial, stale, error, and revision states.
- [ ] Add accessible text alternatives, keyboard navigation, units, and UTC/local-time clarity.
- [ ] Add component and end-to-end smoke tests for simulator scenario flow.

**Exit criteria:** An analyst can follow a selected VSC from source event through agent findings to a fused impact assessment and its evidence without needing a terminal.

## Phase 6 — End-to-end infrastructure and evaluation

**Goal:** Demonstrate a dependable streaming system and measure whether the agent design adds value.

### Infrastructure

- [ ] Create `docker-compose.yml` for broker(s), Flink, PostgreSQL, backend, frontend, Prometheus, Grafana, and Loki.
- [ ] Make a one-command local simulator environment documented and reproducible.
- [ ] Add Kafka topic bootstrap and Flink job deployment scripts.
- [ ] Add production-oriented configuration overlays without applying cloud infrastructure by default.
- [ ] Establish backups/retention for database, checkpoint, raw-capture manifest, and dashboard audit data.

### Evaluation

- [ ] Create immutable source inventories, timelines, and ground-truth labels for approved datasets.
- [ ] Run Agent 1 event precision/recall/F1 and boundary timing error.
- [ ] Run Agent 2 classification/transition metrics only against valid track-status/weather labels.
- [ ] Run Agent 3 review/anomaly precision/recall only against independently reviewed episodes.
- [ ] Run Agent 4 degradation/pit-window metrics against observed stints/pits.
- [ ] Run Agent 5 gap/position/impact metrics against subsequent progression.
- [ ] Run ablation E1–E4 (baseline, single model, specialists without fusion, complete PULSE).
- [ ] Publish dataset/config hashes and result artefacts.

### Resilience

- [ ] Inject duplicate pit event.
- [ ] Inject out-of-order race-control event.
- [ ] Inject delayed weather observation.
- [ ] Inject missing telemetry interval.
- [ ] Crash/restart a specialist agent during an active event.
- [ ] Shuffle Agent 1–4 finding delivery order.
- [ ] Restart Kafka consumer and recover offsets.
- [ ] Restore Flink checkpoint.
- [ ] Interrupt/resume replay.
- [ ] End a session with an unresolved finding.
- [ ] Verify explainability, input accounting, no silent loss, and no duplicate final findings after every experiment.

**Exit criteria:** Evidence supports the acceptance targets in the charter, or the project documents which claims did not hold and why.

## Critical path and stop conditions

| Point | Continue if | Stop/re-scope if |
| --- | --- | --- |
| Data gate | At least one lawful, sufficient capture is approved. | No non-OpenF1 capture can support required event/timing/pit/tyre/weather scope. Keep simulator MVP; block real-data claim. |
| Agent value | An agent has independently measurable contribution. | It adds no value in ablation testing; combine/refactor rather than preserving architecture for appearances. |
| Fusion | Assessment revisions are deterministic and explainable. | Different arrival orders produce materially different final conclusions. Fix correlation semantics before dashboard polish. |
| Performance | P95 targets are measured and acceptable on stated hardware. | Constraints are unsatisfied; profile and right-size before calling real-time. |
| Data claims | Evidence supports wording. | Required ground truth is unavailable; downgrade to proxy/inference or remove the metric. |

## Completion checklist

- [ ] Phase 0 decision logged.
- [ ] Simulator path complete and reproducible.
- [ ] Contracts/versioning/evidence semantics covered by automated tests.
- [ ] Kafka/Flink event-time processing works under duplicate/late/restart conditions.
- [ ] Five agents run independently and publish their own findings.
- [ ] Fusion creates revisioned, evidence-linked assessments.
- [ ] Dashboard shows all five required views and data mode.
- [ ] Operations view exposes health and coverage.
- [ ] Approved replay data, if any, has manifests and evaluation evidence.
- [ ] Fault injection and ablation results are recorded.
- [ ] README, continuation brief, checklist, and decision log reflect final state.

