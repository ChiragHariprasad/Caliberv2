# PULSE / CALIBRE — UI Screenshots & Visual Walkthrough

> **Comprehensive visual catalogue of all main aspects, forensic audit views, and operational cockpits across the PULSE (Formula 1 Tactical Streaming) and CALIBRE (Scoped Integrity Algebra) platform.**

This catalogue documents every major view, modal inspection drawer, formal epistemic workbench, distributed agent pipeline, and historical controversy scenario available in the system.

> [!TIP]
> **Need a curated summary for an executive or technical report?**
> See the [**Top 10 Report Screenshots Subfolder (`top10/`)**](top10/README.md) for the 10 must-add screens with section recommendations.

---

## Visual Table of Contents

| # | Aspect / View | Screenshot File | Primary Purpose |
|---|---|---|---|
| 01 | [Trackside Mission Control](#01-trackside-live-mission-control) | `01_trackside_mission_control.png` | Live circuit map, vehicle dots, timing gates, and participant telemetry shelf |
| 02 | [Tactical Strategy & Pit Window Drawer](#02-trackside-tactical-strategy--pit-window-drawer) | `02_trackside_tactical_drawer.png` | Pit delta loss analysis, undercut threat windows, and sector grip baselines |
| 03 | [Consequence Feed & Momentum Chart](#03-live-tactical-consequence-feed--momentum-chart) | `03_trackside_consequence_feed.png` | Fused multi-agent impact cards, heuristic calibration, and pace momentum |
| 04 | [Driver CAN-Bus Telemetry Modal](#04-driver-can-bus-telemetry-inspector-modal) | `04_driver_telemetry_modal.png` | High-frequency synchronized ECU waveforms (speed, throttle, brake, RPM, gear, DRS) |
| 05 | [Tactical Evidence Provenance Drawer](#05-tactical-evidence-provenance-drawer-why-this) | `05_tactical_evidence_drawer.png` | Slide-over sensor provenance, timestamp bounds, and counter-factual alternatives |
| 06 | [Integrity Board Matrix](#06-integrity-board-multi-contract-evidence-matrix) | `06_integrity_board_matrix.png` | 20-driver x 13-contract lattice integrity matrix (HEALTHY, SUSPECT, UNKNOWN, DEGRADED) |
| 07 | [Decision Inspector (Atoms)](#07-3-click-decision-inspector-constituent-evidence-atoms) | `07_decision_inspector_atoms.png` | 3-click forensic inspection of constituent sensor atoms, values, and formula DAG |
| 08 | [Decision Inspector (Crypto & Revisions)](#08-decision-inspector-cryptographic-hashes--revisions) | `08_decision_inspector_crypto_revisions.png` | BLAKE3 content/record hashes, Merkle proofs, and append-only revision ledger |
| 09 | [SIA Logic Lab (Superposition)](#09-sia-logic-lab-epistemic-envelope--superposition) | `09_sia_logic_lab_superposition.png` | Possible-world superposition, lattice bounds, and collapse conditions |
| 10 | [SIA Logic Lab (Entanglement Graph)](#10-sia-logic-lab-origin-entanglement-graph) | `10_sia_logic_lab_entanglement_graph.png` | Cross-stream origin dependencies, corroboration depth, and common-cause risk |
| 11 | [SIA Logic Lab (Contextuality DAG)](#11-sia-logic-lab-contextuality--scope-isolation-dag) | `11_sia_logic_lab_contextuality_dag.png` | Flag phase lifecycles, safety car directives, and driver exposure gating |
| 12 | [SIA Logic Lab (State Algebra Tree)](#12-sia-logic-lab-deterministic-state-algebra-evaluator) | `12_sia_logic_lab_state_algebra_tree.png` | Syntax tree evaluation of meet (INF) and join (SUP) lattice algebra expressions |
| 13 | [Agents & Pipeline (Runtime Agents)](#13-agents--pipeline-operational-pulse-specialist-agents) | `13_agents_pipeline_runtime.png` | Real-time observability for active Pulse agents (01–06), throughput, and latencies |
| 14 | [Agents & Pipeline (Findings Drawer)](#14-agents--pipeline-agent-live-finding-stream-drawer) | `14_agents_pipeline_findings_drawer.png` | Agent topic bindings, telemetry diagnostics, and chronological synthesized findings |
| 15 | [Agents & Pipeline (Target Archetypes)](#15-agents--pipeline-target-archetypes-a1a5-specification) | `15_agents_pipeline_target_archetypes.png` | Formal rules AR-1 to AR-10 separating pure observation from integrity grading |
| 16 | [Agents & Pipeline (Topology & Diagnostics)](#16-agents--pipeline-transport-diagnostics--topology) | `16_agents_pipeline_topology.png` | Event bus diagnostics, message lag, Flink normalizer, and ingestion rates |
| 17 | [Replay & Audit (Hash-Chain Verifier)](#17-replay--audit-cryptographic-hash-chain-ledger-verifier) | `17_replay_audit_verifier.png` | Automated SHA-256 / BLAKE3 cryptographic ledger verification with Merkle proofs |
| 18 | [Replay & Audit (As-Of Time Machine)](#18-replay--audit-bitemporal-as-of-knowledge-time-machine) | `18_replay_audit_as_of_query.png` | Retrospective query interface evaluating verdicts as of historical knowledge-time |
| 19 | [Replay & Audit (Scenarios Lab)](#19-replay--audit-synthetic-scenario-fault-injector) | `19_replay_audit_scenarios_lab.png` | Adversarial fault injection bench testing sensor dropouts and corrupted inputs |
| 20 | [Corpus: Abu Dhabi GP 2021](#20-historical-controversy-corpus-abu-dhabi-grand-prix-2021) | `20_historical_abu_dhabi_controversy.png` | Yas Marina replay analysing safety car unlapping and restart regulation compliance |
| 21 | [Corpus: British GP 2023](#21-historical-controversy-corpus-british-grand-prix-2023-silverstone) | `21_historical_silverstone_replay.png` | Silverstone high-speed telemetry replay with synchronized sector delta tracking |
| 22 | [Circuit Homologation & Empty State](#22-circuit-homologation--epistemic-empty-state-suzuka-preview) | `22_preview_suzuka_empty_state.png` | Suzuka geometry centerline projection and "NO SESSION DATA" verification state |

---

## Detailed UI Aspects & Screenshot Catalogue

### 01. Trackside Live Mission Control
![01_trackside_mission_control.png](01_trackside_mission_control.png)
- **File Name**: [`01_trackside_mission_control.png`](01_trackside_mission_control.png)
- **Aspect / Component**: Primary Mission Control Cockpit (`Trackside` View)
- **Description**:
  Central live operational cockpit displaying the Circuit de Monaco track map with real-time GPS vehicle coordinates, micro-sector speed indicators, and timing loops. On the right, the 35% telemetry shelf presents real-time driver gap deltas, tyre compounds (Soft/Medium/Hard) and stint ages, alongside the top dual-time bar tracking valid session time against in-memory transport status. Interactive controls allow operators to scrub race replay, adjust playback speed up to 10x, and filter participants by track status.

---

### 02. Trackside Tactical Strategy & Pit Window Drawer
![02_trackside_tactical_drawer.png](02_trackside_tactical_drawer.png)
- **File Name**: [`02_trackside_tactical_drawer.png`](02_trackside_tactical_drawer.png)
- **Aspect / Component**: Collapsible Strategy & Pit Advisory Drawer (`TacticalDrawer.tsx`)
- **Description**:
  Collapsible tactical analysis drawer providing non-epistemic strategic projections, including pit lane time loss deltas (21.4s under green vs 14.1s under VSC/SC) and undercut/overcut threat windows. Correlates multi-compound stint degradation models with micro-sector grip baselines and ambient temperature gradients across the circuit. Clearly labelled with advisory disclaimers to preserve the separation between formal evidence integrity and speculative strategy models.

---

### 03. Live Tactical Consequence Feed & Momentum Chart
![03_trackside_consequence_feed.png](03_trackside_consequence_feed.png)
- **File Name**: [`03_trackside_consequence_feed.png`](03_trackside_consequence_feed.png)
- **Aspect / Component**: Multi-Agent Consequence Synthesis (`ImpactCard.tsx`, `MomentumChart.tsx`, `PulseTimeline.tsx`)
- **Description**:
  Lower cockpit section highlighting the fused multi-agent consequence cards generated by Agent 05 (Fusion Engine) with deterministic heuristic calibration ratings and position retention forecasts. Flanked by the interactive lap-by-lap pace momentum delta chart and official race control event timeline detailing active safety car and pit phase directives. Operators can inspect individual findings to trace evidence provenance or review historical superseding revisions.

---

### 04. Driver CAN-Bus Telemetry Inspector Modal
![04_driver_telemetry_modal.png](04_driver_telemetry_modal.png)
- **File Name**: [`04_driver_telemetry_modal.png`](04_driver_telemetry_modal.png)
- **Aspect / Component**: Synchronous Vehicle Waveform Inspector (`DriverTelemetryModal.tsx`)
- **Description**:
  High-frequency modal inspection window rendering synchronous vehicle telemetry waveforms for Charles Leclerc (#16). Features multi-channel traces for speed (km/h), throttle pedal percentage, hydraulic braking pressure (bar), gear selection, engine RPM, DRS actuation state, and steering angle with sub-500ms sensor freshness. Provides kinematic sanity validation, highlighting rule-based anomaly detection such as sudden deceleration spikes exceeding 2.0g.

---

### 05. Tactical Evidence Provenance Drawer ("Why this?")
![05_tactical_evidence_drawer.png](05_tactical_evidence_drawer.png)
- **File Name**: [`05_tactical_evidence_drawer.png`](05_tactical_evidence_drawer.png)
- **Aspect / Component**: Epistemic Evidence Slide-over Drawer (`EvidenceDrawer.tsx`)
- **Description**:
  Epistemic deep-dive slide-over drawer explaining the underlying rationale and evidentiary backing for an Agent 05 tactical finding. Details raw event identifiers, sensor ingestion timestamps, confidence interval bounds, counter-factual alternatives, and corroborating witness atoms. Ensures complete auditability of automated strategic recommendations by surfacing the exact data sources and processing agents involved in every calculation.

---

### 06. Integrity Board (Multi-Contract Evidence Matrix)
![06_integrity_board_matrix.png](06_integrity_board_matrix.png)
- **File Name**: [`06_integrity_board_matrix.png`](06_integrity_board_matrix.png)
- **Aspect / Component**: SIA Multi-Contract Evaluation Matrix (`IntegrityMatrix.tsx`)
- **Description**:
  Comprehensive SIA governance dashboard mapping all 20 Formula 1 participants against Scoped Integrity Algebra contracts (C01–C13), color-coded by four-valued lattice state (HEALTHY, SUSPECT, UNKNOWN, DEGRADED). Provides top-level system health metrics, active alert filters, and real-time transponder-to-telemetry parity tracking. Clicking any cell immediately opens the forensic Decision Inspector to reveal underlying proofs.

---

### 07. 3-Click Decision Inspector (Constituent Evidence Atoms)
![07_decision_inspector_atoms.png](07_decision_inspector_atoms.png)
- **File Name**: [`07_decision_inspector_atoms.png`](07_decision_inspector_atoms.png)
- **Aspect / Component**: Forensic Decision Inspector — Atoms & Provenance (`DecisionInspector.tsx`)
- **Description**:
  Forensic audit drawer triggered by clicking any decision cell in the Integrity Matrix, exposing the formal formula DAG, revision counter, and individual constituent atoms (e.g., optical loop timing vs onboard CAN telemetry). Displays observed sensor values, physical measurement units, and millisecond-accurate timestamp bounds. Includes tolerance margin gauges showing the exact numerical buffer between measured inputs and contract thresholds.

---

### 08. Decision Inspector (Cryptographic Hashes & Revisions)
![08_decision_inspector_crypto_revisions.png](08_decision_inspector_crypto_revisions.png)
- **File Name**: [`08_decision_inspector_crypto_revisions.png`](08_decision_inspector_crypto_revisions.png)
- **Aspect / Component**: Cryptographic Record & Revision Ledger (`DecisionInspector.tsx`)
- **Description**:
  Lower section of the Decision Inspector displaying BLAKE3 content and record hashes, source-to-processing provenance chains, and zero common-cause failure exposure verifications. Tracks the complete immutable append-only revision ledger showing every state transition from ingestion to final verdict. Enables one-click copying of cryptographic hashes for independent verification against standalone offline verification tools.

---

### 09. SIA Logic Lab — Epistemic Envelope & Superposition
![09_sia_logic_lab_superposition.png](09_sia_logic_lab_superposition.png)
- **File Name**: [`09_sia_logic_lab_superposition.png`](09_sia_logic_lab_superposition.png)
- **Aspect / Component**: Formal Logic Lab — Envelope Workspace (`SuperpositionView.tsx`)
- **Description**:
  Formal epistemic workbench modeling decision uncertainty as a four-state lattice interval between lower and upper bounds (e.g. DEGRADED to HEALTHY). Displays resolution maturity status (OPEN, PROVISIONAL, FINAL) and tracks the pending epistemic conditions required to collapse the superposition. Allows verification of how partial or delayed evidence bounds the system's legitimate belief state without guessing missing data.

---

### 10. SIA Logic Lab — Origin Entanglement Graph
![10_sia_logic_lab_entanglement_graph.png](10_sia_logic_lab_entanglement_graph.png)
- **File Name**: [`10_sia_logic_lab_entanglement_graph.png`](10_sia_logic_lab_entanglement_graph.png)
- **Aspect / Component**: Formal Logic Lab — Provenance Workspace (`EntanglementGraph.tsx`)
- **Description**:
  Interactive dependency topology mapping cross-stream data flows between FOM optical loops, vehicle telematic gateways, and FIA stewarding feeds. Visualizes corroboration depth (D=2) and verifies that sensor origin closures remain disjoint to prevent common-cause failure vulnerabilities. Explicitly highlights shared infrastructure risks, alerting operators when redundant streams share a single physical point of failure.

---

### 11. SIA Logic Lab — Contextuality & Scope Isolation DAG
![11_sia_logic_lab_contextuality_dag.png](11_sia_logic_lab_contextuality_dag.png)
- **File Name**: [`11_sia_logic_lab_contextuality_dag.png`](11_sia_logic_lab_contextuality_dag.png)
- **Aspect / Component**: Formal Logic Lab — Contextuality Workspace (`ContextualityDag.tsx`)
- **Description**:
  Directed acyclic graph illustrating how session-level context states—including track flags, safety car phases, and driver pit lane statuses—gate the legitimate applicability of integrity contracts. Guarantees that rules are only evaluated under their epistemically valid operational envelope. Prevents out-of-context evaluations, such as applying green-flag minimum delta speeds during full-course red flag neutralizations.

---

### 12. SIA Logic Lab — Deterministic State Algebra Evaluator
![12_sia_logic_lab_state_algebra_tree.png](12_sia_logic_lab_state_algebra_tree.png)
- **File Name**: [`12_sia_logic_lab_state_algebra_tree.png`](12_sia_logic_lab_state_algebra_tree.png)
- **Aspect / Component**: Formal Logic Lab — Syntax Tree Evaluator (`StateAlgebraTree.tsx`)
- **Description**:
  Hierarchical AST evaluator rendering Boolean and lattice algebra expressions over meet (INF / AND) and join (SUP / OR) operators. Inspects live node evaluations and demonstrates how sensor quality degrades or propagates upward to determine the final contract integrity verdict. Provides an interactive playground for stewarding teams to test proposed contract modifications under deterministic formal semantics.

---

### 13. Agents & Pipeline — Operational Pulse Specialist Agents
![13_agents_pipeline_runtime.png](13_agents_pipeline_runtime.png)
- **File Name**: [`13_agents_pipeline_runtime.png`](13_agents_pipeline_runtime.png)
- **Aspect / Component**: Pipeline Observability Console (`AgentsPipelineView.tsx`)
- **Description**:
  Real-time observability console monitoring the 6 active runtime Pulse streaming agents (Event Control, Track State, Vehicle Response, Tyre Strategy, Consequence Fusion, and Integrity Bridge). Displays processed input message volumes, emitted findings, p95 latency percentiles (12.4ms), and event transport bus status. Summarizes key streaming metrics across 8 dedicated KPI cards, providing instant visibility into message broker health.

---

### 14. Agents & Pipeline — Agent Live Finding Stream Drawer
![14_agents_pipeline_findings_drawer.png](14_agents_pipeline_findings_drawer.png)
- **File Name**: [`14_agents_pipeline_findings_drawer.png`](14_agents_pipeline_findings_drawer.png)
- **Aspect / Component**: Agent Detailed Inspector & Stream Drawer (`AgentsPipelineView.tsx`)
- **Description**:
  Slide-over diagnostic inspector for individual agents (e.g., Race Event & Control Intelligence), displaying detailed agent role responsibilities, input/output Kafka topic bindings, and a real-time chronological log of synthesized evidence and finding messages. Permits low-level auditing of agent heuristics and message dispatch performance during live race conditions.

---

### 15. Agents & Pipeline — Target Archetypes (A1–A5 Specification)
![15_agents_pipeline_target_archetypes.png](15_agents_pipeline_target_archetypes.png)
- **File Name**: [`15_agents_pipeline_target_archetypes.png`](15_agents_pipeline_target_archetypes.png)
- **Aspect / Component**: Target Architecture Specification View (`AgentsPipelineView.tsx`)
- **Description**:
  Architectural specification matrix contrasting prototype CALIBRE target archetypes (A1 Measurement, A2 Vehicle Telemetry, A3 Spatial Geometry, A4 Session Context, A5 Feed Supervisor) against active streaming agents. Formally defines rules AR-1 through AR-10, separating pure observation from integrity grading. Links each archetype directly to its authoritative Python source implementation and corresponding unit test suite.

---

### 16. Agents & Pipeline — Transport Diagnostics & Topology
![16_agents_pipeline_topology.png](16_agents_pipeline_topology.png)
- **File Name**: [`16_agents_pipeline_topology.png`](16_agents_pipeline_topology.png)
- **Aspect / Component**: Streaming Bus Diagnostics (`AgentsPipelineView.tsx`)
- **Description**:
  End-to-end streaming architecture diagnostic dashboard detailing message broker connectivity (Kafka clustered vs in-memory deterministic bus), queue buffer lags, event ingestion cadences, and Apache Flink / in-process J1 normalizer state machines. Verifies that incoming raw telemetry packets are sequenced monotonically before entering the SIA kernel evaluation pipeline.

---

### 17. Replay & Audit — Cryptographic Hash-Chain Ledger Verifier
![17_replay_audit_verifier.png](17_replay_audit_verifier.png)
- **File Name**: [`17_replay_audit_verifier.png`](17_replay_audit_verifier.png)
- **Aspect / Component**: Cryptographic Ledger Verification Console (`ReplayAuditView.tsx`)
- **Description**:
  High-assurance forensic console executing automated cryptographic audits across all recorded decision instances. Confirms 100% hash-chain integrity using BLAKE3 and SHA-256 Merkle proofs, guaranteeing that historical telemetry and stewarding records remain tamper-evident. Summarizes verified chain counts, genesis block linkage, and historical revision depths for official scrutineering submission.

---

### 18. Replay & Audit — Bitemporal "As-Of" Knowledge Time Machine
![18_replay_audit_as_of_query.png](18_replay_audit_as_of_query.png)
- **File Name**: [`18_replay_audit_as_of_query.png`](18_replay_audit_as_of_query.png)
- **Aspect / Component**: Epistemic Time Machine Query (`ReplayAuditView.tsx`)
- **Description**:
  Bitemporal forensic query tool allowing operators to evaluate any decision instance exactly as known at a past knowledge-time timestamp ($K$). Contrasts retrospective delayed evidence arrivals against original event valid-time ($T$) to identify post-hoc data corrections. Crucial for post-race stewards' inquiries when determining what information was legitimately available at the moment a contested decision was made.

---

### 19. Replay & Audit — LAB Synthetic Scenario Fault Injector
![19_replay_audit_scenarios_lab.png](19_replay_audit_scenarios_lab.png)
- **File Name**: [`19_replay_audit_scenarios_lab.png`](19_replay_audit_scenarios_lab.png)
- **Aspect / Component**: Synthetic Stress-Testing Workbench (`ReplayAuditView.tsx`)
- **Description**:
  Interactive adversarial testing suite allowing engineers to inject simulated telemetry dropouts, transponder regressions, and flag misalignments. Evaluates how the SIA kernel responds to corrupt inputs by automatically transitioning affected decisions into SUSPECT or DEGRADED states. Validates fail-safe mathematical properties under deliberate sensor packet loss or network latency spikes.

---

### 20. Historical Controversy Corpus — Abu Dhabi Grand Prix 2021
![20_historical_abu_dhabi_controversy.png](20_historical_abu_dhabi_controversy.png)
- **File Name**: [`20_historical_abu_dhabi_controversy.png`](20_historical_abu_dhabi_controversy.png)
- **Aspect / Component**: Yas Marina Circuit Replay Session (`AppHeader.tsx`, `TrackMap.tsx`)
- **Description**:
  Specialized historical replay session of the decisive 2021 Abu Dhabi Grand Prix restart at Yas Marina Circuit. Replays multi-car transponder passages, safety car unlapping procedures, and regulatory evidence adequacy under controversial stewarding conditions. Evaluates whether the timing loops and track state evidence available to race control complied with sporting regulations governing safety car withdrawal.

---

### 21. Historical Controversy Corpus — British Grand Prix 2023 (Silverstone)
![21_historical_silverstone_replay.png](21_historical_silverstone_replay.png)
- **File Name**: [`21_historical_silverstone_replay.png`](21_historical_silverstone_replay.png)
- **Aspect / Component**: Silverstone Circuit Historical Replay (`TrackMap.tsx`, `ParticipantShelf.tsx`)
- **Description**:
  High-speed circuit replay session at Silverstone featuring synchronized CAN-bus telemetry, sector pace deltas, and live pit strategy calculations across all 20 drivers. Demonstrates multi-car high-g lateral cornering tracking and DRS deployment compliance through Maggotts, Becketts, and Chapel complex. Leverages Jolpica-F1 and FastF1 historical captures to benchmark system throughput against real championship data.

---

### 22. Circuit Homologation & Epistemic Empty State — Suzuka Preview
![22_preview_suzuka_empty_state.png](22_preview_suzuka_empty_state.png)
- **File Name**: [`22_preview_suzuka_empty_state.png`](22_preview_suzuka_empty_state.png)
- **Aspect / Component**: Homologated Track Geometry & Empty State (`TrackMap.tsx`, `App.tsx`)
- **Description**:
  Verified homologated circuit geometry view for Suzuka International Racing Course in preview mode. Displays the official centerline coordinate projection and sector demarcation while showcasing the "NO SESSION DATA AVAILABLE" state to prevent ungrounded inferences before telemetry capture ingestion. Demonstrates the platform's strict epistemic boundary: never rendering speculative car positions without admitted transponder telemetry.

---

## Capturing Updated Screenshots

To re-run the automated capture suite and regenerate all 22 screenshots at native 1920x1080 resolution, ensure the backend and frontend development servers are active and execute:

```powershell
python scripts/capture_ui_screenshots.py
```

All output PNG files are written to `screenshots/` and can be mirrored into `docs/screenshots/`.
