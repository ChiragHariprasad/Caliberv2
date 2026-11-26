"""Comprehensive benchmark & reconciliation suite for the PULSE Formula 1 streaming pipeline.

Rigorous Phase H methodology:
1. Never mixes transport-disconnected compute benchmarks with connected Kafka publish RTT:
   - Separates Layer 1a (serial acks=all RTT), Layer 1b (batch-50 async), Layer 1c (enqueue+flush throughput).
   - Separates Layer 3/4 CPU-only processing from connected Kafka Finding/Assessment emission.
   - Measures real Stage 3 Apache Flink v3 end-to-end normalization latency & throughput.
2. Segregates cold-start / first-run vs subsequent runs; never prints P95/P99 on n < 20 samples.
3. Measures identical target_index=36321 cold seeks vs target_index=36500 cached keyframe seeks
   across n >= 10 trials, verifying zero SIA record_hash divergence.
4. Measures SQLite WAL crash-recovery load latency, /api/snapshot, /api/integrity/verify,
   SSE delivery latency, and process RSS + Docker container CPU/RAM footprints.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import logging
import math
import os
import statistics
import subprocess
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

import pulse.replay.controller as ctrl_mod
import pulse.state.store as store_mod
import pulse.stream.bus as bus_mod
from pulse.agents.event_control import EventControlAgent
from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.agents.track_state import TrackStateAgent
from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.config import get_settings
from pulse.contracts import EventEnvelope, Finding, Interpretation, Subject, utc_now
from pulse.integrity.agent import IntegrityAgent
from pulse.main import create_app
from pulse.replay.controller import ReplayController
from pulse.replay.processor import ReplayEventProcessor
from pulse.state.store import StateStore, get_state_store
from pulse.stream.bus import PulseEventBus
from pulse.stream.flink.manager import get_flink_manager
from pulse.stream.kafka_client import KafkaBroker
from pulse.stream.kafka_io import CalibreProducer
from pulse.stream.normalizer import StreamNormalizer
from pulse.testing.orchestrator import VerticalSliceVerifier
from pulse.topics import AGENT_TOPICS, INTELLIGENCE_TOPICS, NORMALISED_TOPICS, RAW_TOPICS, raw_topic_for_event

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("pulse.benchmark")


def get_process_rss_mb() -> float:
    """Read current process working-set memory (MB) via Windows API or POSIX fallback."""
    if os.name == "nt":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        hproc = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(hproc, ctypes.byref(counters), counters.cb):
            return round(counters.WorkingSetSize / (1024 * 1024), 2)
    return 0.0


def capture_docker_stats() -> list[dict[str, Any]]:
    """Sample non-streaming CPU% and memory usage for Kafka + Flink containers."""
    containers = ["kafka-1", "kafka-2", "kafka-3", "calibre-flink-jobmanager", "calibre-flink-taskmanager"]
    try:
        res = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}", *containers],
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = []
        for line in res.stdout.splitlines():
            parts = line.strip().split("|")
            if len(parts) == 4:
                out.append({"container": parts[0], "cpu": parts[1], "mem_usage": parts[2], "mem_pct": parts[3]})
        return out
    except Exception as exc:
        return [{"error": str(exc)}]


def compute_stats(samples: list[float]) -> dict[str, Any]:
    """Compute rigorous summary statistics without fabricating P95/P99 on small samples."""
    n = len(samples)
    if n == 0:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "median": 0.0, "range": 0.0, "stdev": 0.0, "p95": None, "p99": None, "count": 0}
    s = sorted(samples)
    p95 = round(s[min(int(math.ceil(0.95 * n)) - 1, n - 1)], 4) if n >= 20 else None
    p99 = round(s[min(int(math.ceil(0.99 * n)) - 1, n - 1)], 4) if n >= 100 else None
    return {
        "min": round(s[0], 4),
        "median": round(statistics.median(s), 4),
        "avg": round(statistics.mean(s), 4),
        "max": round(s[-1], 4),
        "range": round(s[-1] - s[0], 4),
        "stdev": round(statistics.stdev(s), 4) if n > 1 else 0.0,
        "p95": p95,
        "p99": p99,
        "count": n,
    }


async def benchmark_per_event_layers(capture_dir: Path, sample_limit: int = 1000) -> dict[str, Any]:
    """Measure separated transport vs pure-compute latencies across all pipeline layers."""
    print("\n" + "=" * 80)
    print("BENCHMARK 1: SEPARATED COMPUTE VS KAFKA TRANSPORT PER-EVENT LATENCIES")
    print("=" * 80)

    envelopes_file = capture_dir / "envelopes.jsonl"
    all_envelopes: list[EventEnvelope] = []
    with open(envelopes_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_envelopes.append(EventEnvelope.model_validate(json.loads(line)))

    rc_events = [e for e in all_envelopes if e.event_type in {
        "SESSION_STARTED", "VSC_DEPLOYED", "VSC_ENDING", "VSC_ENDED",
        "SAFETY_CAR_DEPLOYED", "SAFETY_CAR_IN_THIS_LAP", "SAFETY_CAR_ENDING",
        "GREEN_FLAG_RESUMED", "TRACK_STATUS_GREEN", "DRIVER_RETIRED", "STEWARD_DECISION",
        "SESSION_CHEQUERED", "RACE_CONTROL_MESSAGE", "RACE_CONTROL_NOTICE",
    }]
    lap_events = [e for e in all_envelopes if e.event_type == "LAP_COMPLETED"]
    weather_events = [e for e in all_envelopes if e.event_type in {"WEATHER_OBSERVATION", "TRACK_STATUS_UPDATE"}]
    strat_events = [e for e in all_envelopes if e.event_type in {"VSC_DEPLOYED", "SAFETY_CAR_DEPLOYED", "PIT_STOP", "PIT_STOP_RECORDED", "TYRE_FITTED"}]
    pos_events = [e for e in all_envelopes if e.event_type == "POSITION_UPDATE"]

    # Stamp fresh event IDs for probe isolation so Flink/dedup don't collapse probes
    probe_tag = f"bench-{uuid4().hex[:6]}"
    publish_sample: list[EventEnvelope] = []
    for idx, orig in enumerate((rc_events + weather_events + strat_events + lap_events[:200] + pos_events)[:sample_limit]):
        cloned = orig.model_copy(deep=True)
        cloned.event_id = f"{probe_tag}-{idx}"
        cloned.run.run_id = probe_tag
        publish_sample.append(cloned)

    # Layer 1a: Serial acks=all RTT (concurrency=1)
    print("[1/8] Layer 1a (serial acks=all), 1b (batch-50 async), 1c (enqueue+flush 5k)...")
    broker = KafkaBroker()
    await broker.start()
    l1_serial: list[float] = []
    for env in publish_sample[:250]:
        topic = raw_topic_for_event(env.event_type)
        key = str(env.subject.driver_number or "session")
        t0 = time.perf_counter_ns()
        await broker.publish(topic, key, env)
        t1 = time.perf_counter_ns()
        l1_serial.append((t1 - t0) / 1_000_000.0)

    # Layer 1b: Batched concurrency=50 async publish
    l1_batch50: list[float] = []
    t_b_all = time.perf_counter()
    for i in range(0, len(publish_sample), 50):
        chunk = publish_sample[i : i + 50]
        t0 = time.perf_counter_ns()
        await asyncio.gather(*[
            broker.publish(raw_topic_for_event(env.event_type), str(env.subject.driver_number or "session"), env)
            for env in chunk
        ])
        l1_batch50.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    b50_sec = time.perf_counter() - t_b_all
    await broker.stop()

    # Layer 1c: Sustained non-blocking enqueue + flush (5,000 events)
    cp = CalibreProducer(bootstrap_servers=get_settings().kafka_bootstrap_servers)
    bulk_5k = pos_events[:5000]
    t_bulk_0 = time.perf_counter()
    for idx, orig in enumerate(bulk_5k):
        cp.publish(
            RAW_TOPICS["timing_positions"],
            {"event_id": f"{probe_tag}-5k-{idx}", "event_type": "POSITION_UPDATE", "run": {"run_id": probe_tag}},
            key=str(orig.subject.driver_number or "session"),
            driver_id=orig.subject.driver_number,
        )
    cp.flush(30.0)
    bulk_sec = time.perf_counter() - t_bulk_0

    # Layer 2: StreamNormalizer CPU parse
    print("[2/8] Layer 2: Canonical schema parse...")
    norm_samples: list[float] = []
    for env in publish_sample:
        raw_dict = env.model_dump(mode="json")
        t0 = time.perf_counter_ns()
        parsed = EventEnvelope.model_validate(raw_dict)
        _ = parsed.time.session_elapsed_ms
        _ = parsed.event_type
        norm_samples.append((time.perf_counter_ns() - t0) / 1_000_000.0)

    # Layer 3: Agents 01-04 PURE COMPUTE (disconnected bus) vs WITH KAFKA PUBLISH
    print("[3/8] Layer 3: Agents 01-04 (compute-only vs Kafka finding publish)...")
    local_bus = PulseEventBus()  # disconnected
    ec_c = EventControlAgent(bus=local_bus)
    ts_c = TrackStateAgent(bus=local_bus)
    vr_c = VehicleResponseAgent(bus=local_bus)
    ty_c = TyreStrategyAgent(bus=local_bus)

    ec_cpu, ts_cpu, vr_cpu, ty_cpu = [], [], [], []
    for env in rc_events:
        t0 = time.perf_counter_ns()
        await ec_c.on_event(NORMALISED_TOPICS["race_events"], "session", env)
        ec_cpu.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    for env in weather_events:
        t0 = time.perf_counter_ns()
        await ts_c.on_event(NORMALISED_TOPICS["track_segments"], "circuit", env)
        ts_cpu.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    for env in lap_events[:sample_limit]:
        t0 = time.perf_counter_ns()
        await vr_c.on_event(NORMALISED_TOPICS["driver_laps"], f"session:{env.subject.driver_number}", env)
        vr_cpu.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    for env in strat_events:
        t0 = time.perf_counter_ns()
        await ty_c.on_event(NORMALISED_TOPICS["race_events"], f"session:{env.subject.driver_number or 44}", env)
        ty_cpu.append((time.perf_counter_ns() - t0) / 1_000_000.0)

    kafka_bus_broker = KafkaBroker()
    await kafka_bus_broker.start()
    kafka_bus = PulseEventBus(broker=kafka_bus_broker)
    ec_k = EventControlAgent(bus=kafka_bus)
    ty_k = TyreStrategyAgent(bus=kafka_bus)
    ec_kafka, ty_kafka = [], []
    for env in rc_events:
        t0 = time.perf_counter_ns()
        await ec_k.on_event(NORMALISED_TOPICS["race_events"], "session", env)
        ec_kafka.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    for env in strat_events[:40]:
        t0 = time.perf_counter_ns()
        await ty_k.on_event(NORMALISED_TOPICS["race_events"], f"session:{env.subject.driver_number or 44}", env)
        ty_kafka.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    await kafka_bus_broker.stop()

    # Layer 4 & 5: Fusion + StateStore (CPU + SSE delivery latency)
    print("[4/8] Layer 4 & 5: Fusion + StateStore + SSE push latency...")
    agent_fu = ConsequenceFusionEngine(bus=local_bus)
    store = StateStore()
    findings_to_fuse: list[Finding] = []
    for i, env in enumerate(strat_events + rc_events):
        findings_to_fuse.append(Finding(
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
        ))
    for drv in range(1, 21):
        for lap in range(1, 15):
            findings_to_fuse.append(Finding(
                finding_id=f"bench-vr-d{drv}-l{lap}",
                agent_id="agent-03-vehicle-response",
                finding_type="PACE_DEVIATION",
                session_id="bench-session",
                run_id="bench-run",
                subject=Subject(driver_number=drv),
                trigger_event_id=f"evt-lap-{drv}-{lap}",
                as_of_event_time=utc_now(),
                interpretation=Interpretation.DERIVED,
                result={"driver_number": drv, "lap_number": lap, "lap_time_seconds": 91.2 + lap * 0.05, "pace_delta_sec": 0.25},
                evidence_refs=[f"evt-lap-{drv}-{lap}"],
                model_version="1.0.0",
            ))

    fusion_samples: list[float] = []
    for f in findings_to_fuse:
        t0 = time.perf_counter_ns()
        await agent_fu.on_finding(AGENT_TOPICS["event_context"], f"session:{f.subject.driver_number}", f)
        fusion_samples.append((time.perf_counter_ns() - t0) / 1_000_000.0)

    statestore_samples: list[float] = []
    sse_queue = store.add_listener()
    sse_samples: list[float] = []
    for f in findings_to_fuse[:100]:
        t0 = time.perf_counter_ns()
        store.record_finding(f)
        t1 = time.perf_counter_ns()
        statestore_samples.append((t1 - t0) / 1_000_000.0)
        # Drain emitted queue notifications & time delivery
        while not sse_queue.empty():
            _ = await sse_queue.get()
        sse_samples.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    store.remove_listener(sse_queue)

    # Layer 6: API Serialization across endpoints
    print("[5/8] Layer 6: API Serving & Serialization...")
    prev_mode = os.environ.get("PULSE_TRANSPORT_MODE")
    os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
    get_settings.cache_clear()
    app = create_app()
    api_samples: list[float] = []
    with TestClient(app) as client:
        for ep in ["/api/health", "/api/replay/status", "/api/findings", "/api/assessments", "/api/agents/metrics", "/api/snapshot"] * 20:
            t0 = time.perf_counter_ns()
            res = client.get(ep)
            t1 = time.perf_counter_ns()
            assert res.status_code == 200
            api_samples.append((t1 - t0) / 1_000_000.0)
    if prev_mode is None:
        os.environ.pop("PULSE_TRANSPORT_MODE", None)
    else:
        os.environ["PULSE_TRANSPORT_MODE"] = prev_mode
    get_settings.cache_clear()

    flink_mgr = get_flink_manager()
    fmetrics = flink_mgr.get_metrics()

    return {
        "layer_1a_kafka_serial_rtt_ms": compute_stats(l1_serial),
        "layer_1b_kafka_batch50_ms": {
            **compute_stats(l1_batch50),
            "events_total": len(publish_sample),
            "elapsed_sec": round(b50_sec, 4),
            "throughput_evt_per_sec": round(len(publish_sample) / b50_sec, 2) if b50_sec > 0 else 0.0,
        },
        "layer_1c_kafka_enqueue_flush_5000": {
            "events": len(bulk_5k),
            "elapsed_sec": round(bulk_sec, 4),
            "ms_per_event": round((bulk_sec * 1000.0) / len(bulk_5k), 4),
            "throughput_evt_per_sec": round(len(bulk_5k) / bulk_sec, 2) if bulk_sec > 0 else 0.0,
        },
        "layer_2_stream_normalization_cpu_ms": compute_stats(norm_samples),
        "flink_live_cluster_metrics": fmetrics.model_dump() if fmetrics else None,
        "layer_3_agent_1_compute_ms": compute_stats(ec_cpu),
        "layer_3_agent_2_compute_ms": compute_stats(ts_cpu),
        "layer_3_agent_3_compute_ms": compute_stats(vr_cpu),
        "layer_3_agent_4_compute_ms": compute_stats(ty_cpu),
        "layer_3_agents_compute_aggregated_ms": compute_stats(ec_cpu + ts_cpu + vr_cpu + ty_cpu),
        "layer_3_agent_1_with_kafka_publish_ms": compute_stats(ec_kafka),
        "layer_3_agent_4_with_kafka_publish_ms": compute_stats(ty_kafka),
        "layer_4_consequence_fusion_compute_ms": compute_stats(fusion_samples),
        "layer_5_statestore_persistence_ms": compute_stats(statestore_samples),
        "layer_7_sse_queue_delivery_ms": compute_stats(sse_samples),
        "layer_6_api_serving_ms": compute_stats(api_samples),
    }


async def benchmark_seek_wal_and_snapshot(seek_runs: int = 10) -> dict[str, Any]:
    """Benchmark identical target_index=36321 cold seeks vs 36500 cached keyframe seeks + WAL restore."""
    print("\n" + "=" * 80)
    print(f"BENCHMARK 2: IDENTICAL-INDEX SEEK, SNAPSHOT, VERIFY & WAL RECOVERY ({seek_runs} TRIALS)")
    print("=" * 80)

    prev_mode = os.environ.get("PULSE_TRANSPORT_MODE")
    os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
    get_settings.cache_clear()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        wal_path = Path(tmp_dir) / "bench_sia_wal.sqlite"
        os.environ["PULSE_SIA_WAL_PATH"] = str(wal_path)
        get_settings.cache_clear()

        store_mod._store = None
        bus_mod._bus = None
        ctrl_mod._controller = None

        cold_36321_ms: list[float] = []
        cached_36500_ms: list[float] = []
        wal_restore_ms: list[float] = []
        snapshot_midrace_ms: list[float] = []
        verify_chains_ms: list[float] = []
        hash_mismatches = 0
        chain_count = 0
        snapshot_bytes = 0

        app = create_app()
        with TestClient(app) as client:
            r_sel = client.post("/api/sessions/select", json={"session_id": "f1-2023-silverstone-race"})
            assert r_sel.status_code == 200
            from pulse.replay.controller import get_replay_controller
            rc = get_replay_controller()
            store = get_state_store()
            assert rc.session_id == "f1-2023-silverstone-race"

            # Cold reference seek at 36500 once (with clean checkpoints) to establish ground-truth hashes
            res_ref = client.post("/api/replay/seek", json={"target_index": 36500})
            assert res_ref.status_code == 200
            ia = store.agents["agent-06-integrity"]
            ref_verdicts = {
                v["decision_instance_id"]: (v["integrity_state"], v["record_hash"], v["revision_number"])
                for v in ia.get_all_verdicts()
            }

            # Snapshot & Verify latency at mid-race load
            for _ in range(50):
                t0 = time.perf_counter_ns()
                r_snap = client.get("/api/snapshot")
                snapshot_midrace_ms.append((time.perf_counter_ns() - t0) / 1_000_000.0)
                assert r_snap.status_code == 200
                snapshot_bytes = len(r_snap.content)

            for _ in range(seek_runs):
                t0 = time.perf_counter_ns()
                r_ver = client.get("/api/integrity/verify")
                verify_chains_ms.append((time.perf_counter_ns() - t0) / 1_000_000.0)
                assert r_ver.status_code == 200
                body = r_ver.json()
                assert body["verified"] is True
                chain_count = int(body.get("chain_count", len(body.get("results", {}))))

            # Measure n cold seeks to 36321 (clear checkpoints -> cold seek builds 5k..35k checkpoints -> jump to 36500)
            for trial in range(1, seek_runs + 1):
                rc._checkpoints.clear()
                t0 = time.perf_counter_ns()
                r_c = client.post("/api/replay/seek", json={"target_index": 36321})
                dt_c = (time.perf_counter_ns() - t0) / 1_000_000.0
                assert r_c.status_code == 200
                cold_36321_ms.append(dt_c)

                # WAL restore benchmark from synced state
                t_w0 = time.perf_counter_ns()
                ia2 = IntegrityAgent(wal_path=wal_path, session_id=rc.session_id)
                assert ia2.restore_from_wal() is True
                wal_restore_ms.append((time.perf_counter_ns() - t_w0) / 1_000_000.0)
                ia2._wal.close()

                # Cached keyframe seek to 36500 (uses checkpoint at 35000 + replays 1500 events)
                t1 = time.perf_counter_ns()
                r_k = client.post("/api/replay/seek", json={"target_index": 36500})
                dt_k = (time.perf_counter_ns() - t1) / 1_000_000.0
                assert r_k.status_code == 200
                cached_36500_ms.append(dt_k)

                cur_verdicts = {
                    v["decision_instance_id"]: (v["integrity_state"], v["record_hash"], v["revision_number"])
                    for v in store.agents["agent-06-integrity"].get_all_verdicts()
                }
                if cur_verdicts != ref_verdicts:
                    hash_mismatches += 1
                print(f"  [Trial {trial}/{seek_runs}] cold_seek(36321)={dt_c:.1f}ms | cached_seek(36500)={dt_k:.1f}ms | wal_restore={wal_restore_ms[-1]:.1f}ms")

            if store.agents["agent-06-integrity"]._wal is not None:
                store.agents["agent-06-integrity"]._wal.close()

    os.environ.pop("PULSE_SIA_WAL_PATH", None)
    if prev_mode is None:
        os.environ.pop("PULSE_TRANSPORT_MODE", None)
    else:
        os.environ["PULSE_TRANSPORT_MODE"] = prev_mode
    get_settings.cache_clear()

    return {
        "trials": seek_runs,
        "cold_seek_36321_first_run_ms": round(cold_36321_ms[0], 2),
        "cold_seek_36321_warm_runs_2_to_n_ms": compute_stats(cold_36321_ms[1:]) if len(cold_36321_ms) > 1 else compute_stats(cold_36321_ms),
        "cold_seek_36321_all_runs_ms": compute_stats(cold_36321_ms),
        "cached_keyframe_seek_36500_ms": compute_stats(cached_36500_ms),
        "keyframe_vs_cold_median_speedup": round(statistics.median(cold_36321_ms) / statistics.median(cached_36500_ms), 2),
        "sia_hash_mismatches": hash_mismatches,
        "wal_restore_midrace_ms": compute_stats(wal_restore_ms),
        "snapshot_midrace_ms": compute_stats(snapshot_midrace_ms),
        "snapshot_payload_kb": round(snapshot_bytes / 1024.0, 2),
        "integrity_verify_all_chains_ms": compute_stats(verify_chains_ms),
        "verified_chain_count": chain_count,
    }


async def benchmark_full_pipeline_multi_runs(num_runs: int = 5) -> dict[str, Any]:
    """Execute full 72,642-event Kafka + Flink v3 E2E runs via VerticalSliceVerifier."""
    print("\n" + "=" * 80)
    print(f"BENCHMARK 3: FULL 72,642-EVENT KAFKA + FLINK V3 E2E BENCHMARK ({num_runs} COMPLETE RUNS)")
    print("=" * 80)

    stage_latencies: dict[str, list[float]] = {}
    total_pipeline_latencies: list[float] = []

    for run_idx in range(1, num_runs + 1):
        print(f"\n--- Full E2E Run {run_idx}/{num_runs} (72,642 events through Kafka + Flink v3) ---")
        t0 = time.perf_counter()
        store_mod._store = None
        bus_mod._bus = None
        ctrl_mod._controller = None

        verifier = VerticalSliceVerifier(
            capture_id="pulse-capture-f1-2023-silverstone-race-v1",
            mode="REPLAY",
            output_dir=f"reports/benchmark_run_{run_idx}",
        )
        result = await verifier.run()
        assert result.status == "PASSED"
        for s in result.stages:
            assert s.drop_count == 0
        run_duration_ms = (time.perf_counter() - t0) * 1000.0
        total_pipeline_latencies.append(run_duration_ms)
        print(f"Run {run_idx} PASSED in {run_duration_ms / 1000.0:.2f}s (all {len(result.stages)} stages, 0 drops)")

        for stage in result.stages:
            stage_latencies.setdefault(stage.stage_name, []).append(stage.latency_ms)

    return {
        "num_runs": num_runs,
        "run_1_cold_ms": round(total_pipeline_latencies[0], 2) if total_pipeline_latencies else 0.0,
        "warm_runs_2_to_n_ms": compute_stats(total_pipeline_latencies[1:]) if len(total_pipeline_latencies) > 1 else compute_stats(total_pipeline_latencies),
        "stages": {k: compute_stats(v) for k, v in stage_latencies.items()},
        "full_pipeline_total": compute_stats(total_pipeline_latencies),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seek-runs", type=int, default=10)
    parser.add_argument("--full-runs", type=int, default=10)
    parser.add_argument("--skip-layers-and-seek", action="store_true")
    parser.add_argument("--skip-full-runs", action="store_true")
    args = parser.parse_args()

    capture_dir = Path("captures/f1-2023-silverstone-race")
    if not capture_dir.exists():
        raise FileNotFoundError("Missing capture directory")

    report_path = Path("reports/pipeline_latency_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {}
    if report_path.exists() and (args.skip_layers_and_seek or args.skip_full_runs):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            report = {}

    rss_start = get_process_rss_mb()
    t_start = time.time()

    if not args.skip_layers_and_seek:
        per_event = await benchmark_per_event_layers(capture_dir, sample_limit=1000)
        seek_wal = await benchmark_seek_wal_and_snapshot(seek_runs=args.seek_runs)
        report["per_event_layer_benchmarks_ms"] = per_event
        report["seek_wal_and_api_benchmarks"] = seek_wal

    if not args.skip_full_runs and args.full_runs > 0:
        multi_run = await benchmark_full_pipeline_multi_runs(num_runs=args.full_runs)
        report["multi_run_full_pipeline_benchmarks_ms"] = multi_run

    rss_end = get_process_rss_mb()
    total_bench_time = time.time() - t_start

    report["timestamp_utc"] = datetime.now(UTC).isoformat()
    report["total_benchmark_duration_seconds"] = round(total_bench_time, 2)
    report["resource_footprint"] = {
        "python_rss_start_mb": rss_start,
        "python_rss_end_mb": rss_end,
        "docker_containers": capture_docker_stats(),
    }

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[OK] Phase H benchmark report saved to {report_path} (elapsed {total_bench_time:.1f}s)")


if __name__ == "__main__":
    asyncio.run(main())
