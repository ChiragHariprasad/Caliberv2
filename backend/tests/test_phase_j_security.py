"""Phase J Security Acceptance & Fail-Closed Configuration Tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pulse.config import DEFAULT_LOCAL_CORS_ORIGINS, Settings, get_settings
from pulse.main import create_app
from pulse.state.store import get_state_store


STRONG_KEY = "pulse-phase-j-demo-control-key-0123456789"


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mem_env(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
    monkeypatch.setenv("PULSE_TRANSPORT_MODE", "MEMORY")
    monkeypatch.setenv("PULSE_SIA_WAL_PATH", "")
    for k, v in overrides.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    get_settings.cache_clear()


def test_security_posture_fail_closed_shared_demo_and_external(monkeypatch: pytest.MonkeyPatch):
    """Shared-demo, auth-required, and non-loopback configs must fail closed on unsafe defaults."""
    # 1. Shared demo without API key must fail closed
    _mem_env(monkeypatch, PULSE_ENV="shared-demo", PULSE_API_KEY="", PULSE_CONTROL_API_KEY="", PULSE_HOST="127.0.0.1")
    with pytest.raises(ValueError, match="PULSE_API_KEY"):
        create_app()

    # 2. Explicit PULSE_REQUIRE_CONTROL_AUTH=true with weak/placeholder key must fail closed
    _mem_env(monkeypatch, PULSE_ENV="development", PULSE_REQUIRE_CONTROL_AUTH="true", PULSE_API_KEY="changeme")
    with pytest.raises(ValueError, match="16 non-placeholder"):
        Settings().validate_security_posture()

    _mem_env(monkeypatch, PULSE_ENV="development", PULSE_REQUIRE_CONTROL_AUTH="true", PULSE_API_KEY="short-key")
    with pytest.raises(ValueError, match="16 non-placeholder"):
        Settings().validate_security_posture()

    # 3. Externally bound host (0.0.0.0) cannot run with empty key OR permissive default local CORS
    _mem_env(monkeypatch, PULSE_ENV="development", PULSE_REQUIRE_CONTROL_AUTH="false", PULSE_HOST="0.0.0.0", PULSE_API_KEY="")
    with pytest.raises(ValueError, match="PULSE_API_KEY"):
        create_app()

    _mem_env(
        monkeypatch,
        PULSE_ENV="development",
        PULSE_HOST="0.0.0.0",
        PULSE_API_KEY=STRONG_KEY,
        PULSE_CORS_ORIGINS=DEFAULT_LOCAL_CORS_ORIGINS,
    )
    with pytest.raises(ValueError, match="local-development CORS origins"):
        create_app()

    # 4. Production/external env rejects localhost origins and wildcard '*'
    _mem_env(
        monkeypatch,
        PULSE_ENV="production",
        PULSE_HOST="0.0.0.0",
        PULSE_API_KEY=STRONG_KEY,
        PULSE_CORS_ORIGINS="http://localhost:5173",
    )
    with pytest.raises(ValueError, match="localhost CORS origins are forbidden"):
        create_app()

    _mem_env(
        monkeypatch,
        PULSE_ENV="shared-demo",
        PULSE_HOST="127.0.0.1",
        PULSE_API_KEY=STRONG_KEY,
        PULSE_CORS_ORIGINS="*",
    )
    with pytest.raises(ValueError, match="wildcard CORS origin"):
        create_app()

    # 5. Valid hardened shared-demo / external configuration succeeds
    _mem_env(
        monkeypatch,
        PULSE_ENV="shared-demo",
        PULSE_HOST="0.0.0.0",
        PULSE_API_KEY=STRONG_KEY,
        PULSE_CORS_ORIGINS="https://pulse-demo.lab.example",
    )
    app = create_app()
    assert app is not None


def test_control_api_key_enforcement_all_mutations_and_runtime_fail_closed(monkeypatch: pytest.MonkeyPatch):
    """Test missing, invalid, valid (X-PULSE-API-Key & Bearer), and runtime missing key fail-closed."""
    _mem_env(
        monkeypatch,
        PULSE_ENV="shared-demo",
        PULSE_HOST="127.0.0.1",
        PULSE_API_KEY=STRONG_KEY,
        PULSE_CORS_ORIGINS="http://localhost:5173",
    )
    app = create_app()
    mutating_calls = [
        ("POST", "/api/sessions/select", {"session_id": "f1-2023-silverstone-race"}),
        ("POST", "/api/replay/start", None),
        ("POST", "/api/replay/pause", None),
        ("POST", "/api/replay/resume", None),
        ("POST", "/api/replay/reset", None),
        ("POST", "/api/replay/seek", {"target_index": 0}),
        ("POST", "/api/replay/speed", {"speed": 2.0}),
        ("POST", "/api/replay/pause", None),
        ("POST", "/api/runs/run-check/controls", {"action": "pause"}),
        ("POST", "/api/integrity/lab-scenario", {"scenario_id": "monaco_pit_bias"}),
    ]

    with TestClient(app) as client:
        # Read-only endpoints stay readable in shared-demo auth mode
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/integrity/summary").status_code == 200

        # Missing & invalid keys must be rejected with 401 on EVERY mutating control route
        for method, path, payload in mutating_calls:
            res_missing = client.request(method, path, json=payload)
            assert res_missing.status_code == 401, f"{path} allowed missing key"

            res_bad_hdr = client.request(method, path, json=payload, headers={"X-PULSE-API-Key": "wrong-key"})
            assert res_bad_hdr.status_code == 401, f"{path} allowed bad X-PULSE-API-Key"

            res_bad_bearer = client.request(method, path, json=payload, headers={"Authorization": "Bearer wrong-key"})
            assert res_bad_bearer.status_code == 401, f"{path} allowed bad Bearer token"

        # Valid X-PULSE-API-Key and Authorization: Bearer succeed on control routes
        assert client.post("/api/replay/pause", headers={"X-PULSE-API-Key": STRONG_KEY}).status_code == 200
        assert client.post(
            "/api/replay/speed",
            json={"speed": 2.0},
            headers={"Authorization": f"Bearer {STRONG_KEY}"},
        ).status_code == 200
        assert client.post(
            "/api/integrity/lab-scenario",
            json={"scenario_id": "monaco_pit_bias"},
            headers={"X-PULSE-API-Key": STRONG_KEY},
        ).status_code == 200

        # Runtime defense-in-depth: if auth is required but key becomes unset at runtime, fail closed (503, never 200!)
        monkeypatch.setenv("PULSE_API_KEY", "")
        monkeypatch.setenv("PULSE_CONTROL_API_KEY", "")
        get_settings.cache_clear()
        res_fail_closed = client.post("/api/replay/pause", headers={"X-PULSE-API-Key": ""})
        assert res_fail_closed.status_code == 503


def test_cors_allowlist_session_isolation_and_sse_limits(monkeypatch: pytest.MonkeyPatch):
    """Verify CORS origin allowlist, session/run isolation, and SSE connection limit enforcement."""
    _mem_env(
        monkeypatch,
        PULSE_ENV="shared-demo",
        PULSE_HOST="127.0.0.1",
        PULSE_API_KEY=STRONG_KEY,
        PULSE_CORS_ORIGINS="https://trusted.pulse.edu,http://localhost:5173",
        PULSE_MAX_SSE_LISTENERS="2",
    )
    app = create_app()
    store = get_state_store()
    original_listeners = list(store._listeners)
    store._listeners.clear()

    try:
        with TestClient(app) as client:
            # 1. CORS allowlist check
            ok_preflight = client.options(
                "/api/replay/pause",
                headers={
                    "Origin": "https://trusted.pulse.edu",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "X-PULSE-API-Key,Content-Type",
                },
            )
            assert ok_preflight.headers.get("access-control-allow-origin") == "https://trusted.pulse.edu"

            bad_get = client.get("/api/health", headers={"Origin": "https://attacker.example"})
            assert bad_get.status_code == 200
            assert "access-control-allow-origin" not in bad_get.headers

            # 2. Session isolation: inactive registered session reads must fail closed with 409, unknown with 404
            sessions = client.get("/api/sessions").json()
            active_sess = client.get("/api/session").json()
            active_sid = active_sess["sessionId"]
            other_sids = [s["session_id"] for s in sessions if s["session_id"] != active_sid]
            assert other_sids, "Expected multiple registered sessions for isolation check"
            inactive_sid = other_sids[0]

            for scoped in ("drivers", "timeline", "track", "strategy", "assessments"):
                assert client.get(f"/api/sessions/{active_sid}/{scoped}").status_code == 200
                assert client.get(f"/api/sessions/{inactive_sid}/{scoped}").status_code == 409
                assert client.get(f"/api/sessions/nonexistent_session_xyz/{scoped}").status_code == 404

            assert client.post(
                "/api/sessions/select",
                json={"session_id": "../../etc/passwd"},
                headers={"X-PULSE-API-Key": STRONG_KEY},
            ).status_code == 422
            assert client.post(
                "/api/sessions/select",
                json={"session_id": "nonexistent_session_xyz"},
                headers={"X-PULSE-API-Key": STRONG_KEY},
            ).status_code == 404

            # 3. SSE listener limit (max_sse_listeners=2 -> 3rd returns HTTP 429; freeing releases capacity)
            q1 = store.try_add_listener(get_settings().max_sse_listeners)
            q2 = store.try_add_listener(get_settings().max_sse_listeners)
            assert q1 is not None and q2 is not None
            assert store.try_add_listener(get_settings().max_sse_listeners) is None

            res_429 = client.get("/api/stream?limit=1")
            assert res_429.status_code == 429

            store.remove_listener(q1)
            res_ok = client.get("/api/stream?limit=1")
            assert res_ok.status_code == 200
            store.remove_listener(q2)
            assert len(store._listeners) == 0
    finally:
        store._listeners[:] = original_listeners
