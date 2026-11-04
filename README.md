# PULSE

**Multi-Agent Real-Time Race Intelligence & Consequence Analytics**

PULSE is a Formula 1 stream-analytics platform. It turns asynchronous race-control, timing, weather, tyre, track, and optional telemetry data into evidence-linked, driver-specific impact assessments for the next one to three laps.

> Current status: **documentation baseline complete; implementation intentionally begins after the data-feasibility gate.** The `backend/` and `frontend/` directories are reserved for the implementation and currently contain no application code.

## What this repository will contain

- A Kafka event backbone and Flink event-time processing jobs.
- Five independently deployable specialist analytics agents.
- A deterministic fusion service that emits explainable `RaceImpactAssessment` revisions.
- Simulation, historical replay, and future authorised live-ingestion modes.
- A FastAPI service and React dashboard for race, strategy, track, impact, and operations views.

PULSE is decision support. It does not issue race-control actions, prescribe pit stops, determine FIA penalties, diagnose mechanical failures, or use generic LLM commentary to decide outcomes.

## Start here

| Document | Purpose |
| --- | --- |
| [Project charter](docs/00-project-charter.md) | Product intent, scope, frozen decisions, and success conditions. |
| [System architecture](docs/01-system-architecture.md) | Components, Kafka topics, deployment boundaries, and data flow. |
| [Data feasibility](docs/02-data-provenance-and-feasibility.md) | The mandatory source-provenance gate and the three-race coverage audit. |
| [Contracts](docs/03-event-and-finding-contracts.md) | Canonical event, finding, assessment, topic, and delivery contracts. |
| [Processing and agents](docs/04-processing-and-agent-design.md) | Flink jobs, agent responsibilities, fusion rules, and algorithms. |
| [API and dashboard](docs/05-api-and-dashboard-spec.md) | Service contract and user-facing views. |
| [Implementation plan](docs/06-implementation-plan-and-checklist.md) | Ordered milestones, task checklist, owners, and exit criteria. |
| [Verification and operations](docs/07-verification-and-operations.md) | Evaluation, fault injection, observability, and incident/replay runbooks. |
| [Continuation brief](docs/08-continuation-brief.md) | Compact handoff for a later chat or engineering session. |
| [Decision log](docs/09-decision-log.md) | Stable architectural decisions and the reasons behind them. |
| [Local development spec](docs/10-local-development-spec.md) | Intended local environment, configuration, and reproducible demo. |
| [First implementation slice](docs/11-first-implementation-slice.md) | Exact simulator-first VSC proof slice for the next coding session. |

## Recovery instruction for a future session

Read [the continuation brief](docs/08-continuation-brief.md), then complete Phase 0 in [the implementation checklist](docs/06-implementation-plan-and-checklist.md). Do not begin a real-data replay build until the coverage audit identifies at least one provenance-approved historical capture. The simulator can be built before that gate passes.

## Repository layout

```text
.
├── backend/                 # Reserved for FastAPI, replay orchestration, and agents
├── frontend/                # Reserved for the React dashboard
├── docs/                    # Durable architecture and delivery documentation
└── README.md
```

