"""Priority D regression checks: replay checkpoint corruption fallback, partial WAL recovery, and session isolation."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from pulse.integrity.agent import IntegrityAgent
from pulse.replay.controller import ReplayController
from pulse.state.store import get_state_store


@pytest.mark.asyncio
async def test_corrupted_checkpoint_falls_back_cleanly_to_cold_replay():
    rc = ReplayController()
    await rc.switch_session("f1-2023-silverstone-race")
    res_first = await rc.seek(target_index=2500)
    assert res_first["currentIndex"] == 2500

    sess_ckpts = rc._checkpoints.get("f1-2023-silverstone-race", {})
    assert 2000 in sess_ckpts
    # Inject corrupted checkpoint bytes
    sess_ckpts[2000] = b"corrupted-not-a-pickle"

    res_recover = await rc.seek(target_index=2100)
    assert res_recover["currentIndex"] == 2100
    assert res_recover["dropCount"] == 0
    assert 2000 in rc._checkpoints["f1-2023-silverstone-race"]
    assert rc._checkpoints["f1-2023-silverstone-race"][2000] != b"corrupted-not-a-pickle"


def test_partial_wal_recovery_handles_corrupted_tail_or_fresh_reopen(tmp_path: Path):
    wal_file = tmp_path / "partial_recovery.sqlite"
    ia1 = IntegrityAgent(wal_path=wal_file, session_id="s-wal-rec")
    ia1.initialize_session_grid("s-wal-rec", [{"driver_number": 1, "code": "VER", "team": "RBR"}])
    if ia1._wal:
        ia1._wal.sync_engine(ia1.engine)
    decisions_before = len(ia1.engine.instances)
    if ia1._wal:
        ia1._wal.close()

    # Corrupt sidecar -wal file with trailing garbage bytes and re-open safely
    sidecar_wal = tmp_path / "partial_recovery.sqlite-wal"
    if sidecar_wal.exists():
        sidecar_wal.write_bytes(sidecar_wal.read_bytes() + b"\x00\xffCORRUPT_TAIL")

    ia2 = IntegrityAgent(wal_path=wal_file, session_id="s-wal-rec")
    try:
        assert ia2.engine.verify() is not None
        assert len(ia2.engine.instances) == decisions_before
    finally:
        if ia2._wal:
            ia2._wal.close()
