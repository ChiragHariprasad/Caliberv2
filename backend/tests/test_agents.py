import pytest
from unittest.mock import AsyncMock

from pulse.agents.event_control import EventControlAgent
from pulse.agents.track_state import TrackStateAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.simulator.scenarios import create_envelope


@pytest.mark.asyncio
async def test_event_control_agent_vsc_lifecycle_only():
    mock_bus = AsyncMock()
    agent = EventControlAgent(bus=mock_bus)

    # Generic VSC deployment without driver-specific context
    vsc_event = create_envelope(
        event_id="evt-vsc-01",
        event_type="VSC_DEPLOYED",
        elapsed_ms=11000,
        segment_id="sector-2",
        payload={"reason": "debris"},
    )

    await agent.on_event("pulse.norm.race_events.v1", "session", vsc_event)
    assert agent.active_lifecycle == "ACTIVE"
    assert agent.active_event_type == "VSC"
    assert mock_bus.publish.call_count == 1  # Emits canonical lifecycle finding
    call_args = mock_bus.publish.call_args[0]
    finding = call_args[2]
    assert finding.finding_type == "RACE_EVENT_LIFECYCLE"
    assert finding.result["lifecycle"] == "ACTIVE"
    assert agent.last_outcome == "FINDING_EMITTED"


@pytest.mark.asyncio
async def test_event_control_agent_vsc_with_driver_exposure():
    mock_bus = AsyncMock()
    agent = EventControlAgent(bus=mock_bus)

    # VSC event specifying an affected driver
    vsc_event = create_envelope(
        event_id="evt-vsc-02",
        event_type="VSC_DEPLOYED",
        elapsed_ms=11000,
        segment_id="sector-2",
        driver_number=16,
        payload={"reason": "debris", "affected_drivers": [16]},
    )

    await agent.on_event("pulse.norm.race_events.v1", "session", vsc_event)
    assert agent.active_lifecycle == "ACTIVE"
    assert mock_bus.publish.call_count == 2  # Emits lifecycle + driver exposure finding
    call_args = mock_bus.publish.call_args_list
    finding_types = [call[0][2].finding_type for call in call_args]
    assert "RACE_EVENT_LIFECYCLE" in finding_types
    assert "DRIVER_EVENT_EXPOSURE" in finding_types


@pytest.mark.asyncio
async def test_track_state_agent():
    mock_bus = AsyncMock()
    agent = TrackStateAgent(bus=mock_bus)

    track_event = create_envelope(
        event_id="evt-trk-01",
        event_type="TRACK_STATUS_UPDATE",
        elapsed_ms=4000,
        payload={"sector_index": 1, "condition": "Dry · clear"},
    )

    await agent.on_event("pulse.norm.track_segments.v1", "session", track_event)
    assert agent.processed_events == 1
    assert mock_bus.publish.call_count == 1


@pytest.mark.asyncio
async def test_tyre_strategy_agent_pit_window_savings():
    mock_bus = AsyncMock()
    agent = TyreStrategyAgent(bus=mock_bus)

    vsc_event = create_envelope(
        event_id="evt-vsc-02",
        event_type="VSC_DEPLOYED",
        elapsed_ms=11000,
        driver_number=16,
    )

    await agent.on_event("pulse.norm.race_events.v1", "session", vsc_event)
    assert agent.processed_events == 1
    assert mock_bus.publish.call_count == 1

    # Check published finding content
    call_args = mock_bus.publish.call_args[0]
    finding = call_args[2]
    assert finding.finding_type == "PIT_WINDOW_OPPORTUNITY"
    assert finding.result["net_time_saving_sec"] == 10.5
    assert finding.result["target_compound"] == "H"
