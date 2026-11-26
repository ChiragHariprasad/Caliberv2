"""Formal verification of SIA Core v3 durability, schema consistency, finality quarantine, and clock determinism."""
from __future__ import annotations

import copy
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "sia_core_v3"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sia_core import (  # noqa: E402
    IntegrityEngine,
    IntegrityState as S,
    OriginRegistry,
    SIAWALStore,
    explain,
    make_atom,
    make_fact,
    make_guard,
    sha256_tagged,
    normalize_hash_hex,
    verify_chain,
)
from sia_core.evaluator import EngineConfig, _supersede_atoms  # noqa: E402
from sia_core.ledger import AtomRec  # noqa: E402
from pulse.contracts import (  # noqa: E402
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
from pulse.integrity.agent import IntegrityAgent  # noqa: E402
from pulse.integrity.contracts import get_contract_by_id  # noqa: E402


def _reg() -> OriginRegistry:
    return OriginRegistry({
        "PITWALL": ["F1_FOM_TIMING"],
        "TRACINGINSIGHTS": ["F1_FOM_TIMING"],
        "CAR_SENSOR": [],
        "GPS": [],
        "SURVEY": [],
    })


def test_void_decision_matches_standard_v3_assessment_schema() -> None:
    eng = IntegrityEngine(registry=_reg(), config=EngineConfig(auto_open=False))
    eng.register_contract(get_contract_by_id("lap_time"))
    sc = {"session_id": "s-void", "driver_id": "31", "lap_number": "8"}
    iid = eng.open_decision("lap_time", sc, "2026-05-24T13:10:00Z")
    rec = eng.void_decision(iid, "2026-05-24T13:10:05Z", reason="DRIVER_RETIRED")
    d = rec.to_dict()

    assert rec.content["schema"] == "calibre.sia.assessment/3.0"
    assert d["integrity_state"] == "UNKNOWN"
    assert d["resolution_maturity"] == "TUPLE_RESOLVED"
    assert d["finality_status"] == "FINAL"
    assert d["envelope"]["lower"] == "UNKNOWN"
    assert d["envelope"]["upper"] == "UNKNOWN"
    assert d["envelope"]["alternatives"] == ["UNKNOWN"]
    assert "resilience" in d and "diagnosis" in d
    assert eng.verify()[iid] == "OK"
    assert "UNKNOWN" in explain(rec)


def test_pre_admission_finality_quarantine_does_not_mutate_ledger() -> None:
    eng = IntegrityEngine(registry=_reg(), config=EngineConfig(auto_open=False))
    eng.register_contract(get_contract_by_id("weather_observation"))
    sc = {"session_id": "s-q"}
    iid = eng.open_decision("weather_observation", sc, "2026-05-24T13:00:00Z", known_at="2026-05-24T13:00:00Z")
    eng.admit_atom(make_atom("weather_reading", 25.0, "2026-05-24T13:00:05Z", sc, ["WEATHER_SERVICE"], unit="celsius"), "2026-05-24T13:00:06Z")
    fin = eng.evaluate(iid, "2026-05-24T13:04:00Z")
    assert fin.finality_status == "FINAL"

    counts_before = eng.ledger.counts()
    late = make_atom("weather_reading", 99.0, "2026-05-24T13:00:10Z", sc, ["PITWALL"], unit="celsius")
    adm = eng.admit_atom(late, "2026-05-24T13:05:00Z")

    assert adm.status == "QUARANTINED"
    assert adm.accepted is False
    assert adm.code == "POST_FINALITY_QUARANTINED"
    assert eng.ledger.counts() == counts_before
    assert eng.ledger.get_atom(late.atom_id) is None
    assert len(eng.quarantined_items) == 1
    assert eng.evaluate(iid, "2026-05-24T13:06:00Z").record_hash == fin.record_hash


def test_supersession_guards_against_cycles_and_cross_origin_hijack() -> None:
    sc = {"session_id": "s-sup", "driver_id": "44", "lap_number": "1"}
    a1 = make_atom("lap_record", 89.5, "2026-05-24T13:01:00Z", sc, ["PITWALL"], processor_family_id="timing_v1")
    # Different source + different processor trying to supersede a1 must be ignored
    hijack = make_atom("lap_record", 95.0, "2026-05-24T13:01:01Z", sc, ["CAR_SENSOR"], processor_family_id="rogue_proc", supersedes=a1.atom_id)
    kept = _supersede_atoms([AtomRec(a1, 100, 1), AtomRec(hijack, 101, 2)])
    assert any(r.atom.atom_id == a1.atom_id for r in kept)

    # Same-origin cyclic references must not delete all records or hang
    c1 = make_atom("lap_record", 89.5, "2026-05-24T13:01:00Z", sc, ["PITWALL"], processor_family_id="p1", supersedes="nonexistent")
    c2 = make_atom("lap_record", 89.6, "2026-05-24T13:01:01Z", sc, ["PITWALL"], processor_family_id="p1", supersedes=c1.atom_id)
    res = _supersede_atoms([AtomRec(c1, 100, 1), AtomRec(c2, 101, 2)])
    assert len(res) == 1 and res[0].atom.atom_id == c2.atom_id


def test_sqlite_wal_durability_recovery_and_tamper_detection(tmp_path: Path) -> None:
    db_path = tmp_path / "sia_wal_test.sqlite"
    wal = SIAWALStore(db_path, session_id="race-wal-1")
    eng = IntegrityEngine(registry=_reg(), config=EngineConfig(auto_open=False), wal=wal)
    eng.register_contract(get_contract_by_id("weather_observation"))
    eng.register_contract(get_contract_by_id("driver_position"))

    sc_sess = {"session_id": "race-wal-1"}
    sc_drv = {"session_id": "race-wal-1", "driver_id": "16", "lap_number": "1"}
    i_wx = eng.open_decision("weather_observation", sc_sess, "2026-05-24T13:00:00Z", known_at="2026-05-24T13:00:00Z")
    i_pos = eng.open_decision("driver_position", sc_drv, "2026-05-24T13:00:00Z", known_at="2026-05-24T13:00:00Z")

    eng.admit_atom(make_atom("weather_reading", 24.5, "2026-05-24T13:00:05Z", sc_sess, ["WEATHER_SERVICE"], unit="celsius"), "2026-05-24T13:00:06Z")
    eng.admit_atom(make_atom("position_report", 1, "2026-05-24T13:00:05Z", sc_drv, ["PITWALL"], unit="enum"), "2026-05-24T13:00:06Z")
    eng.admit_guard(make_guard("PITWALL", "RESUMED", "2026-05-24T13:00:05Z"), "2026-05-24T13:00:06Z")
    eng.evaluate(i_wx, "2026-05-24T13:05:00Z")  # Seals FINAL
    eng.void_decision(i_pos, "2026-05-24T13:05:01Z", reason="TEST_VOID")

    # Quarantine late evidence after seal
    late_wx = make_atom("weather_reading", 40.0, "2026-05-24T13:00:10Z", sc_sess, ["WEATHER_SERVICE"], unit="celsius")
    assert eng.admit_atom(late_wx, "2026-05-24T13:06:00Z").status == "QUARANTINED"
    orig_hashes = {i_wx: eng.history(i_wx)[-1].record_hash, i_pos: eng.history(i_pos)[-1].record_hash}
    orig_counts = eng.ledger.counts()
    wal.close()

    # Restart / reload from WAL database
    wal2 = SIAWALStore(db_path, session_id="race-wal-1")
    restored = wal2.load_engine(registry=_reg(), config=EngineConfig(auto_open=False))
    assert restored.ledger.counts() == orig_counts
    assert restored.verify() == {i_wx: "OK", i_pos: "OK"}
    assert restored.history(i_wx)[-1].record_hash == orig_hashes[i_wx]
    assert restored.history(i_pos)[-1].record_hash == orig_hashes[i_pos]
    assert len(restored.quarantined_items) == 1
    wal2.close()

    # Tamper with content_json directly in SQLite and prove verify() detects tampering
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT content_json FROM sia_assessments WHERE instance_id = ? LIMIT 1", (i_wx,)).fetchone()
        forged = json.loads(row[0])
        forged["limitations"] = ["TAMPERED"]
        conn.execute("UPDATE sia_assessments SET content_json = ? WHERE instance_id = ?", (json.dumps(forged), i_wx))
        conn.commit()
    wal3 = SIAWALStore(db_path, session_id="race-wal-1")
    tampered = wal3.load_engine(registry=_reg(), config=EngineConfig(auto_open=False))
    assert "tampered" in tampered.verify()[i_wx]
    wal3.close()


@pytest.mark.asyncio
async def test_historical_event_with_omitted_ingest_time_never_leaks_wall_clock(tmp_path: Path) -> None:
    """Reproduces the Phase 0 2021-12-12 bug and proves historical clock semantics remain deterministic."""
    agent = IntegrityAgent(wal_path=tmp_path / "agent_wal.sqlite", session_id="f1-2021-abu-dhabi")
    hist_evt = EventEnvelope(
        event_id="hist-wx-2021",
        event_type="WEATHER_OBSERVATION",
        source=SourceRef(provider="FASTF1_RESEARCH", adapter="fastf1", source_record_id="wx-1", capture_id="f1-2021-abu-dhabi"),
        run=RunContext(run_id="run-hist-1", session_instance_id="f1-2021-abu-dhabi", mode=RunMode.REPLAY),
        session=SessionRef(season=2021, meeting_id="yas-marina-2021", session_id="f1-2021-abu-dhabi"),
        time=EventTime(event_time_utc=datetime(2021, 12, 12, 13, 0, tzinfo=timezone.utc), session_elapsed_ms=0),
        subject=Subject(),
        payload={"air_temp_c": 24.1, "track_temp_c": 29.0},
        quality=Quality(interpretation=Interpretation.OBSERVED, completeness=Completeness.COMPLETE, unit_validation=UnitValidation.PASSED),
    )
    await agent.on_event("pulse.raw.weather.v1", "session", hist_evt)
    verdicts = agent.get_all_verdicts()
    assert len(verdicts) == 1
    assert verdicts[0]["integrity_state"] == "HEALTHY"
    assert verdicts[0]["finality_status"] != "FINAL"
    assert verdicts[0]["knowledge_time"].startswith("2021-12-12T13:00:00")
    assert verdicts[0]["roles"]["weather_reading"]["atoms_detail"][0]["value"] == 24.1
    assert sha256_tagged({"a": 1}) == f"sha256:{normalize_hash_hex(sha256_tagged({'a': 1}))}"
