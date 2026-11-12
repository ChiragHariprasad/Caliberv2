# CALIBRE v4 Implementation and Remediation Plan

## Purpose and decision

CALIBRE v4 should become a durable, evidence-verification platform. It may replace feed-health monitoring and human-supported after-the-fact forensic workflows where its evidence supports that use. It must never claim to replace an official measurement system, determine sporting liability, or turn a threshold witness into an automatic enforcement decision.

The current repository is an implemented PULSE Formula 1 analytics application with an embedded SIA v3 integrity engine. It is not the empty implementation described by the README, and it is not yet the v4 platform. The immediate implementation target is therefore a stable v4 boundary around the existing application, not a risky rewrite of working PULSE behavior.

This document is both the migration plan and the remediation register. Items marked **implemented in this change** are complete foundation work; the remaining phases are deliberately sequenced gates, not promises that unverified data or institutional authority already exist.

## Inputs reviewed

- The supplied CALIBRE Design Rationale v4.0.
- The current PULSE documentation, backend, frontend, Kafka transport, capture files, test suite, SIA v3 core, and integrity bridge.
- Current repository behavior, not the README's historical statement that implementation has not started.

The rationale refers to `CALIBRE_Blueprint_v4_Durable_Platform.md`, but that companion blueprint was not included with the supplied attachment or present in the repository. This plan uses the rationale as the controlling design input and retains a Blueprint reconciliation task before the v4 specification is frozen.

## Present state compared with v4

| Area | Present state | v4 requirement | Change path |
| --- | --- | --- | --- |
| Product boundary | PULSE provides F1 race intelligence; SIA exposes integrity assessments. | Evidence monitoring and forensic support, never an official measurement replacement. | Reframe contracts and UI vocabulary after pack migration; add limitation banners and adoption-rung claims. |
| Domain model | `ScopeClass` and default contracts use session, driver, lap, sector, F1 providers, and F1 roles. | Packs own domain vocabulary; the kernel stays domain-neutral. | Add versioned domain packs now; migrate SIA scopes and contracts only after the pack interface is tested by a second pack. |
| History | Kafka and local capture directories are used as operational history. Some raw topics have seven-day retention. | Immutable object-store-style archive is the record; Kafka is transport. | Use v4 archive bundles for every capture/replay now; add object-store adapter and retention policy in Phase 2. |
| Hashes | SIA IDs and manifests commonly use untagged SHA-256 strings. | Algorithm-tagged digests and chain renewal support. | Emit tagged `sha256:` digests at the archive boundary now; retain a read-only legacy adapter for bare v3 hashes; design renewal records before production logs. |
| Time | SIA has typed time classes but absolute instants imply UTC and have no leap-second-table reference. | Explicit time scale and table reference in durable records. | Require a `TimeScaleReference` in every v4 archive now; carry it into event envelopes and evaluator capsules in Phase 1b. |
| Rules and layouts | F1 contracts contain static limits, references, and scope assumptions. | Effective-dated rule-regime facts and layout/calibration references are evidence. | Introduce effective-dated reference registry now; bind references at decision-open in the SIA adapter in Phase 1b. |
| Thresholds | The pit-speed contract compares values but cannot make uncertainty visible as a witness. | Margin versus combined uncertainty, with policy left to people. | Provide a policy-neutral threshold witness now; use it in the F1 pack and dashboard only after measured tolerances are approved. |
| Execution | Kafka/Flink services and in-memory paths are implementation centers. | Execution profiles, mandatory batch replay, thin replaceable streaming tier. | Define profile contract and deterministic batch runner in Phase 2; keep current Flink code behind an adapter. |
| Reproducibility | SIA has hash chains and tests; no portable clean-machine bundle/verifier/capsule requirement. | Archive, pinned evaluator capsule, standalone verifier, corpus replay. | Create self-verifying standard-library bundle now; add capsule generation and CI clean-machine test in Phase 1b. |
| Evidence regimes | Existing modes are simulated, replay, and live. Provenance exists but claims do not model PUBLIC/LICENSED/INSTITUTIONAL/LAB. | Data regime changes permissible claims, not architecture. | Add regime field to bundles now; enforce regime contract profiles in Phase 2. |
| Specifications | Tests act as behavior documentation. | Open specification suite and conformance corpus, then a second implementation. | Extract normative v1.0 specs and golden vectors in Phase 1b; do not declare the code itself the specification. |

