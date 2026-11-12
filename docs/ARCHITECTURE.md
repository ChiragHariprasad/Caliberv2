# CALIBRE / PULSE: System Architecture Specification

## 1. System Mission & Architectural Topology

CALIBRE is a high-assurance evidence verification platform. PULSE is its reference application: a deterministic Formula 1 race intelligence engine that consumes asynchronous telemetry, timing transponders, track state, weather, and race-control feeds, turning them into evidence-linked tactical consequence assessments with deterministic integrity verification.

```text
+---------------------------------------------------------------------------------------------------+
|                                 CALIBRE / PULSE STREAM TOPOLOGY                                   |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [Ingestion / Capture Feeds] (FastF1 / Official FIA Timing / Real-time CAN-bus Transponders)      |
|       │                                                                                           |
|       ▼                                                                                           |
|  [Stream Normalizer / Deduplication] <───> [Dual-Transport: Local Memory Bus / Apache Kafka]     |
|       │                                                                                           |
|       ├───────────────────┼───────────────────┼───────────────────┼───────────────────┐       |
|       ▼                   ▼                   ▼                   ▼                   ▼       |
|  [Agent 01: Event]   [Agent 02: Vehicle]  [Agent 03: Track]   [Agent 04: Tyre]    [Agent 06: SIA] |
|   Race Control &       Dirty Air, Pace     Sectors & Surface   Stints & Window     Integrity &    |
|   Neutralisations      Degradation Delta   Grip / Weather      Undercut Model      Bitemporal Fact|
|       │                   │                   │                   │                   │       |
|       └───────────────────┴─────────┬─────────┴───────────────────┴───────────────────┘       |
|                                     │                                                             |
|                                     ▼                                                             |
|                  [Agent 05: Consequence Fusion Engine]                                            |
|                  * Epistemic Classification (Observed vs Inferred vs Derived)                     |
|                  * Consequence Revision Chains (v1 Provisional -> v2 Confirmed DAG)               |
|                  * Out-of-Order Multi-Agent Reconciliation                                        |
|                                     │                                                             |
|                                     ▼                                                             |
|                            [Active State Store]                                                   |
|                                     │                                                             |
|                   ┌─────────────────┴─────────────────┐                                           |
|                   ▼                                   ▼                                           |
|        [FastAPI Streaming Engine]           [CALIBRE v4 Durable Core]                             |
|        * Server-Sent Events (SSE)           * Domain-Tagged Hashes (BLAKE3/SHA-256)               |
|        * REST State & Control Endpoints     * Effective-Dated Reference Registry                  |
|        * Seeking & Scrubbing Controller     * Continuous Uncertainty Witness                      |
|                   │                         * Offline Standalone Verifier CLI                     |
|                   ▼                                                                               |
|        [React 18 Cockpit UI]                                                                      |
|        * SVG Circuit Map & Live Delta                                                             |
|        * 6-Agent Transparency Dashboard                                                           |
|        * Real-Time Telemetry Modal & Canvases                                                     |
|        * Evidence Audit Drawer & Hash Lineage                                                     |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Component Responsibilities & Data Flow

| Component | Module Path | Core Responsibility |
| :--- | :--- | :--- |
| **Data Ingestion** | `backend/pulse/sessions/` | Loads official session telemetry and timing captures into canonical memory structures. |
| **Stream Normalizer** | `backend/pulse/stream/` | Enforces Pydantic schema validation, maps event types to canonical streams, and filters duplicates. |
| **Dual-Transport Bus** | `backend/pulse/stream/` | Abstracts event dispatching across in-memory `PulseEventBus` and clustered Apache Kafka. |
| **Specialist Agents** | `backend/pulse/agents/` | 6 decoupled single-concern agents producing typed findings from normalized streams. |
| **Consequence Fusion** | `backend/pulse/agents/fusion.py`| Fuses multi-agent findings into coherent driver impact assessments across a revision DAG. |
| **StateStore** | `backend/pulse/state/store.py` | Thread-safe bitemporal ledger maintaining active session state, telemetry buffers, and run lineages. |
| **Replay Engine** | `backend/pulse/replay/` | Drives deterministic playback, variable speed multipliers (0.25x-5.0x), and seek-reconstruction. |
| **SIA Bridge (Agent 06)**| `backend/pulse/integrity/`| Evaluates bitemporal integrity contracts over incoming telemetry and timing assertions. |
| **CALIBRE v4 Core** | `calibre_core/` | Provides domain-tagged hashing, reference registries, uncertainty witnesses, and archive bundling. |
| **React 18 Dashboard** | `frontend/src/` | Visualizes live leaderboard, SVG circuits, telemetry curves, agent metrics, and evidence drawers. |

---

## 3. Stream Topology & Kafka/Flink Integration

Messages are routed across three distinct topic tiers using composite entity routing keys (`session_id:driver_number` or `session_id:segment_id`) to ensure strict physical ordering per car/track segment:

```text
RAW INGESTION TOPICS ──────► STREAM NORMALIZER (Flink / Local) ──────► CANONICAL STREAMS
- pulse.raw.race_control                                              - pulse.norm.race_events.v1
- pulse.raw.driver_timing                                             - pulse.norm.driver_laps.v1
- pulse.raw.driver_telemetry                                          - pulse.norm.driver_state.v1
- pulse.raw.track_weather                                             - pulse.norm.track_segments.v1
- pulse.raw.tyre_stints                                               - pulse.norm.tyre_stints.v1
                                                                                  │
                                     ┌────────────────────────────────────────────┘
                                     ▼
                    AGENT FINDINGS & INTELLIGENCE TOPICS
                    - pulse.agent.findings.event_control.v1
                    - pulse.agent.findings.vehicle_response.v1
                    - pulse.agent.findings.track_state.v1
                    - pulse.agent.findings.tyre_strategy.v1
                    - pulse.agent.findings.integrity.v1
                    - pulse.intelligence.driver_impact.v1 (Fused Assessments)
