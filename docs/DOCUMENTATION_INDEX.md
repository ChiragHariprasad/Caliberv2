# PULSE — Canonical Documentation Index

**Repository:** `E:\Caliberv2` · **Release Candidate Branch:** `pulse-phase-j-rc` *(preserved Phase I checkpoint `f5fbc6a` on `pulse-reconstruction`)* · **Total Canonical Markdown Documents:** `12` (`README.md`, `CHANGELOG.md`, and `10` documents inside `docs/`)

---

## Canonical Documentation Hierarchy

| # | Document | Audience | Authoritative Scope |
|---:|---|---|---|
| 1 | [`README.md`](../README.md) | All Engineers & Researchers | Project mission, quick-start (`KAFKA` & `SIMULATOR` modes), live architecture summary, test commands, and rules |
| 2 | [`CHANGELOG.md`](../CHANGELOG.md) | Reviewers & Release Maintainers | Chronological commits across Pre-Reconstruction (`9f1af40`), Phase H (`0017377`), Phase I (`f5fbc6a`), and Phase J RC |
| 3 | [`docs/DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md) | All Readers | Master navigation map enforcing clean single-source-of-truth documentation |
| 4 | [`docs/architecture/CURRENT_ARCHITECTURE.md`](architecture/CURRENT_ARCHITECTURE.md) | Systems & Backend Engineers | Live runtime architecture, Docker/Flink/FastAPI topology, replay & SQLite WAL stores, fail-closed security & SSE bounds |
| 5 | [`docs/architecture/ARCHITECTURE_HISTORY.md`](architecture/ARCHITECTURE_HISTORY.md) | Architects & Auditors | Reconstruction evolution from legacy CALIBRE prototypes (`calibre_core`) through Phase I and Phase J release validation |
| 6 | [`docs/architecture/KAFKA_ARCHITECTURE.md`](architecture/KAFKA_ARCHITECTURE.md) | Streaming & Infra Engineers | 3-broker KRaft cluster, `70`/`71` topic catalog (`pulse.norm.*`), partitioning/`gzip`, manual commit & Tier 1 vs Tier 2 E2E |
| 7 | [`docs/architecture/AGENT_ARCHITECTURE.md`](architecture/AGENT_ARCHITECTURE.md) | Multi-Agent & ML Engineers | Agents `01–05`, SIA Core v3 `IntegrityAgent` (`5` Python contract dicts), `FindingStatus` & clean-air states |
| 8 | [`docs/METHODOLOGY.md`](METHODOLOGY.md) | Scientists & Evaluators | 17-race FastF1/OpenF1 sourcing, walk-forward, LORO, stint/session block bootstrap, common-support & replay/Kafka methods |
| 9 | [`docs/research/SCIENTIFIC_FOUNDATIONS.md`](research/SCIENTIFIC_FOUNDATIONS.md) | Researchers & Formal Reviewers | SIA contribution statement, 4-state lattice vs multidimensional fidelity, verified invariants, controversy corpus (`2021–2024`) |
| 10 | [`docs/research/RESEARCH_AND_PRIOR_ART.md`](research/RESEARCH_AND_PRIOR_ART.md) | Legal / IP & Academic Reviewers | Literature survey, F1 licensing boundaries, corrected claim-level US patent audit, Sec 3(k) / 2025 CRI Do-Not-File posture |
| 11 | [`docs/validation/VALIDATION_AND_BENCHMARKS.md`](validation/VALIDATION_AND_BENCHMARKS.md) | QA, Perf & Scientific Reviewers | Final regression suites, 17-race generalization CIs, 7-boundary replay, Tier 1/2 Kafka, UI proof & **Academic Demo Package** |
| 12 | [`docs/decisions/DECISION_LOG.md`](decisions/DECISION_LOG.md) | Maintainers | Legacy `ADR-01..ADR-12` + `PULSE-ADR-009..PULSE-ADR-017` (Phase H/I/J accepted & rejected decisions) |

---

## Visual Assets & Historical Archives (Non-Canonical Read-Only Records)

- **UI Screenshot Catalogs:** [`docs/screenshots/`](screenshots/) · [`reports/browser-validation/screenshots/`](../reports/browser-validation/screenshots/)
- **Historical Audit & Pre-Phase-I Archives:** [`reports/historical/INDEX.md`](../reports/historical/INDEX.md) *(contains preserved Phase 0 audits, Phase H verification reports, early `COMPREHENSIVE_SYSTEM_AUDIT_2026.md`, `F1_CONTROVERSY_CORPUS.md` full narratives, and `benchmark_run_1..10`)*
- **Machine-Readable Baselines & Benchmarks:** [`reports/benchmarks/`](../reports/benchmarks/) · [`reports/validation/baselines/`](../reports/validation/baselines/)
