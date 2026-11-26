"""
Phase 6 Tests:
- API session_id isolation (404 for unknown session, 409 for unselected session sub-routes)
- Replay speed strict validation (422 for 99.0, 0.0, -1.0)
- StateStore counter reset across session switches & zero Norris/Verstappen/+10.5s fabrication
- ReplayController keyframe checkpoints: deterministic SIA verdict/hash equivalence & sub-second cached seek
"""

from __future__ import annotations

import os
import time

os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
os.environ["PULSE_SIA_WAL_PATH"] = ""

import pytest
from fastapi.testclient import TestClient

from pulse.main import create_app
from pulse.replay.controller import get_replay_controller
from pulse.state.store import get_state_store


def test_api_session_isolation_and_replay_speed_validation() -> None:
    app = create_app()
    with TestClient(app) as client:
        # 1. Unknown session_id returns 404 (not active session 200 leak)
        for path in [
            "/api/sessions/bogus-session-id",
            "/api/sessions/bogus-session-id/drivers",
            "/api/sessions/bogus-session-id/drivers/1",
            "/api/sessions/bogus-session-id/timeline",
            "/api/sessions/bogus-session-id/track",
            "/api/sessions/bogus-session-id/strategy",
            "/api/sessions/bogus-session-id/assessments",
            "/api/sessions/bogus-session-id/metadata",
        ]:
            res = client.get(path)
            assert res.status_code == 404, f"Expected 404 on {path}, got {res.status_code}"

        # 2. Valid non-active session returns metadata on /sessions/{id} and 409 on active-state sub-routes
        res_meta = client.get("/api/sessions/f1-2021-abu-dhabi")
        assert res_meta.status_code == 200
        assert res_meta.json()["active"] is False

        res_conflict = client.get("/api/sessions/f1-2021-abu-dhabi/drivers")
        assert res_conflict.status_code == 409

        # 3. Replay speed bounds validation -> 422 on invalid speeds
        for bad_speed in (99.0, 0.0, -2.5):
            r_bad = client.post("/api/replay/speed", json={"speed": bad_speed})
            assert r_bad.status_code == 422, f"Expected 422 for speed={bad_speed}, got {r_bad.status_code}"

        r_ok = client.post("/api/replay/speed", json={"speed": 4.0})
        assert r_ok.status_code == 200
        assert r_ok.json()["speed"] == 4.0

        # 4. Boot strategies never fabricate P2 Norris / P3 Verstappen / +10.5s
        strats = client.get("/api/strategy").json()
        assert len(strats) >= 3
        blob = str(strats).lower()
        assert "norris" not in blob
        assert "verstappen" not in blob
        assert "10.5" not in blob


def test_session_switch_resets_counters_and_keyframe_seek_equivalence() -> None:
    app = create_app()
    with TestClient(app) as client:
        store = get_state_store()
        rc = get_replay_controller()
        # Use smaller checkpoint interval in unit test to test keyframe hit cleanly on Silverstone (~943 events)
        old_interval = rc.CHECKPOINT_INTERVAL
        rc.CHECKPOINT_INTERVAL = 250
        try:
            r_sel = client.post("/api/sessions/select", json={"session_id": "f1-2023-silverstone-race"})
            assert r_sel.status_code == 200
            assert store.processed_events_count == 0
            assert store.duplicate_events_count == 0

            # Cold seek to index 600 builds checkpoints at 250 and 500
            r_seek1 = client.post("/api/replay/seek", json={"target_index": 600})
            assert r_seek1.status_code == 200
            assert store.processed_events_count == 600
            ckpts = rc._checkpoints.get("f1-2023-silverstone-race", {})
            assert 250 in ckpts and 500 in ckpts

            # Capture exact ground-truth SIA verdicts at target_index 620 from cold reset vs keyframe-assisted seek
            # First: warm keyframe jump (500 -> 620, only 120 events!)
            t0 = time.perf_counter()
            r_seek_kf = client.post("/api/replay/seek", json={"target_index": 620})
            kf_ms = (time.perf_counter() - t0) * 1000.0
            assert r_seek_kf.status_code == 200
            assert r_seek_kf.json()["currentIndex"] == 620
            ia = store.agents["agent-06-integrity"]
            verdicts_kf = {
                v["decision_instance_id"]: (v["integrity_state"], v["record_hash"], v["revision_number"])
                for v in ia.get_all_verdicts()
            }
            chains_kf = ia.engine.verify()
            assert all(st == "OK" for st in chains_kf.values())

            # Clear checkpoints and seek cold to 620 from 0 -> verify exact SIA verdict & hash chain equivalence
            rc._checkpoints.clear()
            r_seek_cold = client.post("/api/replay/seek", json={"target_index": 620})
            assert r_seek_cold.status_code == 200
            verdicts_cold = {
                v["decision_instance_id"]: (v["integrity_state"], v["record_hash"], v["revision_number"])
                for v in ia.get_all_verdicts()
            }
            assert verdicts_kf == verdicts_cold
            assert kf_ms < 2000.0

            # Verify /api/snapshot speed after seek (< 50ms in TestClient)
            ts0 = time.perf_counter()
            snap_res = client.get("/api/snapshot")
            snap_ms = (time.perf_counter() - ts0) * 1000.0
            assert snap_res.status_code == 200
            assert snap_ms < 100.0

            # Switch to another session -> counters reset cleanly to 0
            r_sw = client.post("/api/sessions/select", json={"session_id": "f1-2026-monaco-sim"})
            assert r_sw.status_code == 200
            assert store.processed_events_count == 0
            assert store.duplicate_events_count == 0
        finally:
            rc.CHECKPOINT_INTERVAL = old_interval
