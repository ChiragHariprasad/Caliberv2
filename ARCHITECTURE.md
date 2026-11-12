# CALIBRE / PULSE: Comprehensive System Architecture Specification

## 1. Architectural Mission & System Identity

The CALIBRE / PULSE architecture is designed for deterministic, high-assurance event streaming, real-time tactical decision support, and cryptographic evidence verification. It addresses the fundamental flaw of naive streaming applications: treating predictive heuristics, uncertain sensor readings, and immutable ground facts as equivalent data points.

```
+-----------------------------------------------------------------------------------------------------------------+
|                                        THREE-TIER SYSTEM ARCHITECTURE                                           |
+-----------------------------------------------------------------------------------------------------------------+
|                                                                                                                 |
|  [ TIER 1: STREAM PROCESSING & DECISION SUPPORT ] (PULSE Reference Implementation)                             |
|  * Asynchronous F1 Ingestion (CAN-bus Telemetry, GPS, Transponders, Race Control, Pit Lane Timers)              |
|  * Canonical Stream Normalization & Deduplication                                                               |
|  * 6 Isolated Specialist Intelligence Agents                                                                    |
|  * Consequence Fusion Engine (Revision DAG: Provisional v1 -> Confirmed v2)                                    |
|  * Real-Time Tactical Race Cockpit (React 18, SVG Circuits, SSE Streaming)                                      |
|                                                                                                                 |
|  [ TIER 2: DETERMINISTIC INTEGRITY ENGINE ] (SIA Core v3)                                                       |
|  * Mathematical Evidence Verification Rules (Lap consistency, Pit speed limits, Micro-sector monotonicity)     |
|  * Bitemporal Fact Ledger (Assertion Time vs Valid Event Time)                                                  |
|  * Embedded Agent 06 Bridge into Active Streaming State                                                         |
|                                                                                                                 |
|  [ TIER 3: DURABLE EVIDENCE VERIFICATION PLATFORM ] (CALIBRE Core v4)                                           |
|  * Domain-Tagged Cryptographic Hashes (BLAKE3 / SHA-256 with explicit domain separation)                         |
|  * Immutable Effective-Dated Reference Registry                                                                 |
|  * Non-Linear Continuous Uncertainty Witness with Guard Bands                                                   |
|  * Self-Contained Portable Archive Bundles (calibre_bundle.tar.zst)                                             |
|  * Offline Standalone Zero-Dependency Verifier CLI                                                              |
|                                                                                                                 |
+-----------------------------------------------------------------------------------------------------------------+
```

---

## 2. Stream Topology & Topic Design

The stream topology enforces strict boundary separation across raw ingestion, normalized canonical streams, agent findings, and fused consequence assessments.

```
+------------------+         +-------------------+         +---------------------+
|    RAW TOPICS    | ------> | STREAM NORMALIZER | ------> |  CANONICAL TOPICS   |
+------------------+         +-------------------+         +---------------------+
| pulse.raw.race   |                                       | pulse.norm.race     |
| pulse.raw.timing |                                       | pulse.norm.laps     |
| pulse.raw.state  |                                       | pulse.norm.state    |
| pulse.raw.track  |                                       | pulse.norm.track    |
| pulse.raw.tyres  |                                       | pulse.norm.tyres    |
+------------------+                                       +---------------------+
                                                                      |
                   +--------------------------------------------------+
                   |
                   v
+--------------------------------------------------------------------------------+
|                         SPECIALIST INTELLIGENCE AGENTS                         |
+--------------------------------------------------------------------------------+
|  [Agent 01: Event Control]       --> pulse.agent.findings.event_control        |
|  [Agent 02: Vehicle Response]    --> pulse.agent.findings.vehicle_response     |
|  [Agent 03: Track State]         --> pulse.agent.findings.track_state          |
|  [Agent 04: Tyre Strategy]       --> pulse.agent.findings.tyre_strategy        |
|  [Agent 06: Integrity Agent]     --> pulse.agent.findings.integrity            |
+--------------------------------------------------------------------------------+
                                           |
                                           v
+--------------------------------------------------------------------------------+
|                       AGENT 05: CONSEQUENCE FUSION ENGINE                      |
|                                          |                                     |
|                                          v                                     |
|               INTELLIGENCE TOPIC: pulse.intelligence.driver_impact             |
+--------------------------------------------------------------------------------+
```

