import pytest
from fastapi.testclient import TestClient

from pulse.circuits import get_circuit, interpolate_track_position, list_circuits, resolve_driver_position
from pulse.circuits.models import PositionMode
from pulse.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_simulation_state():
    from pulse.state.store import get_state_store
    store = get_state_store()
    store.projector.drivers = store.projector._init_full_grid()
    store.projector.official_notices = store.projector._init_official_notices()
    store.projector.data_mode = "SIMULATED"
    store.projector.status = "Green Flag"
    store.projector.active_event_display = "Green Flag"
    store.findings.clear()
    store.latest_assessments.clear()
    store.assessment_history.clear()
    yield




def test_circuits_catalogue_catalogue_and_provenance():
    circuits = list_circuits()
    assert len(circuits) >= 3
    ids = {c["circuit_id"] for c in circuits}
    assert "monaco" in ids
    assert "silverstone" in ids
    assert "suzuka" in ids

    # Validate Monaco specifically
    monaco = get_circuit("monaco")
    assert monaco is not None
    assert monaco.length_meters == 3337.0
    assert len(monaco.corners) == 19
    assert len(monaco.sectors) == 3
    assert monaco.track_direction == "CLOCKWISE"
    assert len(monaco.checksum_sha256) == 64
    assert "FIA" in monaco.source_attribution


def test_circuit_interpolation_and_coordinates():
    monaco = get_circuit("monaco")
    assert monaco is not None

    # Test interpolation at progress 0.0, 0.25, 0.5, 0.75
    p0 = interpolate_track_position(monaco, 0.0)
    p25 = interpolate_track_position(monaco, 0.25)
    p50 = interpolate_track_position(monaco, 0.5)

    assert isinstance(p0, tuple) and len(p0) == 2
    assert p0 != p25
    assert p25 != p50

    # Test resolve_driver_position provenance
    x, y, mode = resolve_driver_position(monaco, progress=0.33)
    assert mode == PositionMode.TIMING_ESTIMATED
    assert x > 0 and y > 0

    # Measured GPS resolution
    x_gps, y_gps, mode_gps = resolve_driver_position(monaco, measured_gps=[500.0, 300.0])
    assert mode_gps == PositionMode.MEASURED_GPS
    assert x_gps == 500.0 and y_gps == 300.0

    # Pit lane resolution
    x_pit, y_pit, mode_pit = resolve_driver_position(monaco, in_pit=True, progress=0.5)
    assert mode_pit == PositionMode.TIMING_ESTIMATED


def test_api_circuits_endpoints():
    res_list = client.get("/api/circuits")
    assert res_list.status_code == 200
    circuits = res_list.json()
    assert len(circuits) >= 3

    res_monaco = client.get("/api/circuit/monaco")
    assert res_monaco.status_code == 200
    m = res_monaco.json()
    assert m["circuit_id"] == "monaco"
    assert len(m["centreline"]) > 50

    res_silverstone = client.get("/api/circuit/silverstone")
    assert res_silverstone.status_code == 200

    res_suzuka = client.get("/api/circuit/suzuka")
    assert res_suzuka.status_code == 200


def test_api_full_grid_drivers():
    res = client.get("/api/drivers")
    assert res.status_code == 200
    drivers = res.json()
    assert len(drivers) == 20
    numbers = [d["number"] for d in drivers]
    assert 16 in numbers  # Leclerc
    assert 4 in numbers   # Norris
    assert 1 in numbers   # Verstappen
    assert 44 in numbers  # Hamilton
    assert 31 in numbers  # Ocon (Retired)

    # Check statuses
    statuses = {d["status"] for d in drivers}
    assert "ACTIVE" in statuses
    assert "PIT_LANE" in statuses
    assert "RETIRED" in statuses


