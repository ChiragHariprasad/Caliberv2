# PULSE (formerly CALIBRE)

> **Evidence-Integrity and Real-Time Formula 1 Analytics Platform built around SIA (Scoped Integrity Algebra) Core v3**

PULSE combines a distributed streaming backbone (**3-broker Apache Kafka KRaft** + **Apache Flink 1.18.1** + **FastAPI** + **React 18**) with **`sia_core_v3`**, a dependency-free Python deterministic integrity kernel (`DEGRADED < UNKNOWN < SUSPECT < HEALTHY`) using bitemporal indexing (`V`/`K`), transitive common-cause origin lineage, pre-admission finality quarantine, and RFC 8785 + SHA-256 hash-chained SQLite WAL persistence.

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
                        └─► FastAPI + Bounded SSE (max 64 listeners, optional X-API-Key) ──► React Cockpit
```

See the full architecture guides in [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md):
- [`docs/architecture/CURRENT_ARCHITECTURE.md`](docs/architecture/CURRENT_ARCHITECTURE.md) · [`docs/architecture/KAFKA_ARCHITECTURE.md`](docs/architecture/KAFKA_ARCHITECTURE.md) · [`docs/architecture/AGENT_ARCHITECTURE.md`](docs/architecture/AGENT_ARCHITECTURE.md)

---

## Verified System Status (Phase I Baseline)

| Dimension | Verified State | Reference |
|---|---|---|
| **Streaming & Durability** | 3-broker KRaft (`RF=3`, `MIN_ISR=2`), `70/70` topics verified zero drift, Flink `v3` `36/36` tasks running, sustained `12,320.9 msg/s` batch sweep & `10,585.9 msg/s` 3-session concurrent fan-in (`0` drops / `0` dedup violations) | [`KAFKA_ARCHITECTURE.md`](docs/architecture/KAFKA_ARCHITECTURE.md) · [`VALIDATION_AND_BENCHMARKS.md`](docs/validation/VALIDATION_AND_BENCHMARKS.md) |
| **Formal & Scientific Rigor** | `9` SIA invariants proven; `6`-baseline causal LORO (`revised_pulse` `MAE=0.5094s`, `PI95=93.91%`, held-out Japan `0.5730s` / `PI95=95.18%`); strict `PROVISIONAL` vs `CONFIRMED` & tri-state `CleanAirStatus` | [`SCIENTIFIC_FOUNDATIONS.md`](docs/research/SCIENTIFIC_FOUNDATIONS.md) · [`METHODOLOGY.md`](docs/METHODOLOGY.md) |
| **Replay & Security** | Standalone cold `seek(36321)` improved `-30.3%` (`21.08s -> 14.69s`, cached `0.29s–1.21s`), subprocess mean `70.88s`, `0` hash mismatches; restricted CORS, optional `PULSE_CONTROL_API_KEY` (`X-PULSE-API-Key`), bounded SSE (`64`) | [`CURRENT_ARCHITECTURE.md`](docs/architecture/CURRENT_ARCHITECTURE.md) · [`DECISION_LOG.md`](docs/decisions/DECISION_LOG.md) |
| **Automated Test Suites** | **`460 passed, 0 failed, 0 skipped`** (`450` non-chaos + `10` live 3-broker Kafka failover `T1–T10`); frontend `npm run build` `60` modules (`2.69s`); `70/70` Kafka topics & `12/12` canonical docs verified | [`VALIDATION_AND_BENCHMARKS.md`](docs/validation/VALIDATION_AND_BENCHMARKS.md) |
| **Patent / IP Posture** | Broad software (`1.5/10`) & standalone SIA (`2.5/10`) unpatentable/barred under US prior art & Indian Sec 3(k) (`2025` CRI Technical Effect standard); filing deferred pending physical interlock (`4.0/10`) + FTO | [`RESEARCH_AND_PRIOR_ART.md`](docs/research/RESEARCH_AND_PRIOR_ART.md) |

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

# 3. Reproducible scientific baseline & ablation suite (offline cached FastF1 data)
python scripts/run_baseline_comparison.py

# 4. Documentation consistency audit
python scripts/check_docs.py
```
