"""Phase J Release Replay Performance & Boundary Decomposition Benchmark.

Reconciles isolated cold-seek boundaries cleanly:
- Process startup & FastAPI create_app()
- Default session JSONL load + WAL restoration
- switch_session cold 83MB envelopes.jsonl load
- Replay reconstruction (domain-only ablation vs full SIA + WAL sync)
- Isolated cold trials, random/warm seeks, checkpoint equivalence, restart recovery
- Real Uvicorn HTTP POST /api/replay/seek round-trip timing
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.request import Request, urlopen


def _stats(vals: list[float]) -> dict[str, float]:
    s = sorted(vals)
    return {
        "n": len(s),
        "mean_sec": round(statistics.mean(s), 4),
        "std_sec": round(statistics.stdev(s), 4) if len(s) > 1 else 0.0,
        "min_sec": round(s[0], 4),
        "p50_sec": round(statistics.median(s), 4),
        "max_sec": round(s[-1], 4),
    }


async def _worker_single_cold(target_index: int, wal_dir: str, *, disable_sia: bool = False) -> dict[str, Any]:
    t_proc0 = time.perf_counter()
    os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
    wal_file = Path(wal_dir) / "sia_bench.sqlite"
    os.environ["PULSE_SIA_WAL_PATH"] = str(wal_file)

    t_imp0 = time.perf_counter()
    from pulse.main import create_app, lifespan
    from pulse.replay.controller import get_replay_controller
    from pulse.state.store import get_state_store

    app = create_app()
    startup_import_sec = time.perf_counter() - t_imp0

    t_life0 = time.perf_counter()
    async with lifespan(app):
        lifespan_default_load_sec = time.perf_counter() - t_life0
        rc = get_replay_controller()
        store = get_state_store()
        ia = store.agents.get("agent-06-integrity")
        try:
            t_sw0 = time.perf_counter()
            await rc.switch_session("f1-2023-silverstone-race")
            switch_load_sec = time.perf_counter() - t_sw0

            if disable_sia and ia is not None:
                # Ablation measurement ONLY: measure projection + 5 domain agents excluding SIA evaluation
                async def _noop(*args, **kwargs):
                    return None
                ia.on_event = _noop  # type: ignore[method-assign]

            t_seek0 = time.perf_counter()
            res_cold = await rc.seek(target_index=target_index)
            cold_seek_sec = time.perf_counter() - t_seek0

            # Measure cached backward & forward seeks while checkpoints are warm
            t_wb = time.perf_counter()
            await rc.seek(target_index=min(18000, target_index))
            warm_back_sec = time.perf_counter() - t_wb

            t_wf = time.perf_counter()
            await rc.seek(target_index=min(target_index + 179, res_cold["totalEvents"]))
            warm_fwd_sec = time.perf_counter() - t_wf

            t_ret = time.perf_counter()
            res_exact = await rc.seek(target_index=target_index)
            warm_exact_sec = time.perf_counter() - t_ret

            hashes = {}
            verify_status = {}
            if ia is not None and not disable_sia:
                verify_status = ia.engine.verify()
                for iid in sorted(ia.engine.instances):
                    ch = ia.engine.history(iid)
                    if ch:
                        hashes[iid] = ch[-1].record_hash

            mismatches = sum(1 for v in verify_status.values() if v != "OK")
            return {
                "target_index": target_index,
                "disable_sia": disable_sia,
                "startup_import_sec": round(startup_import_sec, 4),
                "lifespan_default_load_sec": round(lifespan_default_load_sec, 4),
                "switch_load_silverstone_sec": round(switch_load_sec, 4),
                "cold_seek_sec": round(cold_seek_sec, 4),
                "warm_backward_18000_sec": round(warm_back_sec, 4),
                "warm_forward_179_sec": round(warm_fwd_sec, 4),
                "warm_exact_checkpoint_sec": round(warm_exact_sec, 4),
                "checkpoints_count": len(rc._checkpoints.get("f1-2023-silverstone-race", {})),
                "sia_decisions": len(verify_status),
                "sia_hash_mismatches": mismatches,
                "decision_hashes_digest": hash(tuple(sorted(hashes.items()))),
                "decision_hashes_count": len(hashes),
                "total_wall_sec": round(time.perf_counter() - t_proc0, 4),
                "wal_bytes": wal_file.stat().st_size if wal_file.exists() else 0,
                "hashes": hashes if target_index <= 36321 else {},
            }
        finally:
            if ia is not None and getattr(ia, "_wal", None) is not None:
                ia._wal.close()


async def _worker_wal_restart_recovery(wal_dir: str) -> dict[str, Any]:
    """Measure process restart WAL restoration time & hash preservation on a populated SQLite WAL."""
    os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
    wal_file = Path(wal_dir) / "sia_bench.sqlite"
    os.environ["PULSE_SIA_WAL_PATH"] = str(wal_file)

    t0 = time.perf_counter()
    from pulse.integrity.agent import IntegrityAgent
    ia = IntegrityAgent(wal_path=wal_file, session_id="f1-2023-silverstone-race")
    restored_ok = ia.restore_from_wal()
    restore_sec = time.perf_counter() - t0
    try:
        verify_status = ia.engine.verify()
        mismatches = sum(1 for v in verify_status.values() if v != "OK")
        hashes = {}
        for iid in sorted(ia.engine.instances):
            ch = ia.engine.history(iid)
            if ch:
                hashes[iid] = ch[-1].record_hash
        return {
            "wal_restored_ok": restored_ok,
            "wal_restart_restore_sec": round(restore_sec, 4),
            "restored_decisions": len(verify_status),
            "restored_ledger_counts": ia.engine.ledger.counts(),
            "restored_hash_mismatches": mismatches,
            "hashes": hashes,
        }
    finally:
        if getattr(ia, "_wal", None) is not None:
            ia._wal.close()


def _run_subproc(args_list: list[str]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = r"E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
    proc = subprocess.run(
        [sys.executable, __file__, *args_list],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    marker = "JSON_OUTPUT:"
    pos = proc.stdout.rfind(marker)
    return json.loads(proc.stdout[pos + len(marker):])


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 150.0) -> tuple[float, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = Request(url, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    with urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return time.perf_counter() - t0, body


def _measure_http_boundaries() -> dict[str, Any]:
    port = _free_port()
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["PYTHONPATH"] = r"E:\Caliberv2;E:\Caliberv2\backend;E:\Caliberv2\sia_core_v3"
        env["PULSE_TRANSPORT_MODE"] = "MEMORY"
        env["PULSE_SIA_WAL_PATH"] = str(Path(tmp) / "http_sia.sqlite")
        env["PULSE_API_KEY"] = ""
        env["PULSE_REQUIRE_CONTROL_AUTH"] = "false"

        log_file = Path(tmp) / "uvicorn.log"
        log_handle = open(log_file, "w", encoding="utf-8")
        t_srv0 = time.perf_counter()
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "pulse.main:app", "--host", "127.0.0.1", "--port", str(port)],
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            health_url = f"http://127.0.0.1:{port}/api/health"
            while time.perf_counter() - t_srv0 < 45.0:
                try:
                    _, h = _http_json("GET", health_url, timeout=2.0)
                    if h.get("status"):
                        break
                except Exception:
                    time.sleep(0.25)
            http_ready_sec = round(time.perf_counter() - t_srv0, 4)

            sw_sec, _ = _http_json("POST", f"http://127.0.0.1:{port}/api/sessions/select", {"session_id": "f1-2023-silverstone-race"})
            seek_4500_sec, _ = _http_json("POST", f"http://127.0.0.1:{port}/api/replay/seek", {"target_index": 4500})
            seek_cold_36321_sec, s_res = _http_json("POST", f"http://127.0.0.1:{port}/api/replay/seek", {"target_index": 36321})
            seek_warm_18000_sec, _ = _http_json("POST", f"http://127.0.0.1:{port}/api/replay/seek", {"target_index": 18000})
            return {
                "uvicorn_ready_sec": http_ready_sec,
                "http_switch_silverstone_sec": round(sw_sec, 4),
                "http_cold_seek_4500_sec": round(seek_4500_sec, 4),
                "http_seek_from_4500_to_36321_sec": round(seek_cold_36321_sec, 4),
                "http_warm_seek_18000_sec": round(seek_warm_18000_sec, 4),
                "target_index_verified": s_res.get("currentIndex"),
            }
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
            log_handle.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=["cold", "restart"], default=None)
    parser.add_argument("--target", type=int, default=36321)
    parser.add_argument("--wal-dir", type=str, default="")
    parser.add_argument("--disable-sia", action="store_true")
    parser.add_argument("--http-only", action="store_true")
    args = parser.parse_args()

    if args.http_only:
        print(json.dumps(_measure_http_boundaries(), indent=2))
        return

    if args.worker == "cold":
        res = asyncio.run(_worker_single_cold(args.target, args.wal_dir, disable_sia=args.disable_sia))
        print("JSON_OUTPUT:" + json.dumps(res))
        return
    if args.worker == "restart":
        res = asyncio.run(_worker_wal_restart_recovery(args.wal_dir))
        print("JSON_OUTPUT:" + json.dumps(res))
        return

    print("Running 3 isolated cold seek(36321) trials + WAL restart verification...")
    cold_trials = []
    ref_hashes = None
    with tempfile.TemporaryDirectory() as shared_wal_dir:
        for i in range(3):
            if i == 0:
                out = _run_subproc(["--worker", "cold", "--target", "36321", "--wal-dir", shared_wal_dir])
            else:
                with tempfile.TemporaryDirectory() as tmp_wdir:
                    out = _run_subproc(["--worker", "cold", "--target", "36321", "--wal-dir", tmp_wdir])
            hashes = out.pop("hashes", {})
            if i == 0:
                ref_hashes = hashes
            else:
                assert hashes == ref_hashes, f"Hash mismatch across independent cold trial {i}"
            cold_trials.append(out)
            print(f"  Trial {i+1}/3: cold_seek={out['cold_seek_sec']}s, switch={out['switch_load_silverstone_sec']}s, warm_18k={out['warm_backward_18000_sec']}s, decisions={out['sia_decisions']}, mismatches={out['sia_hash_mismatches']}", flush=True)

        restart_res = _run_subproc(["--worker", "restart", "--wal-dir", shared_wal_dir])
        restored_hashes = restart_res.pop("hashes", {})
        exact_wal_match = (restored_hashes == ref_hashes)
        restart_res["exact_hash_match_with_cold_seek"] = exact_wal_match
        print(f"  WAL restart restore: {restart_res['wal_restart_restore_sec']}s, decisions={restart_res['restored_decisions']}, exact_hash_match={exact_wal_match}", flush=True)

    print("Running no-SIA replay ablation & random-position cold seeks (4500, 18000)...", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        no_sia = _run_subproc(["--worker", "cold", "--target", "36321", "--wal-dir", tmp, "--disable-sia"])
        no_sia.pop("hashes", None)
    print(f"  no-SIA replay seek(36321): {no_sia['cold_seek_sec']}s", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        seek_4500 = _run_subproc(["--worker", "cold", "--target", "4500", "--wal-dir", tmp])
        seek_4500.pop("hashes", None)
    print(f"  cold seek(4500): {seek_4500['cold_seek_sec']}s", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        seek_18000 = _run_subproc(["--worker", "cold", "--target", "18000", "--wal-dir", tmp])
        seek_18000.pop("hashes", None)
    print(f"  cold seek(18000): {seek_18000['cold_seek_sec']}s", flush=True)

    print("Measuring real Uvicorn HTTP round-trip boundaries...", flush=True)
    http_res = _measure_http_boundaries()

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dataset": "f1-2023-silverstone-race",
        "total_events": 72642,
        "isolated_cold_seek_36321_stats": _stats([t["cold_seek_sec"] for t in cold_trials]),
        "isolated_cold_seek_36321_trials": cold_trials,
        "boundary_decomposition_36321": {
            "startup_import_sec_mean": round(statistics.mean(t["startup_import_sec"] for t in cold_trials), 4),
            "lifespan_default_monaco_load_sec_mean": round(statistics.mean(t["lifespan_default_load_sec"] for t in cold_trials), 4),
            "switch_load_silverstone_jsonl_sec_mean": round(statistics.mean(t["switch_load_silverstone_sec"] for t in cold_trials), 4),
            "replay_domain_only_no_sia_sec": no_sia["cold_seek_sec"],
            "full_replay_with_sia_and_wal_sync_sec_mean": round(statistics.mean(t["cold_seek_sec"] for t in cold_trials), 4),
            "sia_plus_wal_sync_attributed_sec": round(statistics.mean(t["cold_seek_sec"] for t in cold_trials) - no_sia["cold_seek_sec"], 4),
            "sia_share_pct": round(100.0 * (statistics.mean(t["cold_seek_sec"] for t in cold_trials) - no_sia["cold_seek_sec"]) / statistics.mean(t["cold_seek_sec"] for t in cold_trials), 2),
        },
        "position_scaling_cold_seeks": {
            "target_4500": {"cold_seek_sec": seek_4500["cold_seek_sec"], "sia_decisions": seek_4500["sia_decisions"]},
            "target_18000": {"cold_seek_sec": seek_18000["cold_seek_sec"], "sia_decisions": seek_18000["sia_decisions"]},
            "target_36321_mean": round(statistics.mean(t["cold_seek_sec"] for t in cold_trials), 4),
        },
        "warm_keyframe_seeks_36321_stats": {
            "backward_18000": _stats([t["warm_backward_18000_sec"] for t in cold_trials]),
            "forward_179": _stats([t["warm_forward_179_sec"] for t in cold_trials]),
            "exact_checkpoint_hit": _stats([t["warm_exact_checkpoint_sec"] for t in cold_trials]),
        },
        "process_restart_wal_recovery": restart_res,
        "http_uvicorn_roundtrip": http_res,
    }
    out_path = Path(__file__).resolve().parent.parent / "reports" / "benchmarks" / "phase_j_replay_benchmarks.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "isolated_cold_seek_36321_trials"}, indent=2))


if __name__ == "__main__":
    main()
