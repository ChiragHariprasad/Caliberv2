# Top 10 Must-Add UI Screenshots for Executive & Technical Reports

> **Curated selection of the 10 most impactful UI screens from CALIBRE / PULSE, optimized for inclusion in engineering audits, executive summaries, and formal architecture reports.**

This selection captures the end-to-end narrative of the platform: from real-time trackside operations and CAN-bus telemetry ingestion to Scoped Integrity Algebra (SIA) governance, mathematical envelope superposition, distributed multi-agent diagnostics, and cryptographic ledger verification.

---

## Executive Report Overview Table

| # | Screenshot Name | Core Domain | Recommended Report Section | High-Level Significance |
|---|---|---|---|---|
| **01** | [`01_trackside_mission_control.png`](screenshots/top10/01_trackside_mission_control.png) | Trackside Cockpit | Operational Overview / Executive Summary | Primary live race cockpit with track map, GPS coordinates, and participant shelf |
| **02** | [`02_driver_telemetry_modal.png`](screenshots/top10/02_driver_telemetry_modal.png) | Vehicle Telemetry | Sensor Ingestion & Telemetry Architecture | Synchronous CAN-bus ECU waveforms (speed, throttle, brake, RPM, DRS, steering) |
| **03** | [`03_trackside_consequence_feed.png`](screenshots/top10/03_trackside_consequence_feed.png) | Consequence Intelligence | Multi-Agent Fusion & Tactical Reasoning | Agent 05 fused impact cards, heuristic calibration ratings, and momentum delta |
| **04** | [`04_integrity_board_matrix.png`](screenshots/top10/04_integrity_board_matrix.png) | SIA Integrity Governance | Integrity Evaluation & Contract Conformance | Multi-driver x multi-contract lattice matrix (`HEALTHY`, `SUSPECT`, `UNKNOWN`, `DEGRADED`) |
| **05** | [`05_decision_inspector_atoms.png`](screenshots/top10/05_decision_inspector_atoms.png) | Epistemic Forensics | Evidence Provenance & Scrutineering | 3-click forensic inspection of constituent sensor atoms, precision unc, and formula DAG |
| **06** | [`06_decision_inspector_crypto_revisions.png`](screenshots/top10/06_decision_inspector_crypto_revisions.png) | Cryptographic Records | Tamper-Evident Ledger & Scrutineering | BLAKE3 content/record hashes, Merkle proofs, and immutable append-only revision ledger |
| **07** | [`07_sia_logic_lab_superposition.png`](screenshots/top10/07_sia_logic_lab_superposition.png) | Mathematical Workbench | SIA Core v3 Mathematical Semantics | Four-valued lattice interval modeling decision uncertainty, maturity, and collapse triggers |
| **08** | [`08_sia_logic_lab_entanglement_graph.png`](screenshots/top10/08_sia_logic_lab_entanglement_graph.png) | Provenance & Risk | Common-Cause Failure & Reliability Analysis | Interactive origin topology verifying disjoint data paths and independent witness corroboration |
| **09** | [`09_agents_pipeline_runtime.png`](screenshots/top10/09_agents_pipeline_runtime.png) | Distributed Infrastructure | Distributed Systems & Runtime Observability | Active Pulse streaming agents (01–06), throughput counters, and 12.4ms p95 latencies |
| **10** | [`10_replay_audit_verifier.png`](screenshots/top10/10_replay_audit_verifier.png) | Scrutineering Audit | Compliance Audit & Scrutineering Sign-Off | Cryptographic hash-chain audit proving 100% data integrity and zero record tampering |

---

## Detailed Report Screenshot Catalogue

### 01. Trackside Live Mission Control
![01_trackside_mission_control.png](screenshots/top10/01_trackside_mission_control.png)
- **File Name**: `01_trackside_mission_control.png`
- **Report Section**: *Section 1: Live Operational Overview & Mission Control*
- **Description**:
  Central live operational cockpit displaying the Circuit de Monaco track map with real-time GPS vehicle coordinates, micro-sector speed indicators, and timing loops. On the right, the 35% telemetry shelf presents real-time driver gap deltas, tyre compounds (Soft/Medium/Hard) and stint ages, alongside the top dual-time bar tracking valid session time against in-memory transport status. Interactive controls allow operators to scrub race replay, adjust playback speed up to 10x, and filter participants by track status.