### Partitioning & Ordering Strategy
- **Partition Key Selection:** To guarantee strict total ordering per physical entity, messages are keyed using composite routing keys:
  - `session_id:driver_number` for car-specific telemetry, lap times, and tyre stints.
  - `session_id:segment_id` for track sectors, speed traps, and micro-sectors.
  - `session_id:global` for track-wide race control notices and neutralisations.
- **Delivery Guarantees:** At-least-once transport delivery paired with deterministic deduplication (`event_id` cache with reset hooks) provides end-to-end exactly-once processing semantics.

---

## 3. Epistemic Classification & Contracts

Every datum traversing CALIBRE carries explicit epistemic status. The platform strictly distinguishes between verified physical observations, inductive hypotheses, and derived numerical metrics.

```
                  +----------------------------------------------+
                  |            EPISTEMIC DATA TAXONOMY           |
                  +----------------------------------------------+
                                          |
          +-------------------------------+------------------------------+
          |                               |                              |
          v                               v                              v
   [ OBSERVED ]                     [ INFERRED ]                   [ DERIVED ]
   Ground Truth Facts               Inductive Models               Algorithmic Calculations
   * Transponder triggers           * "Pace deficit caused         * Gap deltas
   * Speed trap velocities            by dirty air"                * Average stint degradation
   * Official FIA flags             * "Undercut window opening"    * Interval behind leader
   * Cryptographically verified     * "Tyre thermal degradation"   * Sector split comparisons
```

### Core Pydantic Data Contracts

#### A. EventEnvelope (`pulse/contracts.py`)
```python
class EventEnvelope(BaseModel):
    event_id: str                          # Globally unique event identifier
    event_type: str                        # e.g., "POSITION_UPDATE", "VSC_DEPLOYED"
    schema_version: int = 1
    source: SourceProvenance               # Provider, adapter, capture ID, record ID
    time: EventTime                        # UTC event time, elapsed session ms
    subject: Subject                       # Driver number, circuit ID, segment ID
    run: RunContext                        # Run ID, session instance ID, mode
    quality: Quality                       # Completeness, calibration, unit validation
    payload: dict[str, Any]                # Domain payload
```

#### B. Finding (`pulse/contracts.py`)
```python
class Finding(BaseModel):
    finding_id: str                        # Deterministic finding ID
    agent_id: str                          # Identifier of the originating agent
    finding_type: str                      # e.g., "PACE_DEVIATION", "PIT_WINDOW_OPPORTUNITY"
    session_id: str
    run_id: str
    subject: Subject
    trigger_event_id: str                  # Event ID that triggered this evaluation
    as_of_event_time: datetime             # Event-time timestamp
    interpretation: Interpretation         # OBSERVED | INFERRED | DERIVED
    result: dict[str, Any]                 # Agent finding metrics and classifications
    evidence_refs: list[str]               # Upstream event IDs forming the evidence chain
    assessment_status: FindingStatus       # PROVISIONAL | CONFIRMED | SUPERSEDED | RETRACTED
    reason_codes: list[str]                # Canonical reason codes
    model_version: str                     # Agent model/rule version
```

#### C. Assessment (`pulse/contracts.py`)
```python
class Assessment(BaseModel):
    assessment_id: str                     # e.g., "impact-f1-2026-monaco-sim-16-v2"
    assessment_version: int                # 1 (provisional) -> 2 (confirmed)
    session_id: str
    run_id: str
    as_of_event_time: datetime
    trigger: dict[str, Any]                # Triggering event or finding metadata
    subject: Subject                       # Target driver
    impact: Impact                         # Summary, observed changes, consequence
    forecast: str                          # 1-3 lap tactical forecast
    confidence: float                      # Bounded heuristic confidence [0.0, 1.0]
    calibration_status: str                # UNCALIBRATED_HEURISTIC (explicit notice)
    supporting_finding_refs: list[str]     # IDs of Agent 1-4 findings fused
    supersedes_assessment_id: str | None   # Lineage pointer to superseded v1
    evidence_refs: list[str]               # Complete cryptographic evidence leaf set
```

---

## 4. Specialist Agent Specifications