## Findings and required fixes

| ID | Finding | Risk | Required fix | Status |
| --- | --- | --- | --- | --- |
| V4-01 | README says backend/frontend contain no application code, while both are implemented. | New contributors follow a false starting point. | Replace the status and recovery sections after the v4 migration inventory is approved. | Planned |
| V4-02 | Current documentation is PULSE-v0.1-centric and conflicts with current source layout and v4 scope. | Design drift and misleading operational claims. | Make this plan the current migration record; reconcile docs 00–11 against code and then retire or annotate superseded sections. | In progress |
| V4-03 | The companion v4 Blueprint referenced by the rationale is absent. | Several section references and acceptance gates cannot be verified. | Obtain it and run a section-by-section reconciliation before freezing Spec v1.0. | Blocked on supplied artifact |
| V4-04 | Core scope classes and default contracts are F1-shaped. | A second domain would require kernel edits, violating L-1/L-7. | Put scope hierarchy in a versioned `DomainPack`; migrate the SIA schema after a second pack exercises it. | Foundation implemented |
| V4-05 | The bridge maps providers to F1-specific origin names and legacy `OPENF1`, although older docs exclude OpenF1. | Provider policy is inconsistent and common-cause analysis can be misrepresented. | A source-pack lineage graph and F1 reference pack now exist; move bridge aliases/approval decisions into it. | Foundation implemented; bridge migration planned |
| V4-06 | Public providers share an F1 timing upstream, but several contracts make corroboration appear possible. | A user may mistake duplicate public feeds for independent evidence. | Public source pairs are now non-independent by construction; enforce source-pack profile outcomes in the bridge and UI. | Foundation implemented; runtime enforcement planned |
| V4-07 | Raw-stream retention is short and a Kafka transport implementation is presented as durable history. | A source change or broker loss can make old results unreproducible. | Archive immutable raw entries, manifest, reference pack, outputs, and verifier before relying on a replay. | Foundation implemented |
| V4-08 | Bare SHA-256 strings are ambiguous across future algorithms and cannot express renewal. | Archives cannot evolve safely after cryptographic deprecation. | Require tagged digests at v4 boundaries and model renewal/anchors in Spec v1.0. | Foundation implemented; renewal planned |
| V4-09 | Absolute time lacks a durable time-scale/leap-table declaration. | Decade-scale replay can silently use changed conversion assumptions. | Require time-scale and leap-second-table id/version in every archive; preserve them in replay/decision records. | Foundation implemented; propagation planned |
| V4-10 | Rule parameters and layout/calibration inputs are not consistently effective-dated evidence. | The wrong season/regime can be evaluated without detection. | Resolve unambiguous effective-dated references at decision opening and archive their IDs. | Foundation implemented; SIA binding planned |
| V4-11 | Existing numeric comparisons do not surface the guard band around zero-tolerance thresholds. | A tiny margin can be presented as certain despite measurement uncertainty. | Emit a witness with observed value, threshold, margin, combined uncertainty, and no automatic sanction. | Foundation implemented |
| V4-12 | No evaluator capsule or standalone clean-machine verifier exists. | A verdict may depend on a vanished repository or runtime. | Package a standard-library verifier with each archive, then add pinned evaluator capsules and CI clean-machine verification. | Foundation implemented; capsule planned |
| V4-13 | Error handlers use broad `except ...: pass` in several runtime modules. | Operational failures can be silently hidden. | Replace each with a bounded, logged recovery action or a propagated failure; cover recovery paths with tests. | Planned remediation sweep |
| V4-14 | Full tests did not complete within the baseline window because browser/integration tests require longer-lived infrastructure. | A green unit subset can be mistaken for whole-system verification. | The deterministic batch profile now verifies archives and produces stable replay input results; split remaining infrastructure/browser jobs with explicit timeouts. | Partially implemented |
| V4-15 | The SIA bridge mutates `sys.path` to import a sibling implementation. | Packaging, second-implementation testing, and capsules are fragile. | Package SIA as a normal dependency or isolate it behind a stable evaluator adapter. | Planned |
| V4-16 | Current contracts embed tolerance values without a recorded calibration source. | Values can look authoritative though the rationale says they remain placeholders. | Add a calibration/reference record requirement and display `UNCALIBRATED` when values lack approved evidence. | Planned |
| V4-17 | PULSE agent names encode their F1 feeds and job responsibilities. | Source churn forces conceptual churn. | Replace with Measurement, Asset Telemetry, Spatial, Context, and Supervisor archetypes implemented by packs. | Planned |

