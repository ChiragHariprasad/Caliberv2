# CALIBRE / PULSE: Comprehensive Project Evolution & Architectural Decision Record

This document provides the authoritative chronological history, archaeological reconstruction, and engineering decision record of the CALIBRE and PULSE platforms, tracing their evolution from the original CALIBRE system (`E:\CALIBER`) to the modern CALIBRE v4 durable evidence verification platform (`E:\Caliberv2`).

---

## Part I: Chronological History & Archaeological Reconstruction

```
+-----------------------------------------------------------------------------------------------------------------+
|                                           PROJECT EVOLUTION TIMELINE                                            |
+-----------------------------------------------------------------------------------------------------------------+
|                                                                                                                 |
|  2024 - Early 2025: Original CALIBRE (`E:\CALIBER`)                                                             |
|  * Focus: Bitemporal evidence verification for telemetry compliance.                                            |
|  * Tech: SQLite bitemporal ledger, Python SIA v2.2 pure evaluator, Apache Flink on WSL2.                        |
|  * Limitations: Rigid environment coupling (WSL/Linux), monolithic verification rules, no user dashboard.       |
|                                                                                                                 |
|  Mid 2025 - Late 2025: Evolution into PULSE (`E:\Caliberv2`, branch `main`)                                     |
|  * Focus: Real-time Formula 1 streaming intelligence and tactical consequence forecasting (1-3 laps ahead).     |
|  * Tech: Apache Kafka (KRaft), 5 specialist agents, FastAPI, React 18 / Vite tactical cockpit.                  |
|  * Breakthroughs: Multi-agent consequence fusion, out-of-order finding resolution, revision chains (v1 -> v2).   |
|                                                                                                                 |
|  Early 2026: Convergence & SIA Integration (`E:\Caliberv2`, branch `kafka-v2`)                                  |
|  * Focus: Grounding predictive AI in deterministic mathematical evidence.                                       |
|  * Tech: Embedding SIA v3 as `agent-06-integrity` directly into the active streaming state store.              |
|  * Dual-Transport: Abstracting Kafka behind `PulseEventBus` for zero-dependency deterministic local simulation. |
|                                                                                                                 |
|  Late 2026: CALIBRE v4 Durable Evidence Verification Platform                                                   |
|  * Focus: Generalizing beyond F1 streaming into a high-assurance, durable, multi-regime evidence platform.       |
|  * Tech: Domain-tagged cryptographic hashes (BLAKE3/SHA-256), effective-dated references, continuous           |
|    uncertainty witnesses with guard bands, self-contained archive bundles (.tar.zst), offline verifier CLI.     |
|                                                                                                                 |
+-----------------------------------------------------------------------------------------------------------------+
```

### 1. The Original CALIBRE System (`E:\CALIBER`)
The original CALIBRE project was created to solve a specific problem in telemetry-based adjudication: **verifying whether physical vehicle telemetry complied with sporting and technical regulations using an immutable, bitemporal ledger**.
- **Original Architecture:** Built around a pure Python evaluator (`sia_core`), a bitemporal SQLite fact database, and an Apache Flink stream-processing pipeline running under Windows Subsystem for Linux (WSL2).
- **Core Limitations:**
  1. *Host Environment Fragility:* Hard dependencies on WSL2, Java runtimes, and local Linux shell scripts made cross-platform execution unreliable.
  2. *Monolithic Adjudication:* Verification rules evaluated events post-hoc without real-time streaming feedback or predictive awareness.
  3. *Absence of User Interface:* Adjudications were reported solely via console logs and database queries; there was no interactive visual interface for race engineers or stewards.

