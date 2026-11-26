# PULSE — Implemented System Architecture

**Status:** Post-Reconstruction Verified Implementation (2026-11-26)  
**Authoritative Codebase:** `backend/pulse/`, `sia_core_v3/sia_core/`, `frontend/src/`, `docker-compose.kafka.yml`

---

## 1. End-to-End Runtime Dataflow

```text
  Captures (*.jsonl) / Scenario Builder
                 │
                 ▼
       ReplayController (_replay_loop / seek)
         ├── [publish=False during seek reconstruction] ──► local_only() dispatcher
         └── [publish=True during KAFKA playback]
                 │
                 ▼  CalibreProducer (kafka_io: acks=all, idempotent, gzip, DriverSlots key)
      Apache Kafka KRaft Cluster (kafka-1/2/3 :19092-19094, 70 topics, RF=3, MIN_ISR=2)
                 │
                 ├──► pulse.f1.raw.* ──► Apache Flink 1.18.1 (normalizer_job.sql)
                 │                          • kafka_ts METADATA watermark (2s out-of-order)
                 │                          • ROW_NUMBER() OVER (PARTITION BY event_id) dedup
                 │                          ▼
                 └──► pulse.f1.canonical.* ◄──────────────────────┘
                 │
                 ▼  kafka_consumer_loop (IdempotentVerdictSink + paused_replay_buffer + retired-run guard)
        ┌────────┴──────────────────────────────────────────────┐
        ▼                                                       ▼
  Specialist Agents (Agents 01-05)                    IntegrityAgent (Agent 06)
   • agent-01 EventControl (FSM exposure)              • bridge.py origin closure + envelope_to_atom()
   • agent-02 TrackState (weather/surface)             • sia_core_v3 IntegrityEngine + SIAWALStore
   • agent-03 VehicleResponse (RollingCleanAirPace)    • 12s position heartbeat throttle
   • agent-04 TyreStrategy (FuelComp OLS + PitSim)     • Pre-admission finality quarantine + SHA-256 chain
   • agent-05 ConsequenceFusionEngine (SIA-gated)       ▼
        │                                             Verdict Ledger & /api/integrity/*
        └──────────────────┬────────────────────────────┘
                           ▼
                StateStore + RaceStateProjector
                           │
                           ├──► REST Snapshots (/api/snapshot, /api/telemetry/{dn}, /api/sessions/*)
                           └──► SSE Fan-Out (/api/stream with Last-Event-ID resumption)
                                    │
                                    ▼
                        React 19 + TypeScript UI (Vite /dist)
```

---

## 2. Subsystems and Verified Responsibilities

