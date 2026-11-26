"""Reproducible Priority D multi-trial replay benchmark (cold vs cached, random/seq seeks, session switches)."""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path


def _summarize(vals: list[float]) -> dict[str, float]:
    s = sorted(vals)
    return {
        "n": len(s),
        "mean_sec": round(statistics.mean(s), 4),
        "std_sec": round(statistics.stdev(s), 4) if len(s) > 1 else 0.0,
        "min_sec": round(s[0], 4),
        "p50_sec": round(statistics.median(s), 4),
        "p95_sec": round(s[min(int(0.95 * len(s)), len(s) - 1)], 4),
        "max_sec": round(s[-1], 4),
    }


def _run_cold_trial() -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve().parent / "profile_cold_seek.py"), "--mode", "clean"]
    env = dict(os.environ)
    env["PYTHONPATH"] = r"E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
    start = proc.stdout.find("{")
    return json.loads(proc.stdout[start:])


async def _run_cached_and_session_benchmarks() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
        os.environ["PULSE_SIA_WAL_PATH"] = str(Path(tmp) / "bench_replay_sia.sqlite")

        from pulse.main import create_app, lifespan
        from pulse.replay.controller import get_replay_controller
        from pulse.state.store import get_state_store

        app = create_app()
        async with lifespan(app):
            rc = get_replay_controller()
            store = get_state_store()
            ia = store.agents.get("agent-06-integrity")
            try:
                await rc.switch_session("f1-2023-silverstone-race")
                # Build warm keyframes up to 48000
                t_warm = time.perf_counter()
                await rc.seek(target_index=48000)
                warm_build_s = round(time.perf_counter() - t_warm, 4)

                # Capture ground-truth decision hashes at 24000 via sequential rewind vs cached seek
                cached_random_times = []
                for idx in [12000, 36000, 6000, 44000, 24000, 18000]:
                    t0 = time.perf_counter()
                    await rc.seek(target_index=idx)
                    cached_random_times.append(time.perf_counter() - t0)

                sequential_step_times = []
                for idx in [24250, 24500, 24750, 25000, 25250]:
                    t0 = time.perf_counter()
                    await rc.seek(target_index=idx)
                    sequential_step_times.append(time.perf_counter() - t0)

                verify_status = ia.engine.verify() if ia else {}
                mismatches = sum(1 for v in verify_status.values() if v != "OK")

                # Session switching benchmark
                switch_times = []
                for sid in ["f1-2026-monaco-sim", "f1-2026-suzuka-race", "f1-2023-silverstone-race"]:
                    t0 = time.perf_counter()
                    await rc.switch_session(sid)
                    await rc.seek(target_index=4500)
                    switch_times.append(time.perf_counter() - t0)

                return {
                    "warm_build_48000_sec": warm_build_s,
                    "cached_random_seeks": _summarize(cached_random_times),
                    "sequential_step_seeks": _summarize(sequential_step_times),
                    "session_switch_and_seek_4500": _summarize(switch_times),
                    "sia_decisions_verified": len(verify_status),
                    "sia_hash_mismatches": mismatches,
                }
            finally:
                wal_obj = getattr(ia, "_wal", None) or getattr(ia, "wal", None)
                if wal_obj:
                    wal_obj.close()


def main() -> None:
    print("Running 5 isolated subprocess cold seek(36321) trials...")
    cold_trials = []
    for i in range(5):
        out = _run_cold_trial()
        cold_trials.append(out["cold_seek_sec"])
        print(f"  Cold trial {i + 1}/5: {out['cold_seek_sec']}s (decisions={out['sia_decisions']}, mismatches={out['sia_hash_mismatches']})")

    print("Running warm keyframe random/sequential seeks & session switch benchmarks...")
    warm_stats = asyncio.run(_run_cached_and_session_benchmarks())

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "session": "f1-2023-silverstone-race",
        "cold_target_index": 36321,
        "legacy_baseline_cold_sec": [83.8, 87.5],
        "phase_i_cold_seek_trials": _summarize(cold_trials),
        "phase_i_cold_trials_raw_sec": cold_trials,
        **warm_stats,
    }
    out_path = Path(__file__).resolve().parent.parent / "reports" / "benchmarks" / "phase_i_replay_benchmarks.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