### 2. The Strategic Pivot to PULSE (`E:\Caliberv2`)
To address these limitations, the project pivoted to **PULSE**: a real-time race intelligence engine designed to provide tactical decision support during active sessions.
- **The Core Innovation:** Instead of merely validating historical rules, PULSE actively projected tactical consequences 1 to 3 laps into the future (e.g., pit stop loss deltas, undercut/overcut windows, and safety car neutralisation exposure).
- **Architecture Expansion:**
  - Introduced Apache Kafka (KRaft mode) with fine-grained topic segregation (raw vs normalized vs agent findings vs fused intelligence).
  - Deployed 5 decoupled specialist intelligence agents: Event Control, Vehicle Response, Track State, Tyre Strategy, and Consequence Fusion.
  - Implemented a modern React 18 / TypeScript tactical cockpit with real-time SVG circuit maps and Server-Sent Events (SSE) streaming.

### 3. Re-Integration of SIA & Convergence
During the development of PULSE, an epistemic risk was identified: **uncalibrated predictive models and heuristic forecasts could be mistaken by operators for verified ground facts**.
- To prevent this, the SIA integrity engine was re-integrated as **`agent-06-integrity`**.
- Operating directly on canonical event streams, Agent 06 executes deterministic mathematical assertions (e.g., lap time continuity, pit lane speed limits, and micro-sector monotonic progression).
- The state store and frontend UI were enhanced to explicitly separate Ground Truth (`OBSERVED`), Analytical Metrics (`DERIVED`), and Model Hypotheses (`INFERRED`).

### 4. Genesis of CALIBRE v4
While PULSE succeeded as a streaming F1 cockpit, the overarching need for a generalized, durable evidence verification platform remained. CALIBRE v4 was formally specified to decouple evidence verification from transient streaming brokers:
- **Domain-Tagged Hashes:** Cryptographic hashing with explicit domain prefixes to prevent collision attacks across data types.
- **Effective-Dated Reference Registry:** Immutable historical registry for track layouts, sporting regulations, and sensor specifications with strict validity intervals.
- **Continuous Uncertainty Witness:** Non-linear sigmoid scoring replacing arbitrary hard-clamped binary gates.
- **Self-Contained Archive Bundles (`.tar.zst`):** Portable, signed audit packages containing all events, references, and proof DAGs.
- **Offline Standalone Verifier:** A zero-dependency CLI capable of verifying archives decades into the future without databases or network services.

---

## Part II: Architectural Decision Records (ADR-001 to ADR-020)

### ADR-001: Separation of Live Transport from Historical Ingestion
- **Context:** Historical data acquisition from FastF1/FIA APIs operates in large batches, whereas live telemetry arrives as millisecond-level micro-bursts.
- **Decision:** Decouple data acquisition into an offline capture phase producing immutable JSONL manifests and envelopes, separate from the real-time event streaming pipeline.
- **Trade-off:** Requires disk storage for capture bundles (`captures/`), but guarantees deterministic, repeatable replay identical to live execution.
- **Status:** Active & Validated.

### ADR-002: Dual-Transport Abstraction (Deterministic Simulator vs Kafka/Flink)
- **Context:** Kafka and Flink introduce significant operational overhead and JVM/Docker dependencies during local development and automated testing.
- **Decision:** Abstract event publication and subscription behind the `PulseEventBus` interface. Provide two interchangeable implementations: a local in-memory async bus (`SIMULATOR`) and a distributed Kafka broker (`KAFKA`).
- **Trade-off:** Dual code path for event dispatching; requires rigorous test parity across both transports.
- **Status:** Active & Validated.

### ADR-003: Multi-Agent Specialization over Monolithic Predictor
- **Context:** Predicting race outcomes with a single monolithic model creates an uninterpretable "black box" where failures cannot be attributed to specific factors.
- **Decision:** Partition analytical responsibilities into isolated, single-concern specialist agents (Event Control, Vehicle Response, Track State, Tyre Strategy) coordinated by a deterministic Consequence Fusion Engine.
- **Trade-off:** Increased message passing and serialization overhead across agent topics; requires robust out-of-order reconciliation.
- **Status:** Active & Validated.

