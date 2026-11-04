"""Unit tests for Phase 4 Part A: Session Entry Verification and Dynamic Grid Handling."""

from datetime import UTC, datetime
from uuid import uuid4
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
from pulse.stream.projections import RaceStateProjector


def make_envelope(event_type: str, driver_number: int | None = None, payload: dict | None = None) -> EventEnvelope:
    now = datetime.now(UTC)
    return EventEnvelope(
        event_id=f"test-evt-{uuid4().hex[:8]}",
        event_type=event_type,
        source=SourceRef(
            provider="TEST_HARNESS",
            adapter="unit_test_adapter",
            source_record_id=uuid4().hex[:6],
            capture_id="capture-test-001",
        ),
        time=EventTime(event_time_utc=now, session_elapsed_ms=72000),
        session=SessionRef(season=2023, meeting_id="silverstone", session_id="test-session-dynamic"),
        run=RunContext(run_id="run-test", session_instance_id="test-session-dynamic", mode=RunMode.REPLAY),
        subject=Subject(driver_number=driver_number, session_id="test-session-dynamic"),
        payload=payload or {},
        quality=Quality(
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
            interpretation=Interpretation.OBSERVED,
        ),
    )


def test_dynamic_entry_counts_18_and_22():
    """Verify that the projector supports arbitrary grid sizes without assuming a 20-driver limit."""
    projector = RaceStateProjector()

    # 1. Test 18-driver grid
    entries_18 = [
        {"number": i + 1, "name": f"Driver #{i + 1}", "team": "Team A", "status": "ACTIVE", "position": i + 1}
        for i in range(18)
    ]
    projector.load_session_entry_list(entries_18)
    drivers = projector.get_ordered_drivers()
    assert len(drivers) == 18, f"Expected 18 drivers, got {len(drivers)}"
    assert drivers[0]["number"] == 1
    assert drivers[17]["number"] == 18

    # 2. Test 22-driver grid
    entries_22 = [
        {"number": i + 1, "name": f"Driver #{i + 1}", "team": "Team B", "status": "ACTIVE", "position": i + 1}
        for i in range(22)
    ]
    projector.load_session_entry_list(entries_22)
    drivers_22 = projector.get_ordered_drivers()
    assert len(drivers_22) == 22, f"Expected 22 drivers, got {len(drivers_22)}"
    assert drivers_22[21]["number"] == 22


def test_driver_number_changes():
    """Verify handling of historical driver numbers and transfers (e.g. 2023 grid)."""
    projector = RaceStateProjector()
    historical_2023_entries = [
        {"number": 1, "name": "Max Verstappen", "team": "Red Bull Racing"},
        {"number": 2, "name": "Logan Sargeant", "team": "Williams"},
        {"number": 21, "name": "Nyck de Vries", "team": "AlphaTauri"},
        {"number": 77, "name": "Valtteri Bottas", "team": "Alfa Romeo"},
        {"number": 20, "name": "Kevin Magnussen", "team": "Haas"},
    ]
    projector.load_session_entry_list(historical_2023_entries)
    drivers = projector.drivers
    assert len(drivers) == 5
    assert 2 in drivers
    assert drivers[2]["name"] == "Logan Sargeant"
    assert drivers[2]["team"] == "Williams"
    assert 21 in drivers
    assert drivers[21]["name"] == "Nyck de Vries"
    assert 77 in drivers
    assert drivers[77]["name"] == "Valtteri Bottas"


def test_driver_dns_lifecycle():
    """Verify that DRIVER_DNS marks the driver as DNS and sets telemetry to UNAVAILABLE."""
    projector = RaceStateProjector()
    env = make_envelope("DRIVER_DNS", driver_number=2, payload={"reason": "Hydraulic failure on reconnaissance lap"})
    projector.apply_event(env)

    driver = projector.drivers[2]
    assert driver["status"] == "DNS"
    assert "Did Not Start" in driver["impact"]["label"]
    assert driver["history"] == []
    for ch_name, ch_data in driver["telemetry"].items():
        assert ch_data["quality"] == "UNAVAILABLE"


def test_driver_retires_lifecycle():
    """Verify that DRIVER_RETIRED marks status as RETIRED, updates impact label, and records official notice."""
    projector = RaceStateProjector()
    env = make_envelope("DRIVER_RETIRED", driver_number=20, payload={"reason": "Engine fire / Power unit stoppage"})
    projector.apply_event(env)

    driver = projector.drivers[20]
    assert driver["status"] == "RETIRED"
    assert "Retired" in driver["impact"]["label"]
    assert "Engine fire" in driver["impact"]["label"]
    assert driver["history"] == []
    for ch_name, ch_data in driver["telemetry"].items():
        assert ch_data["quality"] == "UNAVAILABLE"

    # Official notices check
    notices = projector.get_official_notices()
    assert any(20 in n.get("driver_numbers", []) and "RETIRED" in n.get("title", "") for n in notices)


def test_pit_lane_entry_and_exit_transitions():
    """Verify PIT_ENTRY and PIT_EXIT state and speed transitions."""
    projector = RaceStateProjector()

    # Enter Pit Lane
    env_in = make_envelope("PIT_ENTRY", driver_number=16)
    projector.apply_event(env_in)
    assert projector.drivers[16]["status"] == "PIT_LANE"
    assert projector.drivers[16]["telemetry"]["speed"]["value"] == 60.0

    # Exit Pit Lane
    env_out = make_envelope("PIT_EXIT", driver_number=16, payload={"speed": 215.0, "gear": 5})
    projector.apply_event(env_out)
    assert projector.drivers[16]["status"] == "ACTIVE"
    assert projector.drivers[16]["telemetry"]["speed"]["value"] == 215.0
    assert projector.drivers[16]["telemetry"]["gear"]["value"] == 5


def test_session_entry_list_stream_envelope():
    """Verify that a SESSION_ENTRY_LIST event envelope reconfigures the full grid dynamically."""
    projector = RaceStateProjector()
    envelope = make_envelope(
        "SESSION_ENTRY_LIST",
        payload={
            "entries": [
                {"number": 44, "name": "Lewis Hamilton", "team": "Mercedes", "position": 1, "status": "ACTIVE"},
                {"number": 63, "name": "George Russell", "team": "Mercedes", "position": 2, "status": "ACTIVE"},
                {"number": 4, "name": "Lando Norris", "team": "McLaren", "position": 3, "status": "ACTIVE"},
            ]
        },
    )
    projector.apply_event(envelope)
    assert len(projector.drivers) == 3
    assert [d["number"] for d in projector.get_ordered_drivers()] == [44, 63, 4]
