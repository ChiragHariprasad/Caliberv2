# Architecture decision log

This log records decisions that future implementation work must preserve unless a later entry deliberately supersedes them.

| ID | Decision | Status | Reason and consequence |
| --- | --- | --- | --- |
| ADR-001 | Keep the product name **PULSE**. | Accepted | It identifies the product without constraining a source/provider. |
| ADR-002 | PULSE is a race-intelligence decision-support system. | Accepted | Primary output is an evidence-linked competitive consequence assessment, not a telemetry viewer. |
| ADR-003 | Use a Kafka-centred event backbone. | Accepted | Agents need independent scaling, replayability, fault isolation, and no direct dependency chain. |
| ADR-004 | Use Flink for event-time normalisation, state reconstruction, and features. | Accepted | Temporal correctness is a stream-processing concern; models remain in specialist services. |
| ADR-005 | Use five distinct analytical agents. | Accepted | Each has a measurable domain: event/control, track state, vehicle response, tyre/strategy, and consequence fusion. |
| ADR-006 | Use deterministic Agent 5 fusion with revisions. | Accepted | Findings arrive asynchronously; fusion must publish partial/revised explanations rather than wait forever or use unconstrained language-model decisions. |
| ADR-007 | Preserve event time, ingest time, and replay clock separately. | Accepted | Replay and source latency are distinct concerns. Changing timestamps corrupts temporal analysis. |
| ADR-008 | Every event/finding needs source/capture/evidence provenance. | Accepted | Enables trustworthy replay, traceable analytics, and data-access accountability. |
| ADR-009 | Treat data interpretation as a first-class enum. | Accepted | `OBSERVED`, `DERIVED`, `INFERRED`, and `PREDICTED` cannot be conflated in UI or downstream models. |
| ADR-010 | Do not silently interpolate missing telemetry. | Accepted | Missing data must remain explicit; interpolation, if ever used, needs a labelled derived product and validation. |
| ADR-011 | Exclude OpenF1 as primary/fallback/required input. | Accepted | The project definition requires a source strategy independent of OpenF1. Legacy OpenF1 material must stay isolated. |
| ADR-012 | FastF1 is optional and access-dependent. | Accepted | The implementation must verify current authorisation and capture provenance; it cannot assume free access. |
| ADR-013 | Jolpica is a reference metadata/results source, not a full telemetry feed. | Accepted | Avoids overstating data coverage. |
| ADR-014 | Simulator-first delivery. | Accepted | Enables contracts, agents, fusion, UI, and fault tests before an approved real historical capture exists. |
| ADR-015 | JSON first, Avro/Protobuf later. | Accepted | JSON speeds v0.1 development and human debugging; topic/schema versioning remains mandatory. |
| ADR-016 | Use append-only finding/assessment revisions and latest materialised views. | Accepted | Enables explainability, late-data corrections, and reliable replay/recovery. |
| ADR-017 | Kafka log compaction only for current-state topics. | Accepted | Historical event and findings require append-oriented retention. |
| ADR-018 | Use FastAPI + React/TypeScript for serving/UI. | Accepted | Provides typed, documented API and an operational dashboard that can consume live updates. |
| ADR-019 | Start with Docker Compose; defer Kubernetes. | Accepted | Complexity should follow measured scale/deployment needs. |
| ADR-020 | Evaluation must include ablation E1–E4. | Accepted | Five agents are justified only if they add measurable value or essential safety/traceability. |

## Change policy

Before changing an accepted decision:

1. Add a new entry with date, author, and explicit superseded ADR.
2. State the evidence or test result requiring the change.
3. Update affected contracts, runbooks, checklist, and continuation brief in the same change.
4. Re-run any impacted simulator or evaluation suite.