Instead of a black-box monolithic neural network, CALIBRE deploys 6 specialized, deterministic agents with transparent execution metrics:

```
+----------------------------------------------------------------------------------------------------+
|                                    SPECIALIST AGENT RESPONSIBILITIES                                |
+----------------------------------------------------------------------------------------------------+
| Agent ID           | Role                 | Inputs                  | Key Findings Produced        |
+--------------------+----------------------+-------------------------+------------------------------+
| agent-01-event-    | Race Control &       | pulse.norm.race_events  | RACE_EVENT_LIFECYCLE         |
| control            | Neutralisations      |                         | DRIVER_EVENT_EXPOSURE        |
+--------------------+----------------------+-------------------------+------------------------------+
| agent-02-vehicle-  | Vehicle Response &   | pulse.norm.driver_laps  | PACE_DEVIATION               |
| response           | Pace Deviation       | pulse.norm.driver_state | VEHICLE_ANOMALY              |
+--------------------+----------------------+-------------------------+------------------------------+
| agent-03-track-    | Track State &        | pulse.norm.track_seg    | TRACK_CONDITION_STATE        |
| state              | Environmental Grip   | pulse.norm.race_events  | LOCAL_GRIP_LOSS              |
+--------------------+----------------------+-------------------------+------------------------------+
| agent-04-tyre-     | Tyre Strategy &      | pulse.norm.tyre_stints  | PIT_WINDOW_OPPORTUNITY       |
| strategy           | Pit Windows          | pulse.norm.driver_state | UNDERCUT_THREAT              |
+--------------------+----------------------+-------------------------+------------------------------+
| agent-05-          | Consequence Fusion   | All Agent Findings      | DRIVER_IMPACT_ASSESSMENT     |
| fusion             | Engine               |                         | (v1 Provisional / v2 Revised)|
+--------------------+----------------------+-------------------------+------------------------------+
| agent-06-          | SIA Evidence         | Canonical Envelopes     | INTEGRITY_ASSESSMENT         |
| integrity          | Verification         | Bitemporal Assertions   | (CONTRACT_COMPLIANT / BREACH)|
+--------------------+----------------------+-------------------------+------------------------------+
```

### Agent 05: Consequence Fusion Engine & Revision Chains
Agent 05 solves the core challenge of multi-agent streaming: **temporal divergence and out-of-order finding arrivals**.
- **Revision DAG (v1 -> v2):** When a high-priority race event occurs (e.g., VSC deployment), Agent 01 immediately fires `DRIVER_EVENT_EXPOSURE`. Agent 05 does not block waiting for complex tyre models; it immediately publishes a **Provisional Assessment v1** with bounded tactical warnings.
- **Convergence to v2:** When Agent 04 finishes computing complex delta pit savings (~150ms later), Agent 05 fuses the tyre finding, increments the version to **Assessment v2**, populates `supersedes_assessment_id="...-v1"`, and updates the forecast.
- **Out-of-Order Resilience:** If Agent 04's finding arrives before Agent 01's finding due to network jitter, Agent 05 constructs the provisional baseline v1 retroactively in history, ensuring that the auditable revision chain `v1 -> v2` is never broken.

---

## 5. Dual-Transport Architecture & Deterministic Replay

CALIBRE abstracts its messaging transport behind the `PulseEventBus` interface, enabling identical system execution across two modes:

```
                      +-----------------------------------+
                      |      PULSE TRANSPORT SWITCH       |
                      +-----------------------------------+
                                        |
               +------------------------+------------------------+
               |                                                 |
               v                                                 v
  [ PULSE_TRANSPORT_MODE=KAFKA ]                   [ PULSE_TRANSPORT_MODE=SIMULATOR ]
  * Production Clustered Topology                  * Local High-Speed In-Memory Bus
  * Apache Kafka 3.7+ (KRaft)                      * Zero External Services or JVM
  * Apache Flink 1.18+ JobManager                  * Deterministic Lockstep Execution
  * Multi-Broker Partitioning                      * Fast-forward seeking (100x speed)
  * Distributed Consumer Groups                    * Instantaneous State Reconstruction
```

