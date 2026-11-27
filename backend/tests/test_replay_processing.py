from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from pulse.contracts import (
    Completeness,
    EventEnvelope,
    EventTime,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
)
from pulse.replay.controller import ReplayController, ReplayStatus
from pulse.replay.processor import ReplayEventProcessor
from pulse.stream.bus import PulseEventBus


def make_event(sequence: int) -> EventEnvelope:
    moment = datetime(2023, 7, 9, 14, 0, tzinfo=UTC) + timedelta(seconds=sequence)
    return EventEnvelope(
        event_id=f"event-{sequence}",
        event_type="LAP_COMPLETED",
        source=SourceRef(
            provider="TEST",
            adapter="pytest",
            source_record_id=str(sequence),
            capture_id="test-capture",
        ),
        run=RunContext(run_id="source-run", session_instance_id="test-session", mode=RunMode.REPLAY),
        session=SessionRef(season=2023, meeting_id="test", session_id="test-session"),
        time=EventTime(event_time_utc=moment, session_elapsed_ms=sequence * 1000),
        subject=Subject(driver_number=44),
        payload={"lap": sequence},
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )


class RecordingProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    async def __call__(self, envelope: EventEnvelope, *, publish: bool) -> None:
        self.calls.append((envelope.event_id, publish))


@pytest.mark.asyncio
async def test_seek_rebuilds_prior_events_through_the_processing_callback_without_republishing() -> None:
    controller = ReplayController()
    controller.envelopes = [make_event(1), make_event(2), make_event(3)]
    processor = RecordingProcessor()
    controller.set_event_processor(processor)
    previous_run_id = controller.run_id

    await controller.seek(target_index=2)

    assert controller.run_id != previous_run_id
    assert [event_id for event_id, _ in processor.calls] == [
        f"event-1-{controller.run_id}",
        f"event-2-{controller.run_id}",
    ]
    assert [publish for _, publish in processor.calls] == [False, False]
    assert controller.current_index == 2
    assert controller.published_count == 2


@pytest.mark.asyncio
async def test_normal_playback_uses_the_same_processing_callback_with_publication() -> None:
    controller = ReplayController()
    controller.envelopes = [make_event(1), make_event(2)]
    processor = RecordingProcessor()
    controller.set_event_processor(processor)

    await controller.start(speed=5.0)
    assert controller._task is not None
    await asyncio.wait_for(controller._task, timeout=1.0)

    assert [publish for _, publish in processor.calls] == [True, True]
    assert controller.status == ReplayStatus.COMPLETED


@pytest.mark.asyncio
async def test_processing_callback_failure_marks_replay_failed() -> None:
    async def fail(_: EventEnvelope, *, publish: bool) -> None:
        raise RuntimeError("processing unavailable")

    controller = ReplayController()
    controller.envelopes = [make_event(1)]
    controller.set_event_processor(fail)

    await controller.start()
    assert controller._task is not None
    await asyncio.wait_for(controller._task, timeout=1.0)

    assert controller.status == ReplayStatus.FAILED


@pytest.mark.asyncio
async def test_connected_broker_publish_failure_is_visible_to_the_caller() -> None:
    class FailingBroker:
        is_connected = True

        async def publish(self, topic: str, key: str, value: object) -> None:
            raise RuntimeError("broker unavailable")

    bus = PulseEventBus(broker=FailingBroker())

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await bus.publish("pulse.raw.timing.laps.v1", "session:44", {"lap": 1})


@pytest.mark.asyncio
async def test_local_only_rebuild_dispatches_handlers_without_transport_publication() -> None:
    class Broker:
        is_connected = True

        def __init__(self) -> None:
            self.publish_calls = 0

        async def publish(self, topic: str, key: str, value: object) -> None:
            self.publish_calls += 1

    broker = Broker()
    bus = PulseEventBus(broker=broker)
    dispatched: list[str] = []

    async def handler(topic: str, key: str, value: object) -> None:
        dispatched.append(key)

    bus.subscribe("pulse.agent.event_context.findings.v1", handler)
    async with bus.local_only():
        await bus.publish("pulse.agent.event_context.findings.v1", "rebuild-event", {"ok": True})

    assert broker.publish_calls == 0
    assert dispatched == ["rebuild-event"]


@pytest.mark.asyncio
async def test_processor_dispatches_canonical_event_but_never_publishes_on_rebuild() -> None:
    class Normalizer:
        def process(self, envelope: EventEnvelope):
            return envelope, "pulse.norm.driver_laps.v1"

    published: list[str] = []
    dispatched: list[tuple[str, str]] = []

    async def publish_raw(topic: str, key: str, envelope: EventEnvelope) -> None:
        published.append(f"{topic}:{key}:{envelope.event_id}")

    async def dispatch(topic: str, key: str, envelope: EventEnvelope) -> None:
        dispatched.append((topic, envelope.event_id))

    processor = ReplayEventProcessor(Normalizer(), dispatch, publish_raw)
    event = make_event(1)

    await processor.process(event, publish=False)

    assert published == []
    assert dispatched == [("pulse.norm.driver_laps.v1", "event-1")]


def test_all_specialist_agents_implement_domain_reset() -> None:
    from pulse.agents.event_control import EventControlAgent
    from pulse.agents.track_state import TrackStateAgent
    from pulse.agents.vehicle_response import VehicleResponseAgent
    from pulse.agents.tyre_strategy import TyreStrategyAgent
    from pulse.agents.fusion import ConsequenceFusionEngine
    from pulse.integrity.agent import IntegrityAgent

    agents = [
        EventControlAgent(),
        TrackStateAgent(),
        VehicleResponseAgent(),
        TyreStrategyAgent(),
        ConsequenceFusionEngine(),
        IntegrityAgent(),
    ]

    for agent in agents:
        assert hasattr(agent, "reset"), f"{agent.agent_id} must implement reset()"
        agent.inputs_received = 42
        agent.reset()
        assert agent.inputs_received == 0


def test_lifespan_wires_and_unwires_replay_event_processor() -> None:
    from fastapi.testclient import TestClient
    from pulse.main import create_app
    from pulse.replay.controller import get_replay_controller

    controller = get_replay_controller()
    assert controller._event_processor is None

    app = create_app()
    with TestClient(app):
        # Inside lifespan, the processor must be registered
        assert controller._event_processor is not None

    # After lifespan shutdown, the processor must be cleaned up
    assert controller._event_processor is None

