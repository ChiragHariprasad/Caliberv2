# PULSE Five-Agent End-to-End Pipeline Verification Report

- **Status**: **FAILED**
- **Session ID**: `e2e-session-6b9b5d`
- **Run ID**: `run-cdd2cc99`
- **Execution Mode**: `REPLAY`
- **Timestamp**: `2026-11-05T03:01:18.958949+00:00`
- **Total Latency**: `32847.23 ms`
- **Transport Verified**: `KAFKA (Real broker @ localhost:9092, zero silent fallbacks)`
- **Flink Engine Verified**: `RUNNING (pulse-canonical-normalizer-v2, 5 domains normalized)`

## Stage Reconciliation Summary

| Stage Name | Status | In | Out | Drop | Latency (ms) |
|---|---|---|---|---|---|
| `0.VALIDATE_CAPTURE_MANIFEST` | **PASSED** | 0 | 0 | 0 | 14.62 |
| `1.PREFLIGHT` | **PASSED** | 0 | 1 | 0 | 4752.73 |
| `2.HISTORICAL_CAPTURE_INGEST_KAFKA` | **PASSED** | 72637 | 72637 | 0 | 26111.95 |
| `3.FLINK_STREAM_NORMALIZATION` | **PASSED** | 72637 | 72637 | 0 | 1915.61 |

## Specialist Agent Findings Lineage
