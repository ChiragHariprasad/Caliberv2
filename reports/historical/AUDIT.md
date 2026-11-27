# CALIBRE V2 — Static Engineering Audit

**Date:** 22 November 2026
**Method:** Read-only static inspection; no application, tests, services, scripts, brokers or dependencies were executed.
**Confidence convention:** Code-path findings are static findings. Runtime properties, performance, broker behaviour, data coverage and prior test claims are **Unverified — Requires Runtime Validation**.

## Executive conclusion

**SIA Core v3 is sound but incomplete as a standalone deterministic evaluator (classification 2).** It has a coherent four-state order, explicit scope checks, typed-time conversion, contract validation, deterministic diagnosis and hash-chain revisions. It is not yet a production integrity system because its admission, state and finality semantics are process-local, and its integration bridge does not populate many required contracts safely.

**PULSE is a demonstration-oriented tactical pipeline, not a production distributed decision platform.** The specialist agents are deterministic heuristics with substantial hard-coded defaults; fusion produces pre-written tactical narratives. The active Kafka path does not use the repository's advanced Kafka utility layer. Documentation previously overstated completion and conflated the archetype and PULSE agent systems.

## Inspection inventory

Inspected statically: all seven pre-existing `docs/*.md` files; root README; all SIA kernel modules; CALIBRE admission/archive/contract/agent modules; backend contracts, config, main topology, normalizer, both Kafka implementations, replay processor/controller, state store, integrity bridge/contracts/agent/router, PULSE agent implementations, API surfaces, deployment configuration, dependency manifests, frontend API/integrity surfaces and static fallback references, source/test inventories and Git status.

Not executed or validated by design: Python/Node code, test suite, Kafka/Flink containers, data acquisition, browser artifacts, prior report metrics, external source claims and every historical capture. Binary FastF1 caches, image screenshots and package-lock internals were inventoried but not semantically decoded; they cannot establish an execution guarantee.

## Scorecard (0–4)

| Subsystem | Score | Evidence and judgement |
|---|---:|---|
| SIA algebra, contracts and evaluator | 3 | Total order and timeline algebra in `algebra.py:23-151`; scope/provenance model in `model.py:21-108`; deterministic evaluator pipeline in `evaluator.py:1-679`. Bounded searches and contract limits are explicit. |
| SIA admission, lifecycle and persistence | 2 | Monotonic in-memory ledger in `ledger.py:52-140`, finality/revision handling in `engine.py:94-178`. No durable atomic admission/state store in active application and no concurrency control. |
| PULSE SIA integration | 1 | Five local contracts in `backend/pulse/integrity/contracts.py:27-270`; bridge maps selected event types only in `bridge.py:67-129`. Required references/roles are not populated end-to-end. |
| Evidence archetypes A1–A5 | 2 | Real files exist under `calibre_core/agents`, but are detached from the PULSE topology; purity and provenance claims are undermined by defaults and diagnostics using `datetime.now` in `agents/base.py:39-46`. |
| PULSE specialist/fusion intelligence | 1 | Rule-only logic and seeded baselines in `vehicle_response.py:29-41`, default tactical values in `fusion.py:204-257`, mutable unbounded correlations in `fusion.py:39-45`. |
| Kafka topology and delivery semantics | 1 | Active client creates one-partition, RF=1 topics (`kafka_client.py:65-77`) and auto-commits (`:92-108`). Advanced module is not in active imports. |
| Ingestion and normalisation | 2 | Pydantic schema gate and event ID filter (`normalizer.py:28-73`) are useful. No durable deduplication, watermarking, schema evolution policy, validation provenance or source-data quality isolation. |
| Replay and recovery | 2 | Shared local processing path and seek reset (`replay/controller.py:307-386`) are credible. Random lineage IDs and no snapshots/offset restore prevent deterministic recovery claims. |
| Serving, observability, security | 1 | REST/SSE and basic metrics exist. State is memory-only, SSE drops old queue entries, CORS permits all origins in `main.py:303-309`, and no authenticated operational boundary is present. |
| Documentation | 1 | Existing docs contain mutually contradictory completion claims; `docs/AUDIT.md` described already-implemented files as absent, while other pages claimed unsupported capabilities. |

**System-wide maturity: 1/4.** Good component prototypes do not compose into a durable, replayable, end-to-end defensible service.

## SIA core audit

### What is genuinely strong