### ADR-004: Explicit Epistemic Data Taxonomy
- **Context:** Race engineers and stewards make catastrophic errors when machine learning predictions are presented with the same authority as physical sensor measurements.
- **Decision:** Every finding and assessment must be explicitly tagged as `OBSERVED` (ground truth sensor fact), `DERIVED` (deterministic calculation), or `INFERRED` (probabilistic/heuristic model output).
- **Trade-off:** More verbose data schemas; frontend must render distinct visual badges (`UNCALIBRATED HEURISTIC`).
- **Status:** Active & Validated.

### ADR-005: Consequence Revision Chains (v1 Provisional -> v2 Confirmed DAG)
- **Context:** Under sudden race neutralisations (VSC, Safety Car), drivers have only seconds to react before passing pit entry. Complex tyre strategy algorithms take 100-200ms to converge.
- **Decision:** Implement a two-stage revision DAG. Agent 05 emits an immediate **Provisional Assessment v1** upon neutralisation detection, followed by a **Confirmed Assessment v2** superseding v1 once tyre calculations complete.
- **Trade-off:** Consumers must handle superseding event semantics and update UI cards dynamically.
- **Status:** Active & Validated.

### ADR-006: Out-of-Order Multi-Agent Arrival Resilience
- **Context:** Due to network jitter or asymmetric CPU load, Agent 04 (Tyre) findings may occasionally arrive before Agent 01 (Event Control) findings.
- **Decision:** Agent 05 buffers partial findings in a correlation map and retroactively synthesizes provisional baselines if a dependent finding arrives out of order, preserving the invariant that `v2` always has a valid `supersedes_assessment_id`.
- **Trade-off:** Small memory buffer required in Agent 05 state.
- **Status:** Active & Validated.

### ADR-007: Seek-Reconstruction via Canonical Processor without Broker Duplication
- **Context:** Scrubbing the replay timeline backward or forward requires rebuilding agent state up to the target event cursor.
- **Decision:** `ReplayController.seek()` rewinds StateStore and fast-replays events through `ReplayEventProcessor` with `publish=False`. Events are processed locally by agent handlers without republishing raw or canonical records to the Kafka broker.
- **Trade-off:** CPU load during fast-replay seeking; prevents polluting live Kafka topics or triggering duplicate downstream alerts.
- **Status:** Active & Validated.

### ADR-008: Bitemporal State Ledger with Replay Lineage Isolation
- **Context:** Repeated seek and replay operations can cross-contaminate state if events from an abandoned playback run arrive late.
- **Decision:** Every seek or reset operation generates a fresh unique `run_id` (e.g., `run-monaco-e2f3ca`). StateStore partitions metrics and assertions by `run_id`. Stale events carrying older run IDs are dropped immediately.
- **Trade-off:** Requires generating and tracking run identifiers across all envelopes.
- **Status:** Active & Validated.

### ADR-009: Domain-Tagged Cryptographic Hashes (CALIBRE v4)
- **Context:** In untagged cryptographic hash trees, an event payload hash could mathematically collide with or masquerade as a finding or state root hash.
- **Decision:** Enforce domain separation prefixes on all hash calculations: `CALIBRE-EVT-v4` for raw events, `CALIBRE-FND-v4` for findings, `CALIBRE-STA-v4` for state roots, and `CALIBRE-BND-v4` for archive manifests.
- **Trade-off:** Requires custom hashing wrappers rather than bare `hashlib.sha256()`.
- **Status:** Active & Validated.

### ADR-010: Effective-Dated Reference Registry (CALIBRE v4)
- **Context:** Sporting regulations, track layout distances, and sensor calibration curves change over time. Validating a 2023 session against 2026 rules yields false violations.
- **Decision:** Implement an immutable reference registry where every regulation, track geometry, and vehicle baseline is tagged with an effective validity interval: `[effective_from_utc, effective_to_utc)`.
- **Trade-off:** Registry lookups must include event timestamps.
- **Status:** Active & Validated.