def test_api_driver_telemetry():
    from datetime import UTC, datetime, timedelta
    from pulse.contracts import Completeness, EventEnvelope, EventTime, Interpretation, Quality, RunContext, RunMode, SessionRef, SourceRef, Subject, UnitValidation
    from pulse.state.store import get_state_store

    store = get_state_store()
    # Prior to telemetry stream arrival, high-frequency channels must report UNAVAILABLE (no fabricated curves)
    res_idle = client.get("/api/telemetry/16")
    assert res_idle.status_code == 200
    tel_idle = res_idle.json()
    assert tel_idle["channels"]["speed"]["quality"] == "UNAVAILABLE"
    assert tel_idle["channels"]["speed"]["value"] is None
    assert tel_idle["history"] == []

    # Ingest 5 real DRIVER_TELEMETRY envelopes -> history and channels populate dynamically
    base = datetime(2026, 5, 24, 13, 0, tzinfo=UTC)
    for idx in range(5):
        env = EventEnvelope(
            event_id=f"tel-test-{idx}",
            event_type="DRIVER_TELEMETRY",
            source=SourceRef(provider="PULSE_SYNTHETIC_SIM", adapter="pytest", source_record_id=f"rec-{idx}", capture_id="cap-test-tel"),
            time=EventTime(event_time_utc=base + timedelta(milliseconds=idx * 500), session_elapsed_ms=idx * 500),
            session=SessionRef(season=2026, meeting_id="monaco-2026", session_id="f1-2026-monaco-sim"),
            run=RunContext(run_id="run-tel-test", session_instance_id="f1-2026-monaco-sim", mode=RunMode.SIMULATED),
            subject=Subject(driver_number=16),
            payload={"speed": 210.0 + idx * 5.0, "throttle": 92.0, "brake": 0.0, "gear": 6, "rpm": 11200},
            quality=Quality(completeness=Completeness.COMPLETE, unit_validation=UnitValidation.PASSED, interpretation=Interpretation.OBSERVED),
        )
        store.record_canonical_event(env)

    res_16 = client.get("/api/telemetry/16")
    assert res_16.status_code == 200
    tel_16 = res_16.json()
    assert tel_16["driver_number"] == 16
    assert tel_16["status"] == "ACTIVE"
    assert tel_16["channels"]["speed"]["quality"] == "AVAILABLE"
    assert tel_16["channels"]["speed"]["value"] == 230.0
    assert len(tel_16["history"]) == 5

    # Retired driver #31 (Ocon) - missing telemetry channels marked UNAVAILABLE
    res_31 = client.get("/api/telemetry/31")
    assert res_31.status_code == 200
    tel_31 = res_31.json()
    assert tel_31["status"] == "RETIRED"
    assert tel_31["channels"]["speed"]["quality"] == "UNAVAILABLE"
    assert tel_31["channels"]["speed"]["value"] is None


def test_api_race_control_notices():
    from datetime import UTC, datetime
    from pulse.contracts import Completeness, EventEnvelope, EventTime, Interpretation, Quality, RunContext, RunMode, SessionRef, SourceRef, Subject, UnitValidation
    from pulse.state.store import get_state_store

    # On clean boot without events, no fake future 2026 notices are pre-populated
    res_empty = client.get("/api/race-control")
    assert res_empty.status_code == 200
    assert res_empty.json() == []

    # Ingest genuine session start & VSC events -> honest notices created
    store = get_state_store()
    t0 = datetime(2026, 5, 24, 13, 0, tzinfo=UTC)
    for eid, etype, pay in [
        ("rc-start-1", "SESSION_STARTED", {"lap": 1, "total_laps": 78}),
        ("rc-vsc-1", "VSC_DEPLOYED", {"reason": "Stopped car Turn 10", "affected_drivers": [16, 4]}),
    ]:
        env = EventEnvelope(
            event_id=eid,
            event_type=etype,
            source=SourceRef(provider="PULSE_SYNTHETIC_SIM", adapter="pytest", source_record_id=eid, capture_id="cap-test-rc"),
            time=EventTime(event_time_utc=t0, session_elapsed_ms=1000),
            session=SessionRef(season=2026, meeting_id="monaco-2026", session_id="f1-2026-monaco-sim"),
            run=RunContext(run_id="run-rc-test", session_instance_id="f1-2026-monaco-sim", mode=RunMode.SIMULATED),
            subject=Subject(),
            payload=pay,
            quality=Quality(completeness=Completeness.COMPLETE, unit_validation=UnitValidation.PASSED, interpretation=Interpretation.OBSERVED),
        )
        store.record_canonical_event(env)

    res = client.get("/api/race-control")
    assert res.status_code == 200
    notices = res.json()
    assert len(notices) == 2
    categories = {n["category"] for n in notices}
    assert "SAFETY_CAR" in categories
    assert "FLAG" in categories
    assert notices[0]["status"] == "SIMULATED_NOTICE"
    assert "PULSE Synthetic Simulator" in notices[0]["source"]


def test_api_pipeline_status():
    with TestClient(app) as c:
        res = c.get("/api/pipeline/status")
        assert res.status_code == 200
        data = res.json()
        assert "kafka" in data
        assert "flink" in data
        assert "agents" in data
        assert data["agents"]["total_registered"] == 6
