# PULSE — Verification Results, Benchmarks & UI Audit Ledger

**Verification Timestamp:** 2026-11-26 (`pulse-reconstruction` branch)

---

## 1. Automated Test Suite Results (Observed Post-Final Edit)

| Suite / Command | Scope | Result | Timing | Warnings / Notes |
|---|---|---|---|---|
| `pytest sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | `sia_core_v3` (`265`), `calibre_core` (`23`), non-T2 `backend` (`133`) including API, SIA WAL/quarantine, clinical ICU domain test, scientific Phase 3 tests, Flink `normalizer_job` & Phase 4 reliability chaos tests, and Phase 6 keyframe replay/isolation | **`421 passed, 0 failed, 0 skipped`** | `167.61s` | `2` library deprecation warnings (`starlette` `multipart`, `fastf1` `.enable_cache`) |
| `pytest backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | Live 3-broker Kafka KRaft failover (`T1`–`T10`: broker stop/start, ISR `<2` safety, cooperative rebalance, EOS `read_committed`, SQLite sink, DLQ, static membership) | **`10 passed, 0 failed, 0 skipped`** | `21.78s` | Live `kafka-1/2/3` (`cp-kafka:7.7.0`) + `calibre-flink-*` running; `kafka_io --ensure --verify` confirmed `70/70` topics zero drift |
| `cd frontend; npm run build` | TypeScript compilation (`tsc -b`) + Vite bundle (`vite build`) | **`59 modules transformed, built in 1.42s`** | `1.42s` | `dist/index.html` (`0.88 kB`), `index-CO7VRx1q.js` (`467.02 kB`), `index-xk1TytgV.css` (`92.67 kB`) |

**Combined Total:** **`431 passed, 0 failed, 0 skipped`** across all automated Python suites.

---

## 2. Replay, Seek & Pipeline Latency Benchmarks

### 2.1 Mid-Race Seek & Snapshot Speedup (`f1-2023-silverstone-race`, `72,642` events)

| Operation | Phase 0 Baseline | Intermediate (`task-1678`) | Post-Reconstruction Observed | Speedup / Change |
|---|---:|---:|---:|---|
| Cold seek to mid-race (`target_index=36321`) | `141,183.6 ms` (`target=25000`) | `230,421.5 ms` (`target=36321`) | **`20,785.1 ms`** (`20.8s`, cooperative yield) | **`11.1x` faster** (`O(N^2)` position flood eliminated; UI polls never starve) |
| Keyframe cached seek (`target_index=36500` after `36321`) | Full rebuild (`~141s+`) | N/A | **`487.4 ms`** (in-process) / `~2s` end-to-end (`L10` via HTTP) | **`>280x` faster** vs uncached baseline; bit-identical hashes |
| Steady-state `GET /api/snapshot` | `6,776.7 ms` (`199.4 KB` mid-race) | `2,993.7 ms` | **`1.1 ms`** (in-process) / **`34.2 ms`** (HTTP live KAFKA server) | `>85x–2700x` speedup (`verify_incremental` cache) |
| Full cryptographic ledger verification (`637` chains) | `—` | `3,019.0 ms` | **`480.3 ms`** (`all_ok=True`) | `6.3x` faster full `GET /api/integrity/verify` |

### 2.2 End-to-End Pipeline Latency Script (`scripts/benchmark_pipeline_latency.py` -> `reports/pipeline_latency_report.json`)

Executed across `1,000` per-event Kafka probes + **`3` full-session `72,642`-event replay runs** (total script runtime `403.69s`):

| Layer / Full-Run Metric | Avg | P95 | Max | Samples / Runs |
|---|---:|---:|---:|---|
| Layer 1: Kafka Ingest (`per-event`) | `42.93 ms` | `64.74 ms` | `119.73 ms` | `n = 1,000` |
| Layer 2: Stream Normalizer (`in-proc`) | `0.0074 ms` | `0.0114 ms` | `0.1491 ms` | `n = 1,000` |
| Layer 3: Agents 01–04 Aggregated | `0.2158 ms` | `0.4965 ms` | `7.0753 ms` | `n = 643` |
| Layer 4: Consequence Fusion (`Agent 05`) | `0.0478 ms` | `0.0880 ms` | `0.3127 ms` | `n = 315` |
| Layer 5: StateStore Projection | `0.0153 ms` | `0.0203 ms` | `1.4542 ms` | `n = 619` |
| Layer 6: API Serving Serialization | `0.5999 ms` | `1.0662 ms` | `1.8001 ms` | `n = 120` |
| **Full 72,642-Event Session E2E (`3` runs)** | **`117.81 s`** (`±4.82 s`) | **`123.37 s`** | **`123.37 s`** | **`3 / 3 PASSED`** (`115.13s`, `123.37s`, `114.92s`) |

---

## 3. Live Chrome + `KAFKA` Server Verification (`http://127.0.0.1:5173/`)

Verified directly against live Chromium DevTools (backed by live `uvicorn` in `PULSE_TRANSPORT_MODE=KAFKA` + Flink `pulse-canonical-normalizer-v2` + 3-broker KRaft cluster, then cleanly stopped with ports `8000` and `5173` released):

- **HTTP & Console Health:** Across `34,352` uvicorn request log lines and `1,004` inspected DevTools network entries, recorded **`0` console errors**, **`0` console warnings**, **`0` HTTP `4xx`/`5xx` errors**, **`0` `net::ERR_ABORTED` aborts**, and **`0` uvicorn `[ERROR]`/`[WARNING]` logs**.
- **Trackside & Playback:** Eliminated nested buttons in `ParticipantShelf` & `TacticalDrawer`; `#circuit-select` renders full session names; retired Car `#31` displays inside labelled `DNF / PIT BAY`; pre-stream sectors honestly read `Awaiting weather telemetry (0%)`; `PAUSED` mode holds lap/elapsed completely static with zero Kafka backlog drift; mid-race `Seek` (`36321` -> `200 OK`) and cached lap seek (`L10` -> `~2s`, `L20` -> `200 OK`) complete cleanly with strictly sorted `P1..P20` leaderboard (`pos1=[55]`), vertical non-overlapping `MomentumChart` labels, `Hold track position (0 net delta)` (zero `P0–P0`), and stable `DriverTelemetryModal` (`120ms` freshness, `high_frequency_track_adapter` source, zero `AWAITING_STREAM` or abort flicker).
- **Integrity, SIA Logic Lab, Agents & Replay Audit Views:** `SIA Logic Lab` Limiting Child Resolution and State Algebra roles bind dynamically to the selected contract (`lap_time` -> `lap_record`, `lap_start`, `session_t0`, `feed_guard`); `Agents & Pipeline` renders dynamic `Kafka Streams` / live decision instance count / `SHA-256 Chain` without stale `81`/`Blake3`/`FOM Feeds & CAN` or `12.4ms` mount flashes; live server checks confirmed `GET /api/integrity/verify` (`verified=True`, `341` chains), bitemporal `as-of` query (`driver_position@f1-2023-silverstone-race|10|1 -> HEALTHY`), and `POST /api/integrity/lab-scenario` (`monaco_pit_bias -> SUSPECT`). *(Note: browser agent hit subscription quota `429` right after verifying `Replay & Audit` chain verification and `Seek Lap L20`/`L10` clicks, so the final `as-of`/`lab-scenario`/`verify` endpoint re-check was completed directly against the running live server logs and HTTP API before shutting down.)*
