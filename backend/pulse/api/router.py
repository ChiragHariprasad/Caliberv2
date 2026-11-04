from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pulse.simulator.runner import get_scenario_runner
from pulse.state.store import get_state_store

logger = logging.getLogger("pulse.api")
api_router = APIRouter(prefix="/api", tags=["PULSE Race Intelligence API"])


class ControlPayload(BaseModel):
    action: str | None = None
    speed: float | None = None


@api_router.get("/health")
async def get_health() -> dict[str, Any]:
    store = get_state_store()
    return store.get_health()


@api_router.get("/session")
async def get_session() -> dict[str, Any]:
    store = get_state_store()
    return store.get_session()


@api_router.get("/drivers")
async def get_drivers() -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_drivers()


@api_router.get("/timeline")
async def get_timeline() -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_timeline()


@api_router.get("/assessments")
async def get_assessments(driver_number: int | None = Query(default=None)) -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_assessments(driver_number=driver_number)


@api_router.get("/findings")
async def get_findings(
    agent_id: str | None = Query(default=None),
    finding_type: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    store = get_state_store()
    findings = store.findings
    if agent_id:
        findings = [f for f in findings if f.agent_id == agent_id]
    if finding_type:
        findings = [f for f in findings if f.finding_type == finding_type]
    return [f.model_dump(mode="json") for f in findings]


@api_router.get("/agents")
async def get_agents() -> list[dict[str, Any]]:
    store = get_state_store()
    metrics = store.get_agent_metrics()
    return list(metrics.values())


@api_router.get("/agents/metrics")
async def get_agents_metrics() -> dict[str, Any]:
    store = get_state_store()
    return store.get_agent_metrics()


@api_router.get("/findings/{finding_id}")
async def get_finding(finding_id: str) -> dict[str, Any]:
    store = get_state_store()
    for f in store.findings:
        if f.finding_id == finding_id:
            return f.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Finding not found: {finding_id}")


@api_router.get("/assessments/{assessment_id}")
async def get_assessment_by_id(assessment_id: str) -> dict[str, Any]:
    store = get_state_store()
    for a in store.assessment_history:
        if a.assessment_id == assessment_id:
            return a.model_dump(mode="json")
    for a in store.latest_assessments.values():
        if a.assessment_id == assessment_id:
            return a.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Assessment not found: {assessment_id}")


@api_router.get("/runs")
async def get_runs() -> list[dict[str, Any]]:
    runner = get_scenario_runner()
    return [runner.run_record.model_dump(mode="json")]


@api_router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    runner = get_scenario_runner()
    return runner.run_record.model_dump(mode="json")


@api_router.get("/sessions/{session_id}")
async def get_session_by_id(session_id: str) -> dict[str, Any]:
    store = get_state_store()
    return store.get_session()


@api_router.get("/sessions/{session_id}/drivers")
async def get_session_drivers(session_id: str) -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_drivers()


@api_router.get("/sessions/{session_id}/drivers/{driver_number}")
async def get_session_driver_by_number(session_id: str, driver_number: int) -> dict[str, Any]:
    store = get_state_store()
    if driver_number in store.projector.drivers:
        return store.projector.drivers[driver_number]
    raise HTTPException(status_code=404, detail=f"Driver #{driver_number} not found")


@api_router.get("/sessions/{session_id}/timeline")
async def get_session_timeline(session_id: str) -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_timeline()


@api_router.get("/sessions/{session_id}/track")
async def get_session_track(session_id: str) -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_track()


@api_router.get("/sessions/{session_id}/strategy")
async def get_session_strategy(session_id: str) -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_strategy()


@api_router.get("/sessions/{session_id}/assessments")
async def get_session_assessments(session_id: str, driver_number: int | None = Query(default=None)) -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_assessments(driver_number=driver_number)


@api_router.get("/strategy")
async def get_strategy() -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_strategy()


@api_router.get("/track")
async def get_track() -> list[dict[str, Any]]:
    store = get_state_store()
    return store.get_track()


@api_router.get("/operations")
async def get_operations() -> dict[str, Any]:
    store = get_state_store()
    runner = get_scenario_runner()
    health = store.get_health()
    return {
        "pipeline": health,
        "runner": {
            "status": runner.status.value if hasattr(runner.status, "value") else str(runner.status),
            "current_index": runner.current_index,
            "total_events": len(runner.events),
            "speed": runner.speed,
            "scenario": runner.scenario_name,
        },
        "findings_count": len(store.findings),
        "assessments_count": len(store.assessment_history),
    }


@api_router.get("/snapshot")
async def get_snapshot() -> dict[str, Any]:
    store = get_state_store()
    return store.get_snapshot()


@api_router.post("/replay/{action}")
async def handle_replay_action(action: str, payload: ControlPayload | None = None) -> dict[str, Any]:
    act = action.lower()
    runner = get_scenario_runner()

    if act == "start":
        await runner.start()
    elif act == "pause":
        runner.pause()
    elif act == "resume":
        runner.resume()
    elif act == "restart":
        await runner.restart()
    elif act == "speed" or act == "set_speed":
        spd = payload.speed if payload and payload.speed is not None else 1.0
        runner.set_speed(spd)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported replay action: {action}")

    return {
        "status": "success",
        "action": act,
        "runner_status": runner.status.value if hasattr(runner.status, "value") else str(runner.status),
        "speed": runner.speed,
    }


@api_router.post("/runs/{run_id}/controls")
async def handle_run_controls(run_id: str, payload: ControlPayload) -> dict[str, Any]:
    action = (payload.action or "").lower()
    return await handle_replay_action(action, payload)


@api_router.get("/stream")
async def event_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) delivering real-time telemetry and intelligence updates."""
    async def sse_generator():
        store = get_state_store()
        queue = store.add_listener()

        # Send initial full snapshot on connection
        initial_snap = json.dumps(store.get_snapshot())
        yield f"event: snapshot\ndata: {initial_snap}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=2.0)
                    data_str = json.dumps(msg["data"])
                    yield f"event: {msg['type']}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            store.remove_listener(queue)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
