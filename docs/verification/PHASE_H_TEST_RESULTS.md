# PULSE — Phase H Test Reproduction, Coverage & Assertion Audit

**Audit Date:** 2026-11-26  
**Branch / Commit:** `pulse-reconstruction` @ `9f1af40b38e39f9484b5852f6f05e08d88518d46`  
**Phase:** Pre-Edit Baseline Reproduction & Test-Quality Audit (Phase B)

---

## 1. Independent Baseline Test & Build Reproduction

All tests and builds below were executed untouched against the pre-Phase-H `pulse-reconstruction` working tree with the 3-broker Kafka KRaft cluster (`kafka-1`, `kafka-2`, `kafka-3`) and Apache Flink `1.18.1` (`calibre-flink-jobmanager`, `calibre-flink-taskmanager`, job `f0b58c7e2477ea5651e0f226c2034a5d`) online:

| Command / Scope | Result | Runtime | Warnings | Notes |
|---|---|---|---|---|
| `pytest sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | **`421 passed, 0 failed, 0 skipped`** | `166.50s` | `2` (`starlette.formparsers`, `fastf1.req.enable_cache`) | Includes live 72,642-event `test_01_normal_complete_historical_replay` |
| `pytest backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | **`10 passed, 0 failed, 0 skipped`** | `19.16s` | `0` | Live 3-broker KRaft test run |
| **Combined Baseline Total** | **`431 passed, 0 failed, 0 skipped`** | `185.66s` | `2` | Matches reported 421 + 10 = 431 count |
| `pytest --cov=sia_core_v3/sia_core --cov=calibre_core --cov=backend/pulse --cov-report=term-missing sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py -k "not test_01_normal_complete_historical_replay" -q --tb=short` | **`420 passed, 1 deselected`** | `59.73s` | `4` (adds 2 `coverage` SQLite `ResourceWarning`s) | Excludes `test_01` under `--cov` (verified separately in 166.50s run) and live `test_kafka_integration_t1_t10.py` |
| `cd frontend && npm run build` | **Exit `0`** | `1.42s` | `0` | `59 modules transformed` (`dist/index.html` `0.88 kB`, CSS `92.67 kB`, JS `467.02 kB`) |

> **Verdict on Reported Test Counts:** The prior claim of `421` general tests + `10` live Kafka tests = `431` passes + green frontend build is **reproduced identically**. However, inspection shows serious **assertion weakness, omitted code paths, and un-covered runtime wiring** underneath the green checkmarks.

---

## 2. Measured Code Coverage Summary (Pre-Edit Baseline)

Aggregate measured line coverage across `9,493` statements (`2,589` missed): **`73%`** *(with `test_01_normal_complete_historical_replay` deselected under `--cov` and `test_kafka_integration_t1_t10.py` run separately)*.

### 2.1 Highest-Risk Coverage Holes in Core Runtime Modules

| Module | Stmts | Miss | Cover | Critical Uncovered Functionality |
|---|---:|---:|---:|---|
| `backend\pulse\testing\orchestrator.py` | `612` | `540` | `12%` | Entire 12-stage E2E verifier excluded when `test_01` is deselected |
| `backend\pulse\stream\kafka_io.py` | `441` | `296` | `33%` | Covered chiefly by separate `T1-T10` suite, not unit tests; CLI verification & `TransactionalProcessor` error paths |
| `backend\pulse\main.py` | `263` | `124` | `53%` | Lifespan Flink job check, `kafka_consumer_loop`, SSE loop, startup WAL init |
| `backend\pulse\agents\event_control.py` | `158` | `72` | `54%` | Multiple race-control flags/handlers untested cleanly |
| `backend\pulse\integrity\agent.py` | `457` | `191` | `58%` | WAL restore paths, `switch_session`, quarantining & cross-partition `session_t0` handling |
| `backend\pulse\stream\flink\client.py` | `132` | `57` | `57%` | Job deployment / cancellation / metric polling paths |
| `backend\pulse\stream\flink\manager.py` | `60` | `24` | `60%` | `ensure_normalizer_job_running()` auto-deployment path |
| `backend\pulse\stream\kafka_client.py` | `193` | `62` | `68%` | Consumer offset management, producer failure callbacks, reconnect logic |
| `backend\pulse\api\router.py` | `352` | `89` | `75%` | Error/edge HTTP branches, snapshot/seek race branches |
| `backend\pulse\intelligence\groq_client.py` | `42` | `42` | `0%` | Legacy unused LLM synthesis client (`0%` exercised) |
| `sia_core_v3\sia_core\witnesses.py` | `22` | `22` | `0%` | CLI witness runner (`__main__`-only module) |

