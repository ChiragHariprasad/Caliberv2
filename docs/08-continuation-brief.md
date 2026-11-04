# PULSE continuation brief

Use this document to restore the project in a later chat or hand it to another engineer.

## Current repository state

- The workspace is `E:\Caliberv2`.
- This is a new project with empty `backend/` and `frontend/` directories reserved for application code.
- Documentation is the source of truth and has been written before implementation by request.
- No source capture, Kafka cluster, Flink job, package lockfile, environment file, or application code exists yet.
- The next meaningful engineering action is Phase 0: a source-provenance and three-race coverage audit. A simulator may be implemented while that audit is underway.

## Product in one paragraph

PULSE is an F1 decision-support platform that consumes race-control, timing, tyres, pits, weather, track status, and optional authorised telemetry. Kafka carries raw and derived events. Flink performs validation, state reconstruction, and feature engineering. Four independent agents emit specialist findings; a fifth deterministic fusion agent emits revised driver impact assessments for the next one to three laps. The dashboard explains evidence, uncertainty, and whether data is simulated, replayed, or live.

## Non-negotiable constraints

1. Do not use OpenF1 as a primary, fallback, or required source.
2. Do not represent replay or simulation as live data.
3. Keep `event_time_utc`, `ingest_time_utc`, and `replay_clock_ms` separate.
4. Preserve source/capture provenance on every event and evidence reference on every finding.
5. Do not fabricate missing telemetry through silent interpolation.
6. Keep `OBSERVED`, `DERIVED`, `INFERRED`, and `PREDICTED` distinct.
7. Do not make official sporting, penalty, pit-command, or mechanical-diagnosis claims.

## Immediate next-session prompt

> Continue the PULSE project in `E:\Caliberv2`. Read `README.md` and every file in `docs/` first. Start at Phase 0 in `docs/06-implementation-plan-and-checklist.md`; implement the deterministic simulator and contract tests in parallel with the data-coverage audit. Preserve all frozen decisions in `docs/00-project-charter.md`, especially provenance, event-time semantics, five independent agents, deterministic fusion, and the no-OpenF1 constraint. Update the checklist and decision log as work completes.

## Build order

1. Follow [the first implementation slice](11-first-implementation-slice.md) to create the contracts package and deterministic VSC simulator.
2. Implement validation, idempotency, event-time handling, and canonical state reconstruction.
3. Add the four specialist agent services and their isolated tests.
4. Add fusion/revision logic and persistence.
5. Add FastAPI read/control endpoints.
6. Build the React dashboard against fixture data then the API.
7. Wire Kafka/Flink/Postgres in Docker Compose.
8. Run replay, evaluation, and fault-injection suites.

The full execution checklist is [here](06-implementation-plan-and-checklist.md). The machine and service interfaces are [here](03-event-and-finding-contracts.md), [here](04-processing-and-agent-design.md), and [here](05-api-and-dashboard-spec.md).

