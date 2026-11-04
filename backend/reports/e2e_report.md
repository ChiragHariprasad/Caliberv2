# PULSE End-to-End Pipeline Verification Report

- **Status**: **PASSED**
- **Session ID**: `verification-demo`
- **Run ID**: `run-9b5fdd92`
- **Execution Mode**: `REPLAY`
- **Timestamp**: `2026-11-04T18:21:35.391344+00:00`
- **Total Latency**: `198.67 ms`
- **Transport Verified**: `KAFKA (Real broker @ localhost:9092, zero silent fallbacks)`
- **Flink Engine Verified**: `RUNNING (pulse-race-control-normalizer-v1)`

## Stage Reconciliation Summary

| Stage Name | Status | In | Out | Drop | Latency (ms) |
|---|---|---|---|---|---|
| `1.PREFLIGHT` | **PASSED** | 0 | 1 | 0 | 94.92 |
| `2.RAW_INGEST_KAFKA` | **PASSED** | 1 | 1 | 0 | 4.99 |
| `3.FLINK_STREAM_PROCESSING` | **PASSED** | 1 | 1 | 0 | 61.47 |
| `4.AGENT_1_EVENT_CONTROL` | **PASSED** | 1 | 3 | 0 | 21.04 |
| `5.STATE_STORE_AND_API` | **PASSED** | 3 | 3 | 0 | 14.76 |

## Specialist Agent Findings Emitted

- **Finding ID**: `finding-lc-evt-vsc-2b69c7ea`
  - **Type**: `RACE_EVENT_LIFECYCLE` | **Interpretation**: `OBSERVED`
  - **Trigger Event ID**: `evt-vsc-2b69c7ea`
  - **Model Version**: `1.0.0`
  - **Reason Codes**: `['RCM_VSC_DEPLOYED']`
  - **Source Provenance**: `{"provider": "PULSE_VERIFICATION_HARNESS", "adapter": "e2e_runner_v1", "source_record_id": "src-evt-vsc-2b69c7ea", "capture_id": "capture-verification-demo", "data_mode": "REPLAY"}`

- **Finding ID**: `finding-exp-evt-vsc-2b69c7ea-16`
  - **Type**: `DRIVER_EVENT_EXPOSURE` | **Interpretation**: `DERIVED`
  - **Trigger Event ID**: `evt-vsc-2b69c7ea`
  - **Model Version**: `1.0.0`
  - **Reason Codes**: `['VSC_EXPOSURE_CALCULATED']`
  - **Source Provenance**: `{"provider": "PULSE_VERIFICATION_HARNESS", "adapter": "e2e_runner_v1", "source_record_id": "src-evt-vsc-2b69c7ea", "capture_id": "capture-verification-demo", "data_mode": "REPLAY"}`

- **Finding ID**: `finding-exp-evt-vsc-2b69c7ea-44`
  - **Type**: `DRIVER_EVENT_EXPOSURE` | **Interpretation**: `DERIVED`
  - **Trigger Event ID**: `evt-vsc-2b69c7ea`
  - **Model Version**: `1.0.0`
  - **Reason Codes**: `['VSC_EXPOSURE_CALCULATED']`
  - **Source Provenance**: `{"provider": "PULSE_VERIFICATION_HARNESS", "adapter": "e2e_runner_v1", "source_record_id": "src-evt-vsc-2b69c7ea", "capture_id": "capture-verification-demo", "data_mode": "REPLAY"}`

## Verification Artifacts

- `pipeline_trace.json`: Full lineage event trace from raw ingress to state persistence.
- `stage_reconciliation.csv`: Granular stage-by-stage I/O counts and latency.
- `e2e_report.json`: Machine-readable test execution metadata and assertion results.

> Generated autonomously by `pulse.testing.run_e2e`.