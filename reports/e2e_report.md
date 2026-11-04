# PULSE Five-Agent End-to-End Pipeline Verification Report

- **Status**: **PASSED**
- **Session ID**: `e2e-five-agents-final`
- **Run ID**: `run-5eca8f5c`
- **Execution Mode**: `REPLAY`
- **Timestamp**: `2026-11-04T18:46:43.084948+00:00`
- **Total Latency**: `3566.28 ms`
- **Transport Verified**: `KAFKA (Real broker @ localhost:9092, zero silent fallbacks)`
- **Flink Engine Verified**: `RUNNING (pulse-canonical-normalizer-v2, 5 domains normalized)`

## Stage Reconciliation Summary

| Stage Name | Status | In | Out | Drop | Latency (ms) |
|---|---|---|---|---|---|
| `1.PREFLIGHT` | **PASSED** | 0 | 1 | 0 | 1166.17 |
| `2.RAW_SCENARIO_INGEST_KAFKA` | **PASSED** | 9 | 9 | 0 | 21.17 |
| `3.FLINK_STREAM_NORMALIZATION` | **PASSED** | 9 | 9 | 0 | 486.97 |
| `4.AGENT_1_EVENT_CONTROL` | **PASSED** | 4 | 5 | 0 | 47.28 |
| `5.AGENT_2_TRACK_STATE` | **PASSED** | 2 | 2 | 0 | 27.91 |
| `6.AGENT_3_VEHICLE_RESPONSE` | **PASSED** | 1 | 1 | 0 | 21.26 |
| `7.AGENT_4_TYRE_STRATEGY` | **PASSED** | 2 | 1 | 0 | 23.93 |
| `8.AGENT_5_CONSEQUENCE_FUSION` | **PASSED** | 9 | 4 | 0 | 25.03 |
| `9.FAULT_INJECTION_AND_DATA_QUALITY` | **PASSED** | 2 | 2 | 0 | 1.78 |
| `10.STATE_STORE_LINEAGE_AND_API` | **PASSED** | 14 | 14 | 0 | 1742.40 |

## Specialist Agent Findings Lineage

- **[AGENT_1]** FINDINGS_VERIFIED: `5` outputs
- **[AGENT_2]** FINDINGS_VERIFIED: `2` outputs
- **[AGENT_3]** FINDINGS_VERIFIED: `1` outputs
- **[AGENT_4]** FINDINGS_VERIFIED: `1` outputs
- **[AGENT_5]** REVISION_CHAIN_CONFIRMED: `` outputs

## Verification Artifacts

- `pipeline_trace.json`: Full lineage event trace across all 5 agents and Kafka topics.
- `stage_reconciliation.csv`: Granular stage-by-stage I/O counts and latency.
- `e2e_report.json`: Machine-readable test execution metadata and assertion results.

> Generated autonomously by `pulse.testing.run_e2e`.