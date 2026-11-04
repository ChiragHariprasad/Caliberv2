import pytest
from pulse.simulator.scenarios import build_vsc_scenario
from pulse.simulator.runner import ScenarioRunner
from pulse.contracts import RunStatus


def test_build_vsc_scenario():
    events = build_vsc_scenario()
    assert len(events) >= 10

    event_types = [e.event_type for e in events]
    assert "SESSION_STARTED" in event_types
    assert "POSITION_UPDATE" in event_types
    assert "VSC_DEPLOYED" in event_types
    assert "PIT_ENTRY" in event_types
    assert "TYRE_FITTED" in event_types
    assert "VSC_ENDING" in event_types
    assert "VSC_ENDED" in event_types

    # Preserves monotonically increasing elapsed ms
    ms_values = [e.time.session_elapsed_ms for e in events if e.time.session_elapsed_ms is not None]
    assert ms_values == sorted(ms_values)


def test_scenario_runner_lifecycle():
    runner = ScenarioRunner()
    assert runner.status == RunStatus.CREATED
    assert runner.speed == 1.0

    runner.pause()
    assert runner.status == RunStatus.PAUSED

    runner.resume()
    assert runner.status == RunStatus.RUNNING

    runner.set_speed(2.5)
    assert runner.speed == 2.5
