# PULSE Five-Agent End-to-End Pipeline Verification Report

- **Status**: **FAILED**
- **Session ID**: `e2e-session-e96249`
- **Run ID**: `run-bb6d949f`
- **Execution Mode**: `REPLAY`
- **Timestamp**: `2026-11-26T10:16:17.665326+00:00`
- **Total Latency**: `160474.35 ms`
- **Transport Verified**: `KAFKA (localhost:19092,localhost:19093,localhost:19094)`
- **Flink Engine Verified**: `RESTARTING (pulse-canonical-normalizer-v3, 5 normalized domains from 9 raw topics)`

## Stage Reconciliation Summary

| Stage Name | Status | In | Out | Drop | Latency (ms) |
|---|---|---|---|---|---|
| `0.VALIDATE_CAPTURE_MANIFEST` | **PASSED** | 0 | 0 | 0 | 0.57 |
| `1.PREFLIGHT` | **PASSED** | 0 | 1 | 0 | 13325.16 |
| `2.HISTORICAL_CAPTURE_INGEST_KAFKA` | **PASSED** | 72642 | 72642 | 0 | 126563.96 |
| `3.FLINK_STREAM_NORMALIZATION` | **FAILED** | 72642 | 72628 | 14 | 20449.64 |

## Specialist Agent Findings Lineage
