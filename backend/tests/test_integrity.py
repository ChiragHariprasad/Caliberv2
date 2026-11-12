"""Tests for SIA Core v3 Integration into PULSE as Agent 6 (IntegrityAgent).

Validates:
1. Contract loading, schema conformity, and validation (V-01..V-12).
2. Bridge translations (envelope -> atom, scope extraction, role mapping).
3. IntegrityAgent initialization, transparency metrics, and lifecycle.
4. End-to-end event flow: EventEnvelope -> atom admission -> tick -> integrity finding.
5. Hash-chained ledger integrity and bitemporal index verification.
6. FastAPI REST endpoints at /api/integrity/*.
7. SSE state notification integration with StateStore.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

# Ensure SIA Core v3 is importable
repo_root = Path(__file__).resolve().parents[2]
sia_path = repo_root / "sia_core_v3"
if str(sia_path) not in sys.path:
    sys.path.insert(0, str(sia_path))

from sia_core.contract import parse_contract, validate_contract
from pulse.integrity.contracts import (
    get_default_contracts,
    get_contract_by_id,
    load_contracts_for_session,
)
from pulse.integrity.bridge import (
    envelope_to_atom,
    extract_scope,
    map_event_to_roles,
    quality_grade,
    sia_assessment_to_dict,
    build_origin_registry,
)
from pulse.integrity.agent import IntegrityAgent
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
    utc_now,
)
from pulse.main import app
from pulse.state.store import get_state_store

client = TestClient(app)


def make_test_envelope(
    event_id: str,
    event_type: str,
    payload: dict,
    driver_number: int | None = None,
    elapsed_ms: int = 1000,
    session_id: str = "f1-2026-monaco-sim",
    interpretation: Interpretation = Interpretation.OBSERVED,
) -> EventEnvelope:
    """Helper to generate valid EventEnvelope for testing."""
    now = datetime.now(timezone.utc)
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        source=SourceRef(
            provider="PITWALL",
            adapter="telemetry_v1",
            source_record_id=f"src-{event_id}",
            capture_id="f1-2026-monaco-sim",
        ),
        run=RunContext(
            run_id="run-integrity-test",
            session_instance_id=session_id,
            mode=RunMode.SIMULATED,
        ),
        session=SessionRef(
            season=2026,
            meeting_id="monaco-2026",
            session_id=session_id,
            session_type="RACE",
        ),
        time=EventTime(
            event_time_utc=now,
            session_elapsed_ms=elapsed_ms,
            ingest_time_utc=now,
        ),
        subject=Subject(driver_number=driver_number),
        payload=payload,
        quality=Quality(
            interpretation=interpretation,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )


# ---------------------------------------------------------------------------
# 1. Contract loading and validation
# ---------------------------------------------------------------------------


def test_contracts_loading_and_validation():
    """All 5 Decision Evidence Contracts must parse and pass SIA Core v3 validation."""
    contracts = get_default_contracts()
    assert len(contracts) == 5

    expected_ids = {
        "lap_time",
        "pit_speed",
        "sector_time",
        "driver_position",
        "weather_observation",
    }
    c_map = {c["contract_id"]: c for c in contracts}
    assert set(c_map.keys()) == expected_ids

    for cid, cdef in c_map.items():
        parsed = parse_contract(cdef)
        assert parsed.contract_id == cid
        assert parsed.version == "1.0.0"
        val = validate_contract(parsed)
        assert val.ok, f"Contract {cid} failed validation: {val.errors}"


# ---------------------------------------------------------------------------
# 2. Bridge translations
# ---------------------------------------------------------------------------


def test_bridge_extract_scope():
    """Extract scope from EventEnvelope into SIA scope dict."""
    env = make_test_envelope(
        event_id="evt-001",
        event_type="LAP_COMPLETED",
        payload={"lap_number": 14, "lap_time_seconds": 78.45},
        driver_number=44,
    )
    scope = extract_scope(env)
    assert scope["session_id"] == "f1-2026-monaco-sim"
    assert scope["driver_id"] == "44"
    assert scope["lap_number"] == "14"


def test_bridge_envelope_to_atom():
    """Map EventEnvelope to SIA Atom with correct content-addressed ID."""
    env = make_test_envelope(
        event_id="evt-lap-01",
        event_type="LAP_COMPLETED",
        payload={"lap_number": 12, "lap_time_seconds": 90.10},
        driver_number=44,
    )
    roles = map_event_to_roles("LAP_COMPLETED")
    assert "lap_record" in roles

    atom = envelope_to_atom(env, "lap_record")
    assert atom is not None
    assert atom.role_id == "lap_record"
    assert atom.value == 90.10
    assert atom.unit == "s"
    atom_scope = dict(atom.scope)
    assert atom_scope["driver_id"] == "44"
    assert atom_scope["lap_number"] == "12"
    assert atom.atom_id is not None
    assert len(atom.atom_id) == 64  # SHA-256


def test_bridge_quality_to_grade():
    """Ensure PULSE quality interpretation maps correctly to IntegrityState."""
    from sia_core import IntegrityState

    env_obs = make_test_envelope(
        event_id="e1", event_type="LAP_COMPLETED", payload={}, interpretation=Interpretation.OBSERVED
    )
    assert quality_grade(env_obs) == IntegrityState.HEALTHY

    env_der = make_test_envelope(
        event_id="e2", event_type="LAP_COMPLETED", payload={}, interpretation=Interpretation.DERIVED
    )
    assert quality_grade(env_der) == IntegrityState.HEALTHY

    env_est = make_test_envelope(
        event_id="e3", event_type="LAP_COMPLETED", payload={}, interpretation=Interpretation.INFERRED
    )
    assert quality_grade(env_est) == IntegrityState.SUSPECT


# ---------------------------------------------------------------------------
# 3. IntegrityAgent initialization & metadata
# ---------------------------------------------------------------------------


def test_integrity_agent_initialization():
    """IntegrityAgent initializes cleanly with 5 contracts and zero verdicts."""
    agent = IntegrityAgent()
    assert agent.agent_id == "agent-06-integrity"
    assert agent.name == "SIA Integrity Engine"
    assert len(agent.get_contracts()) == 5

    summary = agent.get_summary()
    assert summary["overall_state"] == "HEALTHY"
    assert summary["contract_count"] == 5
    assert summary["decision_count"] == 0
    assert summary["chain_verified"] is True


# ---------------------------------------------------------------------------
# 4. End-to-End Event Ingestion & Verdict Emission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integrity_agent_on_event_e2e():
    """Publishing events through IntegrityAgent admits atoms and emits integrity assessments."""
    agent = IntegrityAgent()

    # Session start event (admits session_t0)
    sess_env = make_test_envelope(
        event_id="evt-sess-01",
        event_type="SESSION_STARTED",
        payload={"session_name": "Monaco GP"},
        elapsed_ms=0,
    )
    await agent.on_event("pulse.race.events.v1", "session", sess_env)
    assert agent.inputs_received >= 1

    # Lap completed event (admits lap_start and lap_record)
    lap_env = make_test_envelope(
        event_id="evt-lap-44-12",
        event_type="LAP_COMPLETED",
        payload={"lap_number": 12, "lap_time_seconds": 90.15},
        driver_number=44,
        elapsed_ms=90150,
    )
    await agent.on_event("pulse.race.events.v1", "driver:44", lap_env)

    # Inspect engine decisions
    decisions = agent.get_decisions()
    assert len(decisions) >= 1

    # Inspect verdicts
    verdicts = agent.get_all_verdicts()
    assert len(verdicts) >= 1

    # Verify hash chain on all recorded decisions
    chains = agent.verify_chains()
    for dec_id, result in chains.items():
        assert result == "OK", f"Chain verification failed for {dec_id}: {result}"


# ---------------------------------------------------------------------------
# 5. REST API Endpoints
# ---------------------------------------------------------------------------


def test_api_integrity_summary():
    """GET /api/integrity/summary returns operational integrity metrics."""
    res = client.get("/api/integrity/summary")
    assert res.status_code == 200
    data = res.json()
    assert "overall_state" in data
    assert "contract_count" in data
    assert data["contract_count"] == 5
    assert "chain_verified" in data
    assert "state_distribution" in data


def test_api_integrity_contracts():
    """GET /api/integrity/contracts returns list of registered contracts."""
    res = client.get("/api/integrity/contracts")
    assert res.status_code == 200
    contracts = res.json()
    assert len(contracts) == 5
    ids = [c["contract_id"] for c in contracts]
    assert "lap_time" in ids
    assert "pit_speed" in ids


def test_api_integrity_ledger():
    """GET /api/integrity/ledger returns ledger statistics."""
    res = client.get("/api/integrity/ledger")
    assert res.status_code == 200
    data = res.json()
    assert "atoms" in data
    assert "facts" in data
    assert "guards" in data
    assert "rejections" in data


def test_api_integrity_verify():
    """GET /api/integrity/verify validates cryptographic hash chains."""
    res = client.get("/api/integrity/verify")
    assert res.status_code == 200
    data = res.json()
    assert "verified" in data
    assert "results" in data
    assert isinstance(data["results"], dict)


def test_api_integrity_decisions_and_verdicts():
    """GET /api/integrity/decisions and /api/integrity/verdicts contracts."""
    res_dec = client.get("/api/integrity/decisions")
    assert res_dec.status_code == 200
    assert isinstance(res_dec.json(), list)

    res_ver = client.get("/api/integrity/verdicts")
    assert res_ver.status_code == 200
    assert isinstance(res_ver.json(), list)


# ---------------------------------------------------------------------------
# 6. StateStore SSE Integration
# ---------------------------------------------------------------------------


def test_statestore_integrity_sse():
    """StateStore.notify_integrity_state pushes INTEGRITY_STATE_UPDATED event."""
    store = get_state_store()
    queue = store.add_listener()

    try:
        store.notify_integrity_state({
            "integrity_state": "HEALTHY",
            "decision_instance_id": "lap_time@monaco-2026|44|1",
            "verdict_hash": "abc123hash",
        })

        # Check queue
        assert not queue.empty()
        item = queue.get_nowait()
        assert item["type"] == "INTEGRITY_STATE_UPDATED"
        assert item["data"]["integrity_state"] == "HEALTHY"
        assert item["data"]["decision_instance_id"] == "lap_time@monaco-2026|44|1"
    finally:
        store.remove_listener(queue)
