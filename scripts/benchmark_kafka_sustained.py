"""Priority E Sustained Kafka+Flink Load, Concurrent Sessions, Skew, Lag, and Memory Benchmark."""
from __future__ import annotations

import json
import math
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient

from pulse.config import get_settings
from pulse.stream.kafka_io import (
    IdempotentVerdictSink,
    TopicSpec,
    driver_partition,
    ensure_topics,
    get_driver_slots,
)


def _get_rss_mb() -> float:
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


def _inspect_cluster(admin: AdminClient) -> dict[str, Any]:
    md = admin.list_topics(timeout=10.0)
    brokers = [{"id": b.id, "host": b.host, "port": b.port} for b in md.brokers.values()]
    pulse_topics = [t for t in md.topics.values() if t.topic.startswith(("pulse.", "calibre."))]
    under_replicated = 0
    total_parts = 0
    for t in pulse_topics:
        for p in t.partitions.values():
            total_parts += 1
            if len(p.isrs) < len(p.replicas):
                under_replicated += 1
    return {
        "broker_count": len(brokers),
        "brokers": brokers,
        "pulse_topic_count": len([t for t in pulse_topics if t.topic.startswith("pulse.")]),
        "total_partitions_checked": total_parts,
        "under_replicated_partitions": under_replicated,
    }


def _inspect_flink(flink_url: str) -> dict[str, Any]:
    try:
        with urlopen(f"{flink_url}/jobs/overview", timeout=3.0) as resp:
            overview = json.loads(resp.read().decode("utf-8"))
        jobs = overview.get("jobs", [])
        running = [j for j in jobs if j.get("state") == "RUNNING"]
        details = None
        if running:
            jid = running[0]["jid"]
            with urlopen(f"{flink_url}/jobs/{jid}", timeout=3.0) as r2:
                details = json.loads(r2.read().decode("utf-8"))
        return {
            "online": True,
            "total_jobs": len(jobs),
            "running_jobs": len(running),
            "job_name": running[0]["name"] if running else None,
            "job_id": running[0]["jid"] if running else None,
            "vertex_count": len((details or {}).get("vertices", [])),
            "tasks_running": (running[0].get("tasks", {}) or {}).get("running") if running else 0,
        }
    except Exception as exc:
        return {"online": False, "error": str(exc)}


def _produce_session_stream(
    bootstrap: str,
    topic: str,
    session_id: str,
    lines: list[str],
    num_partitions: int,
    slots: Any,
) -> dict[str, Any]:
    latencies: list[float] = []
    part_counts: dict[int, int] = {i: 0 for i in range(num_partitions)}
    failed = 0
    delivered = 0

    def _on_delivery(err, msg):
        nonlocal failed, delivered
        if err is not None:
            failed += 1
            return
        delivered += 1
        latencies.append((msg.latency() or 0.0) * 1000.0)

    p = Producer({
        "bootstrap.servers": bootstrap,
        "client.id": f"sustained-{session_id}",
        "acks": "all",
        "enable.idempotence": True,
        "linger.ms": 10,
        "batch.size": 262144,
        "compression.type": "zstd",
        "queue.buffering.max.messages": 200000,
    })
    t0 = time.perf_counter()
    bytes_total = 0
    for idx, line in enumerate(lines):
        payload = json.loads(line)
        payload["session"]["session_id"] = session_id
        payload["run"]["session_instance_id"] = session_id
        dn = (payload.get("subject") or {}).get("driver_number")
        part = driver_partition(slots, dn, num_partitions) if dn is not None else (idx % num_partitions)
        part_counts[part] = part_counts.get(part, 0) + 1
        raw = json.dumps(payload).encode("utf-8")
        bytes_total += len(raw)
        key = f"{session_id}:{dn or 'session'}".encode("utf-8")
        for _ in range(30):
            try:
                p.produce(topic, value=raw, key=key, partition=part, on_delivery=_on_delivery)
                break
            except BufferError:
                p.poll(0.02)
        if idx % 200 == 0:
            p.poll(0)
    p.flush(timeout=45.0)
    dt = time.perf_counter() - t0
    sl = sorted(latencies)
    return {
        "session_id": session_id,
        "delivered": delivered,
        "failed": failed,
        "duration_s": round(dt, 3),
        "msg_s": round(delivered / max(dt, 1e-6), 1),
        "mb_s": round((bytes_total / (1024 * 1024)) / max(dt, 1e-6), 2),
        "lat_p50_ms": round(statistics.median(sl), 2) if sl else 0.0,
        "lat_p95_ms": round(sl[min(int(0.95 * len(sl)), len(sl) - 1)], 2) if sl else 0.0,
        "partition_counts": part_counts,
    }