### ADR-011: Continuous Uncertainty Witness over Step-Function Hard Clamping
- **Context:** Binary pass/fail thresholds (e.g., pit speed limit strictly 80.0 km/h) fail to account for radar measurement variance (e.g., 80.05 km/h +/- 0.1 km/h).
- **Decision:** Replace step-function thresholds with a continuous sigmoid uncertainty witness incorporating explicit guard bands (nominal, warning band, violation zone).
- **Trade-off:** Requires floating-point probability calculations rather than simple boolean checks.
- **Status:** Active & Validated.

### ADR-012: Self-Contained Archive Bundles with Offline Standalone Verifier
- **Context:** Long-term archival evidence must remain verifiable decades after specific Kafka clusters, Docker engines, or database instances have been retired.
- **Decision:** Package validated session data into standalone Zstandard tarballs (`.tar.zst`) accompanied by a zero-dependency Python verifier CLI.
- **Trade-off:** Archive creation step required at session completion.
- **Status:** Active & Validated.

### ADR-013: Transparent Agent Metrics and Lineage UI
- **Context:** Operators distrust automated AI recommendations when internal model performance and decision logic are hidden.
- **Decision:** Expose real-time transparency metrics for every specialist agent via `/api/agents/metrics` and render an interactive Agent Operations dashboard in the frontend.
- **Trade-off:** Minor overhead in recording input/output telemetry counters.
- **Status:** Active & Validated.

### ADR-014: High-Performance Canvas & SVG Telemetry Rendering in React
- **Context:** Rendering 20 cars updating at 10 Hz over a complex circuit using standard React DOM nodes causes severe layout thrashing and frame drops.
- **Decision:** Render the circuit track map using optimized SVG paths with hardware-accelerated CSS transforms for vehicle chips, and render high-frequency multi-channel telemetry curves using lightweight SVG polyline geometry.
- **Trade-off:** Requires custom mathematical projection code from GPS/distance coordinates to SVG viewbox space.
- **Status:** Active & Validated.

### ADR-015: FastF1 Canonical Normalization Gate
- **Context:** Raw timing and telemetry data from FastF1 contains missing transponder intervals, non-standardized column names, and NaN values.
- **Decision:** Ingestion pipelines must pass all records through the `StreamNormalizer` gate, translating raw data into standardized Pydantic `EventEnvelope` instances with explicit `Quality` flags before reaching agents.
- **Trade-off:** Malformed records are rejected upfront rather than silently passed downstream.
- **Status:** Active & Validated.

### ADR-016: Strict Separation of Operational Decisions from Stewarding Facts
- **Context:** Consequence assessments (e.g., "Box now to undercut Hamilton") must never be conflated with formal FIA stewarding adjudications (e.g., "Car 16 5-second time penalty for track limits").
- **Decision:** Separate tactical findings (`pulse.intelligence.*`) from official race control notices (`pulse.norm.race_events`). The Cockpit View renders tactical recommendations; the Race Control View renders stewarding notices.
- **Trade-off:** Distinct UI tabs and data models.
- **Status:** Active & Validated.

### ADR-017: Graceful Local Fallback when Docker/WSL Unavailable
- **Context:** Windows developer environments frequently encounter stopped Docker services (`com.docker.service`) or unprivileged PowerShell shells.
- **Decision:** Backend startup checks `PULSE_TRANSPORT_MODE`. If set to `SIMULATOR`, it boots instantly without probing Docker or Kafka ports. Test suites automatically skip distributed Kafka tests when the broker is unreachable.
- **Trade-off:** Requires clear logging so developers know which mode is active.
- **Status:** Active & Validated.

### ADR-018: Normalizer Deduplication Cache Reset on Seek/Reset Boundary
- **Context:** During replay reset or seeking, replaying previously seen event IDs caused `StreamNormalizer` to drop them as duplicates, resulting in empty state projections.
- **Decision:** Register a lifecycle reset hook (`replay_controller.set_reset_hook(normalizer.reset)`). Whenever a seek, reset, or session switch occurs, `StreamNormalizer._seen_events` is cleared.
- **Trade-off:** Must ensure that reset hooks only fire during intentional seek/reset transitions, not during normal linear playback.
- **Status:** Active & Validated.