| Subsystem | Module Paths | Verified Behaviour | Explicit Boundary / Scope |
|---|---|---|---|
| **Transport & Broker** | `backend/pulse/stream/kafka_client.py`, `backend/pulse/stream/kafka_io.py`, `backend/pulse/topics.py` | `kafka_client.py` delegates to production `kafka_io` primitives: `CalibreProducer` (`acks="all"`, `enable.idempotence=True`, `compression_type="gzip"`), `build_topic_catalogue(driver_partitions=11)` (`70` topics, `RF=3`, `MIN_ISR=2`), and `DriverSlots` affinity hashing. | Running `KAFKA` mode requires the 3-broker Docker stack (`docker-compose.kafka.yml`); `MEMORY` and `SIMULATOR` modes run in-process without broker dependencies. |
| **Flink Normalizer** | `backend/pulse/stream/flink/jobs/normalizer_job.sql`, `docker/flink/lib/flink-sql-connector-kafka-3.1.0-1.18.jar`, `backend/pulse/stream/flink/{client,manager}.py` | Flink `1.18.1` runs job `pulse-canonical-normalizer-v2` with Kafka `METADATA` `TIMESTAMP_LTZ(3)` watermarks (`2s`), append-only first-row `ROW_NUMBER()` deduplication across all `7` raw topics, `5000ms` checkpointing, and `300000ms` idle state TTL. | Uses `"gzip"` rather than `"zstd"` because Flink's connector fat JAR omits unbundled `zstd-jni`. |
| **Replay & Keyframes** | `backend/pulse/replay/controller.py`, `backend/pulse/replay/processor.py`, `backend/pulse/main.py` | Cooperative `seek()` (`await asyncio.sleep(0)` every `200` events), `CHECKPOINT_INTERVAL = 2000` (`MAX_CHECKPOINTS_PER_SESSION = 35`) per-session keyframe state snapshots, WAL pause/single-tx sync during seeks, retired `run_id` broker filtering, and bounded `paused_replay_buffer` preventing Kafka/Flink drift while `PAUSED`. | Seeking `target_index=36321` cold executes in `20.8s`; cached keyframe `seek(36500)` completes in `487.4ms` (`MEMORY` mode benchmark). |
| **Explainable F1 Intelligence** | `backend/pulse/analytics/pace_and_tyre.py`, `backend/pulse/agents/{event_control,track_state,vehicle_response,tyre_strategy,fusion}.py` | `VehicleResponseAgent` (`2.0.0`) predicts pace causally prior to observation (`RollingCleanAirPaceEstimator`, conformal 95% PI); `TyreStrategyAgent` (`2.0.0`) fits fuel-compensated OLS with empirical pit loss and field-gap re-entry projection; `ConsequenceFusionEngine` (`3.0.0`) performs bounded (`deque(maxlen=25)`) session-scoped fusion gated on SIA `INTEGRITY_VERDICT`. | Tactical advisories remain strictly read-only projections; they cannot alter SIA integrity states. |
| **SIA Integrity Engine** | `sia_core_v3/sia_core/{algebra,canon,contract,engine,evaluator,ledger,model,timelinedag,verdict,wal,witnesses}.py`, `backend/pulse/integrity/{agent,bridge,contracts,router}.py` | Pure stdlib kernel with 4-state total order, cycle-safe supersession, canonical v3 `void_decision`, pre-admission finality quarantine, historical clock preservation, optional `SIAWALStore` SQLite WAL persistence, `verify_incremental()` snapshot cache, and 12s position heartbeat throttling. | Five contracts (`lap_time`, `pit_speed`, `sector_time`, `driver_position`, `weather_observation`) run actively; full `ALL_13` view falls back gracefully to `UNMODIFIED/UNKNOWN` for inactive specification contracts. |
| **API & Streaming** | `backend/pulse/api/router.py`, `backend/pulse/state/store.py`, `backend/pulse/stream/projections.py`, `backend/pulse/sessions/registry.py` | Session-scoped routes validate `_require_registered_session` (`404`) and `_require_active_session_scope` (`409`); speed endpoints validate `0.1 <= speed <= 20.0` (`422`); telemetry channels report actual stream source adapters & non-zero `freshness_ms`; SSE supports `Last-Event-ID` resumption. | Designed as a research/engineering single-node FastAPI backend with CORS open and no user auth layer (`ROADMAP.md` tracks production hardening). |
| **Frontend Dashboard** | `frontend/src/` (`App.tsx`, `TrackMap.tsx`, `MomentumChart.tsx`, `DriverTelemetryModal.tsx`, `integrity/`, `logic_lab/`, `agents/`, `replay/`) | Live regime/provenance badges (`SYNTHETIC SIM`, `LAB ARCHIVE`, `PREVIEW`), zero-interpolation `MomentumChart` with endpoint collision spacing, DNF/Pit Bay rendering, non-nested interactive buttons, `scroll-margin-top` sticky-header clearance, dynamic Logic Lab / Topology bindings, and 45s seek / in-flight poll guards. | Initial boot keeps legacy synthetic driver `#31` Ocon marked `RETIRED` for API contract tests (`test_circuits_and_operations.py`), visually framed inside a labelled `DNF / PIT BAY`. |

---

## 3. Decoupled Modules Preserved for Reference (`calibre_core`)

The directory `calibre_core/` contains standalone archetype implementations (`calibre_core/agents/{timing,telemetry,spatial,context,supervisor}.py`), durability/admission helpers (`calibre_core/admission.py`, `durable.py`), and `23` unit/historical scenario tests. Per design boundaries, `calibre_core/agents/` are surfaced in the **Agents & Pipeline -> Target Archetypes (A1–A5 Specification)** documentation tab and verified independently by pytest, while active streaming traffic runs through `backend/pulse/agents/` and `backend/pulse/integrity/`.

---

## 4. Failure Domains & Single Points of Failure

- **Kafka KRaft Cluster (`kafka-1/2/3`):** Survives single-broker outage with zero data loss (`RF=3`, `MIN_ISR=2`); intentionally rejects writes when `< 2` ISR brokers remain (`T3` fail-closed safety).
- **Apache Flink (`1.18.1`):** Checkpoints state every `5s` (`pulse-canonical-normalizer-v2`) to recover deduplication windows after TaskManager restarts. In `SIMULATOR`/`MEMORY` modes without Docker, `StreamNormalizer` executes identically in-process.
- **FastAPI Backend Process:** `SIAWALStore` (`sqlite3`) and `IdempotentVerdictSink` (`sqlite3`) persist verdict ledgers and Kafka consumption offsets locally across restarts, while `StateStore` (`StateProjector`, tactical agents, keyframe cache) reconstructs deterministically from captures or checkpoints.
