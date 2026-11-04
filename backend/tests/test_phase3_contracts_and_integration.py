from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import pytest
from fastapi.testclient import TestClient

from pulse.circuits import get_circuit, interpolate_track_position, list_circuits, resolve_driver_position
from pulse.circuits.models import PositionMode
from pulse.contracts import Completeness
from pulse.main import app
from pulse.state.store import get_state_store

client = TestClient(app)


def test_01_monaco_geometry_rendering():
    """Verify Monaco circuit geometry asset, centreline, boundaries, corners and checksum."""
    monaco = get_circuit("monaco")
    assert monaco is not None
    assert monaco.circuit_id == "monaco"
    assert monaco.length_meters == 3337.0
    assert len(monaco.centreline) >= 50
    assert len(monaco.outer_boundary) >= 50
    assert len(monaco.inner_boundary) >= 50
    assert len(monaco.corners) == 19
    assert monaco.corners[0].name == "Sainte Dévote"
    assert monaco.corners[5].name == "Grand Hotel Hairpin"
    assert monaco.corners[17].name == "La Rascasse (Exit)"
    assert len(monaco.checksum_sha256) == 64


def test_02_silverstone_geometry_rendering():
    """Verify Silverstone circuit geometry asset, corners, and DRS zones."""
    silverstone = get_circuit("silverstone")
    assert silverstone is not None
    assert silverstone.circuit_id == "silverstone"
    assert silverstone.length_meters == 5891.0
    assert len(silverstone.corners) == 18
    corner_names = [c.name for c in silverstone.corners]
    assert "Abbey" in corner_names
    assert "Maggotts" in corner_names
    assert "Becketts" in corner_names
    assert "Stowe" in corner_names
    assert len(silverstone.drs_zones) == 2


def test_03_suzuka_geometry_rendering():
    """Verify Suzuka circuit geometry asset, crossover figure-eight, and corners."""
    suzuka = get_circuit("suzuka")
    assert suzuka is not None
    assert suzuka.circuit_id == "suzuka"
    assert suzuka.length_meters == 5807.0
    assert suzuka.track_direction == "FIGURE_EIGHT"
    assert len(suzuka.corners) == 18
    corner_names = [c.name for c in suzuka.corners]
    assert "First Curve" in corner_names
    assert "Degner 1" in corner_names
    assert "Hairpin" in corner_names
    assert "130R" in corner_names


def test_04_dynamic_twenty_plus_driver_entries():
    """Verify full-grid 20+ driver entries from session state."""
    res = client.get("/api/drivers")
    assert res.status_code == 200
    drivers = res.json()
    assert len(drivers) >= 20
    # Every driver carries number, name, team, teamColor, and status
    for d in drivers:
      assert "number" in d
      assert "name" in d
      assert "team" in d
      assert "teamColor" in d
      assert "status" in d


def test_05_driver_hover_and_click_payloads():
    """Verify individual driver telemetry inspection endpoint delivers full channel payload."""
    res = client.get("/api/telemetry/16")
    assert res.status_code == 200
    data = res.json()
    assert data["driver_number"] == 16
    assert data["name"] == "Charles Leclerc"
    assert "channels" in data
    assert "speed" in data["channels"]
    assert "throttle" in data["channels"]
    assert "brake" in data["channels"]
    assert "gear" in data["channels"]
    assert "rpm" in data["channels"]
    assert "drs" in data["channels"]


def test_06_missing_telemetry_channels_handling():
    """Verify that when a driver is retired or telemetry is absent, channels report UNAVAILABLE."""
    res = client.get("/api/telemetry/31")  # Car 31 is retired
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "RETIRED"
    speed = data["channels"]["speed"]
    assert speed["quality"] == "UNAVAILABLE"
    assert speed["value"] is None


def test_07_estimated_versus_observed_positions():
    """Verify coordinate resolver distinguishes MEASURED_GPS from TIMING_ESTIMATED."""
    monaco = get_circuit("monaco")
    assert monaco is not None

    # Transponder lap distance interpolation -> TIMING_ESTIMATED
    x_est, y_est, mode_est = resolve_driver_position(monaco, progress=0.45)
    assert mode_est == PositionMode.TIMING_ESTIMATED

    # True GPS coordinate -> MEASURED_GPS
    x_gps, y_gps, mode_gps = resolve_driver_position(monaco, measured_gps=[450.0, 300.0])
    assert mode_gps == PositionMode.MEASURED_GPS
    assert x_gps == 450.0 and y_gps == 300.0


def test_08_stale_telemetry_freshness():
    """Verify that driver channels carry freshness metadata in milliseconds."""
    res = client.get("/api/telemetry/16")
    data = res.json()
    speed = data["channels"]["speed"]
    assert "freshness_ms" in speed
    assert speed["freshness_ms"] >= 0


