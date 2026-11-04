# PULSE Architecture Diagrams (v2.0)
**Visual Specification of Current Implemented vs New Target Architecture**  
**Author:** Principal Software Architect, F1 Data Systems Engineer, Kafka/Flink Lead  

---

## 1. System Context Diagram

```mermaid
flowchart TB
    subgraph Users[Operational Users]
        STRAT[Race Strategist]
        PERF[Performance Engineer]
        RACE[Race Director / Steward Analyst]
    end

    subgraph ExternalSources[External Data Boundaries]
        F1TV[F1 TV Consumer App<br/><i>Viewing Only - NO Scraping</i>]:::restricted
        JOLP[Jolpica REST API<br/><i>Metadata, Grid, Results</i>]:::current
        FASTF1[FastF1 Historical Archive<br/><i>Permitted Private Captures</i>]:::target
        FIA[FIA Official Noticeboard<br/><i>Decisions & Regulations</i>]:::target
    end

    subgraph PULSE_BOUNDARY[PULSE System Boundary]
        INGEST[Ingestion & Adapters]:::target
        KAFKA[Kafka Event Backbone]:::current
        FLINK[Flink Stateful Stream Processing]:::target
        AGENTS[5 Specialist Intelligence Agents]:::target
        FUSION[Consequence Fusion Engine]:::target
        STORE[State Store & PostgreSQL]:::current
        API[FastAPI & SSE Streaming]:::current
        UI[React Race Cockpit UI]:::target
        HARNESS[E2E Verification Harness]:::target
    end

    STRAT --> UI
    PERF --> UI
    RACE --> UI

    JOLP --> INGEST
    FASTF1 --> INGEST
    FIA --> INGEST
    F1TV -.->|Strictly Prohibited Programmatic Ingestion| INGEST

    INGEST --> KAFKA
    KAFKA --> FLINK
    FLINK --> KAFKA
    KAFKA --> AGENTS
    AGENTS --> KAFKA
    KAFKA --> FUSION
    FUSION --> STORE
    STORE --> API
    API --> UI
    HARNESS --> INGEST & KAFKA & FLINK & AGENTS & API

    classDef current fill:#1e3a5f,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
    classDef restricted fill:#5c1d1d,stroke:#ef4444,stroke-width:2px,stroke-dasharray: 5 5,color:#fff;
```
*Legend: Blue = Current Implemented (Partial); Green = New Target Component; Red Dashed = Prohibited.*

---

## 2. High-Level Streaming Architecture

```mermaid
flowchart LR
    subgraph INGESTION[Ingestion Layer]
        S_SIM[Deterministic Simulator]:::current
        S_REPLAY[FastF1 Capture Replay]:::target
        S_JOLP[Jolpica Roster Fetcher]:::target
    end

    subgraph KAFKA_RAW[Kafka Raw Ingestion]
        T_RC[pulse.raw.race_control.v1]:::current
        T_TL[pulse.raw.timing.laps.v1]:::current
        T_TP[pulse.raw.timing.positions.v1]:::current
        T_TC[pulse.raw.telemetry.car.v1]:::current
        T_TK[pulse.raw.track_status.v1]:::current
    end

    subgraph FLINK_CLUSTER[Apache Flink Stream Engine]
        FJ1[Job 1: Normalizer & Watermarking]:::target
        FJ2[Job 2: Race State Reconstruction]:::target
        FJ3[Job 3: Feature Engineering Engine]:::target
    end

    subgraph KAFKA_PROC[Kafka Normalized & Feature Topics]
        T_NORM_EV[pulse.norm.race_events.v1]:::current
        T_NORM_DS[pulse.norm.driver_state.v1 - Compacted]:::target
        T_NORM_TS[pulse.norm.track_segments.v1 - Compacted]:::target
        T_FEAT_VR[pulse.features.vehicle_response.v1]:::target
        T_FEAT_ST[pulse.features.tyre_stints.v1]:::target
    end

    subgraph AGENT_LAYER[Specialist Analytics Layer]
        A1[Agent 1: Event Control]:::target
        A2[Agent 2: Track State]:::target
        A3[Agent 3: Vehicle Response]:::target
        A4[Agent 4: Tyre Strategy]:::target
        A5[Agent 5: Consequence Fusion]:::target
    end

    subgraph SERVING_LAYER[Serving & Presentation]
        DB[(PostgreSQL Store)]:::target
        FASTAPI[FastAPI + SSE Stream]:::current
        COCKPIT[React Cockpit Dashboard]:::target
    end

    INGESTION --> KAFKA_RAW
    KAFKA_RAW --> FJ1 --> FJ2 --> FJ3
    FJ1 --> T_NORM_EV
    FJ2 --> T_NORM_DS & T_NORM_TS
    FJ3 --> T_FEAT_VR & T_FEAT_ST

    T_NORM_EV --> A1
    T_NORM_TS --> A2
    T_NORM_DS & T_FEAT_VR --> A3
    T_NORM_DS & T_FEAT_ST --> A4

    A1 & A2 & A3 & A4 --> A5
    A5 --> DB --> FASTAPI --> COCKPIT

    classDef current fill:#1e3a5f,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
```

