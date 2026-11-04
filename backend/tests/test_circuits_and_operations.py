import pytest
from fastapi.testclient import TestClient

from pulse.circuits import get_circuit, interpolate_track_position, list_circuits, resolve_driver_position
from pulse.circuits.models import PositionMode
from pulse.main import app

client = TestClient(app)


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
    # Active driver #16 (Leclerc)
    res_16 = client.get("/api/telemetry/16")
    assert res_16.status_code == 200
    tel_16 = res_16.json()
    assert tel_16["driver_number"] == 16
    assert tel_16["status"] == "ACTIVE"
    assert tel_16["channels"]["speed"]["quality"] == "AVAILABLE"
    assert tel_16["channels"]["speed"]["value"] > 200
    assert len(tel_16["history"]) == 20

    # Retired driver #31 (Ocon) - missing telemetry channels marked UNAVAILABLE
    res_31 = client.get("/api/telemetry/31")
    assert res_31.status_code == 200
    tel_31 = res_31.json()
    assert tel_31["status"] == "RETIRED"
    assert tel_31["channels"]["speed"]["quality"] == "UNAVAILABLE"
    assert tel_31["channels"]["speed"]["value"] is None


def test_api_race_control_notices():
    res = client.get("/api/race-control")
    assert res.status_code == 200
    notices = res.json()
    assert len(notices) >= 4
    categories = {n["category"] for n in notices}
    assert "SAFETY_CAR" in categories
    assert "FLAG" in categories
    assert "source" in notices[0]
    assert "regulatory_reference" in notices[0]


def test_api_pipeline_status():
    with TestClient(app) as c:
        res = c.get("/api/pipeline/status")
        assert res.status_code == 200
        data = res.json()
        assert "kafka" in data
        assert "flink" in data
        assert "agents" in data
        assert data["agents"]["total_registered"] == 5
