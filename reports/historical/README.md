# PULSE (formerly CALIBRE) — System Documentation Hub

**Last Reconstructed & Verified:** 2026-11-26  
**Repository:** `E:\Caliberv2` (`pulse-reconstruction` branch)

PULSE is a Formula 1-focused real-time sports event stream analytics platform built on three complementary engineering pillars:

1. **Pillar 1 — Distributed Event Stream Processing:** Multi-broker Apache Kafka (`RF=3`, `MIN_ISR=2`, `11` driver-affine `DriverSlots` partitions across `70` catalogued topics), Apache Flink `1.18.1` SQL canonical normalization (`pulse-canonical-normalizer-v2`), idempotent SQLite sink (`data/pulse_verdicts.sqlite`), dead-letter routing (`DLQ`), and keyframe-checkpointed historical replay.
2. **Pillar 2 — Explainable F1 Race Intelligence:** Causal, leak-free `VehicleResponseAgent` clean-air pace baselines (`RollingCleanAirPaceEstimator`), fuel-mass compensated tyre degradation OLS with hierarchical compound pooling (`FuelCompensatedDegradationModel`), empirical pit-window simulation (`PitWindowStrategySimulator`), track-state and race-control reducers, and SIA-gated `ConsequenceFusionEngine`.
3. **Pillar 3 — SIA Integrity Engine (`sia_core_v3`):** Deterministic 4-state epistemic algebra (`DEGRADED < UNKNOWN < SUSPECT < HEALTHY`), pre-admission finality quarantine, cycle-safe supersession, shared-lineage common-cause resilience analysis, SQLite WAL durability (`SIAWALStore`), and RFC 8785 Canonical JSON SHA-256 hash-chained verdict ledgers.

---

## Core Technical Documentation

| Document | Scope |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Implemented end-to-end architecture across ingestion, Kafka/Flink, Agents 01–06, Fusion, Replay, API/SSE, and React UI |
| [KAFKA_AND_FLINK_ARCHITECTURE.md](KAFKA_AND_FLINK_ARCHITECTURE.md) | Topic topology, `DriverSlots` partitioning, `gzip` Flink compatibility, Flink `1.18.1` SQL `normalizer_job.sql`, and chaos verification (`T1`–`T10`) |
| [SIA_INTEGRITY_ENGINE.md](SIA_INTEGRITY_ENGINE.md) | `sia_core_v3` algebraic semantics, finality quarantine, WAL durability, `verify_incremental()`, and non-motorsport domain independence |
| [F1_SCIENTIFIC_METHODOLOGY.md](F1_SCIENTIFIC_METHODOLOGY.md) | Honest data provenance regimes (`SYNTHETIC`, `LAB`, `PREVIEW`), fuel-burn & tyre regression math, and 5-race FastF1 evaluation results |
| [VALIDATION_AND_BENCHMARKS.md](VALIDATION_AND_BENCHMARKS.md) | Complete observed test counts (`431/431`), 3-run 72,642-event latency tables, keyframe seek speedups, and Chrome live dashboard verification |
| [RESEARCH_AND_PRIOR_ART.md](RESEARCH_AND_PRIOR_ART.md) | Peer-reviewed motorsport literature, F1 API legal boundaries, corrected patent prior-art table, and Indian Section 3(k) patentability assessment |
| [ROADMAP.md](ROADMAP.md) | Reconstructed phases status (Completed Stages B–G) and remaining production-hardening boundary |

---

## Historical & Baseline Reference Material

- [docs/audit/PULSE_BASELINE_VALIDATION.md](audit/PULSE_BASELINE_VALIDATION.md) — Phase 0 baseline reproduction of pre-reconstruction defects.
- [AUDIT.md](AUDIT.md) — Pre-reconstruction static engineering audit (22 November 2026 baseline record).
- [COMPREHENSIVE_SYSTEM_AUDIT_2026.md](COMPREHENSIVE_SYSTEM_AUDIT_2026.md) — Pre-reconstruction deep audit (note: patent misidentifications corrected in [RESEARCH_AND_PRIOR_ART.md](RESEARCH_AND_PRIOR_ART.md)).
- [DATA_SOURCING_ASSESSMENT.md](DATA_SOURCING_ASSESSMENT.md) — Public vs institutional F1 feed governance reference.
- [F1_CONTROVERSY_CORPUS.md](F1_CONTROVERSY_CORPUS.md), [DECISION_LOG.md](DECISION_LOG.md), [HISTORY.md](HISTORY.md), [UI_SCREENSHOTS.md](UI_SCREENSHOTS.md) — Preserved historical corpus, ADR, and visual catalogue records.