---

## 3. Kafka Topic Topology & Keying Structure

```mermaid
flowchart TD
    subgraph RAW[Raw Source Topics]
        R1["pulse.raw.race_control.v1<br/><b>Key: session_id</b> (1 partition)"]:::current
        R2["pulse.raw.timing.positions.v1<br/><b>Key: session_id:driver_number</b> (10 partitions)"]:::current
        R3["pulse.raw.telemetry.car.v1<br/><b>Key: session_id:driver_number</b> (20 partitions)"]:::current
        R4["pulse.raw.track_status.v1<br/><b>Key: session_id:segment_id</b> (3 partitions)"]:::current
        R5["pulse.raw.tyres.stints.v1<br/><b>Key: session_id:driver_number</b> (10 partitions)"]:::current
    end

    subgraph NORM[Normalised & State Topics]
        N1["pulse.norm.race_events.v1<br/><b>Key: session_id</b> (1 partition)"]:::current
        N2["pulse.norm.driver_state.v1<br/><b>Key: session_id:driver_number</b> (10 partitions, COMPACTED)"]:::target
        N3["pulse.norm.track_segments.v1<br/><b>Key: session_id:segment_id</b> (3 partitions, COMPACTED)"]:::target
    end

    subgraph FEAT[Feature Engineering Topics]
        F1["pulse.features.vehicle_response.v1<br/><b>Key: session_id:driver_number</b> (10 partitions)"]:::target
        F2["pulse.features.tyre_stints.v1<br/><b>Key: session_id:driver_number</b> (10 partitions)"]:::target
    end

    subgraph AGENT_FINDINGS[Agent Findings Topics]
        AF1["pulse.agent.event_context.findings.v1<br/><b>Key: session_id:finding_id</b>"]:::current
        AF2["pulse.agent.track_state.findings.v1<br/><b>Key: session_id:segment_id</b>"]:::current
        AF3["pulse.agent.vehicle_response.findings.v1<br/><b>Key: session_id:driver_number</b>"]:::current
        AF4["pulse.agent.tyre_strategy.findings.v1<br/><b>Key: session_id:driver_number</b>"]:::current
    end

    subgraph INTEL[Fused Intelligence Topics]
        I1["pulse.intelligence.driver_impact.v1<br/><b>Key: session_id:driver_number</b> (Revisions v1, v2)"]:::current
    end

    subgraph DLQ[Dead-Letter Topics]
        D1["pulse.dlq.normalizer.v1<br/><b>Key: session_id</b> (Error routing)"]:::target
    end

    RAW --> NORM
    NORM --> FEAT
    NORM & FEAT --> AGENT_FINDINGS
    AGENT_FINDINGS --> INTEL

    classDef current fill:#1e3a5f,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
```

---

## 4. Apache Flink Job Topology