```

In clustered production mode (`PULSE_TRANSPORT_MODE=KAFKA`), an external Apache Flink job normalizes high-throughput raw streams into canonical streams. In local development (`SIMULATOR`), `StreamNormalizer` executes inline in-process with identical validation contracts.

---

## 4. Specialist Agents & Epistemic Revision DAG

CALIBRE partitions intelligence across 6 isolated agents, strictly segregating verified physical facts (`OBSERVED`), analytical calculations (`DERIVED`), and model predictions (`INFERRED`):

| Agent Identifier | Primary Concern | Input Streams | Key Findings / Outputs |
| :--- | :--- | :--- | :--- |
| **`agent-01-event-control`** | Flag lifecycles & neutralisations | `race_events` | `RACE_EVENT_LIFECYCLE`, `DRIVER_EVENT_EXPOSURE` |
| **`agent-02-vehicle-response`**| Dirty air & pace degradation | `driver_laps`, `driver_state` | `PACE_DEVIATION` (`DIRTY_AIR_IMPEDED`, `TYRE_THERMAL_DEGRADATION`)|
| **`agent-03-track-state`** | Weather transitions & grip loss | `track_segments`, `race_events`| `TRACK_CONDITION_STATE`, `LOCAL_GRIP_LOSS` |
| **`agent-04-tyre-strategy`** | Pit loss deltas & undercut windows | `tyre_stints`, `driver_state` | `PIT_WINDOW_OPPORTUNITY`, `UNDERCUT_THREAT` |
| **`agent-05-fusion`** | Multi-agent consequence synthesis | All agent finding topics | `Assessment` (Revision DAG: `v1` $\rightarrow$ `v2`) |
| **`agent-06-integrity`** | Bitemporal evidence verification | Canonical event streams | `INTEGRITY_ASSESSMENT` (`COMPLIANT` / `BREACH`) |

### Consequence Revision Chains (v1 -> v2)
1. **Immediate Reaction (v1):** Upon neutralisation (VSC/SC), Agent 01 detects spatial exposure. Agent 05 immediately publishes a **Provisional Assessment v1** with bounded warnings before complex tyre models converge.
2. **Tactical Revision (v2):** When Agent 04 computes pit loss savings (~150ms later), Agent 05 fuses the tyre finding, increments to **Assessment v2**, populates `supersedes_assessment_id="...-v1"`, and updates the forecast.
3. **Out-of-Order Reconciliation:** If Agent 04's finding arrives before Agent 01 due to transport jitter, Agent 05 buffers the finding and synthesizes the baseline v1 retroactively, guaranteeing that the `v1 -> v2` audit DAG remains unbroken.

---

## 5. Replay, Seeking & Clean State Reconstruction

The `ReplayController` provides deterministic time-travel and scrubbing across historical race captures:

```text
[User scrubs timeline slider to Lap 25 (Event #35,000)]
                      │
                      ▼
[Cancel active background replay task]
                      │
                      ▼
[Trigger Registered Reset Hook: StreamNormalizer.reset()] ──► Clears seen event ID cache
                      │
                      ▼
[Generate fresh execution lineage run_id: run-f1-2026-monaco-sim-a8f3b2]
                      │
                      ▼
[Reset StateStore to Lap 1]
                      │
                      ▼
[Fast-replay events 0..35,000 via ReplayEventProcessor(publish=False)]
                      │
                      ▼
[StateStore instantaneously reconstructed up to target event cursor]
* ZERO duplicate records published to Kafka or external sinks
```

---

## 6. SIA v3 Deterministic Integrity Integration

Agent 06 (`agent-06-integrity`) embeds the pure mathematical SIA verification core directly into the active streaming loop:
- **Bitemporal Fact Ledger:** Tracks both Assertion Time (when data entered the system) and Event Time (when the physical car triggered the transponder).
- **Verification Contracts:**
  - `lap_time v1.0.0`: Validates sector sum equality ($\sum \text{Sectors} = \text{LapTime}$) and physical acceleration limits.
  - `pit_speed v1.0.0`: Checks pit lane transponder delta against strict pit speed limits with radar variance tolerance.
  - `driver_position v1.0.0`: Verifies monotonic lap progression and overtaking admissibility under yellow flag sectors.

---

## 7. CALIBRE v4 Durable Evidence Architecture

To guarantee that streaming evidence remains auditable independently of running infrastructure:

- **Domain-Tagged Hashes:** All Merkle leaves use explicit domain-separation tags (`CALIBRE-EVT-v4`, `CALIBRE-FND-v4`, `CALIBRE-STA-v4`, `CALIBRE-BND-v4`) via BLAKE3 (with SHA-256 fallback), mathematically preventing cross-type collision attacks.
- **Effective-Dated Reference Registry:** Immutable historical registry for track geometries, vehicle baselines, and sporting regulations with strict validity intervals (`[effective_from_utc, effective_to_utc)`).
- **Continuous Uncertainty Witness:** Replaces arbitrary binary pass/fail gates with continuous non-linear sigmoid confidence scoring and explicit guard bands.
- **Self-Contained Archive Bundles (`.tar.zst`):** Standalone compressed archives encapsulating raw events, canonical streams, finding DAGs, reference manifests, and cryptographic leaf signatures.
- **Offline Verifier CLI (`calibre_core.verifier.cli`):** Zero-dependency CLI validating archive bundles mathematically without database or broker connections.

