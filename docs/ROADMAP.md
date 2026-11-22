# CALIBRE V2 — Proposed Remediation Roadmap

**Status:** Proposal based on the 22 November 2026 static audit. Nothing in this file has been implemented or runtime-validated.
**Approval required before implementation:** all phases.

## Target architecture

```text
Versioned raw capture -> validation/normalisation -> durable admission sequencer
                                              |              |
                                              |              +-> immutable admission log + checkpoints
                                              v
       deterministic evidence producers -> SIA evaluator -> versioned verdict history/read model
                                              |
                      deterministic tactical reducers/statistical models -> fusion policy -> API/SSE
                                              |
                              optional LLM explanation service (never a decision input)
```

The sequencer is the sole writer of knowledge time and admission sequence. Kafka transports records; it is not the integrity ledger. SIA reads ordered admission-log slices, and recovery rebuilds state from those slices/checkpoints. Tactical intelligence consumes evidence/facts and emits separately versioned, evidence-backed predictions; it cannot alter SIA integrity states.

## Architectural choices

| Decision | Options | Recommendation and rationale |
|---|---|---|
| SIA state | Retain in memory; external DB; append-only log + materialised view | Append-only log plus rebuildable view. It preserves bitemporal auditability and separates write correctness from serving performance. |
| Kafka delivery | At-least-once + idempotent sink; Kafka transactions; claimed EOS without sink transaction | Kafka transactions for Kafka-to-Kafka stages, idempotent outbox/sink for external storage. Never claim end-to-end EOS without a verified sink protocol. |
| Partition key | Driver; session; composite by event type | Session-affine sequencer input; driver-affine downstream independent analytics. This makes decision order explicit before parallel work. |
| Agent reasoning | LLM; ML; deterministic | Deterministic state/validation by default; calibrated statistical models for pace/tyre only; LLM only for non-authoritative explanation. |
| Replay | Reset handlers; Kafka offset replay; admission log replay | Admission-log replay with checkpoints and an equivalence harness. Kafka offsets are transport coordinates, not sufficient decision history. |

## Phase 0 — establish baselines and contracts

**Objective:** prevent further divergence before any redesign.

- Freeze and version the current PULSE envelope/finding/assessment schemas.
- Create a source-to-contract matrix: each active SIA role must have a producer, scope fields, origin lineage, time basis, reference source and rejection route.
- Mark unsupported contracts inactive; do not manufacture placeholder evidence.
- Record current Kafka topology and consumer groups from configuration as a deployment manifest.

**Dependencies:** none. **Migration/rollback:** additive documentation/schema registry only. **Acceptance:** every enabled contract has complete provenance; unsupported features return an explicit unavailable status. **Later validation:** schema compatibility and capture conformance tests.

## Phase 1 — SIA integrity boundary

**Objective:** make SIA’s lifecycle, schemas and correction semantics internally coherent.

- Define a canonical `Assessment` envelope shared by normal and void decisions; include lifecycle, integrity state, finality, reason, evidence frontier and tagged hashes.
- Replace ad-hoc supersession with a validated revision graph: immutable parent, monotonic revision sequence, cycle rejection, correction authority and reason.
- Add a pre-admission finality gate and explicit `AMENDMENT` policy; never silently mix late material into a sealed decision’s normal ledger view.
- Consolidate kernel and durable canonicalization/digest requirements, with a one-way legacy-read migration path.
- Specify state ownership, legal transitions, transition guard and timeout semantics as executable contract tests.

**Components:** `sia_core_v3/sia_core/{engine,ledger,evaluator,model,verdict,canon}.py`, SIA JSON schemas, bridge serializers. **Risk:** digest migration invalidates existing IDs; retain old IDs as immutable legacy references and issue new schema/version identifiers. **Acceptance:** exact state transition table, no schema branch for void, deterministic correction vectors, and chain verification across migration examples.

## Phase 2 — durable admission and reconstruction

**Objective:** make the ordered evidence record the system of record.

- Promote `calibre_core/admission.py` into the only SIA input protocol; add raw-record digest/reference, schema/version, source lineage and partition/offset metadata.
- Implement sequencer persistence with atomic append/checkpoint boundary and idempotency key `(source identity, canonical content digest, transform version)`.
- Build deterministic state snapshots for evaluator/agent reducers, referenced by admission sequence and hash.
- Make recovery load latest valid snapshot then replay the log; expose an immutable as-of query API.

**Dependencies:** Phase 1. **Interface change:** PULSE bridge emits admission candidates, not direct engine mutation. **Rollback:** dual-write candidate log and compare only before cutover. **Acceptance:** interrupted run resumes to identical assessment hashes; duplicate/reordered candidates follow published policy; log verification detects deletion/reordering/tampering.

## Phase 3 — ingestion and Kafka topology

**Objective:** replace divergent Kafka code paths with one production topology.

