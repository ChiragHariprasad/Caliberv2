"""Profile truly cold seek(36321) vs cached seeks in isolated cold subprocesses (zero singleton reuse)."""
from __future__ import annotations

import argparse
import asyncio
import cProfile
import json
import os
import pstats
import tempfile
import time
from io import StringIO
from pathlib import Path


async def _measure_once(*, profile: bool = False, seek_target: int = 36321) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
        os.environ["PULSE_SIA_WAL_PATH"] = str(Path(tmp) / "profile_sia.sqlite")

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

                pr = cProfile.Profile() if profile else None
                if pr:
                    pr.enable()
                t0 = time.perf_counter()
                res_cold = await rc.seek(target_index=seek_target)
                cold_s = time.perf_counter() - t0
                if pr:
                    pr.disable()

                t1 = time.perf_counter()
                await rc.seek(target_index=18000)
                cached_back_s = time.perf_counter() - t1

                t2 = time.perf_counter()
                await rc.seek(target_index=seek_target + 179)
                cached_fwd_s = time.perf_counter() - t2

                verify_status = ia.engine.verify() if ia else {}
                mismatches = sum(1 for v in verify_status.values() if v != "OK")

                top_tottime = ""
                top_cumtime = ""
                if pr:
                    s1 = StringIO()
                    pstats.Stats(pr, stream=s1).strip_dirs().sort_stats("tottime").print_stats(30)
                    top_tottime = s1.getvalue()
                    s2 = StringIO()
                    pstats.Stats(pr, stream=s2).strip_dirs().sort_stats("cumtime").print_stats(30)
                    top_cumtime = s2.getvalue()

                return {
                    "cold_seek_sec": round(cold_s, 4),
                    "cached_seek_18000_sec": round(cached_back_s, 4),
                    "cached_seek_fwd_sec": round(cached_fwd_s, 4),
                    "checkpoints_count": len(getattr(rc, "_checkpoints", {})),
                    "sia_decisions": len(verify_status),
                    "sia_hash_mismatches": mismatches,
                    "seek_result": res_cold,
                    "cprofile_tottime": top_tottime,
                    "cprofile_cumtime": top_cumtime,
                }
            finally:
                wal_obj = getattr(ia, "_wal", None) or getattr(ia, "wal", None)
                if wal_obj:
                    wal_obj.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["clean", "profile"], default="profile")
    args = parser.parse_args()

    res = asyncio.run(_measure_once(profile=(args.mode == "profile")))
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("cprofile")}, indent=2, default=str))
    if args.mode == "profile":
        print("\n--- TOP 30 TOTTIME ---")
        print(res["cprofile_tottime"])
        print("\n--- TOP 30 CUMTIME ---")
        print(res["cprofile_cumtime"])


if __name__ == "__main__":
    main()