```mermaid
flowchart TD
    subgraph JOB1[Flink Job 1: Ingestion Normalizer & Watermarking]
        J1_SRC[Kafka Raw Sources]:::target
        J1_WM[Assign BoundedOutOfOrderness Watermarks<br/><i>Telemetry: 1.0s, Control: 3.0s, Idleness: 5.0s</i>]:::target
        J1_DEDUP[KeyedProcessFunction Deduplicator<br/><i>State: ValueState&lt;Boolean&gt; (TTL 1h)</i>]:::target
        J1_VAL[Schema & Unit Validator]:::target
        J1_DLQ[DLQ Sink: pulse.dlq.normalizer.v1]:::target
        J1_SINK[Sink: pulse.norm.*.v1]:::target

        J1_SRC --> J1_WM --> J1_DEDUP --> J1_VAL
        J1_VAL -->|Invalid| J1_DLQ
        J1_VAL -->|Valid| J1_SINK
    end

    subgraph JOB2[Flink Job 2: Stateful Race State Reconstruction]
        J2_SRC[Kafka pulse.norm.*.v1]:::target
        J2_KEY[KeyBy: driver_number or segment_id]:::target
        J2_STATE[KeyedStateStore<br/><i>DriverState, TrackSegmentState, PitCycleState</i>]:::target
        J2_SINK[Sink: pulse.norm.driver_state.v1 & track_segments.v1]:::target

        J2_SRC --> J2_KEY --> J2_STATE --> J2_SINK
    end

    subgraph JOB3[Flink Job 3: Streaming Feature Engineering]
        J3_SRC[Normalized State & Events]:::target
        J3_WIN[Sliding Event-Time Windows & Event Aligned Triggers]:::target
        J3_FEAT[Calculate Pace Deltas & Pit Compression Savings]:::target
        J3_SINK[Sink: pulse.features.*.v1]:::target

        J3_SRC --> J3_WIN --> J3_FEAT --> J3_SINK
    end

    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
```

---

## 5. Five-Agent Asynchronous Collaboration & Fusion Flow

```mermaid
sequenceDiagram
    autonumber
    participant RC as Race Control
    participant A1 as Agent 1 (Event Control)
    participant A2 as Agent 2 (Track State)
    participant A3 as Agent 3 (Vehicle Response)
    participant A4 as Agent 4 (Tyre Strategy)
    participant A5 as Agent 5 (Fusion Engine)
    participant DB as PostgreSQL
    participant UI as Dashboard

    RC->>A1: VSC_DEPLOYED (Sector 2 debris)
    A1->>A1: Update FSM: ACTIVE
    A1->>A1: Identify Drivers near Pit Entry (Leclerc, Hamilton, etc.)
    A1->>A5: Emit Finding: DRIVER_EVENT_EXPOSURE (Leclerc P1)
    
    A5->>A5: Open Correlation Group (Deadline 3.0s event-time)
    A5->>A5: Minimum evidence met (Agent 1 finding present)
    A5->>DB: Persist Assessment v1 (PROVISIONAL)
    DB->>UI: SSE Broadcast Assessment v1
    
    par Async Processing
        A2->>A5: Emit Finding: TRACK_CONDITION_STATE (Dry, VSC Delta active)
    and
        A3->>A5: Emit Finding: PACE_DEVIATION (Hamilton dirty air pace loss)
    and
        A4->>A4: Compute Pit Loss: 21.5s - 11.0s = 10.5s Saving
        A4->>A5: Emit Finding: PIT_WINDOW_OPPORTUNITY (Leclerc 10.5s saving)
    end

    A5->>A5: Match correlation group by driver_number=16
    A5->>A5: Construct Revision v2 (Supersedes v1)
    A5->>DB: Persist Assessment v2 (CONFIRMED)
    DB->>UI: SSE Broadcast Assessment v2 (Visibly supersedes v1)
```

---

## 6. Race-Control & Finding Lineage Graph

```mermaid
flowchart LR
    subgraph RawRecords[Source & Ingestion Evidence]
        SR1["Source Record: rcm-821<br/><i>VSC Deployed Sector 2</i>"]:::current
        SR2["Source Record: pit-entry-16<br/><i>Leclerc In Pit Lane</i>"]:::current
        SR3["Source Record: stint-16-med<br/><i>23 Laps on Medium</i>"]:::current
    end

    subgraph KafkaEvents[Kafka Raw & Normalized Events]
        KE1["pulse.norm.race_events.v1<br/><b>Event ID: evt-vsc-01</b>"]:::current
        KE2["pulse.norm.driver_state.v1<br/><b>Driver: 16 (P1)</b>"]:::current
    end

    subgraph FlinkState[Flink State & Features]
        FS1["DriverState KeyedState<br/><i>Gap to P2: 2.48s</i>"]:::target
        FS2["Feature: PitLossCompression<br/><i>Net Saving: 10.5s</i>"]:::target
    end

    subgraph AgentFindings[Specialist Agent Findings]
        AF1["Agent 1 Finding: finding-exp-01<br/><i>DRIVER_EVENT_EXPOSURE</i>"]:::current
        AF4["Agent 4 Finding: finding-strat-01<br/><i>PIT_WINDOW_OPPORTUNITY</i>"]:::current
    end

    subgraph FusedAssessments[Fused Intelligence Revisions]
        ASS1["Assessment v1: impact-vsc-16-v1<br/><i>PROVISIONAL (Strategy pending)</i>"]:::current
        ASS2["Assessment v2: impact-vsc-16-v2<br/><i>CONFIRMED (Supersedes v1)</i>"]:::current
    end

    subgraph DashboardView[Cockpit Display]
        UI1["Live Tactical Consequence Feed<br/><i>Interactive Card with Evidence Drawer</i>"]:::target
    end

    SR1 --> KE1
    SR2 & SR3 --> KE2
    KE1 & KE2 --> FS1 & FS2
    KE1 --> AF1
    FS2 --> AF4
    AF1 --> ASS1
    AF1 & AF4 --> ASS2
    ASS1 -.->|Superseded By| ASS2
    ASS2 --> UI1

    classDef current fill:#1e3a5f,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
```

