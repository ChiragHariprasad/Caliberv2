# PULSE Comprehensive Risk Register (v2.0)
**Risk Assessment, Detection Methods, Mitigations & Fallback Strategies**  
**Author:** Principal Software Architect, F1 Data Systems Engineer, SRE Lead  

---

## 1. Overview & Risk Matrix

| Risk ID | Category | Summary Description | Probability | Impact | Risk Severity | Owner |
|---|---|---|---|---|---|---|
| **RSK-LIC-01** | Regulatory/Licensing | F1 TV programmatic scraping violates subscription terms | HIGH | CRITICAL | **CRITICAL** | WS0-Governance |
| **RSK-DAT-01** | Data Access | Inability to access high-cadence car telemetry for live sessions | HIGH | HIGH | **HIGH** | WS1-Ingestion |
| **RSK-TEC-01** | Technical (Flink) | High complexity of PyFlink local cluster setup & job submission | MED | HIGH | **HIGH** | WS2-Flink |
| **RSK-TEC-02** | Technical (Kafka) | Unobserved Kafka disconnect falling back silently to in-memory bus | HIGH | HIGH | **HIGH** | WS1-Kafka |
| **RSK-DAT-02** | Data Integrity | LLM hallucinations generating fabricated team radio and confidence | HIGH | HIGH | **HIGH** | WS5-Agents |
| **RSK-TEC-03** | Technical (Ordering) | Out-of-order race control and timing events corrupting state machine | MED | HIGH | **HIGH** | WS4-E2E |
| **RSK-OPS-01** | Operational | Specialist agent process crashes during active race neutralisation | MED | MED | **MEDIUM** | WS5-Agents |
| **RSK-DEL-01** | Delivery | Test suite fragility due to hardcoded mock assumptions | HIGH | HIGH | **HIGH** | WS0-Fixes |
| **RSK-PER-01** | Performance | High-volume car telemetry overwhelms consumer processing | LOW | HIGH | **MEDIUM** | WS2-Flink |
| **RSK-GEO-01** | Technical (Geometry) | Incorrect corner coordinates or centerline topology distortion | LOW | MED | **MEDIUM** | WS1-Geometry |

---

## 2. Detailed Risk Profiles

### RSK-LIC-01: F1 TV Programmatic Scraping Violates Subscription Terms
- **Category:** Regulatory / Licensing
- **Probability:** HIGH
- **Impact:** CRITICAL
- **Description:** Attempting to automate browser scraping, reverse-engineer proprietary GraphQL/REST endpoints, or sniff auth tokens from the user's F1 TV Premium subscription violates F1 TV Terms of Use (Sections 6 & 8) and risks account termination, IP ban, or legal action.
- **Detection Method:** Continuous automated codebase audits searching for browser automation (`puppeteer`, `playwright`, `selenium`) or hardcoded F1 TV endpoints.
- **Mitigation:** Strict architecture policy: Zero programmatic access to F1 TV. Use FastF1 for permitted historical archive replay, Jolpica for public metadata, and the internal PULSE simulator for development and evaluation.
- **Fallback:** Run all development, CI/CD, and demonstrations exclusively on the deterministic simulator and approved historical capture files.
- **Owner:** WS0-Governance

---

### RSK-DAT-01: Inability to Access High-Cadence Car Telemetry for Live Sessions
- **Category:** Data Access
- **Probability:** HIGH
- **Impact:** HIGH
- **Description:** Authorized high-cadence car telemetry (throttle, brake, RPM, gear at 10-20 Hz) is restricted by FOM/commercial agreements and not publicly available as a free live stream.
- **Detection Method:** Data coverage matrix in `capture_manifest.yaml` checks telemetry field completeness before run admission.
- **Mitigation:** Enforce strict field-level completeness flags. When car telemetry is unavailable, Agent 3 (Vehicle Response) operates in `TIMING_ONLY` mode (using sector timing deltas) and sets telemetry channels to `NOT_AVAILABLE`. Never impute or invent missing sensors.
- **Fallback:** Clear UI badge stating: `"Chassis Telemetry Unavailable - Pace Derived from Micro-Sector Timing"`.
- **Owner:** WS1-Ingestion

---

### RSK-TEC-01: High Complexity of PyFlink Local Cluster Setup & Job Submission
- **Category:** Technical (Flink)
- **Probability:** MEDIUM
- **Impact:** HIGH
- **Description:** PyFlink requires Java 11/17, Py4J gateway bridges, and exact dependency matching between Python environments and Flink TaskManager containers, which can create brittle developer setup on Windows.
- **Detection Method:** Automated health probe querying Flink JobManager REST API (`http://localhost:8081/v1/jobs/overview`) during test harness startup.
- **Mitigation:**
  1. Provide a Docker Compose definition with pre-configured Flink JobManager and TaskManager images.
  2. Implement a Python streaming processor (`pulse.stream.processor`) implementing identical windowing and stateful semantics that can run directly inside pytest while the containerized Flink cluster runs in integration mode.
- **Fallback:** Automated script tests both native Flink submission and containerized submission, logging exact diagnostic errors if submission fails.
- **Owner:** WS2-Flink

---

### RSK-TEC-02: Unobserved Kafka Disconnect Falling Back Silently to In-Memory Bus
- **Category:** Technical (Kafka)
- **Probability:** HIGH
- **Impact:** HIGH
- **Description:** Current implementation catches Kafka connection failures and silently runs on `PulseEventBus`, giving the illusion of a working streaming backbone while the frontend banner displays `"LIVE STREAM"`.
- **Detection Method:** Runtime transport assertion in `GET /api/health` checking `broker.is_connected`.
- **Mitigation:**
  1. Frontend banner explicitly differentiates Data Mode (`SIMULATED | REPLAY | LIVE`) from Transport Status (`KAFKA_ONLINE | IN_MEMORY_TEST_DISPATCH | DISCONNECTED`).
  2. Integration tests and the E2E verification runner assert `transport == "KAFKA"` and fail immediately if running in fallback mode.