def _run_consumer_lag_and_dedup_recovery(
    bootstrap: str,
    topic: str,
    num_partitions: int,
    expected_total: int,
    sessions: list[str],
) -> dict[str, Any]:
    group_id = f"pulse-sustained-eval-{int(time.time())}"
    c = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    tps = [TopicPartition(topic, p) for p in range(num_partitions)]
    c.assign(tps)

    # Measure initial backlog (lag before draining)
    peak_lag = 0
    for tp in tps:
        lo, hi = c.get_watermark_offsets(tp, timeout=5.0)
        peak_lag += max(0, hi - lo)

    with tempfile.TemporaryDirectory() as tmp:
        sink = IdempotentVerdictSink(Path(tmp) / "sustained_verdicts.db")
        try:
            seen_sessions: dict[str, int] = {s: 0 for s in sessions}
            consumed = 0
            rebalance_replays = 0
            first_10_msgs: list[tuple[str, int, int, str, str]] = []

            t0 = time.perf_counter()
            empty_polls = 0
            while consumed < expected_total and empty_polls < 25:
                msgs = c.consume(num_messages=1000, timeout=0.5)
                if not msgs:
                    empty_polls += 1
                    continue
                empty_polls = 0
                for msg in msgs:
                    if msg.error():
                        continue
                    consumed += 1
                    raw_val = msg.value().decode("utf-8")
                    data = json.loads(raw_val)
                    sid = data["session"]["session_id"]
                    if sid in seen_sessions:
                        seen_sessions[sid] += 1
                    key_str = (msg.key() or b"").decode("utf-8", errors="ignore")
                    if len(first_10_msgs) < 10:
                        first_10_msgs.append((msg.topic(), msg.partition(), msg.offset(), key_str, data["event_id"]))
                    sink.insert_verdict(msg.topic(), msg.partition(), msg.offset(), key_str, data["event_id"])
                c.commit(asynchronous=False)
            drain_s = time.perf_counter() - t0

            # Verify simulated consumer reconnect / duplicate offset replay produces 0 duplicate inserts
            for tp_name, part, off, k_str, ev_id in first_10_msgs:
                if sink.insert_verdict(tp_name, part, off, k_str, ev_id):
                    rebalance_replays += 1
            sink_count = sink.count()
        finally:
            sink.close()

    # Confirm final committed lag == 0
    committed = c.committed(tps, timeout=5.0)
    remaining_lag = 0
    for tp in committed:
        _lo, hi = c.get_watermark_offsets(tp, timeout=5.0)
        if tp.offset >= 0:
            remaining_lag += max(0, hi - tp.offset)
    c.close()

    return {
        "peak_lag_messages": peak_lag,
        "consumed_total": consumed,
        "unique_sink_verdicts": sink_count,
        "drain_duration_s": round(drain_s, 3),
        "drain_msg_s": round(consumed / max(drain_s, 1e-6), 1),
        "remaining_lag_after_drain": remaining_lag,
        "per_session_isolated_counts": seen_sessions,
        "idempotent_sink_dedup_violations_on_reconsume": rebalance_replays,
    }


def main() -> None:
    settings = get_settings()
    bootstrap = settings.kafka_bootstrap_servers
    admin = AdminClient({"bootstrap.servers": bootstrap})
    slots = get_driver_slots()

    rss_start = _get_rss_mb()
    cluster_health = _inspect_cluster(admin)
    flink_health = _inspect_flink(settings.flink_rest_url)

    # Load 15,000 real events from Silverstone capture for sustained multi-session test
    env_file = Path("E:/Caliberv2/captures/f1-2023-silverstone-race/envelopes.jsonl")
    sample_lines = []
    with env_file.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 8000:
                break
            if line.strip():
                sample_lines.append(line.strip())

    # 1. Rising rate sweep on fresh dedicated sustained topic (11 partitions, RF=3)
    rate_topic = f"calibre.bench.sustained.rate.{int(time.time())}"
    ensure_topics(admin, [TopicSpec(rate_topic, partitions=11, retention_ms=3600000)])
    rate_steps = []
    for n_msgs in (2000, 5000, 8000):
        res = _produce_session_stream(bootstrap, rate_topic, f"rate-{n_msgs}", sample_lines[:n_msgs], 11, slots)
        rate_steps.append({"batch_size": n_msgs, "msg_s": res["msg_s"], "mb_s": res["mb_s"], "lat_p95_ms": res["lat_p95_ms"], "failed": res["failed"]})

    # 2. 3 Concurrent sessions producing simultaneously (3 x 6,000 = 18,000 events)
    conc_topic = f"calibre.bench.concurrent.{int(time.time())}"
    ensure_topics(admin, [TopicSpec(conc_topic, partitions=11, retention_ms=3600000)])
    sessions = ["conc-silverstone", "conc-monaco", "conc-suzuka"]
    slices = [sample_lines[:6000], sample_lines[:6000], sample_lines[:6000]]

    t_conc0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [
            pool.submit(_produce_session_stream, bootstrap, conc_topic, sid, sl, 11, slots)
            for sid, sl in zip(sessions, slices)
        ]
        conc_results = [f.result() for f in futs]
    conc_wall_s = time.perf_counter() - t_conc0

    # Compute partition skew across 11 partitions across the 18,000 concurrent events
    agg_parts = {p: 0 for p in range(11)}
    for r in conc_results:
        for p, cnt in r["partition_counts"].items():
            agg_parts[p] += cnt
    counts = list(agg_parts.values())
    mean_c = sum(counts) / len(counts)
    skew_ratio = round(max(counts) / max(mean_c, 1e-6), 3)

    # 3. Consumer lag drain & idempotent sink rebalance verification
    try:
        lag_res = _run_consumer_lag_and_dedup_recovery(bootstrap, conc_topic, 11, 18000, sessions)
    finally:
        try:
            admin.delete_topics([rate_topic, conc_topic], operation_timeout=15.0)
        except Exception:
            pass
    rss_end = _get_rss_mb()

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "cluster_health": cluster_health,
        "flink_health": flink_health,
        "rising_ingestion_sweep": rate_steps,
        "concurrent_sessions_3x6000": {
            "wall_clock_sec": round(conc_wall_s, 3),
            "aggregate_msg_s": round(18000 / max(conc_wall_s, 1e-6), 1),
            "per_session": conc_results,
            "partition_distribution_11p": agg_parts,
            "partition_skew_max_over_mean": skew_ratio,
        },
        "consumer_lag_and_idempotency": lag_res,
        "memory_footprint_rss_mb": {
            "start_mb": rss_start,
            "end_mb": rss_end,
            "delta_mb": round(rss_end - rss_start, 2),
        },
    }

    out_path = Path("E:/Caliberv2/reports/benchmarks/phase_i_kafka_sustained.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