---

## 7. End-to-End Verification Harness Workflow (`pulse.testing.run_e2e`)

```mermaid
flowchart TD
    CLI["CLI Command: python -m pulse.testing.run_e2e<br/><i>--season 2026 --event Monaco --session R --mode replay</i>"]:::target

    subgraph STAGES[10-Stage Pipeline Verification]
        S1["Stage 1: Source Acquisition & Manifest Check<br/><i>Validate hashes & licensing</i>"]:::target
        S2["Stage 2: Kafka Producer Accounting<br/><i>Verify published event IDs</i>"]:::target
        S3["Stage 3: Kafka Consumer Lag & Offset Check<br/><i>Verify 0 lost commits</i>"]:::target
        S4["Stage 4: Flink Job Execution Check<br/><i>Query JobManager REST: state=RUNNING, checkpoints > 0</i>"]:::target
        S5["Stage 5: State Reconstruction Audit<br/><i>Verify driver & segment keys</i>"]:::target
        S6["Stage 6: Feature Generation Validation<br/><i>Verify schema conformance</i>"]:::target
        S7["Stage 7: 5-Agent Execution Accounting<br/><i>Verify FINDING_EMITTED, NO_FINDING, FILTERED</i>"]:::target
        S8["Stage 8: Fusion Engine Revision Chain Audit<br/><i>Verify v1 -> v2 superseding link</i>"]:::target
        S9["Stage 9: PostgreSQL Persistence Idempotency<br/><i>Verify zero duplicate writes</i>"]:::target
        S10["Stage 10: API & Dashboard Snapshot Reconciliation<br/><i>Verify /api/snapshot matches expected state</i>"]:::target
    end

    subgraph REPORTS[Automated Verification Deliverables]
        R_JSON["e2e_report.json"]:::target
        R_MD["e2e_report.md"]:::target
        R_RECON["stage_reconciliation.csv"]:::target
        R_METRICS["agent_metrics.csv"]:::target
    end

    CLI --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10
    S10 --> REPORTS

    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
```

---

## 8. Deployment Topology: Local Development vs Target Production

```mermaid
flowchart TB
    subgraph DOCKER_COMPOSE[Local Development Environment (Docker Compose)]
        subgraph InfraServices[Infrastructure Containers]
            KAFKA_LOCAL[Apache Kafka / Redpanda<br/><i>Port 9092</i>]:::current
            FLINK_JM[Flink JobManager<br/><i>Port 8081</i>]:::target
            FLINK_TM[Flink TaskManager]:::target
            PG_LOCAL[PostgreSQL 16<br/><i>Port 5432</i>]:::target
        end

        subgraph PulseServices[PULSE Containers]
            BACKEND[FastAPI Backend + 5 Agents<br/><i>Port 8000</i>]:::current
            FRONTEND[React Vite Dashboard<br/><i>Port 5173</i>]:::current
        end

        subgraph Observability[Telemetry & Metrics]
            PROM[Prometheus<br/><i>Port 9090</i>]:::target
            GRAF[Grafana<br/><i>Port 3000</i>]:::target
        end
    end

    KAFKA_LOCAL <--> FLINK_JM & FLINK_TM
    KAFKA_LOCAL <--> BACKEND
    PG_LOCAL <--> BACKEND
    BACKEND <--> FRONTEND
    BACKEND & FLINK_JM & KAFKA_LOCAL --> PROM --> GRAF

    classDef current fill:#1e3a5f,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
```

---

## 9. Verified Phase 2 Five-Agent Streaming Integration Topology

