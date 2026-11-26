# Research, Formula 1 Data Ecosystem, and Patent Prior-Art Audit

**Audit Date:** 2026-11-25  
**Scope:** Independent verification of motorsport analytics literature, live/historical Formula 1 data APIs & legal boundaries, and primary patent prior art (including Indian Patent Act Section 3(k) & 2025 CRI Guidelines).

---

## 1. Peer-Reviewed Motorsport Analytics Literature

| Study / Reference | Venue & Year | Methodology | Comparison to PULSE |
|---|---|---|---|
| **Heilmeier, Graf, Betz & Lienkamp**, *"Application of Monte Carlo Methods to Consider Probabilistic Effects in a Race Simulation for Circuit Motorsport"* | *Applied Sciences* (MDPI), Vol. 10, 2020 | Lap-wise race simulation combining fuel mass burn, tire degradation, starting performance, pit-stop duration variance, and stochastic Safety Car / FCY events via Monte Carlo rollouts. | Validates PULSE's core premise that neutralisations (`SC`/`VSC`) and fuel-mass burn cannot be treated with fixed constants (`+0.12 s/lap` / `76.0s` / `21.5s`); motivates explicit empirical uncertainty bounds and circuit-calibrated pit loss. |
| **Heilmeier, Thomaser, Graf & Betz**, *"Virtual Strategy Engineer: Using Artificial Neural Networks for Making Race Strategy Decisions in Circuit Motorsport"* | *Applied Sciences*, Vol. 10, Issue 21, Art. 7805, 2020 ([doi:10.3390/app10217805](https://doi.org/10.3390/app10217805)) | Neural strategy policy trained on 2014–2019 F1 timing data to select pit timing and compound transitions under live race states and traffic. | Unlike opaque neural black boxes, PULSE Phase 3 uses causal fuel-burn normalization, shrinkage-pooled OLS slopes (`SE`, `R^2`), and empirical field-gap projection so every pit advisory remains inspectable and auditable by SIA. |
| **Diego Piccinotti (Politecnico di Milano, DEIB)**, *"Open Loop Planning for Formula 1 Race Strategy Identification"* / Online MDP Strategy Planning | MSc Thesis / Collaboration under Prof. Marcello Restelli | Formulates pit-stop & tyre allocation under SC/traffic uncertainty as Markov Decision Processes (MDPs) solved with open-loop UCT / Monte Carlo tree search. | Highlights why multi-agent race strategy requires stochastic traffic re-entry modeling rather than single-step rule triggers. PULSE focuses on deterministic evidence gating & causal short-horizon state estimation (`<= 20` lap empirical delta + traffic conflict checks). |
| **Catapult RaceWatch** (Industry Standard — FIA & F1 Teams) | Commercial Motorsport Ops Platform | Synchronizes car telemetry, positioning, timing, weather, team radio, and multi-angle video for FIA Race Control monitoring and pit-wall operations. | PULSE does **not** compete with RaceWatch's optical track-limits video pipeline; PULSE's actual differentiator is **SIA (`sia_core_v3`)**: formal source-independence graph voting, bitemporal (`K`/`V`) state evaluation, pre-admission finality quarantine, and RFC 8785 hash-chained evidence verdicts. |

---

## 2. Formula 1 Data Sources & Legal/Compliance Boundaries

1. **Formula 1 Official Digital Products (`formula1.com`, F1TV, SignalR Live Timing)**
   - F1's Terms of Use explicitly prohibit automated scraping, bots, crawlers, bypass of authentication/paywall controls (`F1TV` / `livetiming.formula1.com`), and Text & Data Mining (TDM) or bulk extraction for model training/validation—even for non-commercial projects.
   - **PULSE Compliance Decision:** PULSE avoids F1TV paywall bypasses and never fabricates missing CAN-bus telemetry channels (`speed`, `throttle`, `brake`, `gear`, `rpm`, `drs` remain `UNAVAILABLE` unless supplied cleanly from captured non-proprietary streams).
2. **FastF1 (`https://docs.fastf1.dev`)**
   - Unofficial open-source Python library providing 2018+ session timing/laps/telemetry caches as Pandas DataFrames. Used **strictly offline** from pre-existing workspace cache (`data/fastf1_cache/`) as held-out scientific ground truth for 2021–2022 Grand Prix validation (`2021 British`, `2021 Saudi Arabian`, `2021 Abu Dhabi`, `2022 Monaco`, `2022 Japanese`).
3. **OpenF1 (`https://openf1.org`, `https://api.openf1.org/v1`)**
   - Unofficial open-source REST/CSV/WebSocket API covering historical data from 2023 onward (free historical queries) and authenticated live session windows. Explicitly not affiliated with Formula 1.
4. **Jolpica F1 (`https://api.jolpi.ca/ergast/f1/`)**
   - Community successor to the deprecated Ergast API offering historical F1 classification, standings, and lap/pit summaries (1950–present; ~4 req/s unauthenticated). Note: Jolpica provides summary results, not high-frequency telemetry.
5. **Provenance Honesty Requirement in PULSE**
   - Prior legacy code labeled 2026 synthetic scenarios and composed lab replays as `FIA_OFFICIAL_TIMING_AND_TELEMETRY` / `FIA-F1-DATA-ACQUISITION-V1`. Phase 1 reconstructed all manifests, registry entries, and envelope loaders to distinguish `SYNTHETIC`, `LAB`, and `PREVIEW` regimes accurately.

---

## 3. Corrected Patent Prior-Art Audit & Misidentification Corrections

A live primary-source verification against Google Patents uncovered **five significant misattributions / hallucinated patent mappings** in the earlier 2026 audit (`docs/COMPREHENSIVE_SYSTEM_AUDIT_2026.md`). Those errors are corrected below:

| Patent ID Cited Previously | Claimed Subject in Prior Audit | Actual Verified Title & Scope (Google Patents) | Audit Impact |
|---|---|---|---|
| **`US7578182B2`** | Claimed as *"real-time motorsport tracking & predictive race gaps"* | ***Detection of prepped tires*** — gas/semiconductor vapor detector sniffing chemical tire-prep treatments on racing tires. | **Incorrectly cited** as motorsport gap-tracking prior art. |
| **`US20030117275A1`** | Claimed as *"race tyre/telemetry systems"* | ***Apparatus for detecting potential tire failure*** (D. Scott Watkins) — general vehicle tire failure detection. | **Overstated** as motorsport strategy telemetry art. |
| **`US11069450B2`** | Cited as SIA sensor-independence voting | ***Nuclear reactor protection systems and methods*** (Mitsubishi Electric) — Reactor Trip & Engineered Safety Features I&C. | Domain is nuclear I&C, not motorsport/event streams (though conceptually related to redundant safety voting). |
| **`US9997265B2`** | Cited as generic sensor quorum/voting | ***Safety system for a nuclear power plant and method for operating the same*** (Mitsubishi Electric). | Domain is nuclear plant safety systems. |
| **`US10502806`** | Cited for uncertainty guard bands / voting | No verified sensor-fusion/guard-band utility patent matches bare `US10502806`. | Removed from prior-art table. |

### Verified Relevant Prior Art (Actual Google Patents Matches)

| Patent ID | Verified Title (Assignee) | Actual Disclosure & Relevance to PULSE / SIA |
|---|---|---|
| **`US6020851A`** | *Auto race monitoring system* (Busack) | Track-side ground positioning transmitters/receivers monitoring speed, attitude, and live race car telemetry. Directly anticipates generic live race telemetry monitoring. |
| **`US20080036587A1`** | *Race tracking system and method* (Meinzen) | Hardware/software GPS/RTK race tracking system. Anticipates generic race position tracking & cockpit rendering. |
| **`US8713073B2`** | *Management of temporal data by means of a canonical schema* | Managing bitemporal (`effective-time` & `assertion-time`) relational tables with temporal integrity constraints via canonical schemas. Anticipates generic bitemporal (`V`/`K`) representation and `as-of` querying. |
| **`US10445698B2`** | *System and method for forming, storing, managing, and executing contracts* | Stateful, immutable cryptographic graph data structures for computable/data-driven contracts. Directly relevant to computable contract + ledger execution. |
| **`US10614239B2`** & **`US11418345B2`** | *Immutable cryptographically secured ledger-backed databases* & *Digest proofs in a database journal* (Amazon Technologies / QLDB) | Append-only journal backed by SHA hash chains / Merkle digest proofs combined with temporal verification. Strongly anticipates standalone hash-chained ledgers. |
| **`US11567823B2`** | *Control method and device that resolves closed loops in automatic fault tree analysis* (Siemens AG) | Automated common-cause failure evaluation and closed-loop resolution across multi-component safety systems. Crowded prior art for common-cause correlation. |
| **`US11747360B2`** | *Neural network system ... for estimation of aircraft air data* | Avoiding common-cause sensor failures by generating analytical redundancy from independent source modalities. Crowded prior art for independent-source cross-validation. |
| **`US20180089328A1`** & **`US11943123B1`** | *Techniques for ingesting metrics data* (Splunk) & *Timeline framework for time-state analytics* | Routing out-of-order / anomalous timestamp stream records into quarantine buckets (`US20180089328A1`) and watermark-driven timeline state spans (`US11943123B1`). |

---

## 4. Indian Patent Act Section 3(k) & CRI Guidelines (2025) Patentability Verdict

1. **Statutory Bar (Section 3(k)):** Excludes *"a mathematical or business method or a computer programme per se or algorithms"*.
2. **2017 -> 2025 Evolution (*Ferid Allani v. Union of India*, `2019:DHC:6944`, & *Microsoft*):** The **IPO CRI Guidelines (2025)** discard the rigid 2016 "novel hardware" mandate and institutionalize the **Technical Effect / Technical Contribution** standard: a software-implemented system must solve a technical problem in computer/network/device operation (e.g., cryptographic state security, bounded resource utilization, deterministic real-time control gating) rather than claiming an abstract algorithm, dashboard UI, or mathematical evaluation *per se*.
3. **Overall Patentability Score & Narrowest Honest Strategy:**
   - **Broad PULSE Concept ("Kafka + multi-agent F1 analytics + React cockpit"): `1.5 / 10`** — Unpatentable over `US6020851A`, `US20080036587A1`, Heilmeier et al. (2020), and Section 3(k).
   - **Generic SIA Features ("bitemporal `K`/`V` schema + RFC 8785 hash chain + quarantine bucket"): `2.5 / 10`** — Anticipated individually by `US8713073B2`, `US10614239B2`, `US10445698B2`, and `US20180089328A1`.
   - **Narrowest Potentially Arguable Angle (Requires Physical/Network Coupling + Formal Counsel FTO): `4.0 / 10`** — Only a **combined fail-closed admission & hardware/network interlock** that executes *pre-admission finality quarantine prior to mutable ledger mutation* alongside *shared-lineage common-cause origin collapse under bounded clock-skew uncertainty* (producing deterministic `verdict_hash` invariance across distributed partition failovers and preventing late/compromised telemetry frames from actuating safety-critical pit/track controllers) even plausibly argues a non-trivial technical contribution. A formal prior-art clearance search on Espacenet/PATENTSCOPE/USPTO (focusing on `US11567823B2`, `US10614239B2`, `US20180089328A1`) would be mandatory before any filing.
