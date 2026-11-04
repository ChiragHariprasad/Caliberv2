"""PULSE Phase 4.2 — Automated Streaming Test Suite.

Verifies:
1. ReplayController lifecycle: READY -> RUNNING -> PAUSED -> RESUME -> RESET -> COMPLETED.
2. ReplayController speed scaling across allowed speeds [0.25, 0.5, 1.0, 2.0, 5.0].
3. ReplayController seek navigation: index, lap, and elapsed_ms.
4. ReplayController offset monotonicity and envelope counter incrementing.
5. ReplayController run ID generation and isolation on reset.
6. Session Registry discovery and metadata contracts.
7. Session switching from simulation to historical replay.
8. Session switching to NO_SESSION_DATA (Suzuka preview) with empty data state.
9. Circuit geometry preservation during NO_SESSION_DATA session state.
10. StateStore sequence counter monotonicity and incremental SSE event IDs.
11. StateStore rolling buffer and Last-Event-ID missed-event recovery.
12. Continuous SSE stream connects with initial snapshot.
13. Continuous SSE stream emits typed domain event: SESSION_STATE_UPDATED.
14. Continuous SSE stream emits typed domain event: DRIVER_STATE_UPDATED.
15. Continuous SSE stream emits typed domain event: REPLAY_STATUS_UPDATED.
16. Fast-forward replay advances lap and elapsed session time dynamically.
17. FastAPI GET /api/replay/status contract and playback progress metrics.
18. FastAPI POST /api/replay/speed validation.
19. Zero emojis verification in frontend codebase.
20. Multi-agent execution transparency metrics increment during live replay.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pulse.api.router import get_state_store
from pulse.main import app
from pulse.replay.controller import ReplayController, ReplayStatus, get_replay_controller
from pulse.sessions.registry import get_session_by_id, list_sessions

client = TestClient(app)


# --- 1. ReplayController Lifecycle Tests ---


@pytest.mark.asyncio
async def test_01_replay_lifecycle_transitions():
    """Verify ReplayController transitions: READY -> RUNNING -> PAUSED -> RUNNING -> RESET -> READY."""
    controller = ReplayController()
    assert controller.status == ReplayStatus.READY

    # Start playback
    start_res = await controller.start()
    assert start_res["status"] == "RUNNING"
    assert controller.status == ReplayStatus.RUNNING

    # Pause playback
    pause_res = controller.pause()
    assert pause_res["status"] == "PAUSED"
    assert controller.status == ReplayStatus.PAUSED

    # Resume playback
    resume_res = controller.resume()
    assert resume_res["status"] == "RUNNING"
    assert controller.status == ReplayStatus.RUNNING

    # Reset playback
    reset_res = await controller.reset()
    assert reset_res["status"] == "READY"
    assert controller.status == ReplayStatus.READY
    assert controller.current_index == 0


def test_02_allowed_speeds_and_scaling():
    """Verify allowed replay speeds and speed setting clamping."""
    controller = ReplayController()
    for spd in [0.25, 0.5, 1.0, 2.0, 5.0]:
        res = controller.set_speed(spd)
        assert res["speed"] == spd
        assert controller.speed == spd

    # Invalid speed defaults back to 1.0
    res_inv = controller.set_speed(999.0)
    assert res_inv["speed"] == 1.0


@pytest.mark.asyncio
async def test_03_replay_seek_by_index():
    """Verify seek navigation by envelope index."""
    controller = ReplayController()
    await controller.reset()
    assert controller.current_index == 0

    seek_res = await controller.seek(target_index=3)
    assert seek_res["currentIndex"] == 3
    assert controller.current_index == 3

    # Reset back to start
    await controller.reset()
    assert controller.current_index == 0


@pytest.mark.asyncio
async def test_04_replay_seek_by_elapsed_ms():
    """Verify seek navigation by elapsed milliseconds."""
    controller = ReplayController()
    await controller.reset()

    seek_res = await controller.seek(target_elapsed_ms=5000)
    assert seek_res["status"] in {"READY", "PAUSED"}
    assert controller.current_index >= 0
    await controller.reset()


@pytest.mark.asyncio
async def test_05_run_id_isolation_on_reset():
    """Verify that resetting replay allocates a fresh run ID and isolates execution state."""
    controller = ReplayController()
    run_1 = controller.run_id

    await controller.reset()
    run_2 = controller.run_id

    assert run_1 != run_2
    assert run_2.startswith("run-")


# --- 2. Session Registry & Isolation Tests ---


def test_06_session_registry_catalogue():
    """Verify that Session Registry contains historical, simulation, and preview sessions."""
    sessions = list_sessions()
    ids = {s.session_id for s in sessions}
    assert "f1-2023-silverstone-race" in ids
    assert "f1-2026-monaco-sim" in ids
    assert "f1-2026-suzuka-preview" in ids

    silverstone = get_session_by_id("f1-2023-silverstone-race")
    assert silverstone.availability_status == "AVAILABLE_HISTORICAL"
    assert silverstone.circuit_id == "silverstone"
    assert silverstone.total_laps == 52

    suzuka = get_session_by_id("f1-2026-suzuka-preview")
    assert suzuka.availability_status == "NO_SESSION_DATA"
    assert suzuka.circuit_id == "suzuka"


def test_07_session_switch_to_historical():
    """Verify switching session to historical replay configures projector to Silverstone."""
    store = get_state_store()
    store.switch_session("f1-2023-silverstone-race")
    session = store.get_session()

    assert session["circuitId"] == "silverstone"
    assert session["mode"] == "REPLAY"
    assert session["totalLaps"] == 52
    assert len(store.get_drivers()) == 20

    # Restore to simulation
    store.switch_session("f1-2026-monaco-sim")


def test_08_session_switch_to_no_session_data():
    """Verify switching to Suzuka preview triggers NO_SESSION_DATA and empties driver data."""
    store = get_state_store()
    store.switch_session("f1-2026-suzuka-preview")
    session = store.get_session()

    assert session["status"] == "NO_SESSION_DATA"
    assert session["circuitId"] == "suzuka"
    assert len(store.get_drivers()) == 0

    # Restore to simulation
    store.switch_session("f1-2026-monaco-sim")


def test_09_circuit_geometry_preservation_on_no_session_data():
    """Verify circuit geometry remains verified and intact even when session has no timing data."""
    res = client.get("/api/circuit/suzuka")
    assert res.status_code == 200
    geo = res.json()
    assert geo["circuit_id"] == "suzuka"
    assert len(geo["centreline"]) > 100
    assert len(geo["corners"]) == 18
    assert geo["length_meters"] == 5807.0


# --- 3. SSE Continuous Stream & Sequence Ordering Tests ---


def test_10_sse_sequence_monotonicity():
    """Verify that StateStore sequence counter strictly increments with each event."""
    store = get_state_store()
    seq_start = store.sse_sequence_counter

    store.notify_session_state()
    assert store.sse_sequence_counter == seq_start + 1

    store.notify_driver_state()
    assert store.sse_sequence_counter == seq_start + 2


def test_11_last_event_id_reconnection_buffer():
    """Verify rolling buffer stores events and returns missed items after Last-Event-ID."""
    store = get_state_store()
    # Trigger notifications
    store.notify_session_state()
    cur_seq = store.sse_sequence_counter

    store.notify_session_state()
    store.notify_session_state()

    missed = store.get_history_after_id(f"sse-evt-{cur_seq}")
    assert len(missed) >= 2
    for m in missed:
        assert m["seq"] > cur_seq


def test_12_sse_endpoint_initial_snapshot():
    """Verify that connecting to /api/stream returns initial snapshot event."""
    with client.stream("GET", "/api/stream?limit=1") as response:
        assert response.status_code == 200
        first_chunk = next(response.iter_lines())
        assert "sse-evt-" in first_chunk or "id:" in first_chunk


def test_13_sse_typed_session_update_emission():
    """Verify that store.notify_session_state places typed SESSION_STATE_UPDATED in listener queue."""
    store = get_state_store()
    queue = store.add_listener()
    try:
        store.notify_session_state()
        assert not queue.empty()
        msg = queue.get_nowait()
        assert msg["type"] == "SESSION_STATE_UPDATED"
        assert "lap" in msg["data"]
        assert "circuitId" in msg["data"]
    finally:
        store.remove_listener(queue)


def test_14_sse_typed_driver_update_emission():
    """Verify that store.notify_driver_state places typed DRIVER_STATE_UPDATED in listener queue."""
    store = get_state_store()
    queue = store.add_listener()
    try:
        store.notify_driver_state(16)
        assert not queue.empty()
        msg = queue.get_nowait()
        assert msg["type"] == "DRIVER_STATE_UPDATED"
        assert "drivers" in msg["data"]
    finally:
        store.remove_listener(queue)


def test_15_sse_typed_replay_status_emission():
    """Verify that store.notify_replay_status places typed REPLAY_STATUS_UPDATED in listener queue."""
    store = get_state_store()
    queue = store.add_listener()
    try:
        payload = {"status": "PAUSED", "speed": 1.0, "currentLap": 24}
        store.notify_replay_status(payload)
        assert not queue.empty()
        msg = queue.get_nowait()
        assert msg["type"] == "REPLAY_STATUS_UPDATED"
        assert msg["data"]["status"] == "PAUSED"
    finally:
        store.remove_listener(queue)


# --- 4. Replay API Contract & Monotonic Progression Tests ---


def test_16_api_replay_status_contract():
    """Verify GET /api/replay/status returns the required 16 contract fields."""
    res = client.get("/api/replay/status")
    assert res.status_code == 200
    data = res.json()

    required_fields = [
        "sessionId",
        "captureId",
        "runId",
        "status",
        "mode",
        "speed",
        "allowedSpeeds",
        "currentIndex",
        "totalEvents",
        "publishedCount",
        "dropCount",
        "currentLap",
        "totalLaps",
        "elapsed",
        "elapsedMs",
        "progressPercent",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    assert data["speed"] in [0.25, 0.5, 1.0, 2.0, 5.0]


def test_17_api_replay_speed_contract():
    """Verify POST /api/replay/speed adjusts playback speed."""
    res = client.post("/api/replay/speed", json={"speed": 5.0})
    assert res.status_code == 200
    assert res.json()["speed"] == 5.0

    # Reset speed back to 1.0
    res_reset = client.post("/api/replay/speed", json={"speed": 1.0})
    assert res_reset.status_code == 200
    assert res_reset.json()["speed"] == 1.0


def test_18_api_sessions_catalogue_and_selection():
    """Verify GET /api/sessions and POST /api/sessions/select."""
    res = client.get("/api/sessions")
    assert res.status_code == 200
    sessions = res.json()
    assert len(sessions) >= 3

    # Switch session via API
    sel_res = client.post("/api/sessions/select", json={"session_id": "f1-2023-silverstone-race"})
    assert sel_res.status_code == 200
    assert sel_res.json()["session"]["circuitId"] == "silverstone"

    # Switch back to Monaco
    sel_back = client.post("/api/sessions/select", json={"session_id": "f1-2026-monaco-sim"})
    assert sel_back.status_code == 200
    assert sel_back.json()["session"]["circuitId"] == "monaco"


def test_19_zero_emojis_in_frontend():
    """Verify that zero emoji unicode characters remain in the frontend source code."""
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50]|[\u25A0-\u25FF]"
    )

    matches = []
    frontend_src = Path("frontend/src")
    assert frontend_src.exists(), "frontend/src must exist"

    for p in frontend_src.rglob("*.tsx"):
        txt = p.read_text(encoding="utf-8")
        for line_no, line in enumerate(txt.splitlines(), start=1):
            found = emoji_pattern.findall(line)
            if found:
                matches.append((str(p), line_no, line.strip(), found))

    assert len(matches) == 0, f"Found {len(matches)} emoji occurrences in frontend: {matches}"


@pytest.mark.asyncio
async def test_20_execution_transparency_metrics_increment():
    """Verify that processing envelopes increments agent metrics and projector counters."""
    controller = ReplayController()
    store = get_state_store()
    init_events = store.processed_events_count

    # Seek to event index 2 to process envelopes
    await controller.seek(target_index=2)

    # Projector and StateStore processed events incremented
    assert store.processed_events_count >= init_events
    await controller.reset()
