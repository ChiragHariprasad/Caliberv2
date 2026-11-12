# CALIBRE

**Durable evidence verification platform with the PULSE Formula 1 reference application**

CALIBRE is being evolved from the implemented PULSE Formula 1 stream-analytics application into a durable evidence-verification platform. PULSE turns asynchronous race-control, timing, weather, tyre, track, and optional telemetry data into evidence-linked, driver-specific impact assessments for the next one to three laps. The embedded SIA core evaluates the integrity of selected evidence chains.

> Current status: **PULSE and the SIA integration are implemented.** CALIBRE v4 migration work is under way. It adds durable archives, tagged hashes, explicit time-scale declarations, domain packs, effective-dated references, and a standalone verifier. It does not claim to replace an official measurement system or make sporting decisions.

## What this repository contains

- A Kafka event backbone and Flink event-time processing integration.
- PULSE specialist analytics agents, deterministic fusion, simulation, replay, FastAPI service, and React dashboard.
- SIA v3 deterministic integrity engine integration.
- CALIBRE v4 durable archive, reference, time-scale, uncertainty-witness, and verifier foundations.

PULSE is decision support. It does not issue race-control actions, prescribe pit stops, determine FIA penalties, diagnose mechanical failures, or use generic LLM commentary to decide outcomes.

## Start here

| Document | Purpose |
| --- | --- |
| [CALIBRE v4 plan](docs/12-calibre-v4-implementation-plan.md) | Current migration plan, implementation status, issues, fixes, and gates. |
| [Project charter](docs/00-project-charter.md) | Historical PULSE product intent, scope, frozen decisions, and success conditions. |
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

Start with [the CALIBRE v4 plan](docs/12-calibre-v4-implementation-plan.md). The earlier PULSE documents remain useful implementation history but are not the current platform plan. Do not promote a public-feed replay into an independent-evidence claim; follow the v4 source, archive, and regime gates first.

## Repository layout

```text
.
├── backend/                 # FastAPI, replay orchestration, PULSE agents, SIA bridge
├── frontend/                # React dashboard
├── calibre_core/            # CALIBRE v4 durable platform primitives
├── sia_core_v3/             # Existing deterministic integrity reference engine
├── docs/                    # PULSE history and current CALIBRE v4 plan
└── README.md
```