- **Fallback:** Local development unit tests explicitly set `PULSE_ALLOW_IN_MEMORY=True`, but production and E2E verification reject the fallback.
- **Owner:** WS1-Kafka

---

### RSK-DAT-02: LLM Hallucinations Generating Fabricated Team Radio and Confidence
- **Category:** Data Integrity
- **Probability:** HIGH
- **Impact:** HIGH
- **Description:** In `pulse/agents/fusion.py`, Groq LLM is used to generate synthetic team-radio dialogue (`"Lewis, stay out for now..."`), which the frontend explicitly misrepresents as `"AUTHENTIC TEAM RADIO TRANSMISSION"`.
- **Detection Method:** Unit tests auditing Fusion engine output for unverified string patterns or fabricated quote fields.
- **Mitigation:** Completely decouple LLMs from the analytical consequence path. Tactical summaries and consequence assessments must be generated by deterministic template engines based on verified inputs. Strip all fake radio quotes from the UI.
- **Fallback:** If an LLM is ever used for stylistic rephrasing, it must strictly summarize provided input fields without inventing dialogue or facts, and the UI badge must state `"LLM Summarized - Synthetic Formatting"`.
- **Owner:** WS5-Agents

---

### RSK-TEC-03: Out-of-Order Race Control and Timing Events Corrupting State Machine
- **Category:** Technical (Ordering)
- **Probability:** MEDIUM
- **Impact:** HIGH
- **Description:** Late arrival of race control events (e.g. `VSC_DEPLOYED` arriving after `VSC_ENDING`) can cause invalid state machine transitions.
- **Detection Method:** FSM validation assertions in Agent 1 logging invalid transition attempts.
- **Mitigation:** Flink Job 1 assigns `BoundedOutOfOrderness` watermarks to enforce event-time ordering. Agent 1 maintains an immutable transition log and rejects illegal transitions (e.g. `ENDED -> ACTIVE` without a new deployment event ID), emitting a review finding.
- **Fallback:** Golden fixture `GF-12` specifically tests out-of-order race control messages and confirms deterministic recovery.
- **Owner:** WS4-E2E

---

### RSK-OPS-01: Specialist Agent Process Crashes During Active Race Neutralisation
- **Category:** Operational
- **Probability:** MEDIUM
- **Impact:** MEDIUM
- **Description:** If Agent 4 (Tyre Strategy) crashes while Agent 1 has triggered a correlation group, Agent 5 could wait indefinitely or stall downstream assessment updates.
- **Detection Method:** Agent 5 correlation group timeout timer (deadline = 3.0s event-time) and Agent health heartbeat topic `pulse.ops.agent_health.v1`.
- **Mitigation:** Agent 5 publishes a `PROVISIONAL` assessment v1 upon Agent 1 event arrival. If Agent 4 findings do not arrive before the deadline, Agent 5 emits an updated assessment flagging `strategy: UNAVAILABLE` with widened uncertainty ranges rather than stalling the pipeline.
- **Fallback:** Golden fixture `GF-14` validates agent crash and pipeline continuation.
- **Owner:** WS5-Agents

---

### RSK-DEL-01: Test Suite Fragility Due to Hardcoded Mock Assumptions
- **Category:** Delivery
- **Probability:** HIGH
- **Impact:** HIGH
- **Description:** Existing unit tests like `test_event_control_agent_vsc` broke because hardcoded driver numbers (#16, #44) were added directly to agent code without updating tests or schemas.
- **Detection Method:** CI/CD test run execution (`pytest -v`).
- **Mitigation:**
  1. Fix `test_event_control_agent_vsc` in Task-001.
  2. Implement dynamic fixtures using parametric inputs rather than magic driver numbers.
  3. Require all tests to pass before any commit.
- **Fallback:** Automated pre-commit hook runs `pytest` and `npm run typecheck`.
- **Owner:** WS0-Fixes

---

### RSK-PER-01: High-Volume Car Telemetry Overwhelms Consumer Processing
- **Category:** Performance
- **Probability:** LOW
- **Impact:** HIGH
- **Description:** 20 cars streaming 20 Hz telemetry generates 400 msgs/sec, which could cause consumer lag if processed synchronously in Python services.
- **Detection Method:** Prometheus Kafka consumer lag metric `kafka_consumer_lag_records`.
- **Mitigation:**
  1. Partition `pulse.raw.telemetry.car.v1` into 20 partitions keyed by `driver_number`.
  2. Decouple high-frequency car telemetry from low-frequency race-control events.
  3. Flink Job 3 aggregates telemetry into 1-second tumbling windows before publishing to feature topics.
- **Fallback:** Throttling or downsampling filter in Flink Job 1 when consumer lag exceeds 500 ms.
- **Owner:** WS2-Flink

---

### RSK-GEO-01: Incorrect Corner Coordinates or Centerline Topology Distortion
- **Category:** Technical (Geometry)
- **Probability:** LOW
- **Impact:** MEDIUM
- **Description:** Hand-crafted track coordinates could cause cars to render off-track, in reverse direction, or disjointed across sector boundaries.
- **Detection Method:** Automated topology validator in `tests/test_circuits.py` checking closed polygon loop, monotonicity of distance markers, and corner sequence.
- **Mitigation:** Sourcing official GPS coordinates from verified open datasets (e.g. OpenStreetMap / Wikimedia verified circuit GeoJSON) and validating against official FIA circuit maps.
- **Fallback:** Revert to verified circuit geometry asset revision if a distortion is detected.
- **Owner:** WS1-Geometry

