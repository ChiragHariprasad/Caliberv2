# PULSE Implementation Backlog (v2.0)
**Actionable Engineering Work Breakdown Structure**  
**Audience:** Autonomous Coding Agents & Core Engineering Team  
**Standard:** Every task has explicit dependencies, test requirements, complexity, and verifiable acceptance criteria.  

---

## EPIC 0: Baseline Repair & Contract Normalization

### Feature 0.1: Test Suite Restoration
- **TASK-001: Fix `test_event_control_agent_vsc` Failure**
  - **File:** `backend/tests/test_agents.py`
  - **Description:** Line 27 asserts `mock_bus.publish.call_count == 2`, but `EventControlAgent.on_event` emits 3 findings (`finding_lc`, `finding_exp` for #16, and `finding_exp_44` for #44). Update the test fixture and assertions to test both single-driver and multi-driver exposure emissions cleanly, or refactor Agent 1 to iterate over active drivers dynamically rather than hardcoding #16 and #44.
  - **Dependencies:** None.
  - **Complexity:** Small (S)
  - **Test Requirements:** `pytest tests/test_agents.py` passes 100%.
  - **Acceptance Criteria:** `test_event_control_agent_vsc` passes without assertion error.

- **TASK-002: Add Data Mode Validation to `RunContext`**
  - **File:** `backend/pulse/contracts.py`
  - **Description:** Enforce strict validation that `mode` is one of `SIMULATED`, `REPLAY`, `LIVE`. Add a model validator rejecting any event where `mode` is missing or where synthetic source records are passed with `mode="LIVE"`.
  - **Dependencies:** TASK-001
  - **Complexity:** Small (S)
  - **Test Requirements:** `pytest tests/test_contracts.py` includes validation tests for mixed data modes.
  - **Acceptance Criteria:** Pydantic raises `ValidationError` if simulated provenance is labeled as live.

---

## EPIC 1: Circuit Geometry Engine

### Feature 1.1: Versioned GeoJSON Geometry Assets
- **TASK-101: Create Monaco Circuit Geometry Asset**
  - **File:** `backend/pulse/circuits/assets/monaco.json`
  - **Description:** Create an authoritative GeoJSON asset for Circuit de Monaco (3,337m length). Include actual track centerline coordinates (100+ points), 19 numbered corners with verified names (Sainte Dévote, Beau Rivage, Massenet, Casino, Mirabeau Haute, Grand Hotel Hairpin, Mirabeau Bas, Portier, Tunnel, Nouvelle Chicane, Tabac, Louis Chiron, Piscine, Rascasse, Anthony Noghès), 3 sector boundary markers (S1: 0-1050m, S2: 1050-2340m, S3: 2340-3337m), pit lane entry/exit paths, pit speed limit (60 km/h), and DRS activation zones.
  - **Dependencies:** None.
  - **Complexity:** Medium (M)
  - **Test Requirements:** `tests/test_circuits.py` validates GeoJSON schema, closed loop, corner sequence, and monotonicity.
  - **Acceptance Criteria:** Centerline forms a valid closed loop matching official Monaco circuit topology.

- **TASK-102: Create Silverstone & Suzuka Geometry Assets**
  - **Files:** `backend/pulse/circuits/assets/silverstone.json`, `backend/pulse/circuits/assets/suzuka.json`
  - **Description:** Create GeoJSON assets for Silverstone Grand Prix Circuit (5,891m, 18 corners, 2 DRS zones) and Suzuka International Racing Course (5,807m, 18 corners, figure-8 crossover).
  - **Dependencies:** TASK-101
  - **Complexity:** Medium (M)
  - **Test Requirements:** Schema and topology tests in `tests/test_circuits.py`.
  - **Acceptance Criteria:** Suzuka crossover elevation/intersection modeled without topology errors; Silverstone 18 corners verified.

- **TASK-103: Circuit Coordinate Normalization & Projection Service**
  - **File:** `backend/pulse/circuits/manager.py`
  - **Description:** Implement `CircuitManager` providing:
    - `get_circuit(circuit_id: str) -> CircuitModel`
    - `interpolate_position(circuit_id: str, distance_m: float) -> tuple[float, float]`
    - `get_sector_for_distance(circuit_id: str, distance_m: float) -> str`
    - `transform_to_viewport(coords: list[tuple[float, float]], width: int, height: int, padding: int) -> list[tuple[float, float]]`
  - **Dependencies:** TASK-101, TASK-102
  - **Complexity:** Medium (M)
  - **Test Requirements:** Unit tests verifying coordinate interpolation at distance 0m, $L/2$, and $L$.
  - **Acceptance Criteria:** Distance 0m returns start/finish line; $L$ wraps correctly; projection scales cleanly to SVG viewBox.

- **TASK-104: Expose Circuit API Endpoints**
  - **File:** `backend/pulse/api/router.py`
  - **Description:** Add `GET /api/circuits` and `GET /api/circuits/{circuit_id}` returning full GeoJSON geometry and sector metadata.
  - **Dependencies:** TASK-103
  - **Complexity:** Small (S)
  - **Test Requirements:** `test_api.py` asserts 200 OK and validates response schema.
  - **Acceptance Criteria:** Calling `/api/circuits/monaco` returns 19 corners and verified centerline.

---

## EPIC 2: Dynamic Grid & Telemetry Inspection

### Feature 2.1: Full Session Entry List & State Reconstruction
- **TASK-201: Dynamic Driver Registry & State Store**
  - **File:** `backend/pulse/state/store.py`, `backend/pulse/stream/projections.py`
  - **Description:** Remove the hardcoded 5-driver dictionary. Implement `load_entry_list(drivers: list[DriverMeta])` supporting dynamic 20-driver grids. Update `RaceStateProjector` to dynamically instantiate and update driver state based on ingested `POSITION_UPDATE`, `LAP_COMPLETED`, and `TYRE_FITTED` events.
  - **Dependencies:** TASK-001
  - **Complexity:** Medium (M)
  - **Test Requirements:** Unit test loading a 20-car grid and asserting all 20 cars are tracked.
  - **Acceptance Criteria:** `/api/drivers` returns 20 cars when 20 are registered.

- **TASK-202: Per-Driver Telemetry Channel Model & Ingestion**
  - **File:** `backend/pulse/contracts.py`, `backend/pulse/state/store.py`
  - **Description:** Create Pydantic model `CarTelemetrySample`:
    - `speed_kph`: float (or null)
    - `throttle_pct`: float (0-100) (or null)
    - `brake_active`: bool (or null)
    - `gear`: int (1-8, or 0 for neutral) (or null)
    - `rpm`: int (or null)
    - `drs_status`: str (`OFF`, `AVAILABLE`, `ACTIVE`)
    - `data_source`: str
    - `data_quality`: str (`OBSERVED`, `ESTIMATED`, `UNAVAILABLE`)
    - `age_ms`: int
  - **Dependencies:** TASK-201
  - **Complexity:** Medium (M)
  - **Test Requirements:** Serialization tests; missing fields default to `null` with completeness `PARTIAL`.
  - **Acceptance Criteria:** No sensor value is ever fabricated; missing sensors return `null`.

- **TASK-203: Telemetry Query API**
  - **File:** `backend/pulse/api/router.py`
  - **Description:** Add `GET /api/drivers/{driver_number}/telemetry` returning current channels, latest update age, and rolling 10-lap trace history.
  - **Dependencies:** TASK-202
  - **Complexity:** Small (S)
  - **Test Requirements:** API test asserting 200 OK and channel types.
  - **Acceptance Criteria:** Returns latest telemetry sample with millisecond timestamp.

---

## EPIC 3: Race Control & Stewarding Module

### Feature 3.1: Officiating Timeline & Evidence Segregation
- **TASK-301: Race Control Data Contracts & State Machine**
  - **File:** `backend/pulse/contracts.py`
  - **Description:** Define models:
    - `OfficialMessage`: `message_id`, `timestamp_utc`, `flag_status`, `message_type` (`FLAG`, `SAFETY_CAR`, `VSC`, `INCIDENT`, `INVESTIGATION`, `DECISION`), `scope` (`TRACK`, `SECTOR_1`, etc.), `drivers_involved`, `official_status` (`REPORTED`, `NOTED`, `UNDER_INVESTIGATION`, `DECISION_ISSUED`, `NO_FURTHER_ACTION`, `CLOSED`), `sporting_regulation_ref`.
    - `StewardingDecision`: `incident_id`, `decision_text`, `penalty_type`, `penalty_seconds`, `penalty_grid_positions`, `penalty_points`, `official_document_ref`.
  - **Dependencies:** None.
  - **Complexity:** Medium (M)
  - **Test Requirements:** Contract validation tests in `tests/test_contracts.py`.
  - **Acceptance Criteria:** Rejects unsupported official statuses.

- **TASK-302: Race Control API Endpoints**
  - **File:** `backend/pulse/api/router.py`
  - **Description:** Implement:
    - `GET /api/race-control/messages`: List chronological official race control messages.
    - `GET /api/race-control/stewarding`: List active incidents, investigations, and formal decisions.
    - `GET /api/race-control/assessments/{incident_id}`: Return PULSE's independent analytical assessment for that incident.
  - **Dependencies:** TASK-301
  - **Complexity:** Medium (M)
  - **Test Requirements:** API router tests in `tests/test_api.py`.
  - **Acceptance Criteria:** Clean separation of official decisions from PULSE assessments.

---

## EPIC 4: Streaming Engine Overhaul (Kafka & Flink)

### Feature 4.1: Apache Flink Streaming Pipeline
- **TASK-401: Flink Job 1 — Normalization, Deduplication & Watermarking**
  - **File:** `backend/pulse/stream/flink/normalizer_job.py`
  - **Description:** Implement Flink streaming job consuming from `pulse.raw.*.v1`. Assign BoundedOutOfOrderness watermarks (2.0s telemetry lag, 5.0s race control lag). Implement `KeyedProcessFunction` deduplicating by `event_id` with 1-hour TTL. Route malformed payloads to `pulse.dlq.normalizer.v1`. Sink canonical events to `pulse.norm.*.v1`.
  - **Dependencies:** None.
  - **Complexity:** Large (L)
  - **Test Requirements:** Integration test verifying out-of-order event ordering and duplicate drop.
  - **Acceptance Criteria:** Duplicate event produces single output record; watermark advances monotonically.

- **TASK-402: Flink Job 2 — Stateful Race State Reconstruction**
  - **File:** `backend/pulse/stream/flink/state_job.py`
  - **Description:** Implement Flink job maintaining `KeyedState` for driver positions, lap counts, stint age, tyre compound, and sector locations. Sink to compacted topic `pulse.norm.driver_state.v1`.
  - **Dependencies:** TASK-401
  - **Complexity:** Large (L)
  - **Test Requirements:** State checkpoint and restore test.
  - **Acceptance Criteria:** Keyed state survives job cancellation and savepoint resume.

- **TASK-403: Flink Job 3 — Streaming Feature Engineering**
  - **File:** `backend/pulse/stream/flink/features_job.py`
  - **Description:** Implement sliding window event-time feature calculations:
    - 3-lap rolling median pace per driver in clean air.
    - Real-time VSC/SC pit loss compression saving delta.
  - **Dependencies:** TASK-402
  - **Complexity:** Large (L)
  - **Test Requirements:** Windowed calculation tests with synthetic late events.
  - **Acceptance Criteria:** Emits feature records to `pulse.features.*.v1`.

- **TASK-404: Flink Verification REST Client**
  - **File:** `backend/pulse/stream/flink/client.py`
  - **Description:** Implement `FlinkJobManagerClient` that queries Flink JobManager REST API (`http://localhost:8081/v1/jobs/{job_id}`). Verifies:
    - Job state is `RUNNING`
    - Ingestion and sink record counts > 0
    - Checkpoint count > 0 and failed checkpoints == 0
    - Watermark is progressing
  - **Dependencies:** TASK-401
  - **Complexity:** Medium (M)
  - **Test Requirements:** Mock REST API client test.
  - **Acceptance Criteria:** Returns `is_healthy=False` if JobManager endpoint is 200 OK but job state is not `RUNNING`.

---

## EPIC 5: Specialist Agents Overhaul & Transparency

### Feature 5.1: Decoupled Agent Logic & Hallucination Purge
- **TASK-501: Decouple Agent 1 (Event Control) from Hardcoded Drivers**
  - **File:** `backend/pulse/agents/event_control.py`
  - **Description:** Refactor `EventControlAgent` to query `RaceStateProjector` or `driver_state` topic for all currently active drivers. For each driver within 150m of pit entry at VSC deployment, emit `DRIVER_EVENT_EXPOSURE` with level `CRITICAL_OPPORTUNITY`. For drivers trapped in congested sectors, emit `HIGH_TRAFFIC_RISK`. Remove all hardcoded `#16` and `#44` references.
  - **Dependencies:** TASK-201
  - **Complexity:** Medium (M)
  - **Test Requirements:** Unit test with 10 simulated drivers; asserts findings emitted for all eligible drivers.
  - **Acceptance Criteria:** Zero hardcoded driver numbers in `event_control.py`.

- **TASK-502: Purge Hallucinated Radio & Fake Confidence from Agent 5 (Fusion)**
  - **File:** `backend/pulse/agents/fusion.py`
  - **Description:**
    1. Remove Groq LLM synthetic team radio generation.
    2. Replace narrative with deterministic template engine based on verified inputs:
       - Headline: `"{driver_name} inside critical pit window under {event_type}"`
       - Narrative: `"Neutralisation reduces pit transit loss by {saving:.1f}s. Stint age {stint_laps} on {compound} compound."`
    3. Remove fake `confidence: 85`. Set confidence to `None` with `uncertainty: {"calibration": "UNRECORDED_HEURISTIC"}`.
  - **Dependencies:** TASK-501
  - **Complexity:** Medium (M)
  - **Test Requirements:** `test_fusion.py` validates output schema without network calls.
  - **Acceptance Criteria:** Zero fabricated team-radio strings emitted by Fusion engine.

- **TASK-503: Agent Operational Instrumentation & Metrics Collector**
  - **File:** `backend/pulse/agents/base.py`, `backend/pulse/api/router.py`
  - **Description:** Instrument `BaseAgent`:
    - `messages_received_count`: int
    - `eligible_count`: int
    - `processed_count`: int
    - `findings_emitted_count`: int
    - `no_finding_count`: int
    - `insufficient_data_count`: int
    - `filtered_count`: int
    - `failed_count`: int
    - `latency_ms_p50`: float
    - `latency_ms_p95`: float
    - `kafka_consumer_lag`: int
  - Add `GET /api/agents/operations` returning detailed instrumentation for all 5 agents.
  - **Dependencies:** None.
  - **Complexity:** Medium (M)
  - **Test Requirements:** Agent metrics recording tests in `tests/test_agents.py`.
  - **Acceptance Criteria:** API returns exact runtime latency and outcome breakdown.

---

## EPIC 6: Frontend Race-Intelligence Cockpit Rebuild

### Feature 6.1: Real Circuit Renderer & Telemetry Popovers
- **TASK-601: Interactive Circuit Map Component**
  - **File:** `frontend/src/components/TrackMap.tsx`
  - **Description:** Replace the generic SVG oval with a Canvas / SVG renderer loading GeoJSON geometry from `/api/circuits/{circuit_id}`.
    - Renders track centerline, corner numbers/names, sector boundaries, pit lane, and DRS zones.
    - Dynamically renders all 20+ driver markers on centerline based on progress $s$.
    - Driver markers show driver number, team color bar, and status.
  - **Dependencies:** TASK-104, TASK-201
  - **Complexity:** Large (L)
  - **Test Requirements:** React testing library / Vitest component tests.
  - **Acceptance Criteria:** Monaco renders with 19 corners; Silverstone renders with 18 corners.

- **TASK-602: Driver Telemetry Popover & Detail Inspector**
  - **File:** `frontend/src/components/DriverTelemetryPopover.tsx`
  - **Description:** Implement interactive popover that opens when clicking any car marker on the map or row in the leaderboard.
    - Displays Speed, Throttle, Brake, Gear, RPM, DRS, Tyre compound, Stint age, Gaps.
    - Displays data source, update latency (ms), and quality status (`OBSERVED` vs `ESTIMATED`).
    - Missing channels display `NOT AVAILABLE` with subdued styling.
  - **Dependencies:** TASK-203, TASK-601
  - **Complexity:** Medium (M)
  - **Test Requirements:** Component interaction tests.
  - **Acceptance Criteria:** Popover renders live data on click; closes on outside click or Esc.

- **TASK-603: Race Control & Stewarding Interface**
  - **File:** `frontend/src/components/RaceControlPanel.tsx`
  - **Description:** Build dedicated panel with 2 clearly separated tabs:
    - **Official FIA Feed:** Chronological cards for RCMs, flags, SC/VSC lifecycles, steward investigations, penalties.
    - **PULSE Consequence Analysis:** Side-by-side analytical assessment showing estimated sporting impact, penalty cost, and telemetry evidence.
  - **Dependencies:** TASK-302
  - **Complexity:** Medium (M)
  - **Test Requirements:** Component tests verifying segregation of official and AI cards.
  - **Acceptance Criteria:** User cannot mistake a PULSE prediction for an FIA official decision.

- **TASK-604: Agent Operations & Lineage Explorer**
  - **File:** `frontend/src/components/AgentOperationsPanel.tsx`, `frontend/src/components/LineageModal.tsx`
  - **Description:**
    - Live cards for all 5 agents showing status, messages, lag, latency p95, and terminal outcomes.
    - Lineage Explorer modal allowing users to click any assessment and inspect the full upstream chain: `Source Record -> Kafka Event -> Flink Processing -> Agent Finding -> Persisted Assessment`.
  - **Dependencies:** TASK-503
  - **Complexity:** Large (L)
  - **Test Requirements:** Component rendering tests with mocked operations API.
  - **Acceptance Criteria:** Displays full lineage graph with clickable node IDs.

- **TASK-605: Fix Header Mode & Connection Discrepancy**
  - **File:** `frontend/src/components/BroadcastBanner.tsx`
  - **Description:** Separate Data Mode (`SIMULATED`, `REPLAY`, `LIVE`) from Pipeline Connection (`KAFKA CONNECTED`, `IN-MEMORY DISPATCH`, `DISCONNECTED`). Remove conflicting "SIMULATED + LIVE STREAM" badge state.
  - **Dependencies:** None.
  - **Complexity:** Small (S)
  - **Test Requirements:** Visual state tests for banner combinations.
  - **Acceptance Criteria:** Mode and transport status displayed independently with distinct colors.

---

## EPIC 7: End-to-End Verification Harness (`pulse.testing.run_e2e`)

### Feature 7.1: Automated 10-Stage Verification Runner
- **TASK-701: Implement CLI Runner Entrypoint**
  - **File:** `backend/pulse/testing/run_e2e.py`
  - **Description:** Implement CLI command supporting:
    ```bash
    python -m pulse.testing.run_e2e \
      --season 2026 \
      --event Monaco \
      --session R \
      --mode replay \
      --replay-speed 1.0 \
      --fault-profile none \
      --report-dir artifacts/e2e/monaco
    ```
  - **Dependencies:** All previous backend epics.
  - **Complexity:** Medium (M)
  - **Test Requirements:** CLI argument parsing test.
  - **Acceptance Criteria:** CLI executes and creates report directory.

- **TASK-702: Implement 10-Stage Pipeline Executor & Reconciliation**
  - **File:** `backend/pulse/testing/orchestrator.py`
  - **Description:** Orchestrate and verify stages 1 through 10:
    1. Source Manifest check
    2. Kafka Producer accounting
    3. Consumer offset verification
    4. Flink Job state & checkpoint check via REST
    5. Driver state key audit
    6. Feature generation validation
    7. 5-agent execution accounting (`FINDING_EMITTED`, `NO_FINDING`, etc.)
    8. Fusion engine revision chain audit (v1 -> v2)
    9. PostgreSQL persistence verification
    10. API snapshot reconciliation
  - **Dependencies:** TASK-701, TASK-404, TASK-503
  - **Complexity:** Extra Large (XL)
  - **Test Requirements:** Test running orchestrator against seeded simulator run.
  - **Acceptance Criteria:** Produces stage reconciliation matrix with zero unaccounted records.

- **TASK-703: Implement 16 Deterministic Golden Fixtures**
  - **File:** `backend/pulse/testing/fixtures.py`
  - **Description:** Build 16 deterministic scenarios covering normal green flag running, VSC/SC lifecycles, yellow flags, undercut/overcut pit sequences, rain onset, drying transitions, duplicate events, out-of-order race control, agent crashes, and Flink checkpoint recovery.
  - **Dependencies:** TASK-702
  - **Complexity:** Large (L)
  - **Test Requirements:** Automated test running all 16 fixtures.
  - **Acceptance Criteria:** Actual outputs match golden expected outputs 100%.

- **TASK-704: Machine-Readable & Markdown Report Generator**
  - **File:** `backend/pulse/testing/reporter.py`
  - **Description:** Generate:
    - `e2e_report.json`: Machine-readable summary with stage statuses, metrics, and reconciliation counts.
    - `e2e_report.md`: Formatted executive Markdown report.
    - `stage_reconciliation.csv`: Line-by-line stage input/output accounting.
    - `agent_metrics.csv`: Per-agent latency, lag, and execution outcomes.
  - **Dependencies:** TASK-702
  - **Complexity:** Medium (M)
  - **Test Requirements:** Output format verification test.
  - **Acceptance Criteria:** Generates all 4 report files upon runner completion.

---

## EPIC 8: Pipeline Lab Interface

### Feature 8.1: Interactive Execution Graph & Replay Control
- **TASK-801: Pipeline Lab Backend API**
  - **File:** `backend/pulse/api/router.py`
  - **Description:** Add:
    - `GET /api/lab/graph`: Returns pipeline nodes, edges, active throughput, error count, and health.
    - `POST /api/lab/fault`: Injects specified fault profile (`DUPLICATE_EVENT`, `INJECT_LATENCY`, `DROP_EVENT`, `KILL_AGENT`).
  - **Dependencies:** TASK-503
  - **Complexity:** Medium (M)
  - **Test Requirements:** API test asserting fault injection triggering.
  - **Acceptance Criteria:** Injecting `DUPLICATE_EVENT` increments deduplication counter in normalizer.

- **TASK-802: Pipeline Lab UI View**
  - **File:** `frontend/src/components/PipelineLabView.tsx`
  - **Description:** Build visual pipeline execution graph with interactive nodes:
    - `SOURCE -> KAFKA -> FLINK -> STATE -> 5 AGENTS -> FUSION -> DB -> API -> DASHBOARD`.
    - Clicking any node opens live input/output counters and p95 latency.
    - Interactive replay speed slider (0.2x to 16x) and fault injection buttons.
    - Button to download verification reports.
  - **Dependencies:** TASK-801
  - **Complexity:** Large (L)
  - **Test Requirements:** Component interaction tests.
  - **Acceptance Criteria:** User can pause replay, inject a fault, and observe node error counter increment.

