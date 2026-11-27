"""Phase J Distributed System Release Validation: Broker vs E2E Analytics Throughput.

Clearly separates:
1. Tier 1: Isolated raw Kafka broker batch/fan-in/drain throughput (matching Phase I protocol).
2. Tier 2: 35-second sustained 3-session concurrent end-to-end processing through live Kafka ->
   Flink v3 (pulse-canonical-normalizer-v3) -> Python Consumer -> 6 Agents -> SIA WAL -> SQLite VerdictSink,
   monitoring Flink checkpoints/backpressure, consumer lag, partition skew, RSS growth, and crash/offset consistency.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import gc
import json
import os
from pathlib import Path
import statistics
import tempfile
import time
from typing import Any
from urllib.request import urlopen

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

from pulse.agents.event_control import EventControlAgent
from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.agents.track_state import TrackStateAgent
from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.contracts import EventEnvelope
from pulse.integrity.agent import IntegrityAgent
from pulse.state.store import StateStore
from pulse.stream.bus import PulseEventBus
from pulse.stream.kafka_io import IdempotentVerdictSink, driver_partition, get_driver_slots
from pulse.topics import NORMALISED_TOPICS, raw_topic_for_event, routing_key


def _rss_mb() -> float:
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


def _ensure_temp_topic(bootstrap: str, name: str, partitions: int = 11, rf: int = 3) -> None:
    adm = AdminClient({"bootstrap.servers": bootstrap})
    md = adm.list_topics(timeout=10)
    if name in md.topics and not md.topics[name].error:
        return
    fs = adm.create_topics([
        NewTopic(name, num_partitions=partitions, replication_factor=rf, config={"min.insync.replicas": "2"})
    ])
    for _, f in fs.items():
        f.result(timeout=15)


def _flink_snapshot(flink_url: str) -> dict[str, Any]:
    jobs = json.loads(urlopen(f"{flink_url}/jobs/overview", timeout=5).read())
    running = [j for j in jobs.get("jobs", []) if j.get("state") == "RUNNING"]
    if not running:
        return {"online": False}
    jid = running[0]["jid"]
    ckpts = json.loads(urlopen(f"{flink_url}/jobs/{jid}/checkpoints", timeout=5).read())
    detail = json.loads(urlopen(f"{flink_url}/jobs/{jid}", timeout=5).read())
    bp_levels: dict[str, str] = {}
    for v in detail.get("vertices", []):
        vid = v["id"]
        bp = json.loads(urlopen(f"{flink_url}/jobs/{jid}/vertices/{vid}/backpressure", timeout=5).read())
        lvl = str(bp.get("backpressureLevel") or "ok")
        if lvl != "ok":
            bp_levels[v.get("name", vid)] = lvl
    counts = ckpts.get("counts") or {}
    latest_dur = (ckpts.get("latest") or {}).get("completed", {}).get("end_to_end_duration")
    return {
        "online": True,
        "job_id": jid,
        "job_name": running[0]["name"],
        "checkpoints_completed": counts.get("completed", 0),
        "checkpoints_failed": counts.get("failed", 0),
        "latest_ckpt_duration_ms": latest_dur,
        "vertices_total": len(detail.get("vertices", [])),
        "non_ok_backpressure_vertices": bp_levels,
    }


def _tier1_broker_and_drain(bootstrap: str, tmp_dir: Path) -> dict[str, Any]:
    """Reproduce Tier 1 broker ingestion & consumer drain measurements on an isolated topic."""
    topic = "pulse.bench.phasej.tier1"
    _ensure_temp_topic(bootstrap, topic, partitions=11, rf=3)
    slots = get_driver_slots()

    # 1. Batch sweep (zstd vs gzip comparison on isolated broker topic)
    sweep_results: dict[str, list[dict[str, Any]]] = {}
    for codec in ("zstd", "gzip"):
        rows = []
        p = Producer({
            "bootstrap.servers": bootstrap,
            "acks": "all",
            "enable.idempotence": True,
            "compression.type": codec,
            "linger.ms": 10,
            "batch.size": 65536,
        })
        for batch_n in (2000, 5000, 8000):
            lats: list[float] = []
            errs = 0
            tot_bytes = 0

            def _cb(err, msg):
                nonlocal errs
                if err is not None:
                    errs += 1

            t0 = time.perf_counter()
            for i in range(batch_n):
                drv = (i % 20) + 1
                part = driver_partition(slots, drv, 11)
                payload = json.dumps({"seq": i, "drv": drv, "speed": 295.4, "pad": "x" * 700}).encode("utf-8")
                tot_bytes += len(payload)
                ts_s = time.perf_counter()
                p.produce(topic, value=payload, key=f"tier1:{drv}", partition=part, callback=_cb)
                lats.append((time.perf_counter() - ts_s) * 1000.0)
                if i % 1000 == 999:
                    p.poll(0)
            p.flush(30)
            dur = time.perf_counter() - t0
            rows.append({
                "batch_size": batch_n,
                "duration_sec": round(dur, 4),
                "msg_per_sec": round(batch_n / max(dur, 1e-6), 1),
                "mb_per_sec": round((tot_bytes / (1024 * 1024)) / max(dur, 1e-6), 2),
                "failed": errs,
            })
        sweep_results[codec] = rows

    # 2. Concurrent 3-session fan-in (3 x 6,000 = 18,000) & consumer backlog drain with IdempotentVerdictSink
    drain_topic = "pulse.bench.phasej.drain"
    _ensure_temp_topic(bootstrap, drain_topic, partitions=11, rf=3)
    p = Producer({
        "bootstrap.servers": bootstrap,
        "acks": "all",
        "enable.idempotence": True,
        "compression.type": "zstd",
        "linger.ms": 10,
        "batch.size": 65536,
    })
    sessions = ["conc-j-1", "conc-j-2", "conc-j-3"]
    part_counts = [0] * 11
    t_fan0 = time.perf_counter()
    for s_idx, sid in enumerate(sessions):
        for i in range(6000):
            drv = (i % 20) + 1
            key = f"{sid}:{drv}"
            part = driver_partition(slots, drv, 11)
            part_counts[part] += 1
            val = json.dumps({"event_id": f"{sid}-{i}", "session": sid, "seq": i}).encode("utf-8")
            p.produce(drain_topic, value=val, key=key.encode("utf-8"), partition=part)
        p.poll(0)
    p.flush(30)
    fan_dur = time.perf_counter() - t_fan0
    skew_ratio = round(max(part_counts) / max(statistics.mean(part_counts), 1.0), 3)

    rss_before = _rss_mb()
    sink = IdempotentVerdictSink(tmp_dir / "tier1_verdicts.sqlite")
    c = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": f"phasej-tier1-drain-{int(time.time())}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "isolation.level": "read_committed",
    })
    try:
        tps = [TopicPartition(drain_topic, pt) for pt in range(11)]
        c.assign(tps)

        consumed = 0
        t_dr0 = time.perf_counter()
        idle = 0
        while consumed < 18000 and idle < 30:
            msgs = c.consume(num_messages=1000, timeout=0.5)
            if not msgs:
                idle += 1
                continue
            idle = 0
            for m in msgs:
                if m.error():
                    continue
                data = json.loads(m.value().decode("utf-8"))
                sink.insert_verdict(m.topic(), m.partition(), m.offset(), m.key().decode("utf-8"), data["event_id"])
                consumed += 1
            c.commit(asynchronous=False)
        drain_dur = time.perf_counter() - t_dr0
        unique_verdicts = sink.count()
    finally:
        c.close()
        sink.close()
    rss_after = _rss_mb()

    return {
        "batch_sweep": sweep_results,
        "concurrent_3session_fan_in_18000": {
            "duration_sec": round(fan_dur, 4),
            "msg_per_sec": round(18000 / max(fan_dur, 1e-6), 1),
            "partition_skew_max_over_mean": skew_ratio,
        },
        "consumer_drain_with_sqlite_sink": {
            "consumed": consumed,
            "unique_verdicts": unique_verdicts,
            "dedup_violations": abs(consumed - unique_verdicts),
            "duration_sec": round(drain_dur, 4),
            "msg_per_sec": round(consumed / max(drain_dur, 1e-6), 1),
            "rss_before_mb": rss_before,
            "rss_after_mb": rss_after,
            "rss_delta_mb": round(rss_after - rss_before, 2),
        },
    }


def _load_sample_envelopes(limit: int = 1200) -> list[dict[str, Any]]:
    """Build representative EventEnvelopes (LAP_COMPLETED, WEATHER, TRACK_STATUS, POSITION) from Silverstone."""
    envs: list[dict[str, Any]] = []
    pos_keep = 0
    with open(r"E:\Caliberv2\captures\f1-2023-silverstone-race\envelopes.jsonl", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            et = obj.get("event_type")
            if et == "POSITION_UPDATE":
                if pos_keep % 10 != 0:
                    continue
                pos_keep += 1
            envs.append(obj)
            if len(envs) >= limit:
                break
    return envs


async def _tier2_sustained_flink_e2e(bootstrap: str, flink_url: str, tmp_dir: Path, duration_sec: float = 35.0) -> dict[str, Any]:
    """Run sustained >=35s 3-session multi-stream E2E through live Kafka -> Flink v3 -> 6 Agents -> SIA WAL -> VerdictSink."""
    os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
    sample_envs = _load_sample_envelopes(1200)
    sessions = [
        ("conc-j-silverstone", f"bench-phasej-silv-{int(time.time())}"),
        ("conc-j-monaco", f"bench-phasej-mon-{int(time.time())}"),
        ("conc-j-suzuka", f"bench-phasej-suz-{int(time.time())}"),
    ]
    run_ids = {rid for _, rid in sessions}

    # Build isolated 6-agent pipeline per concurrent session (no global singleton cross-talk)
    sink_path = tmp_dir / "phasej_e2e_verdicts.sqlite"
    sink = IdempotentVerdictSink(sink_path)
    pipelines: dict[str, dict[str, Any]] = {}
    for sid, _rid in sessions:
        bus = PulseEventBus()
        wal_path = tmp_dir / f"phasej_e2e_sia_{sid}.sqlite"
        store = StateStore()
        agent_ec = EventControlAgent(bus=bus)
        agent_ts = TrackStateAgent(bus=bus)
        agent_vr = VehicleResponseAgent(bus=bus)
        agent_ty = TyreStrategyAgent(bus=bus)
        agent_fu = ConsequenceFusionEngine(bus=bus)
        agent_ia = IntegrityAgent(bus=bus, wal_path=str(wal_path), session_id=sid)
        for a in (agent_ec, agent_ts, agent_vr, agent_ty, agent_fu, agent_ia):
            store.register_agent(a)

        def _make_handler(fu):
            async def _on_finding(_t, k, v):
                await fu.on_finding(_t, k, v)
            return _on_finding

        for at in (
            "pulse.agent.event_context.findings.v1",
            "pulse.agent.track_state.findings.v1",
            "pulse.agent.vehicle_response.findings.v1",
            "pulse.agent.tyre_strategy.findings.v1",
            "pulse.agent.integrity.findings.v1",
        ):
            bus.subscribe(at, _make_handler(agent_fu))
        pipelines[sid] = {
            "bus": bus,
            "wal_path": wal_path,
            "store": store,
            "ec": agent_ec,
            "ts": agent_ts,
            "vr": agent_vr,
            "ty": agent_ty,
            "fu": agent_fu,
            "ia": agent_ia,
        }

    async def _dispatch_norm(sid: str, topic: str, key: str, env: EventEnvelope) -> None:
        p = pipelines[sid]
        p["store"].record_canonical_event(env)
        if topic == NORMALISED_TOPICS["race_events"]:
            await p["ec"].on_event(topic, key, env)
            await p["ts"].on_event(topic, key, env)
            await p["ty"].on_event(topic, key, env)
            await p["ia"].on_event(topic, key, env)
        elif topic == NORMALISED_TOPICS["driver_laps"]:
            await p["vr"].on_event(topic, key, env)
            await p["ia"].on_event(topic, key, env)
        elif topic == NORMALISED_TOPICS["driver_state"]:
            await p["vr"].on_event(topic, key, env)
            await p["ty"].on_event(topic, key, env)
            await p["ia"].on_event(topic, key, env)
        elif topic == NORMALISED_TOPICS["track_segments"]:
            await p["ts"].on_event(topic, key, env)
            await p["ia"].on_event(topic, key, env)
        elif topic == NORMALISED_TOPICS["tyre_stints"]:
            await p["ty"].on_event(topic, key, env)
            await p["ia"].on_event(topic, key, env)

    norm_topics = list(NORMALISED_TOPICS.values())
    group_id = f"pulse-phasej-sustained-e2e-{int(time.time())}"
    cons = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
        "isolation.level": "read_committed",
    })
    # Assign all partitions explicitly at high-watermark and seed initial committed offsets so crash recovery never rewinds past t=0
    norm_tps: list[TopicPartition] = []
    md = cons.list_topics(timeout=10)
    for t in norm_topics:
        for pid in md.topics[t].partitions:
            _, hi = cons.get_watermark_offsets(TopicPartition(t, pid), timeout=5)
            norm_tps.append(TopicPartition(t, pid, hi))
    cons.assign(norm_tps)
    cons.commit(offsets=norm_tps, asynchronous=False)

    prod = Producer({
        "bootstrap.servers": bootstrap,
        "acks": "all",
        "enable.idempotence": True,
        "compression.type": "gzip",
        "linger.ms": 5,
    })

    flink_before = _flink_snapshot(flink_url)
    rss_start = _rss_mb()
    rss_samples = [rss_start]
    lag_samples: list[int] = []
    sent_count = 0
    processed_count = 0
    per_session_processed = {sid: 0 for sid, _ in sessions}
    e2e_latencies_ms: list[float] = []
    crash_tested = False
    pre_crash_processed = 0

    # Build partitioned topics & query partition counts (track/session raw topics have 1, driver topics have 11)
    raw_part_counts = {
        t: len(md.topics[t].partitions)
        for t in md.topics
        if t.startswith("pulse.raw.")
    }
    slots = get_driver_slots()
    stop_prod = False
    prod_err: list[Exception] = []
    target_rate_per_sec = 120.0
    base_event_dt = datetime(2026, 7, 1, 14, 0, 0, tzinfo=UTC)

    import threading

    def _producer_worker() -> None:
        nonlocal sent_count
        seq_local = 0
        t0_p = time.perf_counter()
        try:
            while not stop_prod and (time.perf_counter() - t0_p) < duration_sec:
                # Pace 3-session concurrent bursts smoothly at ~target_rate_per_sec (6 msgs/tick every ~50ms)
                for s_idx, (sid, rid) in enumerate(sessions):
                    for k in range(2):
                        tmpl = sample_envs[(seq_local * 2 + k + s_idx * 37) % len(sample_envs)]
                        ev = json.loads(json.dumps(tmpl))
                        ev["event_id"] = f"pj|{sid}|{seq_local}|{k}|{time.time():.6f}"
                        ev["run"] = {**ev["run"], "run_id": rid, "session_instance_id": sid}
                        ev["session"] = {**ev["session"], "session_id": sid}
                        ev_dt = (base_event_dt + timedelta(milliseconds=(seq_local * 2 + k) * 50)).isoformat()
                        ev["time"] = {
                            **ev.get("time", {}),
                            "event_time_utc": ev_dt,
                            "ingest_time_utc": ev_dt,
                            "session_elapsed_ms": (seq_local * 2 + k) * 50,
                        }
                        raw_t = raw_topic_for_event(ev["event_type"])
                        subj_drv = (ev.get("subject") or {}).get("driver_number")
                        rk = routing_key(sid, subj_drv, (ev.get("subject") or {}).get("segment_id"))
                        n_parts = raw_part_counts.get(raw_t, 1)
                        part = driver_partition(slots, subj_drv if subj_drv is not None else rk, n_parts)
                        prod.produce(raw_t, value=json.dumps(ev).encode("utf-8"), key=rk.encode("utf-8"), partition=part)
                        sent_count += 1
                prod.poll(0)
                seq_local += 1
                desired_t = t0_p + (sent_count / target_rate_per_sec)
                sleep_for = desired_t - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
            prod.flush(15)
        except Exception as exc:
            prod_err.append(exc)

    prod_thread = threading.Thread(target=_producer_worker, daemon=True)
    t_start = time.perf_counter()
    prod_thread.start()
    next_sample_t = t_start + 5.0

    try:
        # Phase A: Consume Flink-normalized stream while concurrent 3-session producer streams over duration_sec
        while prod_thread.is_alive():
            now = time.perf_counter()
            elapsed = now - t_start

            batch = cons.consume(num_messages=300, timeout=0.05)
            if batch:
                for msg in batch:
                    if msg.error() or msg.value() is None:
                        continue
                    val = json.loads(msg.value().decode("utf-8"))
                    rb = val.get("run") or {}
                    if rb.get("run_id") not in run_ids:
                        continue
                    if sink.has_verdict(msg.topic(), msg.partition(), msg.offset()):
                        continue
                    env = EventEnvelope.model_validate(val)
                    sid_msg = rb.get("session_instance_id")
                    key_s = msg.key().decode("utf-8") if msg.key() else ""
                    await _dispatch_norm(sid_msg, msg.topic(), key_s, env)
                    sink.insert_verdict(msg.topic(), msg.partition(), msg.offset(), key_s, env.event_id)
                    processed_count += 1
                    per_session_processed[sid_msg] += 1
                    try:
                        sent_ep = float(str(env.event_id).rsplit("|", 1)[-1])
                        e2e_latencies_ms.append((time.time() - sent_ep) * 1000.0)
                    except Exception:
                        pass
                cons.commit(asynchronous=False)

            # Simulate consumer crash + restart recovery mid-run (~18s in) while producer & Flink continue
            if (not crash_tested) and elapsed >= duration_sec * 0.5 and processed_count > 100:
                crash_tested = True
                pre_crash_processed = processed_count
                cons.close()
                cons = Consumer({
                    "bootstrap.servers": bootstrap,
                    "group.id": group_id,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                    "isolation.level": "read_committed",
                })
                cons.assign([TopicPartition(tp.topic, tp.partition) for tp in norm_tps])

            if now >= next_sample_t:
                rss_samples.append(_rss_mb())
                tot_lag = 0
                for tp in norm_tps:
                    c_pos = cons.position([tp])[0].offset
                    _, hi = cons.get_watermark_offsets(tp, timeout=1)
                    if c_pos >= 0 and hi >= c_pos:
                        tot_lag += (hi - c_pos)
                lag_samples.append(tot_lag)
                next_sample_t += 5.0
            await asyncio.sleep(0.005)

        prod_thread.join(timeout=20)
        if prod_err:
            raise prod_err[0]

        # Phase B: Drain remaining in-flight Flink-normalized records down to zero lag
        t_drain0 = time.perf_counter()
        quiet = 0
        while processed_count < sent_count and quiet < 15 and (time.perf_counter() - t_drain0) < 35.0:
            batch = cons.consume(num_messages=300, timeout=0.2)
            if not batch:
                quiet += 1
                continue
            quiet = 0
            for msg in batch:
                if msg.error() or msg.value() is None:
                    continue
                val = json.loads(msg.value().decode("utf-8"))
                rb = val.get("run") or {}
                if rb.get("run_id") not in run_ids:
                    continue
                if sink.has_verdict(msg.topic(), msg.partition(), msg.offset()):
                    continue
                env = EventEnvelope.model_validate(val)
                sid_msg = rb.get("session_instance_id")
                key_s = msg.key().decode("utf-8") if msg.key() else ""
                await _dispatch_norm(sid_msg, msg.topic(), key_s, env)
                sink.insert_verdict(msg.topic(), msg.partition(), msg.offset(), key_s, env.event_id)
                processed_count += 1
                per_session_processed[sid_msg] += 1
                try:
                    sent_ep = float(str(env.event_id).rsplit("|", 1)[-1])
                    e2e_latencies_ms.append((time.time() - sent_ep) * 1000.0)
                except Exception:
                    pass
            cons.commit(asynchronous=False)

        total_wall = time.perf_counter() - t_start
        final_lag = 0
        for tp in norm_tps:
            c_pos = cons.position([tp])[0].offset
            _, hi = cons.get_watermark_offsets(tp, timeout=2)
            if c_pos >= 0 and hi >= c_pos:
                final_lag += (hi - c_pos)
    finally:
        stop_prod = True
        if prod_thread.is_alive():
            prod_thread.join(timeout=5)
        cons.close()
        prod.flush(5)

    flink_after = _flink_snapshot(flink_url)
    tot_decisions = 0
    sia_mismatches = 0
    try:
        for sid, p in pipelines.items():
            if getattr(p["ia"], "_wal", None) is not None:
                p["ia"]._wal.sync_engine(p["ia"].engine)
            v_res = p["ia"].engine.verify()
            tot_decisions += len(v_res)
            sia_mismatches += sum(1 for v in v_res.values() if v != "OK")
    finally:
        for p in pipelines.values():
            p["ia"].close()
        verdict_rows = sink.count()
        sink.close()
    gc.collect()
    rss_end = _rss_mb()

    # Verify WAL + engine reload post-process restart across all 3 session WALs
    reload_decisions = 0
    reload_mismatches = 0
    for sid, p in pipelines.items():
        ia_rel = IntegrityAgent(wal_path=str(p["wal_path"]), session_id=sid)
        ok_rel = ia_rel.restore_from_wal()
        assert ok_rel, f"WAL restore failed for {sid}"
        rel_v = ia_rel.engine.verify()
        reload_decisions += len(rel_v)
        reload_mismatches += sum(1 for v in rel_v.values() if v != "OK")
        ia_rel.close()

    e2e_sorted = sorted(e2e_latencies_ms)
    return {
        "sustained_duration_sec": round(total_wall, 3),
        "concurrent_sessions": [sid for sid, _ in sessions],
        "raw_events_published": sent_count,
        "flink_normalized_e2e_processed": processed_count,
        "sqlite_verdict_rows": verdict_rows,
        "per_session_processed": per_session_processed,
        "mid_stream_consumer_restart_tested": crash_tested,
        "processed_before_restart": pre_crash_processed,
        "complete_e2e_analytics_throughput_ev_per_sec": round(processed_count / max(total_wall, 1e-6), 2),
        "e2e_latency_ms": {
            "p50": round(statistics.median(e2e_sorted), 1) if e2e_sorted else None,
            "p95": round(e2e_sorted[min(int(0.95 * len(e2e_sorted)), len(e2e_sorted) - 1)], 1) if e2e_sorted else None,
            "max": round(e2e_sorted[-1], 1) if e2e_sorted else None,
        },
        "lag_samples": lag_samples,
        "final_consumer_lag": final_lag,
        "memory_rss_mb": {
            "start": rss_start,
            "peak": max(rss_samples + [rss_end]),
            "end_after_gc": rss_end,
            "growth_mb": round(rss_end - rss_start, 2),
        },
        "flink_health": {
            "checkpoints_before": flink_before.get("checkpoints_completed"),
            "checkpoints_after": flink_after.get("checkpoints_completed"),
            "checkpoints_failed_after": flink_after.get("checkpoints_failed"),
            "latest_ckpt_duration_ms": flink_after.get("latest_ckpt_duration_ms"),
            "non_ok_backpressure_vertices": flink_after.get("non_ok_backpressure_vertices"),
        },
        "sia_consistency": {
            "decisions": tot_decisions,
            "hash_mismatches": sia_mismatches,
            "wal_reloaded_decisions": reload_decisions,
            "wal_reloaded_mismatches": reload_mismatches,
        },
    }


def main() -> None:
    bootstrap = os.environ.get("PULSE_KAFKA_BOOTSTRAP_SERVERS", "localhost:19092,localhost:19093,localhost:19094")
    flink_url = os.environ.get("PULSE_FLINK_REST_URL", "http://127.0.0.1:8081")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print("Running Tier 1: isolated Kafka broker throughput + drain benchmark...", flush=True)
        tier1 = _tier1_broker_and_drain(bootstrap, tmp_path)
        print("Running Tier 2: 35s sustained 3-session Flink v3 + 6-agent + SIA WAL E2E benchmark...", flush=True)
        tier2 = asyncio.run(_tier2_sustained_flink_e2e(bootstrap, flink_url, tmp_path, duration_sec=35.0))

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "tier1_broker_and_direct_consumer": tier1,
        "tier2_sustained_flink_6agent_sia_e2e": tier2,
    }
    out_path = Path(__file__).resolve().parent.parent / "reports" / "benchmarks" / "phase_j_kafka_sustained.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
