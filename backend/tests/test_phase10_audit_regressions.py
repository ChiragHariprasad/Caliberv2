"""Phase X Regression Tests for Confirmed Audit Defects."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from pulse.agents.base import BaseAgent
from pulse.contracts import (
    Completeness,
    EventEnvelope,
    EventTime,
    Finding,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
)
from pulse.main import create_app
from pulse.replay.controller import ReplayController
from pulse.state.store import StateStore


def _make_envelope(event_id: str, event_type: str, ts_offset_s: int, payload: dict, dn: int | None = 16) -> EventEnvelope:
    ts = datetime(2024, 5, 26, 13, 0, tzinfo=UTC) + timedelta(seconds=ts_offset_s)
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        source=SourceRef(provider="FIA_OFFICIAL_TIMING", adapter="pytest", source_record_id=event_id, capture_id="cap-1"),
        run=RunContext(run_id="run-test", session_instance_id="sess-1", mode=RunMode.REPLAY),
        session=SessionRef(season=2024, meeting_id="m-1", session_id="f1-2026-monaco-sim"),
        time=EventTime(event_time_utc=ts, ingest_time_utc=ts, session_elapsed_ms=ts_offset_s * 1000),
        subject=Subject(driver_number=dn),
        payload=payload,
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )


def test_statestore_deduplicates_event_ids_and_findings_without_double_sse() -> None:
    store = StateStore()
    queue = store.add_listener()
    try:
        e1 = _make_envelope("dup-ev-1", "LAP_COMPLETED", 10, {"lap": 2, "last_lap_seconds": 75})
        store.record_canonical_event(e1)
        store.record_canonical_event(e1)
        assert store.processed_events_count == 1
        assert store.duplicate_events_count == 1

        # Drain event SSEs and check finding idempotency
        while not queue.empty():
            queue.get_nowait()

        f = Finding(
            finding_id="f-unique-1",
            agent_id="agent-01-event-control",
            finding_type="TEST_FINDING",
            session_id="f1-2026-monaco-sim",
            run_id="run-test",
            subject=Subject(driver_number=16),
            trigger_event_id="dup-ev-1",
            as_of_event_time=datetime(2024, 5, 26, 13, 0, 10, tzinfo=UTC),
            interpretation=Interpretation.DERIVED,
            result={"ok": True},
            evidence_refs=["dup-ev-1"],
            model_version="1.0.0",
        )
        store.record_finding(f)
        emitted_first = queue.qsize()
        store.record_finding(f)
        emitted_second = queue.qsize() - emitted_first
        assert len(store.findings) == 1
        assert emitted_first == 3
        assert emitted_second == 0
    finally:
        store.remove_listener(queue)


def test_projector_ignores_stale_out_of_order_lap_completed() -> None:
    store = StateStore()
    newer = _make_envelope("ev-lap-2", "LAP_COMPLETED", 20, {"lap": 2, "last_lap_seconds": 75})
    older = _make_envelope("ev-lap-1", "LAP_COMPLETED", 10, {"lap": 1, "last_lap_seconds": 79})
    store.record_canonical_event(newer)
    store.record_canonical_event(older)
    assert store.projector.drivers[16]["lastLap"] == "1:15.000"


def test_base_agent_uses_empirical_latency_percentiles() -> None:
    class DummyAgent(BaseAgent):
        async def on_event(self, topic, key, event):
            pass

    a = DummyAgent("agent-dummy", "Dummy", "pulse.dummy.v1")
    for val in [1.0, 2.0, 3.0, 4.0, 100.0]:
        a.record_outcome("FINDING_EMITTED", val)
    m = a.get_metrics()
    assert m.p50_latency_ms == 3.0
    assert m.p95_latency_ms == 100.0


def test_api_routes_deduplicated_and_validation_enforced() -> None:
    app = create_app()
    replay_status_routes = [r for r in app.routes if getattr(r, "path", None) == "/api/replay/status"]
    assert len(replay_status_routes) == 1

    with TestClient(app) as client:
        r_bad_sess = client.post("/api/sessions/select", json={"session_id": "nonexistent-session-999"})
        assert r_bad_sess.status_code == 404

        r_neg_seek = client.post("/api/replay/seek", json={"target_elapsed_ms": -50})
        assert r_neg_seek.status_code == 422


@pytest.mark.asyncio
async def test_replay_controller_does_not_double_record_when_processor_wired() -> None:
    from pulse.state.store import get_state_store

    store = get_state_store()
    before = store.processed_events_count
    called = 0

    async def fake_proc(env: EventEnvelope, *, publish: bool) -> None:
        nonlocal called
        called += 1

    rc = ReplayController()
    rc.set_event_processor(fake_proc)
    ev = _make_envelope("single-proc-1", "LAP_COMPLETED", 5, {"lap": 1, "last_lap_seconds": 76})
    await rc._process(ev, publish=True)
    assert called == 1
    assert store.processed_events_count == before
