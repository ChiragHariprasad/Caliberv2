# Local development specification

This document defines the intended local developer experience. It is a build target, not a claim that the commands exist before Phase 0/1 implementation.

## Prerequisites

| Tool | Minimum role |
| --- | --- |
| Docker Desktop / Docker Compose | Local Kafka, Flink, PostgreSQL, observability stack, and containerised app services. |
| Python 3.12+ | Contracts, simulator, agents, API, test/evaluation tooling. |
| Node.js 20+ | React/Vite dashboard and frontend tests. |
| Git | Source control and reproducible configuration history. |

All exact dependency versions belong in lockfiles once chosen. Do not pin undocumented versions based only on a pasted plan.

## Configuration

Create `.env` from `.env.example`. The first implementation should include non-secret defaults such as:

```dotenv
PULSE_ENV=development
PULSE_MODE=SIMULATED
PULSE_LOG_LEVEL=INFO
PULSE_DATABASE_URL=postgresql://pulse:pulse@postgres:5432/pulse
PULSE_KAFKA_BOOTSTRAP_SERVERS=kafka:9092
PULSE_FLINK_REST_URL=http://flink-jobmanager:8081
PULSE_REPLAY_SPEED=1.0
PULSE_LATE_EVENT_WINDOW_SECONDS=30
PULSE_FUSION_TIMEOUT_SECONDS=5
PULSE_SIMULATOR_SEED=20261104
```

Provider credentials are intentionally absent. A future authorised adapter uses a secret-store reference or local ignored environment variable; the raw value is never committed or published to Kafka.

## Intended developer commands

| Action | Target command shape | Success signal |
| --- | --- | --- |
| Install backend | `python -m pip install -e '.[dev]'` or lockfile equivalent | Contract/simulator imports resolve. |
| Install frontend | `npm ci` | Vite type-check/build works. |
| Run backend unit suite | `pytest` | Contract, simulator, state, agent unit suites pass. |
| Run frontend checks | `npm run lint && npm run test && npm run build` | Dashboard builds from fixture data. |
| Start local stack | `docker compose up --build` | health endpoint, broker, DB, Flink, and dashboard are healthy. |
| Start simulator | API or CLI scenario command | `SIMULATED` run appears in the dashboard. |
| Run end-to-end test | compose profile/test harness | VSC scenario creates an assessment revision. |

During implementation, record the actual commands in this table and README. Keep commands cross-platform or provide PowerShell-specific equivalents because this workspace is on Windows.

## Development profiles

| Profile | Services | Use case |
| --- | --- | --- |
| `unit` | Python/Node only, in-memory event bus. | Fast deterministic development. |
| `integration` | broker + database + backend services. | Topic, persistence, and agent boundaries. |
| `full` | integration + Flink + frontend + observability. | Demo, end-to-end, performance, recovery. |
| `replay` | full + approved capture mount/reference. | Historical validation only after data gate. |

## Repository hygiene

- Commit source contracts, scenario definitions, configuration templates, golden expected outputs, and source manifests.
- Never commit `.env`, secrets, full licensed captures, broker/database volumes, cache files, compiled artefacts, or provider tokens.
- Keep generated OpenAPI/JSON Schema outputs only if deliberately versioned for review.
- Add data samples only when their provenance/licence permits redistribution and the sample is explicitly labelled.
- Update [the continuation brief](08-continuation-brief.md) after each meaningful milestone.

## Definition of a reproducible demo

A fresh developer with prerequisites can clone/open the workspace, install dependencies, start the local stack, run `vsc_pit_window` with a known seed, open the dashboard, and inspect:

1. the VSC source event and lifecycle;
2. the relevant race/driver state;
3. Agent 1 and Agent 4 findings arriving independently;
4. a provisional then superseding impact assessment;
5. all linked evidence, provenance, and data coverage;
6. pipeline/agent health and final accounting.