### Seek-Reconstruction without Broker Duplication
A fundamental engineering innovation in CALIBRE is the **Replay Seek Engine**:
1. When a user scrubs the timeline slider to Lap 25 (e.g., event 35,000):
2. The active replay background task is gracefully cancelled.
3. The normalizer deduplication cache is reset via registered lifecycle hooks.
4. A fresh execution lineage `run_id` is generated (e.g., `run-monaco-a8f3b2`).
5. StateStore is cleared and re-initialized to Lap 1.
6. The `ReplayEventProcessor` streams events 0 through 35,000 into the agents using `publish=False`.
7. **Crucial Invariant:** Reconstructing state rewinds and fast-forwards through the exact canonical agent pipelines without publishing duplicate records to the Kafka broker or external sinks.

---

## 6. CALIBRE Core v4 Durable Evidence Foundations

While PULSE provides live streaming intelligence, `calibre_core` provides long-term cryptographic durability.

```
+----------------------------------------------------------------------------------------------------+
|                                    CALIBRE v4 DURABLE FOUNDATIONS                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Domain-Tagged Cryptographic Hashes ]                                                            |
|  * Uses BLAKE3 (with SHA-256 fallback) with strict domain separation prefixes:                     |
|    - TAG_EVENT = "CALIBRE-EVT-v4"                                                                  |
|    - TAG_FINDING = "CALIBRE-FND-v4"                                                                |
|    - TAG_STATE = "CALIBRE-STA-v4"                                                                  |
|    - TAG_BUNDLE = "CALIBRE-BND-v4"                                                                 |
|  * Prevents cross-type collision attacks where a finding hash could masquerade as an event hash.  |
|                                                                                                    |
|  [ Effective-Dated Reference Registry ]                                                            |
|  * Tracks track layouts, vehicle baselines, sporting regulations, and sensor calibrations with     |
|    strict validity intervals: [effective_from_utc, effective_to_utc).                             |
|  * Historical verifications always bind against the exact rules in force at event time.           |
|                                                                                                    |
|  [ Continuous Uncertainty Witness with Guard Bands ]                                              |
|  * Replaces fragile binary thresholds with continuous non-linear sigmoid confidence scoring.       |
|  * Uses explicit guard bands: nominal, warning zone, and violation zone.                           |
|                                                                                                    |
|  [ Self-Contained Archive Bundles (.tar.zst) ]                                                     |
|  * Bundles raw event envelopes, canonical projections, finding DAGs, reference manifests, and     |
|    cryptographic leaf signatures into a single compressed, portable archive.                       |
|                                                                                                    |
|  [ Standalone Zero-Dependency Verifier CLI ]                                                       |
|  * Completely decoupled from backend, Kafka, and databases.                                        |
|  * Command: python -m calibre_core.verifier.cli verify --bundle <path> --strict                    |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 7. Frontend User Interface Architecture

The frontend is built on **React 18, TypeScript, and Vite**, organized into 4 primary views and 2 tactical inspection drawers:

1. **Cockpit View:**
   - Multi-channel F1 Leaderboard with live gap, interval, pit status, tyre compound, and age.
   - Interactive SVG Circuit Map featuring real-time vehicle coordinate interpolation.
   - Live Tactical Consequence Feed rendering `ImpactCard` stacks with revision badges (`REV v1`, `REV v2`) and explicit calibration notices (`UNCALIBRATED HEURISTIC`).
   - Momentum charts and pulse timeline.
2. **Race Control & Stewarding View:**
   - Official FIA incident flags, sector yellows, VSC notices, and stewarding investigations.
3. **Agent Operations View:**
   - Real-time transparency dashboard displaying all 6 registered agents.
   - Metrics: inputs received, eligible inputs, findings emitted, no-finding decisions, latency distributions, and failures.
   - Interactive Finding Execution Trace modal showing full lineage and provenance.
4. **Pipeline Lab View:**
   - Lineage graph rendering the 6 pipeline stages from FastF1 ingestion to state projection.
   - Verification run records and cryptographic integrity certificates.
5. **Driver Telemetry Modal:**
   - High-density CAN-bus inspection: Vehicle Speed, Throttle, Brake, Gear/RPM, DRS, and Tyre wear.
   - SVG multi-curve time-series graph with millisecond precision.
6. **Evidence Audit Drawer:**
   - Slide-over briefing drawer displaying tactical rationale, forecast horizon, calibration warning, supporting finding refs, and SHA-256 evidence leaf hashes.