## Architecture target

The durable waist is: `raw entries -> archive manifest -> pack and effective references -> deterministic evaluator -> assessments and revision chain -> verifier bundle`. Kafka, Flink, FastAPI, React, provider adapters, learned advisory models, and even the current Python evaluator are execution-profile details outside this waist.

Every archive must contain: immutable raw payloads; a tagged-digest manifest; pack id/version; data regime; explicit time-scale and leap-table reference; effective reference IDs; evaluator capsule identifier; output artifacts; and a standard-library verifier. A bundle must validate without the repository, network access, Kafka, or an installed application dependency.

## Implemented foundation

The `calibre_core` package now provides these v4 Day-0 facilities:

1. Tagged durable `sha256:` digests, canonical JSON serialization, and explicit recognition of legacy bare hashes only when requested.
2. `DataRegime` and `TimeScale` types with required leap-second-table identifier/version.
3. Versioned `DomainPack` scope validation so a new domain vocabulary is not added to the kernel.
4. Effective-dated `ReferenceRegistry` for rule regimes, surveyed layouts, calibration records, and other references. Ambiguous active references fail closed.
5. Policy-neutral `ThresholdWitness` that classifies margin versus combined uncertainty as below, above, or indeterminate, without declaring compliance or a penalty.
6. Immutable archive bundle creation. It copies explicit payloads, emits a manifest, refuses to overwrite an archive destination, validates paths, and includes a standard-library-only `verify_bundle.py`.
7. Tests for digest migration behavior, guard-band arithmetic, effective-date/ambiguity behavior, clean-machine verifier execution, and tamper detection.
8. A source-pack lineage graph with regime-specific permitted claims. The F1 reference pack models the common public F1 timing upstream and only recognizes independent corroboration for approved, distinct institutional origins.
9. A mandatory `batch-v1` profile that verifies an archive and deterministically accounts for every NDJSON input record without using Kafka, Flink, wall-clock time, or network access.
10. An explicit `archive_legacy_capture` migration utility. It defaults legacy PULSE capture folders to `LAB`, includes source-pack and empty-effective-reference records, and refuses to silently upgrade their data-regime claim.

## Delivery sequence and exit gates

### Phase 0 — evidence and migration inventory

- Obtain the missing Blueprint and reconcile every rationale reference.
- Inventory providers, licensing, source terms, cadence/noise/units, existing capture provenance, and all public claims.
- Inventory every existing PULSE/SIA schema, topic, capture, and endpoint to classify as retain, adapter, migrate, or retire.
- Establish the two-person reviewer for contracts and reference packs.

**Exit G0:** approved source register, licensing note, migration inventory, and no unqualified claim that a public source is independent.

### Phase 1a — archive pilot and v4 boundary

- Produce an archive for one LAB capture and one approved historical capture.
- Include raw entries, pack manifest, effective references, result set, time-scale reference, and standalone verifier.
- Verify both on a clean environment; tamper tests must fail.
- Publish the explicit legacy mapping for existing v3 bare hashes rather than rewriting old evidence IDs.

**Exit G1:** reproducible bundle checks pass; no archive is produced without tagged digest, time scale, pack, regime, and verifier.

### Phase 1b — freeze the Day-0 specification

- Write normative JSON schemas for atom, reference, assessment, archive, pack, digest-renewal record, and evaluator capsule.
- Write behavior specifications for scope matching, effective-date selection, typed-time conversion, uncertainty witnesses, finality, revision chaining, and legacy upcasting.
- Extract a versioned golden corpus from SIA/PULSE tests; add explicit Monaco data only as a blind case, never the acceptance benchmark.
- Bind pack/reference versions to decision open and persist those bindings in outputs.
- Define the change-control rule: semantic change requires a major schema/spec version plus corpus diff report.

