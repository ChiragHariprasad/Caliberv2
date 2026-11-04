# PULSE Five-Agent End-to-End Pipeline Verification Report

- **Status**: **FAILED**
- **Session ID**: `e2e-session-c5608a`
- **Run ID**: `run-c1fa0445`
- **Execution Mode**: `REPLAY`
- **Timestamp**: `2026-11-04T20:01:25.296475+00:00`
- **Total Latency**: `6817.59 ms`
- **Transport Verified**: `KAFKA (Real broker @ localhost:9092, zero silent fallbacks)`
- **Flink Engine Verified**: `RUNNING (pulse-canonical-normalizer-v2, 5 domains normalized)`

## Stage Reconciliation Summary

| Stage Name | Status | In | Out | Drop | Latency (ms) |
|---|---|---|---|---|---|
| `0.VALIDATE_CAPTURE_MANIFEST` | **PASSED** | 8 | 8 | 0 | 2.91 |
| `1.PREFLIGHT` | **PASSED** | 0 | 1 | 0 | 1865.57 |
| `2.HISTORICAL_CAPTURE_INGEST_KAFKA` | **PASSED** | 943 | 943 | 0 | 261.83 |
| `3.FLINK_STREAM_NORMALIZATION` | **PASSED** | 943 | 943 | 0 | 692.24 |
| `4.AGENT_1_EVENT_CONTROL` | **PASSED** | 11 | 20 | 0 | 79.88 |
| `5.AGENT_2_TRACK_STATE` | **PASSED** | 4 | 4 | 0 | 22.22 |
| `6.AGENT_3_VEHICLE_RESPONSE` | **PASSED** | 903 | 903 | 0 | 1736.88 |
| `7.AGENT_4_TYRE_STRATEGY` | **PASSED** | 26 | 2 | 0 | 3.89 |
| `8.AGENT_5_CONSEQUENCE_FUSION` | **PASSED** | 929 | 912 | 0 | 1883.87 |
| `9.FAULT_INJECTION_AND_DATA_QUALITY` | **PASSED** | 2 | 2 | 0 | 2.65 |
| `10.RACE_INTELLIGENCE_EVALUATION` | **PASSED** | 10 | 10 | 0 | 0.32 |
| `11.STATE_STORE_LINEAGE_AND_API` | **PASSED** | 1841 | 1841 | 0 | 218.08 |

## Specialist Agent Findings Lineage

- **[AGENT_1]** HISTORICAL_FINDINGS_CONFIRMED: `20` outputs
- **[AGENT_2]** FINDINGS_VERIFIED: `4` outputs
- **[AGENT_3]** LAP_INTELLIGENCE_PROCESSED: `` outputs
- **[AGENT_4]** STRATEGY_FINDINGS_VERIFIED: `2` outputs
- **[AGENT_5]** REVISION_CHAIN_CONFIRMED: `` outputs