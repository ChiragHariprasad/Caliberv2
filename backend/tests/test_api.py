import pytest
from fastapi.testclient import TestClient

from pulse.main import app

client = TestClient(app)


def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"


def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "active_agents" in data
    assert len(data["active_agents"]) == 5


def test_api_session():
    response = client.get("/api/session")
    assert response.status_code == 200
    data = response.json()
    assert "sessionName" in data
    assert "lap" in data
    assert "mode" in data


def test_api_drivers():
    response = client.get("/api/drivers")
    assert response.status_code == 200
    drivers = response.json()
    assert isinstance(drivers, list)
    assert len(drivers) > 0
    # Check driver 16 is in the list
    numbers = [d["number"] for d in drivers]
    assert 16 in numbers


def test_api_timeline():
    response = client.get("/api/timeline")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_assessments():
    response = client.get("/api/assessments")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_strategy():
    response = client.get("/api/strategy")
    assert response.status_code == 200
    strategies = response.json()
    assert isinstance(strategies, list)
    assert len(strategies) >= 3


def test_api_track():
    response = client.get("/api/track")
    assert response.status_code == 200
    sectors = response.json()
    assert len(sectors) == 3


def test_api_operations():
    response = client.get("/api/operations")
    assert response.status_code == 200
    ops = response.json()
    assert "pipeline" in ops
    assert "runner" in ops


def test_api_snapshot():
    response = client.get("/api/snapshot")
    assert response.status_code == 200
    snap = response.json()
    for field in ["mode", "sessionName", "lap", "drivers", "timeline", "assessments", "strategies", "sectors"]:
        assert field in snap


def test_api_replay_controls():
    pause_res = client.post("/api/replay/pause")
    assert pause_res.status_code == 200
    assert pause_res.json()["runner_status"] == "PAUSED"

    resume_res = client.post("/api/replay/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["runner_status"] == "RUNNING"

    speed_res = client.post("/api/replay/speed", json={"speed": 2.0})
    assert speed_res.status_code == 200
    assert speed_res.json()["speed"] == 2.0


def test_api_findings_and_agents_transparency():
    # Test findings endpoint
    res_f = client.get("/api/findings")
    assert res_f.status_code == 200
    assert isinstance(res_f.json(), list)

    # Test agents transparency endpoints
    res_a = client.get("/api/agents")
    assert res_a.status_code == 200
    assert isinstance(res_a.json(), list)

    res_m = client.get("/api/agents/metrics")
    assert res_m.status_code == 200
    assert isinstance(res_m.json(), dict)
