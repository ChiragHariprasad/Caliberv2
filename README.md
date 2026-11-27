# PULSE (formerly CALIBRE)

> **Evidence-Integrity and Real-Time Formula 1 Analytics Platform built around SIA (Scoped Integrity Algebra) Core v3**

PULSE combines a distributed streaming backbone (**3-broker Apache Kafka KRaft** + **Apache Flink 1.18.1** + **FastAPI** + **React 19**) with **`sia_core_v3`**, a dependency-free Python deterministic integrity kernel (`DEGRADED < UNKNOWN < SUSPECT < HEALTHY`) using bitemporal indexing (`V`/`K`), transitive common-cause origin lineage, pre-admission finality quarantine, and RFC 8785 + SHA-256 hash-chained SQLite WAL persistence.

PULSE explicitly separates **observed facts**, **statistical pace/degradation models**, **advisory pit-window projections** (`is_globally_optimal=False`), and **formal epistemic evidence verdicts**, and **never issues sporting penalties or mislabels synthetic/lab archives as official FIA telemetry**.

---

## Core Architecture

```text
RAW INGEST (pulse.raw.* — 9 topics, RF=3, min.insync.replicas=2, gzip)
   └─► Apache Flink 1.18.1 (pulse-canonical-normalizer-v3, 18 vertices / 36 subtasks)
          └─► NORMALIZED STREAMS (pulse.norm.* -> KafkaConsumer enable_auto_commit=False)
                 ├─► Agents 01–04 (EventControl, TrackState, VehicleResponse, TyreStrategy)
                 ├─► SIA Core v3 IntegrityAgent (Pre-admission quarantine, OriginDAG, SHA-256 WAL)
                 └─► Agent 05 ConsequenceFusionEngine (OBSERVED/PROVISIONAL/CONFIRMED/REJECTED/SUPERSEDED)
                        └─► FastAPI + Bounded SSE (max 64 listeners, fail-closed X-PULSE-API-Key / Bearer) ──► React Cockpit
```

See the full architecture guides in [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md):
- [`docs/architecture/CURRENT_ARCHITECTURE.md`](docs/architecture/CURRENT_ARCHITECTURE.md) · [`docs/architecture/KAFKA_ARCHITECTURE.md`](docs/architecture/KAFKA_ARCHITECTURE.md) · [`docs/architecture/AGENT_ARCHITECTURE.md`](docs/architecture/AGENT_ARCHITECTURE.md)

---

## Verified System Status (Phase J Release Candidate)