### ADR-019: Agent 06 Integrity Verification Embedded in Cockpit
- **Context:** Operators needed visual confirmation that the SIA mathematical verification engine was actively auditing live streaming data.
- **Decision:** Implement Agent 06 as an active participant in `AgentOperationsView.tsx`, displaying its contract verification status, passing tests, and execution trace alongside the 5 tactical agents.
- **Trade-off:** Increased frontend component scope.
- **Status:** Active & Validated.

### ADR-020: Standalone Verifier CLI for Durable Audit
- **Context:** Regulatory bodies require an auditable tool that can verify evidence packages without running the full PULSE streaming backend.
- **Decision:** Provide `python -m calibre_core.verifier.cli` with comprehensive verification passes: header check, signature validation, reference matching, and Merkle leaf verification.
- **Trade-off:** Maintenance of a dedicated CLI codebase in `calibre_core`.
- **Status:** Active & Validated.

---

## Part III: Implementation Findings & Remediation Record

During the final audit and implementation phase, several concrete technical issues were discovered and systematically remediated:

1. **Frontend Incomplete Agent Registration:**
   - *Problem:* `AgentOperationsView.tsx` only registered 5 specialist agents; Agent 06 (`agent-06-integrity`) was omitted from the UI grid despite backend implementation.
   - *Remediation:* Implemented Agent 06 card in `AgentOperationsView.tsx` with `ScaleIcon`, dynamic integrity metrics, and updated status pill to `6/6 AGENTS REGISTERED & ACTIVE`.
2. **Replay Deduplication Cache Starvation on Seek:**
   - *Problem:* `StreamNormalizer` permanently stored event IDs in `_seen_events`. Scrubbing or resetting replay caused all subsequent replayed events to be discarded as duplicates.
   - *Remediation:* Implemented `StreamNormalizer.reset()` and wired it to `ReplayController.seek()`, `reset()`, and `switch_session()` via a registered reset hook (ADR-018).
3. **Vehicle Response Telemetry Key Inconsistency:**
   - *Problem:* `VehicleResponseAgent` checked for `speed_kmh` in event payload, whereas FastF1 position telemetry envelopes used the key `speed`. This caused valid position updates to be classified as `INSUFFICIENT_DATA` rather than triggering pace deviation findings.
   - *Remediation:* Updated `VehicleResponseAgent` to inspect both `speed` and `speed_kmh`, and filtered nominal pacing so that true traffic/degradation pace loss is emitted as `PACE_DEVIATION`, triggering immediate Agent 05 consequence assessments.
4. **Browser Test Execution Failure via DevTools Active Port:**
   - *Problem:* Browser subagent failed to connect to Chrome DevTools port due to sandbox environment constraints.
   - *Remediation:* Developed an automated Playwright Chromium test suite (`scripts/run_browser_system_validation.py`) executing directly against local ports 8000 and 5173, capturing 12 comprehensive visual validation screenshots with 0 console or page errors.

---

## Part IV: Platform Maturity & Future Roadmap

While CALIBRE v4 and PULSE are fully functional, integrated, and demonstrable in both local simulator and clustered environments, future engineering milestones include:
1. **Multi-Regime Verification Domain Packs:** Expanding domain packs beyond Formula 1 motorsport into commercial flight recorder (QAR/FDR) telemetry and autonomous vehicle safety logs.
2. **Hardware Security Module (HSM) Signing:** Integrating PKCS#11 hardware security modules for automated digital signing of archive bundle manifests.
3. **Real-Time WebGL Track View:** Transitioning the 2D SVG track layout to a WebGL/Three.js 3D track model supporting camera switching and driver cockpit perspectives.
4. **Distributed Flink Cluster Auto-Scaling:** Implementing reactive Flink TaskManager auto-scaling based on consumer lag metrics during high-density multi-session replays.