- Select one client abstraction and remove/deprecate unused parallel implementation after feature parity is proven.
- Define topic catalogue by lifecycle: `raw`, `normalised`, `admission-candidate`, `admission-log`, `evidence`, `finding`, `verdict`, `dlq`; version schemas independently.
- Configure retention, replication/min ISR, partition counts, producer idempotence, `read_committed`, retry/DLQ and consumer offset commits deliberately.
- Use session key at candidate/sequencer boundary; permit driver keys only after ordering constraints are resolved. Include partition growth/migration policy.
- Add a genuine normalizer deployment or explicitly remove Flink claims. Flink is justified only for sustained stateful throughput/windowing; a Kafka Streams/Python consumer topology is lower-operational-cost if volume is modest.

**Dependencies:** Phase 2. **Migration:** mirror raw topics and compare canonical candidate digests before switching consumers. **Rollback:** keep old raw producers and read-only legacy consumers. **Acceptance:** chaos tests for broker loss, rebalance, poison records, duplication, retry and DLQ; end-to-end guarantees documented precisely.

## Phase 4 — evidence producers and data quality

**Objective:** make A1–A5 real bounded evidence producers and remove hidden defaults.

- Wire A1 timing, A2 telemetry, A3 geometry, A4 context and A5 supervisor into the canonical input topology or retire them from the claimed architecture.
- Remove wall-clock/default measurements from atom identity paths; require raw-span records and semantic time/scope resolution.
- Model late/out-of-order watermarks, source schema changes, missing versus zero, and data-regime limitations explicitly.
- Create an effective-dated reference registry for circuit/rule datasets and provenance metadata for captures.

**Dependencies:** Phases 2–3. **Performance:** vectorise/offload only pure batch calculations; retain bounded buffers and explicit overflow results. **Acceptance:** live/replay byte-equivalent atom vectors, origin closure tests, and source coverage reports that distinguish public data from institutional claims.

## Phase 5 — tactical intelligence and fusion

**Objective:** replace demo heuristics with explainable, calibrated decision support.

- Treat EventControl/TrackState as deterministic reducers over evidence facts.
- Replace fixed VehicleResponse/TyreStrategy constants with versioned feature pipelines and calibrated baselines stratified by circuit, compound, weather and session context. Until validated, emit abstention rather than a recommendation.
- Implement Fusion as immutable event-time joins with correlation IDs, bounded windows, late-event policy, disagreement status and explicit supersession links.
- Store calibration datasets, training code/version/metrics separately from real-time execution. Require model registry, drift thresholds and deterministic fallback.
- If approved, add an explanation-only LLM adapter with retrieval citations, JSON schema validation, timeout/circuit breaker, output redaction, cost ceiling and retained prompt/model version. It must never enter integrity or fusion computation.

**Dependencies:** Phase 4. **Acceptance:** blind historical holdout tests, calibration/error metrics, permutation/order-invariance tests for fusion and fallback-latency SLOs. **Deferred:** autonomous strategy recommendations until calibrated performance and human-review workflow are accepted.

## Phase 6 — API, serving and observability

**Objective:** serve immutable audit facts and actionable operational health safely.

- Split write-side logs from read models; rebuild read models from checkpoints/logs.
- Expose verdict lineage, evidence references, finality/amendment state, data regime and model provenance; remove frontend placeholders that masquerade as measured values.
- Add trace IDs from raw record to verdict, metrics for lag/retries/DLQ/finality violations/model abstention, structured logs and alert thresholds.
- Add authentication/authorisation, restrictive CORS, request limits and SSE backpressure/reconnect semantics.

**Dependencies:** Phases 2–5. **Acceptance:** a user can navigate verdict -> admission entries -> raw span without server memory; load/soak and access-control tests pass.

## Phase 7 — integration and release gate

**Objective:** establish evidence for production claims.

- Unit/property tests: algebra laws, scope isolation, timeline/finality, revision graph, serialization and digest compatibility.
- Integration tests: producer/consumer topology, sequencer, checkpoint restore, agent/fusion event-time joins and API projections.
- Scenario tests: historical captures labelled by availability, fault injection, delayed reference, correction, poison record, broker interruption and agent restart.
- Performance tests: measured throughput/lag/latency at stated hardware/configuration; publish methodology and bounds.
- Live/replay equivalence: same immutable admission log must produce same verdict-history hashes and specified tactical outputs.

**Definition of done:** every enabled feature has a versioned contract, source/data regime, deterministic or calibrated behaviour claim, failure policy, observability and reproducible verification evidence. Documentation is regenerated from the implemented topology and no proposal is represented as completed.

## Approval decisions required

1. Approve log-first architecture and admission sequencer as the source of truth.
2. Approve replacement/consolidation of the active Kafka client path.
3. Approve retiring or wiring the disconnected A1–A5 archetype implementation.
4. Approve calibrated statistical models before any tactical recommendation; decide whether explanation-only LLM support is in scope.
5. Approve migration tolerance for hash/schema identifiers and historical replay compatibility.