- The integrity algebra is explicit rather than merely branding: `and_state`/`or_state`/`k_of_n_state` and lifted state sets are defined in `sia_core_v3/sia_core/algebra.py:38-90`.
- Scope locality is mechanically checked by `scope_in` and `scope_covers` (`model.py:52-67`). Evidence is content-addressed and records source plus processing origins (`model.py:128-189`).
- Contract parsing/validation rejects missing roles, invalid formula shapes, illegal scope/time combinations and invalid corroboration claims (`contract.py:216-276`, `:321-394`).
- The evaluator models absence, freshness, typed-time references, agreement, diagnosis, resilience and finality as separate concepts (`evaluator.py:259-679`). Assessment content and chronological record hashes are deliberately distinct (`verdict.py:121-144`).

### Material weaknesses

1. **Identity is deterministic but revisions are only partially modelled.** Evidence supersession picks a transform-version/atom-ID winner (`evaluator.py:155-171`) without validating supersession lineage, cycles, authority, revision ordering or correction reason. Facts similarly drop only explicitly superseded IDs. Consequence: two conflicting “latest” corrections can remain admissible and move a verdict to `SUSPECT` rather than being governed by a deterministic correction policy.
2. **Post-finality is observational, not a quarantine boundary.** Items are admitted first and then `_check_finality` adds a log record (`engine.py:75-105`). They cannot change the sealed decision, but remain in the ledger and can affect other scopes. Required fix: admission router must route post-finality evidence to a quarantine stream/store before normal ledger admission, with explicit re-open/amendment policy.
3. **Void content is schema-inconsistent.** `void_decision` uses `maturity_status` and a numeric `state` whereas regular evaluation emits `resolution_maturity` and string envelopes (`engine.py:133-148` versus `evaluator.py:660-678`). API/UI consumers can observe divergent shapes.
4. **Kernel hash format conflicts with durable layer.** SIA uses bare SHA-256 hex (`canon.py:154-155`), but durable artifacts mandate tagged digests (`calibre_core/durable.py:49-65`). Cross-layer verification is therefore not one integrity model.
5. **The claimed decision state machine is not persisted.** Instance registration, ledger, revisions, sealed state and evaluation clock live in dictionaries/lists (`engine.py:28-39`), so process restart, multi-worker access and concurrent admission are ungoverned. **Unverified — Requires Runtime Validation** for race conditions, but no lock/transaction is present statically.

### Evidence lifecycle verdict

Scope isolation is strong within the evaluator, provided scopes are supplied correctly. The PULSE bridge can build only session/driver/lap/sector scope from packet fields (`bridge.py:170-212`) and many streams omit those fields. It does not bind raw spans, revision authority, source-capture hash or durable sequence. Thus, SIA can evaluate well-formed evidence but PULSE does not reliably produce a complete evidentiary record.

## Multi-agent audit

The active PULSE agents are **not independent reasoning agents**. They are event handlers with mutable state and if/else classification. For example, VehicleResponse has five driver-specific baseline values and default intervals (`vehicle_response.py:29-41`, `:126-144`); Fusion emits hard-coded savings, forecasts and `BOX_THIS_LAP` recommendation if inputs omit values (`fusion.py:204-257`). This is useful as a UI scenario demonstrator but unsuitable as calibrated sports analytics.

| Current agent | Assessment | Required direction |
|---|---|---|
| EventControl | Parses known event types and emits lifecycle/exposure findings. | Convert to a versioned, event-sourced session-state reducer; no inferred driver exposure without position/time evidence. |
| TrackState | Translates payload weather/status fields. | Keep deterministic; add source quality, location/time coverage and no invented sector defaults. |
| VehicleResponse | Heuristic pace classifier. | Replace fixed baselines with session-conditioned deterministic/statistical model; produce calibrated residuals and abstain on insufficient inputs. |
| TyreStrategy | Fixed compound slopes and scenario calculations. | Use an offline-trained, versioned model only after a data-quality gate; preserve deterministic fallback. |
| Fusion | Formats conditional narratives/revisions. | Make it a deterministic policy reducer over versioned findings; bounded correlation windows, event-time joins and explicit conflict states. |
| Integrity | Useful SIA adapter. | Feed it only sequenced evidence/admission events, not ad-hoc normalised packets. |