def test_09_official_versus_pulse_event_separation():
    """Verify complete separation between official FIA regulatory notices and PULSE analytical assessments."""
    res_notices = client.get("/api/race-control")
    assert res_notices.status_code == 200
    notices = res_notices.json()
    assert len(notices) >= 4
    for n in notices:
      assert "source" in n
      assert "regulatory_reference" in n
      assert "FIA" in n["source"] or "Meteo" in n["source"]

    res_pulse = client.get("/api/assessments")
    assert res_pulse.status_code == 200
    assessments = res_pulse.json()
    for a in assessments:
      assert "forecast" in a
      assert "evidence" in a


def test_10_all_five_agent_operational_cards():
    """Verify that all five specialist agents expose runtime metrics via API."""
    with TestClient(app) as c:
      res = c.get("/api/agents/metrics")
      assert res.status_code == 200
      metrics = res.json()
      assert len(metrics) == 5
      expected_agents = {
          "agent-01-event-control",
          "agent-02-track-state",
          "agent-03-vehicle-response",
          "agent-04-tyre-strategy",
          "agent-05-fusion",
      }
      assert set(metrics.keys()) == expected_agents


def test_11_agent_execution_trace():
    """Verify that agent findings endpoint provides auditable execution traces."""
    res = client.get("/api/findings")
    assert res.status_code == 200
    findings = res.json()
    assert isinstance(findings, list)


def test_12_finding_lineage():
    """Verify finding lineage query by ID."""
    store = get_state_store()
    if store.findings:
      target_id = store.findings[0].finding_id
      res = client.get(f"/api/findings/{target_id}")
      assert res.status_code == 200
      assert res.json()["finding_id"] == target_id


def test_13a_flink_live_cluster_integration_job_running():
    """STRICT FLINK INTEGRATION TEST: Requires the actual Flink cluster and RUNNING job.
    Fails or reports BLOCKED if the Flink normalizer job is not running or checkpoints are 0.
    """
    from pulse.stream.flink.manager import get_flink_manager
    mgr = get_flink_manager()
    if not mgr.client.is_cluster_online():
        pytest.fail("BLOCKED: Flink cluster is offline or unreachable on http://localhost:8081")
    
    metrics = mgr.get_metrics()
    if not metrics:
        pytest.fail("BLOCKED: Flink normalizer job is not active or could not be queried")
    
    assert metrics.state == "RUNNING", f"Expected Flink job to be RUNNING, got {metrics.state}"
    assert metrics.checkpoints_completed > 0, f"Expected completed checkpoints > 0, got {metrics.checkpoints_completed}"
    assert metrics.job_id is not None


def test_13b_flink_offline_unit_safe_fallback(monkeypatch):
    """OFFLINE UNIT TEST: Verifies pipeline status API exposes safe status even if Flink is offline."""
    from pulse.stream.flink import manager
    class MockOfflineManager:
        def get_metrics(self):
            return None
    
    monkeypatch.setattr(manager, "get_flink_manager", lambda: MockOfflineManager())
    with TestClient(app) as c:
        res = c.get("/api/pipeline/status")
        assert res.status_code == 200
        data = res.json()
        assert "flink" in data
        assert data["flink"]["status"] in {"UNKNOWN", "DEGRADED", "OFFLINE"}


def test_14_kafka_transport_status():
    """Verify pipeline reports active Kafka broker transport and connection status."""
    with TestClient(app) as c:
      res = c.get("/api/pipeline/status")
      assert res.status_code == 200
      kafka = res.json()["kafka"]
      assert "connected" in kafka
      assert "transport" in kafka


def test_15_pipeline_lab_metrics():
    """Verify pipeline lab metrics and verification report runs endpoints."""
    res_runs = client.get("/api/pipeline/verification-runs")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    assert isinstance(runs, list)
    if runs:
      assert "run_id" in runs[0]
      assert "stages_passed" in runs[0]

    res_lineage = client.get("/api/pipeline/lineage")
    assert res_lineage.status_code == 200
    assert isinstance(res_lineage.json(), list)


def test_16_replay_versus_simulation_labels():
    """Verify that session and snapshot expose separate DATA MODE and PIPELINE STATUS."""
    res = client.get("/api/session")
    assert res.status_code == 200
    sess = res.json()
    assert sess["mode"] in {"SIMULATED", "REPLAY", "LIVE"}
    assert "pipelineStatus" in sess
    assert sess["pipelineStatus"] in {
        "CONNECTED",
        "PROCESSING",
        "DEGRADED",
        "FAILED",
    }


def test_17_sse_endpoint_connects():
    """Verify that SSE endpoint /api/stream establishes valid event-stream headers and emits initial snapshot."""
    with client.stream("GET", "/api/stream?limit=1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        lines = [line for line in response.iter_lines() if line]
        assert any("snapshot" in line or "event:" in line or "data:" in line for line in lines)
