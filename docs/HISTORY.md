# CALIBRE / PULSE: Project Evolution & Architectural Decision Record

This document provides the authoritative chronological history, architectural archaeology, and engineering rationale tracing the system from the original CALIBRE repository (`E:\CALIBER`) to the modern CALIBRE v4 durable evidence verification platform (`E:\Caliberv2`).

---

## 1. Evolution Timeline & Core Milestones

```text
+---------------------------------------------------------------------------------------------------+
|                                     PROJECT EVOLUTION CHRONOLOGY                                  |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  2024 - Early 2025: Original CALIBRE (`E:\CALIBER`)                                               |
|  * Focus: Bitemporal evidence verification for telemetry compliance against sporting rules.       |
|  * Tech: SQLite bitemporal ledger, Python SIA v2.2 pure evaluator, Apache Flink on WSL2.          |
|  * Limitations: Fragile WSL/Java interop, monolithic post-hoc rules, no visual cockpit.           |
|                                                                                                   |
|  Mid 2025 - Late 2025: Evolution into PULSE (`E:\Caliberv2`, branch `main`)                       |
|  * Focus: Real-time Formula 1 streaming intelligence and tactical consequence forecasting.       |
|  * Tech: Apache Kafka (KRaft), 5 specialist agents, FastAPI, React 18 / Vite tactical cockpit.    |
|  * Innovations: Multi-agent consequence fusion, out-of-order finding resolution, revision DAGs.   |
|                                                                                                   |
|  Early 2026: SIA v3 Re-Integration & Dual Transport (`E:\Caliberv2`, branch `kafka-v2`)          |
|  * Focus: Grounding tactical AI predictions in deterministic mathematical ground truth.           |
|  * Tech: Embedded SIA v3 as `agent-06-integrity` directly into the active streaming state.        |
|  * Dual-Transport: Abstracted Kafka behind `PulseEventBus` for zero-dependency local simulation. |
|                                                                                                   |
|  Late 2026: CALIBRE v4 Durable Evidence Verification Platform                                     |
|  * Focus: Generalizing beyond F1 streaming into a durable, multi-regime evidence platform.       |
|  * Tech: Domain-tagged hashes (BLAKE3/SHA-256), effective-dated references, continuous           |
|    uncertainty witnesses, self-contained archive bundles (.tar.zst), offline verifier CLI.       |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Chronological Archaeological Analysis

### Phase 1: Original CALIBRE (`E:\CALIBER`)
The original CALIBRE project investigated whether physical telemetry from motorsport could be formally verified against sporting and technical regulations using an immutable, bitemporal ledger.
- **Initial Architecture (`commit 8404aee`):** Centered on a pure Python evaluator (`sia_core`), a bitemporal SQLite fact database, and an Apache Flink stream-processing engine deployed on Windows Subsystem for Linux (WSL2).
- **Emerging Limitations:**
  1. *Host Environment Fragility:* Heavy coupling to WSL2, Java runtimes, and local Linux daemon scripts created friction in deployment and automated testing.
  2. *Monolithic Post-Hoc Adjudication:* Rules evaluated events retroactively without real-time streaming feedback or predictive awareness.
  3. *Lack of Visual Interface:* Adjudications were reported solely via console logs and database queries; no interactive interface existed for race engineers or stewards.

### Phase 2: The PULSE Transformation (`E:\Caliberv2`)
To address these limitations, the architecture pivoted to **PULSE**: transforming passive historical adjudication into real-time tactical streaming intelligence.
- **Architectural Charter (`commit 7840c8a`):** Defined the multi-stream F1 model: projecting tactical consequences 1 to 3 laps into the future (pit stop loss deltas, undercut/overcut windows, and safety car neutralisation exposure).
- **Multi-Agent Decoupling (`commit 19e10d3`):** Replaced monolithic prediction logic with decoupled, single-concern specialist agents (Event Control, Vehicle Response, Track State, Tyre Strategy) coordinated by a deterministic Consequence Fusion Engine.
- **Full-Stack Implementation (`commit bd6c354`):** Built a high-performance FastAPI backend delivering Server-Sent Events (SSE) and a React 18 / TypeScript tactical race cockpit with hardware-accelerated SVG circuits.
- **Real-World Telemetry Acquisition (`commit 43d98a0`):** Replaced synthetic feeds with FastF1 historical telemetry captures across Monaco, Silverstone, and Suzuka, enforcing strict provenance tracking.

### Phase 3: SIA v3 Re-Integration & Dual Transport
During PULSE deployment, an epistemic risk emerged: uncalibrated heuristic predictions could be mistaken by operators for verified ground facts.
- **Integrity Integration (`commit ce6659e`):** The SIA integrity engine was embedded directly into the streaming pipeline as **`agent-06-integrity`**, continuously auditing lap sum equality, pit speed limits, and micro-sector monotonicity.
- **Dual-Transport Abstraction (`commit badc07f`):** Abstracted messaging behind `PulseEventBus`, enabling identical system execution across clustered Apache Kafka and an in-memory high-speed async bus (`SIMULATOR`), resolving local Docker dependencies.

### Phase 4: CALIBRE v4 Durable Evidence Foundations
To ensure that streaming evidence remains verifiable decades after transient streaming brokers and databases are decommissioned, the platform evolved into **CALIBRE v4 (`commit 1d96aa0`)**:
- Domain-separated cryptographic hashes (`BLAKE3`/`SHA-256`) preventing cross-type collision attacks.
- Effective-dated reference registry ensuring historical events are validated against the exact rules in force at event time.
- Continuous sigmoid uncertainty witnesses with explicit guard bands replacing fragile binary gates.
- Self-contained archive bundles (`.tar.zst`) with an offline standalone verifier CLI.

### Phase 5: Recent Implementation & Audit Remediations
During the final codebase audit and validation phase, several concrete technical issues were discovered and systematically remediated:
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

### Architectural Comparison: Original CALIBRE vs Modern CALIBRE / PULSE

| Dimension | Original CALIBRE (`E:\CALIBER`) | Modern CALIBRE / PULSE (`E:\Caliberv2`) |
| :--- | :--- | :--- |
| **Primary Paradigm** | Post-hoc regulatory compliance verification | Real-time streaming consequence forecasting + durable evidence |
| **Execution Environment**| WSL2 Linux daemon + Java Apache Flink jar | Native cross-platform Python 3.11+ / Node.js 18+ (Win/Mac/Linux) |
| **Transport Layer** | Fixed external Flink stream socket | Dual-transport: high-speed in-memory async bus & Apache Kafka |
| **Intelligence Model** | Monolithic rule evaluator (`sia_core v2.2`) | 6 decoupled specialist agents + Consequence Fusion Engine |
| **Temporal Semantics** | Static bitemporal SQLite queries | Sub-second event-time streaming + revision DAGs (`v1 -> v2`) |
| **User Interface** | None (terminal logs and SQLite queries) | React 18 / TypeScript tactical race cockpit with SVG track maps |
| **Evidence Durability** | SQLite database dumps | Domain-tagged cryptographic hashes (`BLAKE3`) & `.tar.zst` bundles |
| **Offline Verification** | Requires full database and runtime stack | Zero-dependency standalone verifier CLI (`calibre verify`) |

---

## 3. Consequential Engineering Decisions (ADR Summary)

| ADR | Problem Context | Chosen Architectural Approach | Consequence / Trade-off | Commit Reference |
| :--- | :--- | :--- | :--- | :--- |
| **ADR-001** | Live transport vs historical ingestion coupling. | Decouple ingestion into immutable capture packages (`captures/`); stream via canonical envelopes. | Disk footprint for captures; guarantees deterministic replay parity. | `commit 43d98a0` |
| **ADR-002** | Kafka/Flink operational overhead in local dev/test. | Dual-transport abstraction via `PulseEventBus` (`SIMULATOR` vs `KAFKA`). | Must maintain test parity across both transport implementations. | `commit badc07f` |
| **ADR-003** | Black-box monolithic prediction model uninterpretable. | 6 isolated single-concern specialist agents coordinated by Consequence Fusion. | Increased topic messaging; requires out-of-order finding resolution. | `commit 19e10d3` |
| **ADR-004** | AI heuristics mistaken for physical facts. | Strict epistemic taxonomy: `OBSERVED` vs `DERIVED` vs `INFERRED` data badges. | Schema verbosity; frontend displays explicit calibration chips. | `commit 7840c8a` |
| **ADR-005** | Delayed strategic reaction during sudden VSC/SC. | Two-stage revision DAG: Provisional `v1` emitted immediately, superseded by Confirmed `v2`. | Frontend must handle dynamic card replacement and superseding IDs. | `commit ce6659e` |
| **ADR-006** | Asymmetric agent latency (Tyre arriving before Event). | Agent 05 buffers partial findings; synthesizes baseline `v1` retroactively if needed. | Small in-memory correlation buffer; guarantees unbroken `v1->v2` DAG. | `commit ce6659e` |
| **ADR-007** | Timeline scrubbing polluting Kafka topics. | Seek rewinds StateStore and fast-replays via `ReplayEventProcessor(publish=False)`. | CPU spike during seek; prevents broker pollution or duplicate alerts. | `commit badc07f` |
| **ADR-008** | Stale events contaminating state after seek. | Every seek/reset generates a fresh `run_id`; StateStore drops mismatched run IDs. | Run identifiers must be tracked across all downstream contracts. | `commit badc07f` |
| **ADR-009** | Cryptographic collision attacks across data types. | Domain-separated tagged hashes (`CALIBRE-EVT-v4`, `CALIBRE-FND-v4`, etc.). | Custom hashing wrappers required instead of raw `hashlib.sha256()`. | `commit 1d96aa0` |
| **ADR-010** | Rules and track layouts changing across seasons. | Immutable Reference Registry with validity intervals: `[effective_from, effective_to)`. | Registry queries must include event-time timestamps. | `commit 1d96aa0` |
| **ADR-011** | Sensor radar noise triggering false binary violations. | Continuous sigmoid uncertainty witness with explicit guard bands. | Floating-point confidence score calculation vs simple boolean. | `commit 1d96aa0` |
| **ADR-012** | Auditing evidence without active streaming infrastructure. | Self-contained archive bundles (`.tar.zst`) with offline standalone verifier CLI. | Archive packaging step required at session conclusion. | `commit 1d96aa0` |
| **ADR-013** | Lack of operator visibility into agent decisions. | Expose agent metrics via `/api/agents/metrics` and interactive trace modal in UI. | Minor telemetry counter overhead in agent base classes. | `commit bd6c354` |
| **ADR-014** | DOM layout thrashing during 10 Hz 20-car updates. | Optimized SVG circuit paths with hardware-accelerated transforms and polyline curves. | Custom mathematical projection from GPS coordinates to SVG viewBox. | `commit bd6c354` |
| **ADR-015** | Missing or non-standardized FastF1 columns. | Strict `StreamNormalizer` gate translating raw packets into typed `EventEnvelope`s. | Malformed records rejected upfront with explicit error reasons. | `commit 43d98a0` |
| **ADR-016** | Conflation of tactical advice with stewarding facts. | Segregate tactical feed (Cockpit) from official FIA notices (Race Control). | Strict UI tab and data contract segregation. | `commit bd6c354` |
| **ADR-017** | Windows Docker named pipe permission restrictions. | Graceful local fallback to `PULSE_TRANSPORT_MODE=SIMULATOR`; skip Kafka tests offline. | Transparent logging of active transport mode during startup. | `commit badc07f` |
| **ADR-018** | Replay deduplication cache starvation on seek/reset. | Register lifecycle reset hook (`replay_controller.set_reset_hook(normalizer.reset)`). | Normalizer deduplication cache clears only on seek/reset transitions. | `commit current` |
| **ADR-019** | Agent 06 omitted from visual operations cockpit. | Added Agent 06 to `AgentOperationsView.tsx` with `ScaleIcon` (`6/6 ACTIVE`). | Full UI transparency for mathematical verification contracts. | `commit current` |
| **ADR-020** | Regulatory verification requiring full application stack. | Standalone `calibre_core.verifier.cli` verifying bundles with zero external deps. | Maintenance of dedicated verification CLI package. | `commit 1d96aa0` |

---

## 4. Current State & Platform Maturity

The platform is fully integrated, operational, and validated:
- **Zero Regressions:** 380 unit, property, and integration tests passing; 17 Docker-dependent tests gracefully skipped.
- **Serving & Validated:** Backend (FastAPI) and frontend (React 18 / Vite) running locally with 12/12 automated Playwright browser journeys verified and recorded in `reports/browser-validation/screenshots/`.
- **Repository Health:** Clean, minimal 3-file canonical documentation structure with all intermediate reports archived.