LLMs should not participate in integrity determination, ordering, finality or live forecast calculations. A hosted/local LLM may be added later for operator explanation or retrieval over regulations only, with schema-constrained output, prompt/model version, timeout, cost budget and a deterministic non-LLM fallback. Statistical forecasting is appropriate for tyre/pace residuals only after labelled, partitioned historical evaluation; deterministic methods remain superior for state reduction, validation, provenance and evidence admission.

## Kafka and pipeline audit

The repository contains two divergent designs. `kafka_io.py` describes idempotence, transactions, `read_committed`, DLQ and driver partitions, but the runtime imports `KafkaBroker` from `kafka_client.py` (`bus.py:11`, `main.py:233`). The runtime producer only sets `acks="all"`; topics are created one partition/RF=1; the backend consumer auto-commits. Therefore the deployed topology cannot claim partition affinity, exactly-once processing, durable DLQ, consumer recovery or an end-to-end transaction.

The key `session:driver` preserves relative order only inside a Kafka partition if it is actually used by a correctly configured producer and all causally related events share that key. Track-wide events use session/segment keys, while fusion joins cross-topic and cross-partition findings in memory. No join watermark or offset/vector coordination exists. Recommendation: select a session-affine key for decision/evidence sequencing first; use driver-affine partitions only for independent analytical work. A dedicated sequencer must restore one deterministic admission order for SIA.

## Replay, recovery and data audit

Replay resets and locally rebuilds state with `publish=False`, which avoids deliberately duplicating raw records. It creates a random run ID on reset/seek (`replay/controller.py:198`, `:228`, `:350`) and resets the normalizer, agents and in-memory state. There are no snapshots, consumed-offset checkpoints, Kafka seek/replay orchestration, persisted agent state or evidence admission log in the active path. Live versus replay equivalence is therefore **Unverified — Requires Runtime Validation** and structurally not guaranteed.

The normalizer’s event-id set is process-local and unbounded. It neither protects against semantically duplicate IDs nor preserves invalid/rejected raw payloads as auditable records. Capture and corpus files exist, but the audit did not execute or externally validate their provenance/coverage.

## Findings register

| ID | Severity | Subsystem | Current behaviour and evidence | Proposed fix | Priority / validation |
|---|---|---|---|---|---|
| F-001 | Critical | Kafka | App uses `kafka_client.py`, not transaction/idempotence utilities. | Adopt one runtime transport implementation; transactional consume-transform-produce plus idempotent sink. | P0; broker failure/rebalance/duplicate tests. |
| F-002 | Critical | SIA integration | Bridge only maps five tactical contracts; missing reference facts/roles cause incomplete decisions. | Sequence evidence through admission log; activate only contracts with complete producer wiring. | P0; contract-to-producer conformance tests. |
| F-003 | Critical | State/recovery | Ledger, index, agents and StateStore are volatile. | Persist append-only admission log and checkpoints; reconstruct all state exclusively from them. | P0; crash/restart and replay equivalence. |
| F-004 | High | Finality | Post-finality items are admitted before logging. | Quarantine before evaluator ledger; controlled amendment workflow. | P1; late-correction cases. |
| F-005 | High | Agents | Tactical heuristics generate conclusions from defaults. | Remove defaults from decision paths, calibrate deterministic models, explicit abstention. | P1; labelled backtest and calibration. |
| F-006 | High | Fusion | Unbounded buffers and mutable historical objects; no event-time joins. | Windowed immutable reducer, correlation key and watermark policy. | P1; ordering/permutation/property tests. |
| F-007 | High | Contracts | Two contract catalogues disagree; PULSE five vs CALIBRE C01–C13. | One versioned catalogue and activation manifest. | P1; schema/coverage validation. |
| F-008 | Medium | SIA schemas | Void output differs from normal assessment; digest formats diverge. | Canonical assessment schema and tagged digest migration. | P2; serialization compatibility vectors. |
| F-009 | Medium | Normalization | Event-ID-only, volatile dedup and permissive fallback routing. | Raw immutable capture, canonical ID/content digest, schema registry, rejection stream. | P2; source/order/duplicate tests. |
| F-010 | Medium | Security/API | Open CORS and in-memory fan-out. | Authn/authz, rate limits, durable read model, SSE backpressure policy. | P2; security and soak tests. |
| F-011 | Medium | Documentation | Claims of production completion conflict with code. | Maintain this hierarchy; CI checks links and contract/topology assertions. | P2; doc/source conformance review. |