### 2.2 Well-Covered Subsystems

- `sia_core_v3\sia_core\timeclass.py`: `99%`
- `sia_core_v3\sia_core\model.py`: `96%`
- `sia_core_v3\sia_core\algebra.py`: `94%`
- `sia_core_v3\sia_core\evaluator.py`: `91%`
- `sia_core_v3\sia_core\ledger.py`: `90%`
- `sia_core_v3\sia_core\contract.py`: `87%`
- `sia_core_v3\sia_core\engine.py`: `84%`
- `sia_core_v3\sia_core\wal.py`: `79%`
- `backend\pulse\contracts.py`: `100%`
- `backend\pulse\analytics\pace_and_tyre.py`: `86%`
- `backend\pulse\replay\controller.py`: `87%`
- `backend\pulse\state\store.py`: `90%`
- `backend\pulse\agents\fusion.py`: `92%`

---

## 3. Test-Quality Audit — Tests Passing Without Proving Their Claimed Invariant

Direct line-by-line inspection of the existing suites identified the following tests whose assertions **do not validate the specification stated in their docstrings**:

| Test File & Function | Claimed Invariant | Actual Pre-Edit Implementation & Flaw | Risk / Impact |
|---|---|---|---|
| `backend/tests/test_kafka_integration_t1_t10.py::test_t3_two_broker_failure_not_enough_replicas_safety` | Stops 2 of 3 brokers and proves `NotEnoughReplicas` rejects un-replicated commits | Instantiates `Producer` `p` without calling `p.produce()`, stops zero Docker containers, and only calls `verify_topics()` | **High** — runtime 2-of-3 quorum/ISR failure rejection was completely untested |
| `backend/tests/test_kafka_integration_t1_t10.py::test_t8_clock_watermark_and_replay_isolation` | Verifies live vs replay run isolation and durable evaluation clock topics | Publishes 1 JSON string `{"tick_utc": ..., "epoch": 100}` to `calibre.guard.clock` and asserts `producer.stats.delivered >= 1`; zero consumers, zero isolation checks | **High** — no actual replay vs live topic/run isolation proof |
| `backend/tests/test_kafka_integration_t1_t10.py::test_t9_static_membership_no_rebalance_on_quick_restart` | Consumer with `group.instance.id` restarts quickly without rebalance | Subscribes once, polls 0.5s, and closes (`c.close()`); **never restarts a second consumer** with the same `group.instance.id` | **High** — static membership takeover without rebalance was never exercised |
| `backend/tests/test_kafka_integration_t1_t10.py::test_t10_partition_count_invariance` | Same per-driver decisions whether 1 or 11 partitions exist | Never contacts Kafka; computes local `driver_partition()` values `p1`/`p11`, ignores them, and hashes the same static list twice | **Medium** — tautology (`h1 == h11`) without multi-partition Kafka reordering or digest equivalence |
| `backend/tests/test_phase4_reliability.py::test_06_kafka_consumer_restart_recovery` | Consumer group restart resumes safely | Creates second consumer `c2` with a **different `group_id_2`**, reading from `earliest` instead of verifying same-group committed offset continuation | **High** — offset resume / at-least-once handoff untested |
| `backend/tests/test_phase4_reliability.py::test_07_flink_checkpoint_recovery` | Active Flink checkpoints and healthy running job | Asserts `metrics.checkpoints_completed >= 0`, which passes trivially when zero checkpoints have completed | **Medium** — checkpointing can be silently broken or disabled |
| `backend/tests/test_phase4_reliability.py::test_08_concurrent_run_isolation` | Concurrent race sessions maintain strict isolation across streaming pipeline | Invokes `agent.on_event(...)` synchronously in-process against RAM `StateStore`, bypassing Kafka and Flink | **Medium** — streaming multi-session isolation not verified over broker/Flink |
| `backend/tests/test_browser_cockpit.py::test_captured_cockpit_screenshots_exist_and_non_empty` | Cockpit screenshots exist cleanly | Only checks `stat().st_size > 50_000` on static PNG artifacts captured historically | **Medium** — cannot catch broken SSE wiring or regression in `App.tsx` / `PipelineLabView.tsx` |
| `backend/tests/test_phase4_reliability.py::test_01_normal_complete_historical_replay` (via `orchestrator.py`) | 10-stage Kafka/Flink E2E verification with 0 drops | Stage 3 returned an in-memory `expected_map` without consuming `pulse.norm.*`; routed `POSITION_UPDATE` to unsubscribed `pulse.raw.telemetry.car.v1` | **Critical** — masked both missing Flink SQL tables and duplicate-`event_id` dedup suppression across repeated runs |

