# PULSE / CALIBRE V2 — Reconstruction Status & Forward Roadmap

**Updated:** 2026-11-26 (`pulse-reconstruction` branch)

This document tracks what has been completed and runtime-verified during reconstruction versus what remains intentionally scoped out as future production hardening.

---

## 1. Completed & Runtime-Verified Milestones

| Stage | Scope | Status | Verification Evidence |
|---|---|---|---|
| **Baseline & Discovery** | Audited active codebase, reproduced Flink `ValidationException`, Kafka `kafka_client.py` vs `kafka_io.py` split-brain, SIA schema/finality defects, hardcoded F1 baselines, and slow uncached seek. | **Completed** | [audit/PULSE_BASELINE_VALIDATION.md](audit/PULSE_BASELINE_VALIDATION.md) |
| **Provenance & Regime Separation** | Replaced false `FIA_OFFICIAL_TIMING` claims across registries, manifests, UI badges, and stream projectors with `SYNTHETIC`, `LAB`, and `PREVIEW` regimes; enforced explicit `UNAVAILABLE` missing channels. | **Completed** | `backend/pulse/sessions/registry.py`, `backend/pulse/stream/projections.py`, UI re-audit |
| **SIA Core v3 Hardening** | Added `SIAWALStore` SQLite durability, pre-admission finality quarantine, canonical v3 `void_decision`, historical clock invariance, cycle-safe supersession, clinical ICU domain-independence test, and `verify_incremental()` + 12s position throttling. | **Completed** | `265/265` tests in `sia_core_v3/tests` + live WAL/quarantine verification |
| **F1 Scientific Reconstruction** | Replaced hardcoded `76.0s` / `21.5s` / `+0.12` heuristics with `RollingCleanAirPaceEstimator`, fuel-burn normalization, shrinkage-pooled `FuelCompensatedDegradationModel`, empirical `PitWindowStrategySimulator`, and SIA-gated `ConsequenceFusionEngine`. | **Completed** | `5`-race FastF1 benchmark (`-84.8%` to `-97.9%` MAE) & `test_phase3_f1_scientific.py` |
| **Kafka & Flink Unification** | Consolidated `kafka_client.py` onto `kafka_io` (`RF=3`, `MIN_ISR=2`, `gzip`, `DriverSlots`, DLQ, `IdempotentVerdictSink`); deployed `flink-sql-connector-kafka-3.1.0-1.18.jar`; repaired Flink 1.18 SQL metadata watermarks and dedup; retired-run & `PAUSED` buffer isolation in `main.py`. | **Completed** | `10/10` live `T1`–`T10` failover + `70/70` topics verified + Flink `RUNNING` |
| **Replay Checkpointing, API Isolation & UI Honesty** | Added keyframe checkpoints (`CHECKPOINT_INTERVAL=2000`), `404`/`409`/`422` API validation, zero-interpolation `MomentumChart` with endpoint de-confliction, non-nested buttons, `DNF / PIT BAY` framing, dynamic SIA Logic Lab & Pipeline diagrams, and polling/timeout hardening. | **Completed** | `421/421` pytest + `npm run build` (`1.42s`) + Chrome DevTools & `34,352` uvicorn log audit |
| **Literature, API Compliance & Prior-Art Audit** | Verified Heilmeier et al. (2020), Piccinotti MDP, Catapult RaceWatch, OpenF1/Jolpica/F1 ToU, and Google Patents primary texts; removed `5` misidentified patents; reassessed India Section 3(k) / CRI 2025 patentability (`1.5–4.0 / 10`). | **Completed** | [RESEARCH_AND_PRIOR_ART.md](RESEARCH_AND_PRIOR_ART.md) |

---

## 2. Explicit Boundaries & Remaining Production-Hardening Work

1. **Licensed Real-Time F1 Telemetry Feed:** PULSE operates ethically on offline FastF1 research caches, capture archives, and synthetic simulations (`F1` official live SignalR/F1TV scraping/DRM bypass is out of bounds). Live real-world track ops require a licensed telemetry agreement providing genuinely disjoint hardware timing loops (`INSTITUTIONAL` regime) for true `k >= 1` fault isolation.
2. **Multi-Worker Security & External Storage:** The FastAPI backend currently runs as a single process with permissive CORS (`*`), no RBAC/OAuth authentication, and local SQLite persistence (`SIAWALStore`, `IdempotentVerdictSink`). Multi-replica deployment would require Postgres/Timescale-backed SIA WAL storage, JWT/mTLS auth boundaries, and shared keyframe object storage.
3. **Full `calibre_core/agents/` Runtime Unification:** `calibre_core` archetypes A1–A5 are preserved as verified specification references alongside `backend/pulse/agents/`. Future unification can collapse both packages once `C01`–`C13` full-contract producers are licensed/populated.
4. **Formal Patent FTO Clearance (If Pursuing IP):** Any defensive or hardware-coupled pre-admission finality filing requires formal IP counsel prior-art clearance over `US11567823B2`, `US10614239B2`, `US8713073B2`, and `US20180089328A1`.
