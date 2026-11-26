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
    assert len(data["active_agents"]) == 6


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

    # Direct seek endpoint test
    seek_res = client.post("/api/replay/seek", json={"target_index": 2})
    assert seek_res.status_code == 200
    assert seek_res.json()["currentIndex"] == 2

    # Action-based seek endpoint test
    action_seek_res = client.post("/api/replay/seek", json={"action": "seek", "target_index": 1})
    assert action_seek_res.status_code == 200

    # Run controls seek endpoint test
    run_seek_res = client.post("/api/runs/test-run-123/controls", json={"action": "seek", "target_index": 3})
    assert run_seek_res.status_code == 200
    assert run_seek_res.json()["status"] == "success"

    cleanup_res = client.post("/api/replay/reset")
    assert cleanup_res.status_code == 200


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


def test_api_security_cors_and_optional_control_key(monkeypatch):
    import pulse.config as pcfg

    # 1. CORS restricts untrusted origin and permits configured localhost origin
    r_ok = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r_ok.headers.get("access-control-allow-origin") == "http://localhost:5173"

    r_bad = client.options(
        "/api/health",
        headers={"Origin": "https://untrusted.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r_bad.headers.get("access-control-allow-origin") != "https://untrusted.example.com"
    assert r_bad.headers.get("access-control-allow-origin") != "*"

    # 2. Invalid session_id traversal rejected before handler
    bad_sel = client.post("/api/sessions/select", json={"session_id": "../secret"})
    assert bad_sel.status_code == 422

    # 3. Optional PULSE_API_KEY blocks unauthenticated control routes while allowing reads
    monkeypatch.setenv("PULSE_API_KEY", "test-secret-phase-i-key")
    pcfg.get_settings.cache_clear()
    try:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/replay/pause").status_code == 401
        assert client.post("/api/sessions/select", json={"session_id": "f1-2023-silverstone-race"}).status_code == 401
        assert client.post("/api/integrity/lab-scenario", json={"scenario_id": "monaco_p3_uncertainty"}).status_code == 401

        auth_res = client.post("/api/replay/pause", headers={"X-PULSE-API-Key": "test-secret-phase-i-key"})
        assert auth_res.status_code == 200

        bearer_res = client.post("/api/replay/reset", headers={"Authorization": "Bearer test-secret-phase-i-key"})
        assert bearer_res.status_code == 200
    finally:
        monkeypatch.delenv("PULSE_API_KEY", raising=False)
        pcfg.get_settings.cache_clear()

