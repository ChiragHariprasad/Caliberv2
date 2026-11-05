"""Comprehensive latency benchmark suite for the PULSE Formula 1 streaming pipeline.

Measures:
1. Per-event processing latency across each architectural layer:
   - Layer 1: Ingestion & Kafka Transport (event serialization & broker publish)
   - Layer 2: Flink Stream Normalization & Canonical Watermarking
   - Layer 3: Specialist Analytics Agents:
       * Agent 1: Race Event & Control Intelligence
       * Agent 2: Track-State Intelligence
       * Agent 3: Vehicle-Response Intelligence
       * Agent 4: Tyre & Strategy Intelligence
       * Aggregated Specialist Agent Layer
   - Layer 4: Consequence Fusion Engine (Agent 5)
   - Layer 5: State Store Persistence & Projection
   - Layer 6: API Serving & Serialization
   - Full Pipeline Per-Event End-to-End Latency (Ingest -> Flink -> Agent -> Fusion -> Store)

2. Stage-by-stage session replay latency across repeated full pipeline executions:
   - 3 complete runs of the historical 52-lap session (72,642 events)
   - Min, Avg, Max execution time for each stage and the full pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

import pulse.state.store as store_mod
import pulse.stream.bus as bus_mod
from pulse.agents.event_control import EventControlAgent
from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.agents.track_state import TrackStateAgent
from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.config import get_settings
from pulse.contracts import EventEnvelope, Finding, Interpretation, Subject, utc_now
from pulse.main import create_app
from pulse.state.store import StateStore, get_state_store
from pulse.stream.bus import PulseEventBus
from pulse.stream.kafka_client import KafkaBroker
from pulse.testing.orchestrator import VerticalSliceVerifier
from pulse.topics import AGENT_TOPICS, INTELLIGENCE_TOPICS, NORMALISED_TOPICS, RAW_TOPICS

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("pulse.benchmark")


def compute_stats(samples: list[float]) -> dict[str, float]:
    """Computes min, max, avg, median, p95, p99, and stdev for a list of latency samples (in ms)."""
    if not samples:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0, "stdev": 0.0, "count": 0}
    s = sorted(samples)
    n = len(s)
    p95_idx = min(int(math.ceil(0.95 * n)) - 1, n - 1)
    p99_idx = min(int(math.ceil(0.99 * n)) - 1, n - 1)
    return {
        "min": round(s[0], 4),
        "max": round(s[-1], 4),
        "avg": round(statistics.mean(s), 4),
        "median": round(statistics.median(s), 4),
        "p95": round(s[p95_idx], 4),
        "p99": round(s[p99_idx], 4),
        "stdev": round(statistics.stdev(s), 4) if n > 1 else 0.0,
        "count": n,
    }


async def benchmark_per_event_layers(capture_dir: Path, sample_limit: int = 1000) -> dict[str, Any]:
    """Measures granular per-event processing latency across each architectural layer."""
    print("\n" + "=" * 80)
    print("RUNNING BENCHMARK 1: PER-EVENT PROCESSING LATENCY PER ARCHITECTURAL LAYER")
    print("=" * 80)

    # 1. Load sample envelopes from historical capture
    envelopes_file = capture_dir / "envelopes.jsonl"
    all_envelopes: list[EventEnvelope] = []
    with open(envelopes_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_envelopes.append(EventEnvelope.model_validate(json.loads(line)))

    print(f"Loaded {len(all_envelopes)} total envelopes from capture.")

    # Categorize envelopes
    rc_events = [e for e in all_envelopes if e.event_type in {
        "SESSION_STARTED", "VSC_DEPLOYED", "VSC_ENDING", "VSC_ENDED",
        "SAFETY_CAR_DEPLOYED", "SAFETY_CAR_IN_THIS_LAP", "SAFETY_CAR_ENDING",
        "GREEN_FLAG_RESUMED", "TRACK_STATUS_GREEN", "DRIVER_RETIRED", "STEWARD_DECISION", "SESSION_CHEQUERED",
        "RACE_CONTROL_MESSAGE", "RACE_CONTROL_NOTICE",
    }]
    lap_events = [e for e in all_envelopes if e.event_type == "LAP_COMPLETED"]
    weather_events = [e for e in all_envelopes if e.event_type in {"WEATHER_OBSERVATION", "TRACK_STATUS_UPDATE"}]
    strat_events = [e for e in all_envelopes if e.event_type in {"VSC_DEPLOYED", "SAFETY_CAR_DEPLOYED", "PIT_STOP", "PIT_STOP_RECORDED", "TYRE_FITTED"}]
    pos_events = [e for e in all_envelopes if e.event_type == "POSITION_UPDATE"]

    # ----------------------------------------------------
    # LAYER 1: Ingestion & Kafka Transport Latency
    # ----------------------------------------------------
    print("[1/7] Profiling Layer 1: Ingestion & Kafka Transport...")
    broker = KafkaBroker()
    await broker.start()
    kafka_samples: list[float] = []

    # Sample across various topics
    publish_sample = (rc_events + weather_events + strat_events + lap_events[:200] + pos_events[: sample_limit])[:sample_limit]
    for env in publish_sample:
        topic = RAW_TOPICS["telemetry_car"] if env.event_type == "POSITION_UPDATE" else RAW_TOPICS["race_control"]
        key = str(env.subject.driver_number or "session")
        t0 = time.perf_counter_ns()
        await broker.publish(topic, key, env)
        t1 = time.perf_counter_ns()
        kafka_samples.append((t1 - t0) / 1_000_000.0)

    await broker.stop()

    # ----------------------------------------------------
    # LAYER 2: Stream Normalization & Canonical Watermarking
    # ----------------------------------------------------
    print("[2/7] Profiling Layer 2: Stream Normalization & Canonical Validation...")
    norm_samples: list[float] = []
    for env in publish_sample:
        raw_dict = env.model_dump(mode="json")
        t0 = time.perf_counter_ns()
        # Canonical schema validation and timestamp normalization
        parsed = EventEnvelope.model_validate(raw_dict)
        _ = parsed.time.session_elapsed_ms
        _ = parsed.event_type
        t1 = time.perf_counter_ns()
        norm_samples.append((t1 - t0) / 1_000_000.0)

    # ----------------------------------------------------
    # LAYER 3: Specialist Analytics Agents
    # ----------------------------------------------------
    print("[3/7] Profiling Layer 3: Specialist Intelligence Agents...")
    bus = PulseEventBus()
    agent_ec = EventControlAgent(bus=bus)
    agent_ts = TrackStateAgent(bus=bus)
    agent_vr = VehicleResponseAgent(bus=bus)
    agent_ty = TyreStrategyAgent(bus=bus)

    # Agent 1
    ec_samples: list[float] = []
    for env in rc_events:
        t0 = time.perf_counter_ns()
        await agent_ec.on_event(NORMALISED_TOPICS["race_events"], "session", env)
        t1 = time.perf_counter_ns()
        ec_samples.append((t1 - t0) / 1_000_000.0)

    # Agent 2
    ts_samples: list[float] = []
    for env in weather_events:
        t0 = time.perf_counter_ns()
        await agent_ts.on_event(NORMALISED_TOPICS["track_segments"], "circuit", env)
        t1 = time.perf_counter_ns()
        ts_samples.append((t1 - t0) / 1_000_000.0)

    # Agent 3
    vr_samples: list[float] = []
    for env in lap_events[:sample_limit]:
        t0 = time.perf_counter_ns()
        await agent_vr.on_event(NORMALISED_TOPICS["driver_laps"], f"session:{env.subject.driver_number}", env)
        t1 = time.perf_counter_ns()
        vr_samples.append((t1 - t0) / 1_000_000.0)

    # Agent 4
    ty_samples: list[float] = []
    for env in strat_events:
        t0 = time.perf_counter_ns()
        await agent_ty.on_event(NORMALISED_TOPICS["race_events"], f"session:{env.subject.driver_number or 44}", env)
        t1 = time.perf_counter_ns()
        ty_samples.append((t1 - t0) / 1_000_000.0)

    specialist_all_samples = ec_samples + ts_samples + vr_samples + ty_samples

    # ----------------------------------------------------
    # LAYER 4: Consequence Fusion Engine (Agent 5)
    # ----------------------------------------------------
    print("[4/7] Profiling Layer 4: Consequence Fusion Engine (Agent 5)...")
    agent_fu = ConsequenceFusionEngine(bus=bus)
    store = StateStore()

    # Collect findings generated by agents 1-4
    candidate_findings: list[Finding] = []
    # Register findings from agents
    # Use store findings from verifier or generate
    for f_id in agent_ec.output_finding_ids:
        pass
    # We can use findings generated in agent_ec and synthetic/real findings
    findings_to_fuse: list[Finding] = []
    for i, env in enumerate(strat_events + rc_events):
        f = Finding(
            finding_id=f"bench-f-{i}-{uuid4().hex[:6]}",
            agent_id="agent-04-tyre-strategy" if i % 2 == 0 else "agent-01-event-control",
            finding_type="PIT_WINDOW_OPPORTUNITY" if i % 2 == 0 else "RACE_EVENT_LIFECYCLE",
            session_id="bench-session",
            run_id="bench-run",
            subject=env.subject,
            trigger_event_id=env.event_id,
            as_of_event_time=utc_now(),
            interpretation=Interpretation.DERIVED,
            result={"net_time_saving_sec": 10.5, "driver_number": env.subject.driver_number or 16},
            evidence_refs=[env.event_id],
            model_version="1.2.0",
        )
        findings_to_fuse.append(f)

    # Add vehicle response findings for 20 drivers
    for i in range(1, 21):
        for lap in range(1, 15):
            f = Finding(
                finding_id=f"bench-vr-d{i}-l{lap}",
                agent_id="agent-03-vehicle-response",
                finding_type="PACE_DEVIATION",
                session_id="bench-session",
                run_id="bench-run",
                subject=Subject(driver_number=i, segment_id=None),
                trigger_event_id=f"evt-lap-{i}-{lap}",
                as_of_event_time=utc_now(),
                interpretation=Interpretation.DERIVED,
                result={"driver_number": i, "lap_number": lap, "lap_time_seconds": 91.2 + (lap * 0.05), "pace_delta_sec": 0.25},
                evidence_refs=[f"evt-lap-{i}-{lap}"],
                model_version="1.0.0",
            )
            findings_to_fuse.append(f)

    fusion_samples: list[float] = []
    for f in findings_to_fuse:
        t0 = time.perf_counter_ns()
        await agent_fu.on_finding(AGENT_TOPICS["event_context"], f"session:{f.subject.driver_number}", f)
        t1 = time.perf_counter_ns()
        fusion_samples.append((t1 - t0) / 1_000_000.0)

    # ----------------------------------------------------
    # LAYER 5: State Store Persistence & Projection
    # ----------------------------------------------------
    print("[5/7] Profiling Layer 5: State Store Persistence & Projection...")
    statestore_samples: list[float] = []
    for f in findings_to_fuse:
        t0 = time.perf_counter_ns()
        store.record_finding(f)
        t1 = time.perf_counter_ns()
        statestore_samples.append((t1 - t0) / 1_000_000.0)

    for a in agent_fu.assessment_history:
        t0 = time.perf_counter_ns()
        store.record_assessment(a)
        t1 = time.perf_counter_ns()
        statestore_samples.append((t1 - t0) / 1_000_000.0)

    # ----------------------------------------------------
    # LAYER 6: API Serving & Query Serialization
    # ----------------------------------------------------
    print("[6/7] Profiling Layer 6: API Serving & Serialization...")
    app = create_app()
    api_samples: list[float] = []
    with TestClient(app) as client:
        endpoints = ["/api/health", "/api/replay/status", "/api/findings", "/api/assessments", "/api/agents/metrics", "/api/snapshot"]
        for ep in endpoints * 20:
            t0 = time.perf_counter_ns()
            res = client.get(ep)
            t1 = time.perf_counter_ns()
            assert res.status_code == 200, f"Endpoint {ep} failed with {res.status_code}"
            api_samples.append((t1 - t0) / 1_000_000.0)

    # ----------------------------------------------------
    # FULL PIPELINE PER-EVENT END-TO-END
    # ----------------------------------------------------
    print("[7/7] Profiling Full Pipeline Per-Event End-to-End Latency...")
    e2e_per_event_samples: list[float] = []
    e2e_broker = KafkaBroker()
    await e2e_broker.start()
    e2e_bus = PulseEventBus(broker=e2e_broker)
    e2e_agent_ec = EventControlAgent(bus=e2e_bus)
    e2e_agent_fu = ConsequenceFusionEngine(bus=e2e_bus)
    e2e_store = StateStore()

    async def handle_agent_finding(topic: str, key: str, f: Finding):
        await e2e_agent_fu.on_finding(topic, key, f)
        e2e_store.record_finding(f)

    async def handle_assessment(topic: str, key: str, a: Any):
        e2e_store.record_assessment(a)

    e2e_bus.subscribe(AGENT_TOPICS["event_context"], handle_agent_finding)
    e2e_bus.subscribe(INTELLIGENCE_TOPICS["driver_impact"], handle_assessment)

    # Prime grid in store
    entry_list_file = capture_dir / "entry_list.json"
    if entry_list_file.exists():
        e2e_store.load_session_entry_list(json.loads(entry_list_file.read_text(encoding="utf-8")))

    for env in rc_events:
        t_start = time.perf_counter_ns()
        # 1. Layer 1: Ingest to Kafka
        await e2e_broker.publish(RAW_TOPICS["race_control"], str(env.subject.driver_number or "session"), env)
        # 2. Layer 2: Normalization parse
        norm_env = EventEnvelope.model_validate(env.model_dump(mode="json"))
        # 3. Layer 3, 4, 5: Bus-driven propagation through Agent 1 -> Fusion -> StateStore
        await e2e_agent_ec.on_event(NORMALISED_TOPICS["race_events"], "session", norm_env)
        await e2e_bus.drain()
        t_end = time.perf_counter_ns()
        e2e_per_event_samples.append((t_end - t_start) / 1_000_000.0)

    await e2e_broker.stop()

    return {
        "layer_1_kafka_ingest": compute_stats(kafka_samples),
        "layer_2_flink_normalization": compute_stats(norm_samples),
        "layer_3_agent_1_event_control": compute_stats(ec_samples),
        "layer_3_agent_2_track_state": compute_stats(ts_samples),
        "layer_3_agent_3_vehicle_response": compute_stats(vr_samples),
        "layer_3_agent_4_tyre_strategy": compute_stats(ty_samples),
        "layer_3_specialist_agents_aggregated": compute_stats(specialist_all_samples),
        "layer_4_consequence_fusion": compute_stats(fusion_samples),
        "layer_5_statestore_persistence": compute_stats(statestore_samples),
        "layer_6_api_serving": compute_stats(api_samples),
        "full_pipeline_per_event_e2e": compute_stats(e2e_per_event_samples),
    }


async def benchmark_full_pipeline_multi_runs(num_runs: int = 3) -> dict[str, Any]:
    """Executes multiple complete pipeline runs through the full historical replay suite and computes statistics."""
    print("\n" + "=" * 80)
    print(f"RUNNING BENCHMARK 2: FULL PIPELINE REPLAY BENCHMARK ({num_runs} COMPLETE RUNS)")
    print("=" * 80)

    stage_latencies: dict[str, list[float]] = {}
    total_pipeline_latencies: list[float] = []

    for run_idx in range(1, num_runs + 1):
        print(f"\n--- Starting Full Pipeline Run {run_idx}/{num_runs} (72,642 events) ---")
        t0 = time.perf_counter()

        # Reset singletons
        store_mod._store = None
        bus_mod._bus = None

        verifier = VerticalSliceVerifier(
            capture_id="pulse-capture-f1-2023-silverstone-race-v1",
            mode="REPLAY",
            output_dir=f"reports/benchmark_run_{run_idx}",
        )

        result = await verifier.run()
        run_duration_ms = (time.perf_counter() - t0) * 1000.0
        total_pipeline_latencies.append(run_duration_ms)

        print(f"Run {run_idx} completed in {run_duration_ms / 1000.0:.2f}s with status: {result.status}")

        for stage in result.stages:
            if stage.stage_name not in stage_latencies:
                stage_latencies[stage.stage_name] = []
            stage_latencies[stage.stage_name].append(stage.latency_ms)

    # Compute statistics per stage
    stage_summary = {}
    for stage_name, samples in stage_latencies.items():
        stage_summary[stage_name] = compute_stats(samples)

    total_summary = compute_stats(total_pipeline_latencies)

    return {
        "num_runs": num_runs,
        "stages": stage_summary,
        "full_pipeline_total": total_summary,
    }


async def main():
    capture_dir = Path("captures/f1-2023-silverstone-race")
    if not capture_dir.exists():
        raise FileNotFoundError("Missing capture directory")

    t_start = time.time()

    # 1. Per-event layer benchmark
    per_event_metrics = await benchmark_per_event_layers(capture_dir, sample_limit=1000)

    # 2. Multi-run complete pipeline benchmark
    multi_run_metrics = await benchmark_full_pipeline_multi_runs(num_runs=3)

    total_bench_time = time.time() - t_start

    # Combine into comprehensive report
    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "total_benchmark_duration_seconds": round(total_bench_time, 2),
        "per_event_layer_benchmarks_ms": per_event_metrics,
        "multi_run_full_pipeline_benchmarks_ms": multi_run_metrics,
    }

    report_path = Path("reports/pipeline_latency_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[OK] Latency report saved to {report_path}")

    # Print summary tables to stdout
    print("\n" + "=" * 90)
    print("PULSE PIPELINE LATENCY SUMMARY: PER-EVENT PROCESSING (MILLISECONDS)")
    print("=" * 90)
    print(f"{'Layer / Component':<42} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'Max (ms)':<10} | {'P95 (ms)':<10} | {'Samples':<8}")
    print("-" * 90)
    for layer_name, stats in per_event_metrics.items():
        print(f"{layer_name:<42} | {stats['min']:<10.4f} | {stats['avg']:<10.4f} | {stats['max']:<10.4f} | {stats['p95']:<10.4f} | {stats['count']:<8}")

    print("\n" + "=" * 90)
    print(f"PULSE PIPELINE LATENCY SUMMARY: FULL-SESSION REPLAY ACROSS {multi_run_metrics['num_runs']} RUNS (MILLISECONDS)")
    print("=" * 90)
    print(f"{'Stage Name':<42} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'Max (ms)':<10} | {'StdDev':<10}")
    print("-" * 90)
    for stage_name, stats in multi_run_metrics["stages"].items():
        print(f"{stage_name:<42} | {stats['min']:<10.2f} | {stats['avg']:<10.2f} | {stats['max']:<10.2f} | {stats['stdev']:<10.2f}")
    print("-" * 90)
    tot = multi_run_metrics["full_pipeline_total"]
    print(f"{'FULL PIPELINE END-TO-END (TOTAL)':<42} | {tot['min']:<10.2f} | {tot['avg']:<10.2f} | {tot['max']:<10.2f} | {tot['stdev']:<10.2f}")
    print(f"{'FULL PIPELINE END-TO-END (SECONDS)':<42} | {tot['min']/1000:<10.2f} | {tot['avg']/1000:<10.2f} | {tot['max']/1000:<10.2f} | {tot['stdev']/1000:<10.2f}")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
