# PULSE — Research Literature, F1 Data Governance & Claim-Level Patentability Analysis

**Audit Date:** 2026-11-26  
**Scope:** Peer-reviewed motorsport strategy research, Formula 1 data source & licensing boundaries, Google Patents primary-source Independent Claim 1 audit, and Indian Patents Act Section 3(k) / 2025 CRI Guidelines legal assessment.

---

## 1. Peer-Reviewed Motorsport Strategy & Operations Context

| Reference | Venue / Year | Core Methodology | Relationship & Contrast to PULSE |
|---|---|---|---|
| **Heilmeier, Graf, Betz & Lienkamp**, *"Application of Monte Carlo Methods to Consider Probabilistic Effects in a Race Simulation for Circuit Motorsport"* | *Applied Sciences* (MDPI), Vol. 10, 2020 | Lap-wise stochastic race simulation combining fuel mass burn, tyre degradation, starting loss, pit-duration variance, and probabilistic `SC`/`FCY` rollouts. | Establishes that constant global baselines (`76.0s`, fixed `21.5s` pit loss, `0.12 s/lap` wear) fail across circuits and neutralisations; justifies calibrated circuit pit-loss and explicit limitation disclosure in `PitWindowStrategySimulator`. |
| **Heilmeier, Thomaser, Graf & Betz**, *"Virtual Strategy Engineer: Using Artificial Neural Networks for Making Race Strategy Decisions in Circuit Motorsport"* | *Applied Sciences*, Vol. 10(21), Art. 7805, 2020 ([doi:10.3390/app10217805](https://doi.org/10.3390/app10217805)) | Neural strategy policy trained on 2014–2019 F1 timing data predicting pit timing and compound shifts under traffic. | Unlike opaque black-box policies, PULSE keeps pace/tyre regression inspectable (`SE`, `R^2`, empirical-Bayes pooling, explicit `model_limitations`) and separates speculative strategy advisories (`is_globally_optimal=False`) from formal SIA evidence verdicts. |
| **Piccinotti (Politecnico di Milano, DEIB)**, *"Open Loop Planning for Formula 1 Race Strategy Identification"* | MSc Thesis / Online MDP Research | Models multi-agent pit timing and tyre allocation under stochastic Safety Car and traffic transitions via open-loop UCT / Markov Decision Processes. | Highlights that full global optimality requires stochastic multi-agent rollouts across remaining race distance—hence PULSE strictly scopes `PitWindowStrategySimulator` to `ADVISORY_LOCAL_PIT_WINDOW_ONLY`. |
| **Catapult RaceWatch** | Industry Standard (FIA & F1 Teams) | Synchronizes telemetry, car positioning, lap timing, radio, and multi-angle video for Race Control and pit-wall operations. | PULSE does **not** claim video/transponder hardware parity with RaceWatch; its academic research differentiator is `sia_core_v3` (source-independence lineage graph, bitemporal `K`/`V` index, pre-admission finality quarantine, RFC 8785 chained verdicts). |

---

## 2. Formula 1 Data Sources, Compliance & Regime Segregation

| Source / Regime | Scope & Technical Resolution | Terms & Legal / Scientific Boundaries | PULSE Runtime Policy |
|---|---|---|---|
| **Official F1 Digital Products** (`formula1.com`, F1TV, SignalR Live Timing) | Proprietary live timing, multi-car telemetry, FOM feeds | Strictly prohibits scraping, bots, paywall bypass, and automated Text & Data Mining (TDM). | **Never accessed, scraped, or bypassed.** Missing CAN-bus channels remain `UNAVAILABLE`. |
| **FastF1 (v3.9.0+)** | ~3–4 Hz resampled car telemetry, laps, sectors, `LapStartTime`, weather, race control | Unofficial community wrapper over public replay endpoints; redistribution of proprietary payloads restricted. | Used **strictly offline** from workspace cache (`data/fastf1_cache/`) across held-out/calibration validation (`2021–2022`). |
| **OpenF1** (`api.openf1.org`) & **Jolpica-F1** (`api.jolpi.ca/ergast/f1/`) | Community REST/WebSocket (2023+ OpenF1; 1950+ Jolpica CC BY-NC-SA lap/pit summaries) | Lacks surveyed timing-loop transponder pulses and high-rate ECU traces; non-official. | Mapped transparently into `LAB` / `PUBLIC` data regimes with explicit `F1_FOM_TIMING` upstream closure. |
| **`SYNTHETIC` / `LAB` / `PREVIEW`** (Runtime Sessions) | Scenario replays, fault-injected stress harnesses, geometry previews | Zero independent hardware redundancy (`source depth = 1` on public feeds). | `_apply_honest_session_provenance()` labels all 12 registry entries truthfully (`PULSE_SYNTHETIC_SIMULATOR`, `JOLPICA_OPEN_AND_SYNTHETIC_TELEMETRY`, `PULSE_LAB_REPLAY_CAPTURE`, `PREVIEW_GEOMETRY_CATALOGUE`). |

---

## 3. Corrected Prior-Art Audit & Independent Claim 1 Comparison

### 3.1 Removal of Misattributed Patents (2026 Audit Correction)
Earlier project notes (`COMPREHENSIVE_SYSTEM_AUDIT_2026.md`) cited five patents whose actual Google Patents disclosures do not support the claimed PULSE/SIA mapping:
- **`US7578182B2`** — Actually *Detection of prepped tires* (chemical vapor detector), **not** motorsport predictive gap tracking.
- **`US20030117275A1`** — General automotive *Apparatus for detecting potential tire failure*, **not** live F1 telemetry strategy.
- **`US11069450B2`** & **`US9997265B2`** — Mitsubishi Electric *Nuclear reactor protection systems*, outside sports telemetry software.
- **`US10502806`** — No matching sensor-fusion / guard-band utility patent found.

### 3.2 Verified Prior Art: Claim-Level Overlap Matrix

| Patent ID | Title (Assignee) | Independent Claim 1 Functional Scope | Direct Overlap with PULSE / SIA | Remaining Structural Delta |
|---|---|---|---|---|
| **`US6020851A`** | *Auto race monitoring system* (Busack) | Track-side transmitters/receivers triangulating race-vehicle location and transmitting live vehicle telemetry (speed, pressures, engine metrics) to monitoring receivers/displays. | Directly anticipates live motorsport positional tracking, multi-channel vehicle telemetry ingest, and race monitoring displays. | Lacks bitemporal epistemic algebra, common-cause lineage collapse, or cryptographic hash chaining. |
| **`US20080036587A1`** | *Race tracking system and method* (Meinzen) | GPS/RTK hardware/software acquisition rendering live race vehicle positions and telemetry visualizations. | Directly anticipates track map UI (`Trackside`) and live gap/position rendering. | Does not disclose formal epistemic grading (`HEALTHY`/`SUSPECT`/`UNKNOWN`/`DEGRADED`) or pre-admission quarantine. |
| **`US8713073B2`** | *Management of temporal data by means of a canonical schema* (Asserted Versioning) | Canonical schema storing bitemporal effective-time (`valid time`) and assertion-time (`transaction time`) periods within unified temporal tables enforcing temporal integrity constraints. | Anticipated `V`/`K` separation and `as_of(K)` historical state queries at the schema/database level. | Focused on relational temporal versioning rather than multi-source common-cause DAG closure or pre-admission stream quarantine. |
| **`US10445698B2`** | *System and method for forming, storing, managing, and executing contracts* (Clause / DocuSign) | Transforming natural-language/structured agreements into executable object graphs whose state transitions and evaluations record immutably onto append-only hash-linked structures. | Anticipated computable evidence contracts (`C01–C13`) mapped onto immutable verdict logs. | Does not pair computable contracts with guarded physical measurement uncertainty (`P3`) or common-cause upstream collapse. |
| **`US10614239B2`** | *Immutable cryptographically secured ledger-backed databases* (Amazon / QLDB) | Append-only journaled database maintaining cryptographically linked blocks/hash chains over committed state revisions for tamper-evident history verification without decentralized consensus. | Directly anticipates `SIAWALStore` + chained `record_hash` / `previous_digest` ledger verification. | Lacks sports-telemetry stream normalization, guard-banded epistemic lattice, and pre-finality quarantine rules. |
| **`US11418345B2`** | *Digest proofs in a journaled database* (Amazon) | Generating and verifying inclusion/consistency digest proofs over ordered transaction journal entries to authenticate state history independently. | Directly anticipates offline standalone chain verification and bit-identical replay digest checks (`SHA-256` / RFC 8785). | Does not compute epistemic possibility bounds over partial/uncorroborated real-time sensor streams. |
| **`US11567823B2`** | *Method and system for identifying and evaluating common cause failures of system components* (Siemens) | Automated safety/fault-tree analysis tracing shared component dependencies and resolving closed loops to detect common-cause failures across redundant channels. | Crowded prior art against `OriginRegistry` common-cause dependency detection and source-depth collapse (`depth=1`). | Operates in industrial fault-tree design/maintenance rather than online bitemporal finality quarantine. |
| **`US11747360B2`** | *Neural network system ... for estimation of aircraft air data* | Cross-validating heterogeneous/analytical signal modalities to detect and mitigate common-cause pitot-static sensor failures. | Crowded prior art against multi-source cross-validation for fault isolation. | ML flight-data reconstruction rather than deterministic stdlib lattice verdicting (`ADR-01`). |
| **`US20180089328A1`** | *Techniques for ingesting metrics data* (Splunk) | Evaluating streaming event timestamps against ingestion acceptance windows and routing anomalous / late / malformed records to quarantine storage separate from indexed primary storage. | Directly anticipates routing late/malformed telemetry records into `quarantined_items` / WAL `quarantine` outside main query views. | Does not link quarantine cutoff directly to sealed contract `finality_status` + cryptographic `verdict_hash` invariance. |
| **`US11943123B1`** | *Time-State Analytics Platform* | Aggregating streaming events into watermark-bounded state spans (`Timeline`) across entities for streaming analytics. | Crowded prior art against Kafka/Flink watermark state-span construction (`TrackStateAgent` / `Normalizer`). | General analytics platform without SIA cryptographic finality locks. |

---

## 4. Indian Patents Act Section 3(k) & 2025 CRI Guidelines Assessment

1. **Statutory Framework & Judicial Evolution:**
   - **Section 3(k)** of the Patents Act, 1970 bars patents on *"a mathematical or business method or a computer programme per se or algorithms."*
   - Following ***Ferid Allani v. Union of India*** (`2019:DHC:6944`) and ***Microsoft Technology Licensing LLC v. Assistant Controller*** (`2023`), the Indian Patent Office's **2025 CRI Guidelines** abandon the deprecated rigid "novel hardware" gate and evaluate computer-related inventions on whether the claimed subject matter achieves a concrete **technical effect or technical contribution** (e.g., measurably improving underlying computer/network system security, storage efficiency, deterministic state consistency, or gating physical/industrial controllers) beyond abstract mathematical evaluation or business rules.

2. **Claim Strategy Evaluation & Honest Scores (Not Legal Advice — Formal Counsel Required):**

| Candidate Claim Scope | Defensibility Score | Legal & Technical Analysis | Recommendation |
|---|---:|---|---|
| **Scope A: Broad Platform** (*Kafka + Flink + F1 Multi-Agent Analytics + React UI*) | **`1.5 / 10`** | Fully anticipated cleanly by `US6020851A`, `US20080036587A1`, `US11943123B1`, and Heilmeier et al. (2020); Section 3(k) bars statistical pace regression + UI presentation *per se*. | **Do Not File** |
| **Scope B: Standalone Software SIA** (*Bitemporal `K`/`V` + 4-State Lattice + RFC 8785 Chain + Quarantine*) | **`2.5 / 10`** | Individually anticipated by `US8713073B2`, `US10614239B2`, `US11418345B2`, `US10445698B2`, `US20180089328A1`, and `US11567823B2`. Pure in-memory/SQLite data verification risks Section 3(k) rejection as an abstract verification algorithm unless tied to demonstrable system/hardware technical effect. | **Do Not File** (`PULSE-ADR-016`) |
| **Scope C: Narrowest Arguable Technical Contribution** (*Fail-Closed Stream-to-Actuator Interlock + Deterministic Distributed Partition Replica Convergence*) | **`4.0 / 10`** | Combines: (i) *pre-admission finality quarantine prior to immutable ledger append* under bounded clock-skew (`session_t0` supersession invariance), (ii) *transitive common-cause origin collapse*, and (iii) *fail-closed hardware/network control gating* guaranteeing identical `verdict_hash` convergence across replicated partition failovers while preventing stale/compromised telemetry frames from actuating downstream physical controllers. **Gap today:** PULSE currently runs software dashboards (`ADVISORY` only) with no physical pit/track controller actuation wired. | **Deferred Pending Hardware Interlock & Independent Espacenet/USPTO FTO Clearance** |

---

## 5. Verdict
In accordance with Rule 16 and `PULSE-ADR-016`, **no patent application should be filed on PULSE or standalone SIA in its current Phase I software state**. Prior-art density across temporal databases (`US8713073B2`), journaled ledgers (`US10614239B2`), metrics quarantine (`US20180089328A1`), and common-cause fault trees (`US11567823B2`) leaves narrow headroom that requires physical/network control coupling and formal registered-attorney FTO analysis prior to any submission.
