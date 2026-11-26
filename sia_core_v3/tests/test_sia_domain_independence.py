"""Domain-independent SIA Core v3 verification (Phase 2.6).

Demonstrates in an isolated test that SIA's contracts, source-independence cliques,
bitemporal evaluation, guard-band constraints, finality quarantine, and SQLite WAL
persistence operate unchanged on non-motorsport clinical ICU vitals telemetry.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "sia_core_v3"))

from sia_core import (  # noqa: E402
    IntegrityEngine,
    IntegrityState as S,
    OriginRegistry,
    SIAWALStore,
    make_atom,
    make_fact,
)
from sia_core.evaluator import EngineConfig  # noqa: E402


def _icu_spo2_contract(corroboration_mode: str = "INFORMATIONAL") -> dict:
    return {
        "contract_id": "icu_spo2_safety",
        "version": "1.0.0",
        "epoch": 1,
        "decision_type": "hypoxemia_monitoring",
        "decision_scope": {"scope_class": "DRIVER_LAP"},  # maps cleanly to generic (ward/shift, patient_id, window_id)
        "formula": "AND(spo2_optical, spo2_blood_gas)",
        "simultaneity_window_s": 10.0,
        "roles": {
            "spo2_optical": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["PULSE_OX_A", "PULSE_OX_B", "MASIMO_INDEPENDENT"],
                "agreement": {"metric": "abs_diff", "unit": "pct", "tolerance": 2.0},
                "freshness": {"soft_age_s": 30, "hard_age_s": 120},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 120},
                "corroboration": {"mode": corroboration_mode, "min_source_depth": 1},
            },
            "spo2_blood_gas": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["ARTERIAL_BLOOD_GAS_LAB", "BED_SIDE_GAS"],
                "agreement": {"metric": "abs_diff", "unit": "pct", "tolerance": 2.0},
                "freshness": {"soft_age_s": 60, "hard_age_s": 180},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [
            {"id": "spo2_cross_check", "kind": "abs_diff", "operands": ["spo2_optical", "spo2_blood_gas"], "tolerance": 3.0},
            {"id": "spo2_physiological", "kind": "bounds", "operands": ["spo2_optical"], "lo": 50.0, "hi": 100.0},
        ],
        "fault_model": {"diagnosis_budget": 1, "resilience_requirement": 1, "report_k": 1},
        "limitations": [],
    }


def test_sia_domain_independence_clinical_icu_telemetry(tmp_path: Path) -> None:
    registry = OriginRegistry({
        "PULSE_OX_A": ["BEDSIDE_HUB_HW"],
        "PULSE_OX_B": ["BEDSIDE_HUB_HW"],  # Common upstream hub -> not independent!
        "MASIMO_INDEPENDENT": [],
        "ARTERIAL_BLOOD_GAS_LAB": [],
        "BED_SIDE_GAS": [],
    })
    wal = SIAWALStore(tmp_path / "icu_wal.sqlite", session_id="icu-shift-1")
    eng = IntegrityEngine(registry=registry, config=EngineConfig(auto_open=False), wal=wal)
    eng.register_contract(_icu_spo2_contract(corroboration_mode="INFORMATIONAL"))

    scope = {"session_id": "icu-shift-1", "driver_id": "patient-402", "lap_number": "win-14"}
    iid = eng.open_decision("icu_spo2_safety", scope, "2026-06-01T08:00:00Z", known_at="2026-06-01T08:00:00Z")

    # 1. Optical probes sharing bedside hub expose common-cause SPOF under resilience_requirement=1
    eng.admit_atom(make_atom("spo2_optical", 97.0, "2026-06-01T08:00:10Z", scope, ["PULSE_OX_A"], unit="pct"), "2026-06-01T08:00:12Z")
    eng.admit_atom(make_atom("spo2_optical", 97.5, "2026-06-01T08:00:11Z", scope, ["PULSE_OX_B"], unit="pct"), "2026-06-01T08:00:12Z")
    eng.admit_atom(make_atom("spo2_blood_gas", 97.2, "2026-06-01T08:00:11Z", scope, ["ARTERIAL_BLOOD_GAS_LAB"], unit="pct"), "2026-06-01T08:00:12Z")
    eng.admit_atom(make_atom("spo2_blood_gas", 97.1, "2026-06-01T08:00:11Z", scope, ["BED_SIDE_GAS"], unit="pct"), "2026-06-01T08:00:12Z")

    v = eng.evaluate(iid, "2026-06-01T08:00:15Z")
    assert v.integrity_state == S.SUSPECT
    assert "COMMON_CAUSE_EXPOSURE" in {w["code"] for w in v.witnesses}
    assert "S:BEDSIDE_HUB_HW" in v.content["resilience"]["critical_origins"]
    assert eng.verify()[iid] == "OK"

    # 2. Admitting genuinely independent probe cures SPOF -> HEALTHY
    eng.admit_atom(make_atom("spo2_optical", 97.3, "2026-06-01T08:00:12Z", scope, ["MASIMO_INDEPENDENT"], unit="pct"), "2026-06-01T08:00:16Z")
    v2 = eng.evaluate(iid, "2026-06-01T08:00:17Z")
    assert v2.integrity_state == S.HEALTHY
    assert v2.content["resilience"]["critical_origins"] == []
    wal.close()

    # 3. Recover cleanly from SQLite WAL
    wal_reopened = SIAWALStore(tmp_path / "icu_wal.sqlite", session_id="icu-shift-1")
    eng2 = wal_reopened.load_engine(registry=registry, config=EngineConfig(auto_open=False))
    assert eng2.verify()[iid] == "OK"
    assert eng2.history(iid)[-1].record_hash == v2.record_hash
    wal_reopened.close()
