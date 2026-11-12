"""Production Kafka Benchmark Suite for CALIBRE / PULSE.

Executes:
1. Partition count sweep: N in {1, 3, 6, 11, 22} on fresh topics calibre.bench.p<N> (RF 3, min.isr 2), 3 runs each.
2. Tuning matrix at best N: linger.ms in {0, 5, 20, 50} x compression.type in {none, lz4, zstd}.
3. Full pipeline session replay benchmark comparing new KRaft 3-broker cluster against baseline.
4. Generates structured JSON reports and Markdown tables for documentation.
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

from confluent_kafka import Message, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from pulse.config import get_settings
from pulse.contracts import EventEnvelope
from pulse.stream.kafka_io import (
    DriverSlots,
    TopicSpec,
    build_topic_catalogue,
    driver_partition,
    ensure_topics,
    get_driver_slots,
)
from pulse.testing.orchestrator import VerticalSliceVerifier

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("calibre.benchmark")


def load_envelopes(capture_dir: Path) -> list[tuple[str, int | None, bytes]]:
    """Loads all 72,642 raw envelopes into memory as (event_type, driver_number, raw_bytes)."""
    env_file = capture_dir / "envelopes.jsonl"
    items: list[tuple[str, int | None, bytes]] = []

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            et = data.get("event_type", "UNKNOWN")
            subj = data.get("subject", {})
            dn = subj.get("driver_number") if isinstance(subj, dict) else None
            items.append((et, dn, line.encode("utf-8")))

    return items


def run_producer_batch(
    bootstrap: str,
    topic: str,
    num_partitions: int,
    envelopes: list[tuple[str, int | None, bytes]],
    slots: DriverSlots,
    linger_ms: int = 20,
    compression_type: str = "zstd",
) -> dict[str, Any]:
    """Runs a single timed ingest run of all envelopes against topic."""
    latencies: list[float] = []
    failed_count = 0
    delivered_count = 0

    def on_delivery(err, msg: Message):
        nonlocal failed_count, delivered_count
        if err is not None:
            failed_count += 1
            return
        delivered_count += 1
        lat = msg.latency() or 0.0
        latencies.append(lat * 1000.0)  # ms

    conf = {
        "bootstrap.servers": bootstrap,
        "client.id": f"calibre-bench-{topic}",
        "acks": "all",
        "enable.idempotence": True,
        "max.in.flight.requests.per.connection": 5,
        "linger.ms": linger_ms,
        "batch.size": 524288,
        "batch.num.messages": 20000,
        "compression.type": compression_type,
        "delivery.timeout.ms": 120000,
        "queue.buffering.max.messages": 500000,
        "queue.buffering.max.kbytes": 1048576,
    }

    p = Producer(conf)
    total_bytes = sum(len(raw) for _, _, raw in envelopes)

    t0 = time.perf_counter()
    for et, dn, raw_bytes in envelopes:
        if dn is not None:
            part = driver_partition(slots, dn, num_partitions)
        else:
            part = -1  # unassigned

        key = f"driver-{dn}".encode("utf-8") if dn else b"session"

        for _ in range(50):
            try:
                p.produce(topic, value=raw_bytes, key=key, partition=part, on_delivery=on_delivery)
                break
            except BufferError:
                p.poll(0.05)
        p.poll(0)

    p.flush(timeout=60.0)
    ingest_duration_s = time.perf_counter() - t0

    # Stats
    n = len(latencies)
    if n > 0:
        s_lat = sorted(latencies)
        p95_idx = min(int(math.ceil(0.95 * n)) - 1, n - 1)
        lat_avg = statistics.mean(s_lat)
        lat_p95 = s_lat[p95_idx]
        lat_max = s_lat[-1]
    else:
        lat_avg, lat_p95, lat_max = 0.0, 0.0, 0.0

    msg_s = len(envelopes) / ingest_duration_s if ingest_duration_s > 0 else 0.0
    mb_s = (total_bytes / (1024 * 1024)) / ingest_duration_s if ingest_duration_s > 0 else 0.0

    return {
        "ingest_s": round(ingest_duration_s, 2),
        "msg_s": round(msg_s, 2),
        "mb_s": round(mb_s, 2),
        "lat_avg_ms": round(lat_avg, 2),
        "lat_p95_ms": round(lat_p95, 2),
        "lat_max_ms": round(lat_max, 2),
        "failed": failed_count,
        "delivered": delivered_count,
    }


def ensure_bench_topic(admin: AdminClient, topic_name: str, partitions: int) -> None:
    spec = TopicSpec(topic_name, partitions=partitions, retention_ms=86400000)
    ensure_topics(admin, [spec])


def main():
    settings = get_settings()
    bootstrap = settings.kafka_bootstrap_servers
    admin = AdminClient({"bootstrap.servers": bootstrap})
    capture_dir = Path("captures/f1-2023-silverstone-race")
    results_dir = Path("docs/kafka/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("CALIBRE KAFKA PRODUCTION BENCHMARK SUITE")
    print(f"Cluster Bootstrap: {bootstrap}")
    print("=" * 80)

    envelopes = load_envelopes(capture_dir)
    print(f"Loaded {len(envelopes)} historical envelopes ({sum(len(b) for _,_,b in envelopes)/(1024*1024):.2f} MB)")
    slots = get_driver_slots()

    # --------------------------------------------------------------------------
    # 1. PARTITION SWEEP
    # --------------------------------------------------------------------------
    print("\n--- 1. PARTITION SWEEP (N in 1, 3, 6, 11, 22) ---")
    partition_counts = [1, 3, 6, 11, 22]
    partition_results: list[dict[str, Any]] = []

    for n_parts in partition_counts:
        topic_name = f"calibre.bench.p{n_parts}"
        ensure_bench_topic(admin, topic_name, n_parts)

        for run_idx in range(1, 4):
            print(f"Testing Partitions N={n_parts:<2} | Run {run_idx}/3 ... ", end="", flush=True)
            res = run_producer_batch(bootstrap, topic_name, n_parts, envelopes, slots, linger_ms=20, compression_type="zstd")
            res["partitions"] = n_parts
            res["run"] = run_idx
            partition_results.append(res)
            print(f"Done: {res['ingest_s']}s | {res['msg_s']:.0f} msg/s | {res['mb_s']:.2f} MB/s | lat avg: {res['lat_avg_ms']}ms | p95: {res['lat_p95_ms']}ms")

    (results_dir / "benchmark_partition_sweep.json").write_text(json.dumps(partition_results, indent=2), encoding="utf-8")

    # Determine best N by average msg/s
    n_averages = {}
    for n_parts in partition_counts:
        runs = [r for r in partition_results if r["partitions"] == n_parts]
        n_averages[n_parts] = statistics.mean(r["msg_s"] for r in runs)

    best_n = max(n_averages, key=n_averages.get)
    print(f"\nBest Partition Count by Throughput: N={best_n} ({n_averages[best_n]:.0f} msg/s avg)")

    # --------------------------------------------------------------------------
    # 2. TUNING MATRIX AT BEST N
    # --------------------------------------------------------------------------
    print(f"\n--- 2. TUNING MATRIX AT BEST N={best_n} ---")
    linger_options = [0, 5, 20, 50]
    compression_options = ["none", "lz4", "zstd"]
    tuning_results: list[dict[str, Any]] = []
    tuning_topic = f"calibre.bench.p{best_n}"

    for comp in compression_options:
        for linger in linger_options:
            print(f"Testing Tuning: linger={linger:<2}ms | comp={comp:<4} ... ", end="", flush=True)
            res = run_producer_batch(bootstrap, tuning_topic, best_n, envelopes, slots, linger_ms=linger, compression_type=comp)
            res["linger_ms"] = linger
            res["compression"] = comp
            tuning_results.append(res)
            print(f"Done: {res['ingest_s']}s | {res['msg_s']:.0f} msg/s | {res['mb_s']:.2f} MB/s | lat avg: {res['lat_avg_ms']}ms | p95: {res['lat_p95_ms']}ms")

    (results_dir / "benchmark_tuning_matrix.json").write_text(json.dumps(tuning_results, indent=2), encoding="utf-8")

    # --------------------------------------------------------------------------
    # 3. FULL PIPELINE REPLAY COMPARISON
    # --------------------------------------------------------------------------
    print("\n--- 3. FULL PIPELINE REPLAY (KRaft 3-Broker Cluster) ---")
    t_start = time.perf_counter()
    verifier = VerticalSliceVerifier(
        capture_id="pulse-capture-f1-2023-silverstone-race-v1",
        mode="REPLAY",
        output_dir="reports/full_race_kraft",
    )
    replay_result = asyncio.run(verifier.run())
    replay_duration_s = time.perf_counter() - t_start

    print(f"\nFull Pipeline Replay Finished in {replay_duration_s:.2f}s with status: {replay_result.status}")

    # Extract stages
    stage_table = []
    for s in replay_result.stages:
        stage_table.append({
            "stage": s.stage_name,
            "status": s.status,
            "in": s.input_count,
            "out": s.output_count,
            "latency_ms": round(s.latency_ms, 2),
        })

    replay_summary = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "total_replay_seconds": round(replay_duration_s, 2),
        "status": replay_result.status,
        "stages": stage_table,
    }
    (results_dir / "new_pipeline_replay_benchmark.json").write_text(json.dumps(replay_summary, indent=2), encoding="utf-8")

    # Print Summary Tables
    print("\n" + "=" * 90)
    print("PARTITION SWEEP RESULTS TABLE")
    print("=" * 90)
    print(f"{'partitions':<12} | {'run':<4} | {'ingest s':<10} | {'msg/s':<10} | {'MB/s':<8} | {'lat avg ms':<12} | {'lat P95 ms':<12} | {'lat max ms':<12} | {'failed':<6}")
    print("-" * 90)
    for r in partition_results:
        print(f"{r['partitions']:<12} | {r['run']:<4} | {r['ingest_s']:<10.2f} | {r['msg_s']:<10.1f} | {r['mb_s']:<8.2f} | {r['lat_avg_ms']:<12.2f} | {r['lat_p95_ms']:<12.2f} | {r['lat_max_ms']:<12.2f} | {r['failed']:<6}")

    print("\n" + "=" * 90)
    print("TUNING MATRIX RESULTS TABLE")
    print("=" * 90)
    print(f"{'linger ms':<10} | {'compression':<12} | {'ingest s':<10} | {'msg/s':<10} | {'MB/s':<8} | {'lat avg ms':<12} | {'lat P95 ms':<12} | {'lat max ms':<12}")
    print("-" * 90)
    for r in tuning_results:
        print(f"{r['linger_ms']:<10} | {r['compression']:<12} | {r['ingest_s']:<10.2f} | {r['msg_s']:<10.1f} | {r['mb_s']:<8.2f} | {r['lat_avg_ms']:<12.2f} | {r['lat_p95_ms']:<12.2f} | {r['lat_max_ms']:<12.2f}")


if __name__ == "__main__":
    main()