| Dimension | Verified State | Reference |
|---|---|---|
| **Streaming & Durability** | 3-broker KRaft (`RF=3`, `MIN_ISR=2`), `70` catalogued topics verified (`0` drift; `71` live with `pulse.agent.integrity.findings.v1`), Flink `v3` `18` vertices / `36` subtasks on `4` slots; **Tier 1** isolated broker sweeps (`73,662 msg/s` `gzip` / `83,809 msg/s` `zstd`, `30,569 msg/s` fan-in, `18,471 msg/s` SQLite drain) vs **Tier 2** sustained `110.86s` E2E (`Kafka -> Flink v3 -> 6 Agents -> unpaused SIA WAL -> per-event SQLite sink`): **`9.67 ev/s`**, `24` checkpoints (`0` failed), `978/978` WAL hashes intact post-restart | [`KAFKA_ARCHITECTURE.md`](docs/architecture/KAFKA_ARCHITECTURE.md) · [`VALIDATION_AND_BENCHMARKS.md`](docs/validation/VALIDATION_AND_BENCHMARKS.md) |
| **Formal & Scientific Rigor** | `12` SIA formal & semantic invariant test groups; **17-race cached corpus (`2021–2024`: 6 FastF1 + 11 OpenF1)** with `2,000`-replicate stint-block bootstrap (`lag-1 resid ACF = +0.38`): unseen `2023–2024` (`n=4,594`) `MAE=0.5288s [0.4855, 0.5740]`, `PI95=94.41% [93.69%, 95.12%]`; LORO-16 `MAE=0.5239s [0.4882, 0.5595]`, `PI95=94.28% [93.68%, 94.87%]`; dry `PI95=94.72%`, wet under-coverage `91.28% [89.14%, 93.25%]` flagged | [`SCIENTIFIC_FOUNDATIONS.md`](docs/research/SCIENTIFIC_FOUNDATIONS.md) · [`METHODOLOGY.md`](docs/METHODOLOGY.md) |
| **Replay & Security** | Uncontended cold `seek(36321)` `mean=14.98s` (`std=0.25s`, no-SIA `1.64s`, SIA+WAL `89.04%`), warm keyframe `0.33s–1.16s`, WAL recovery `0.75s` (`625/625` exact hashes); reconciles `14.69s` vs `70.88s` contended throttling and raises UI seek timeout to `120s`; fail-closed `PULSE_REQUIRE_CONTROL_AUTH` / non-dev / non-loopback key + CORS validation, HTTP `503` runtime guard, atomic SSE cap (`64`) | [`CURRENT_ARCHITECTURE.md`](docs/architecture/CURRENT_ARCHITECTURE.md) · [`DECISION_LOG.md`](docs/decisions/DECISION_LOG.md) |
| **Automated Test Suites** | **`467 passed, 0 failed, 0 skipped`** (`457` non-chaos in `192.01s` + `10` live `T1–T10` failover in `56.26s`); Vite build `60` modules (`1.38s`); `70/70` Kafka topics (`0` drift); `12/12` docs; live Chrome `13`-step walkthrough (`0` console/HTTP errors) | [`VALIDATION_AND_BENCHMARKS.md`](docs/validation/VALIDATION_AND_BENCHMARKS.md) |
| **Patent / IP Posture** | Broad software (`1.5/10`) & standalone SIA (`2.5/10`) unpatentable/barred under US prior art & Indian Sec 3(k) (`2025` CRI Technical Effect standard); Phase J upholds **Do Not File** — continue academic dissemination | [`RESEARCH_AND_PRIOR_ART.md`](docs/research/RESEARCH_AND_PRIOR_ART.md) |

> **Academic Demonstration Package:** Complete reproducible startup commands, a 13-step live technical walkthrough, benchmark summary, and honest known limitations are maintained in [`VALIDATION_AND_BENCHMARKS.md`](docs/validation/VALIDATION_AND_BENCHMARKS.md).

---

## Quick Start

### Option A — Live Kafka + Flink Mode (Full Distributed Runtime)
Ensure Docker containers (`kafka-1`, `kafka-2`, `kafka-3`, `calibre-flink-jobmanager`, `calibre-flink-taskmanager`) are healthy, then verify topics and start the backend & frontend:

```powershell
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
python -m pulse.stream.kafka_io --ensure --verify
$env:PULSE_TRANSPORT_MODE="KAFKA"
python -m uvicorn pulse.main:app --host 127.0.0.1 --port 8000 --log-level info
```

### Option B — Local Simulator Mode (Zero External Broker)
```powershell
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
$env:PULSE_TRANSPORT_MODE="SIMULATOR"
python -m uvicorn pulse.main:app --host 127.0.0.1 --port 8000 --log-level info
```

Start the React frontend cockpit:
```powershell
cd E:\Caliberv2\frontend
npm run build
npm run preview
```

---

## Running Verification & Benchmarks

```powershell
$env:PYTHONPATH="E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
# 1. Non-chaos core suites (SIA formal invariants, contracts, API/security, scientific evaluation, replay/durability)
pytest sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py -v --tb=short

# 2. Live 3-broker Kafka failover & EOS integration suite (requires healthy Docker cluster)
pytest backend/tests/test_kafka_integration_t1_t10.py -v --tb=short

# 3. Reproducible 6-race + 17-race (2021-2024) scientific baseline & generalization suites
python scripts/run_baseline_comparison.py
python scripts/run_phase_j_generalization.py

# 4. Documentation consistency audit
python scripts/check_docs.py
```