---

## 4. Phase H Action Plan for Suite Hardening

1. Repair the underlying runtime/SQL/SIA defects (`normalizer_job.sql`, `orchestrator.py`, `main.py`, `kafka_client.py`, `integrity/agent.py`, `App.tsx`, `PipelineLabView.tsx`) first so tests exercise genuine behavior.
2. Strengthen `T3`, `T8`, `T9`, `T10` in `backend/tests/test_kafka_integration_t1_t10.py` and `test_06`/`test_07` in `backend/tests/test_phase4_reliability.py` cleanly so every docstring claim is backed by real broker/Flink/consumer checks.
3. Add targeted Phase H regression tests verifying:
   - Kafka manual offset commit <-> SIA WAL write coupling & crash/restart recovery (`main.py` + `IntegrityAgent`).
   - Out-of-order cross-partition `session_t0` supersession invariance (`IntegrityAgent`).
   - SIA WAL crash/kill, partial trailing line corruption handling, and duplicate verdict idempotency.
   - Flink normalization across all 9 `RAW_TOPICS` (including `pulse.raw.telemetry.car.v1` and `pulse.raw.session_status.v1`).
4. Re-run all 3 test tiers + live Kafka `T1–T10` + frontend build after the final edit and record updated before/after metrics cleanly.

---

## 5. Final Post-All-Edits Verification Sweep (`2026-11-26 19:21–19:25`)

After completing all Phase H code fixes across Flink SQL v3, Kafka manual offset coupling, `SIAWALStore.sync_engine()` + lifecycle teardown, `session_t0` supersession invariance, hardened `T3`/`T8`/`T9`/`T10` & `test_06`/`test_07` assertions, `5` new `test_phase_h_verification.py` tests, and frontend `App.tsx` / `PipelineLabView.tsx` / `AgentsPipelineView.tsx` repairs, the complete sequential verification pipeline exited **`0`** (`0` failures, `0` skips):

| Post-Edit Check Command | Exact Scope | Observed Result | Runtime | Warnings |
|---|---|---|---:|---|
| `python -m pulse.stream.kafka_io --verify` | Live 3-broker KRaft topic catalogue (`70` topics) | **`[OK] All 70 topics verified against live broker with zero drift.`** | `< 2s` | `1` (`runpy` module preload) |
| `pytest sia_core_v3/tests calibre_core/tests backend/tests --ignore=backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | All non-T2 suites (`sia_core_v3`, `calibre_core`, `backend`, including live Flink v3 `72,642`-event `test_01` & `test_phase_h_verification.py`) | **`426 passed, 0 failed, 0 skipped`** | `190.24s` | `2` (`starlette` `multipart`, `fastf1` `.enable_cache`) |
| `pytest backend/tests/test_kafka_integration_t1_t10.py -v --tb=short` | Live 3-broker KRaft `T1`–`T10` integration & Docker chaos suite (hardened `T3`/`T8`/`T9`/`T10`) | **`10 passed, 0 failed, 0 skipped`** | `44.17s` | `0` |
| **Combined Post-Edit Total** | **All automated suites (`non-T2` + live `T1–T10`)** | **`436 passed, 0 failed, 0 skipped`** | `234.41s` | `2` |
| `cd frontend && npm run build` | TypeScript compilation (`tsc -b`) + Vite bundle | **`✓ 60 modules transformed`** (`index-xk1TytgV.css` `92.67 kB`, `index-BjXZdcy5.js` `479.10 kB`) | `1.41s` | `0` |