**Exit G2:** two reviewers approve Spec v1.0; all corpus vectors pass; a clean-machine bundle includes a pinned evaluator capsule.

### Phase 2 — profiles and packs

- Extend the implemented deterministic batch profile from input accounting to specification-defined domain evaluation as the evaluator boundary is frozen.
- Move Kafka/Flink behavior behind an execution-profile interface; retain the existing profile as an adapter, not architecture.
- Replace hard-coded origin aliases with source-pack lineage graph and approval status.
- Implement the F1 reference pack using measured, evidence-linked calibrations only.
- Build a minimal second timed-domain pack to prove the pack boundary before generalizing the kernel.
- Add PUBLIC, LICENSED, INSTITUTIONAL, and LAB contract profiles and permitted-claim banners.

**Exit G3:** batch replay is deterministic, two packs run without kernel edits, and profile claims correctly degrade under PUBLIC data.

### Phase 3 — operating model and benchmark

- Create the 17-class taxonomy and held-out living benchmark; retain Monaco as one blind case.
- Establish annual pack review, calibration review, corpus growth, override audit, and semiannual execution-profile upgrade drill.
- Add drift sentinel using approved reference baselines; learned detectors remain advisory inputs outside the trust boundary.
- Produce adoption-rung evidence: monitoring (0–1), forensic support (2), institution-gated evidence gate/standard (3–4).

**Exit G4:** benchmark and maintenance calendar run successfully; public documentation states data-regime and authority limits beside every conclusion.

### Horizon 2 — independent implementation and cryptographic renewal

- Build a second evaluator solely from Spec v1.0 and the corpus; perform differential tests and resolve specification ambiguities.
- Add digest-chain renewal records, timestamp/anchor policy, and a verifier that validates old and renewed anchors.
- Review whether the current Python SIA implementation becomes the reference kernel, an adapter, or is replaced.

**Exit G5:** independent implementation passes corpus and any semantic differences are approved specification changes, not silent code drift.

## Migration safeguards

- Do not rename or rewrite historical SIA content-addressed IDs. Archive both the original and an explicitly tagged legacy mapping.
- Do not use `PUBLIC` data to claim independent-source corroboration; report the common-cause limitation.
- Do not insert a synthetic measurement where a raw source is missing. LAB is a declared regime, not a substitute for observed evidence.
- Do not treat `ABOVE_THRESHOLD` as a violation. It is a numeric witness for an authorized human process.
- Do not retire Kafka/Flink, frontend, or the SIA core until batch replay, golden corpus, and archive verification prove the replacement path.
- Do not freeze v1.0 until the missing Blueprint is reconciled and the Day-0 records have been independently reviewed.

## Verification matrix

| Check | Evidence | Frequency |
| --- | --- | --- |
| Unit behavior | `calibre_core` tests and SIA/PULSE fast tests | Every change |
| Archive integrity | Manifest, payload, path-safety, and tamper tests | Every archive build |
| Clean-machine replay | Bundled verifier and pinned evaluator capsule | Every release/archive class |
| Semantic stability | Golden corpus result and major-version diff report | Every release |
| Source legitimacy | Source register, licence status, lineage graph | Before each new source/season |
| Rule validity | Effective-date reference review with two-person approval | Before each rule/layout change |
| Execution churn | Batch parity and Flink/Kafka upgrade drill | Twice yearly |
| Trust/overclaiming | Regime banner, limitations, override audit | Every UI/report release |

## Acceptance criteria for this implementation increment

- A v4 archive cannot be silently overwritten, cannot include traversal paths, and fails verification after payload tampering.
- New manifest and entry digests are tagged; legacy bare hashes are accepted only through an explicit compatibility option.
- Archives require a declared time scale and leap-second table reference.
- A reference lookup fails closed when more than one active record applies.
- A 0.1 km/h margin with 0.11 km/h uncertainty is reported as indeterminate, not automatically compliant or noncompliant.
- The copied verifier runs with only Python's standard library.
- The fast v4 foundation test suite passes.