### 02. Driver CAN-Bus Telemetry Inspector Modal
![02_driver_telemetry_modal.png](screenshots/top10/02_driver_telemetry_modal.png)
- **File Name**: `02_driver_telemetry_modal.png`
- **Report Section**: *Section 2: High-Frequency Ingestion & Asset Telemetry*
- **Description**:
  High-frequency modal inspection window rendering synchronous vehicle telemetry waveforms for Charles Leclerc (#16). Features multi-channel traces for speed (km/h), throttle pedal percentage, hydraulic braking pressure (bar), gear selection, engine RPM, DRS actuation state, and steering angle with sub-500ms sensor freshness. Provides kinematic sanity validation, highlighting rule-based anomaly detection such as sudden deceleration spikes exceeding 2.0g.

### 03. Live Tactical Consequence Feed & Momentum Chart
![03_trackside_consequence_feed.png](screenshots/top10/03_trackside_consequence_feed.png)
- **File Name**: `03_trackside_consequence_feed.png`
- **Report Section**: *Section 3: Multi-Agent Consequence Synthesis & Strategy*
- **Description**:
  Lower cockpit section highlighting the fused multi-agent consequence cards generated by Agent 05 (Fusion Engine) with deterministic heuristic calibration ratings and position retention forecasts. Flanked by the interactive lap-by-lap pace momentum delta chart and official race control event timeline detailing active safety car and pit phase directives. Operators can inspect individual findings to trace evidence provenance or review historical superseding revisions.

### 04. Integrity Board (Multi-Contract Evidence Matrix)
![04_integrity_board_matrix.png](screenshots/top10/04_integrity_board_matrix.png)
- **File Name**: `04_integrity_board_matrix.png`
- **Report Section**: *Section 4: Scoped Integrity Algebra (SIA) Governance Matrix*
- **Description**:
  Comprehensive SIA governance dashboard mapping all 20 Formula 1 participants against Scoped Integrity Algebra contracts (C01–C13), color-coded by four-valued lattice state (HEALTHY, SUSPECT, UNKNOWN, DEGRADED). Provides top-level system health metrics, active alert filters, and real-time transponder-to-telemetry parity tracking. Clicking any cell immediately opens the forensic Decision Inspector to reveal underlying proofs.

### 05. 3-Click Decision Inspector (Constituent Evidence Atoms)
![05_decision_inspector_atoms.png](screenshots/top10/05_decision_inspector_atoms.png)
- **File Name**: `05_decision_inspector_atoms.png`
- **Report Section**: *Section 5: Forensic Evidence Atoms & Provenance*
- **Description**:
  Forensic audit drawer triggered by clicking any decision cell in the Integrity Matrix, exposing the formal formula DAG, revision counter, and individual constituent atoms (e.g., optical loop timing vs onboard CAN telemetry). Displays observed sensor values, physical measurement units, and millisecond-accurate timestamp bounds. Includes tolerance margin gauges showing the exact numerical buffer between measured inputs and contract thresholds.

### 06. Decision Inspector (Cryptographic Record & Revision History)
![06_decision_inspector_crypto_revisions.png](screenshots/top10/06_decision_inspector_crypto_revisions.png)
- **File Name**: `06_decision_inspector_crypto_revisions.png`
- **Report Section**: *Section 6: Cryptographic Verification & Append-Only Ledger*
- **Description**:
  Lower section of the Decision Inspector displaying BLAKE3 content and record hashes, source-to-processing provenance chains, and zero common-cause failure exposure verifications. Tracks the complete immutable append-only revision ledger showing every state transition from ingestion to final verdict. Enables one-click copying of cryptographic hashes for independent verification against standalone offline verification tools.

### 07. SIA Logic Lab — Epistemic Envelope & Superposition
![07_sia_logic_lab_superposition.png](screenshots/top10/07_sia_logic_lab_superposition.png)
- **File Name**: `07_sia_logic_lab_superposition.png`
- **Report Section**: *Section 7: Epistemic Uncertainty & Superposition Mechanics*
- **Description**:
  Formal epistemic workbench modeling decision uncertainty as a four-state lattice interval between lower and upper bounds (e.g. DEGRADED to HEALTHY). Displays resolution maturity status (OPEN, PROVISIONAL, FINAL) and tracks the pending epistemic conditions required to collapse the superposition. Allows verification of how partial or delayed evidence bounds the system's legitimate belief state without guessing missing data.

### 08. SIA Logic Lab — Origin Entanglement Graph
![08_sia_logic_lab_entanglement_graph.png](screenshots/top10/08_sia_logic_lab_entanglement_graph.png)
- **File Name**: `08_sia_logic_lab_entanglement_graph.png`
- **Report Section**: *Section 8: Common-Cause Risk & Independent Corroboration*
- **Description**:
  Interactive dependency topology mapping cross-stream data flows between FOM optical loops, vehicle telematic gateways, and FIA stewarding feeds. Visualizes corroboration depth (D=2) and verifies that sensor origin closures remain disjoint to prevent common-cause failure vulnerabilities. Explicitly highlights shared infrastructure risks, alerting operators when redundant streams share a single physical point of failure.

### 09. Agents & Pipeline — Distributed Runtime Diagnostics
![09_agents_pipeline_runtime.png](screenshots/top10/09_agents_pipeline_runtime.png)
- **File Name**: `09_agents_pipeline_runtime.png`
- **Report Section**: *Section 9: Streaming Architecture & Agent Pipeline Telemetry*
- **Description**:
  Real-time observability console monitoring the 6 active runtime Pulse streaming agents (Event Control, Track State, Vehicle Response, Tyre Strategy, Consequence Fusion, and Integrity Bridge). Displays processed input message volumes, emitted findings, p95 latency percentiles (12.4ms), and event transport bus status. Summarizes key streaming metrics across 8 dedicated KPI cards, providing instant visibility into message broker health.

### 10. Replay & Audit — Cryptographic Hash-Chain Ledger Verifier
![10_replay_audit_verifier.png](screenshots/top10/10_replay_audit_verifier.png)
- **File Name**: `10_replay_audit_verifier.png`
- **Report Section**: *Section 10: Forensic Compliance & Scrutineering Sign-off*
- **Description**:
  High-assurance forensic console executing automated cryptographic audits across all recorded decision instances. Confirms 100% hash-chain integrity using BLAKE3 and SHA-256 Merkle proofs, guaranteeing that historical telemetry and stewarding records remain tamper-evident. Summarizes verified chain counts, genesis block linkage, and historical revision depths for official scrutineering submission.

---

## Accessing Files

- Top 10 Subfolder: [`screenshots/top10/`](screenshots/top10/)
- Complete 22-Screenshot Gallery: [`UI_SCREENSHOTS.md`](UI_SCREENSHOTS.md)