```mermaid
flowchart TD
    subgraph KAFKA_CLUSTER["Apache Kafka Broker (localhost:9092)"]
        subgraph RAW_TOPICS["Raw Ingestion Domain Topics"]
            R_RC["pulse.raw.race_control.v1"]
            R_TL["pulse.raw.timing_laps.v1"]
            R_TP["pulse.raw.timing_positions.v1"]
            R_TS["pulse.raw.track_status.v1"]
            R_TY["pulse.raw.tyres_stints.v1"]
            R_PI["pulse.raw.pit_events.v1"]
            R_WE["pulse.raw.weather.v1"]
        end

        subgraph NORM_TOPICS["Flink Canonical Normalized Topics (Event-Time Watermarked)"]
            N_RC["pulse.norm.race_events.v1"]
            N_TS["pulse.norm.track_segments.v1"]
            N_DL["pulse.norm.driver_laps.v1"]
            N_DS["pulse.norm.driver_state.v1"]
            N_TY["pulse.norm.tyre_stints.v1"]
        end

        subgraph AGENT_TOPICS["Specialist Agent Finding Topics"]
            A1_OUT["pulse.agent.event_context.findings.v1"]
            A2_OUT["pulse.agent.track_state.findings.v1"]
            A3_OUT["pulse.agent.vehicle_response.findings.v1"]
            A4_OUT["pulse.agent.tyre_strategy.findings.v1"]
        end

        subgraph FUSION_TOPICS["Consequence Fusion Topics"]
            A5_OUT["pulse.intelligence.driver_impact.v1"]
        end
    end

    subgraph FLINK_CLUSTER["Apache Flink 1.18.1 Cluster (localhost:8081)"]
        FLINK_JOB["Job: pulse-canonical-normalizer-v2<br/>ID: 4ac2d03605f6993dfba914eadc3faec8<br/>Status: RUNNING<br/>Checkpoints: 190+ Completed, 0 Failed"]
    end

    subgraph AGENT_PIPELINE["Specialist Intelligence Agents (Asynchronous Event-Driven)"]
        AG1["Agent 1: EventControlAgent<br/>• Race control lifecycle FSM<br/>• Dynamic driver event exposure<br/>• Strict provenance & zero hallucinated radio"]
        AG2["Agent 2: TrackStateAgent<br/>• Sector condition transitions<br/>• Weather correlations (temp, rain risk)<br/>• Explicit INSUFFICIENT_DATA handling"]
        AG3["Agent 3: VehicleResponseAgent<br/>• Dynamic driver pace baselines<br/>• Clean-air vs dirty-air traffic detection<br/>• Strictly no mechanical failure claims without telemetry"]
        AG4["Agent 4: TyreStrategyAgent<br/>• Compound degradation modeling (S, M, H, I, W)<br/>• VSC pit delta savings (10.5s calculated)<br/>• Deterministic alternative scenarios (Box/Hold/Stay)"]
        AG5["Agent 5: ConsequenceFusionEngine<br/>• Multi-agent correlation across all 4 domains<br/>• Bounded waiting with provisional v1 assessments<br/>• Superseding v2 revisions & 2-lap horizon forecasts"]
    end

    subgraph STATE_SERVING["State Management & Serving"]
        STORE["StateStore (In-Memory + Lineage Trace)<br/>• Registered Agents (5/5)<br/>• 13 Transparency Execution Metrics<br/>• Idempotent Finding & Assessment Storage"]
        API["FastAPI REST & Streaming Router<br/>• GET /api/findings<br/>• GET /api/agents<br/>• GET /api/agents/metrics<br/>• GET /api/assessments<br/>• GET /api/health"]
    end

    RAW_TOPICS --> FLINK_JOB
    FLINK_JOB --> NORM_TOPICS

    N_RC --> AG1
    N_TS --> AG2
    N_DL & N_DS --> AG3
    N_RC & N_TY --> AG4

    AG1 --> A1_OUT
    AG2 --> A2_OUT
    AG3 --> A3_OUT
    AG4 --> A4_OUT

    A1_OUT & A2_OUT & A3_OUT & A4_OUT --> AG5
    AG5 --> A5_OUT

    A1_OUT & A2_OUT & A3_OUT & A4_OUT & A5_OUT --> STORE
    STORE --> API

    classDef current fill:#1e3a5f,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef target fill:#1a4d2e,stroke:#10b981,stroke-width:2px,color:#fff;
```


