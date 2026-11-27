"""Phase J Epistemic, Lattice, Finality & Common-Cause Audit Tests for SIA Core v3."""
from __future__ import annotations

import itertools

from sia_core import (
    EngineConfig,
    IntegrityEngine,
    IntegrityState as S,
    OriginRegistry,
    TimeClass,
    TypedTime,
    and_state,
    make_atom,
    make_guard,
    or_state,
    parse_contract,
)


def _project_multidim(content: dict) -> dict[str, str]:
    """Compare multidimensional verdict summary recovered strictly from EvalOutput.content."""
    roles = content.get("roles", {})
    witnesses = content.get("witnesses", [])
    w_codes = {w["code"] for w in witnesses}

    ev_roles = [r for r in roles.values() if r["kind"] == "evidence"]
    if not ev_roles or all(not r["has_evidence"] for r in ev_roles):
        availability = "MISSING"
    elif all(r["has_evidence"] for r in ev_roles):
        availability = "COMPLETE"
    else:
        availability = "PARTIAL"

    if w_codes & {"UNRESOLVED_CONFLICT", "CONSTRAINT_VIOLATION", "AMBIGUOUS_REFERENCE_FACT"}:
        consistency = "CONFLICTED"
    elif w_codes & {"LOW_QUALITY_EVIDENCE", "FUTURE_DATED_OBSERVATION", "TIME_BASIS_MISMATCH"}:
        consistency = "QUESTIONABLE"
    elif availability == "COMPLETE":
        consistency = "AGREED"
    else:
        consistency = "INCOMPLETE"

    res = content.get("resilience", {})
    if w_codes & {"INSUFFICIENT_CORROBORATION", "INSUFFICIENT_RESILIENCE"} or res.get("critical_origins"):
        corroboration = "DEPENDENT_OR_SINGLE_POINT"
    elif any(r.get("source_depth", 0) >= 1 for r in ev_roles):
        corroboration = "INDEPENDENT"
    else:
        corroboration = "UNCORROBORATED"

    return {
        "availability": availability,
        "consistency": consistency,
        "corroboration": corroboration,
        "finality": content.get("finality_status", "OPEN"),
    }


def _contract_spec(*, two_branch: bool = True, formula: str = "AND(branch_a, branch_b)", resilience_req: int = 0) -> dict:
    roles = {
        "branch_a": {
            "kind": "evidence",
            "scope_class": "DRIVER_LAP",
            "time_class_required": "ABSOLUTE_UTC",
            "admissible_source_origins": ["SRC_1", "SRC_2", "SRC_P1", "SRC_P2", "SRC_INDEP"],
            "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.1},
            "freshness": {"soft_age_s": 10, "hard_age_s": 30},
            "slot": {"deadline_s": 15, "allowed_lateness_s": 60},
            "corroboration": {"mode": "INFORMATIONAL", "min_source_depth": 0, "min_processing_depth": 0},
        },
    }
    if two_branch:
        roles["branch_b"] = {
            "kind": "evidence",
            "scope_class": "DRIVER_LAP",
            "time_class_required": "ABSOLUTE_UTC",
            "admissible_source_origins": ["SRC_B1", "SRC_B2"],
            "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.1},
            "freshness": {"soft_age_s": 10, "hard_age_s": 30},
            "slot": {"deadline_s": 15, "allowed_lateness_s": 60},
            "corroboration": {"mode": "INFORMATIONAL", "min_source_depth": 0, "min_processing_depth": 0},
        }
    return {
        "contract_id": "audit_contract",
        "version": "1.0.0",
        "epoch": 1,
        "decision_type": "audit_validation",
        "decision_scope": {"scope_class": "DRIVER_LAP"},
        "formula": formula,
        "simultaneity_window_s": 2.0,
        "roles": roles,
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": resilience_req, "report_k": 1},
        "limitations": [],
    }


def test_four_state_lattice_axioms_and_scalar_masking_vs_multidim_fidelity():
    """Verify distributive chain axioms and prove how scalar min/max masking preserves signal in EvalOutput.content."""
    states = list(S)
    assert [int(s) for s in states] == [0, 1, 2, 3]
    for a, b, c in itertools.product(states, repeat=3):
        assert and_state(a, b) == and_state(b, a)
        assert or_state(a, b) == or_state(b, a)
        assert and_state(a, or_state(b, c)) == or_state(and_state(a, b), and_state(a, c))
        assert or_state(a, and_state(b, c)) == and_state(or_state(a, b), or_state(a, c))
        assert and_state(a, or_state(a, b)) == a

    # Algebraic blind spots under total order DEGRADED(0) < UNKNOWN(1) < SUSPECT(2) < HEALTHY(3):
    assert and_state(S.SUSPECT, S.UNKNOWN) == S.UNKNOWN
    assert or_state(S.SUSPECT, S.HEALTHY) == S.HEALTHY
    assert or_state(S.DEGRADED, S.UNKNOWN) == S.UNKNOWN

    # Concrete engine verification: branch_a has active conflict (SUSPECT), branch_b is pending pre-deadline (UNKNOWN)
    t0 = "2026-01-01T12:00:00Z"
    scope = {"session_id": "s1", "driver_id": "1", "lap_number": "2"}
    eng = IntegrityEngine(OriginRegistry({}), EngineConfig())
    eng.register_contract(parse_contract(_contract_spec(two_branch=True, formula="AND(branch_a, branch_b)")))
    iid = eng.open_decision("audit_contract", scope, t0)
    tt = TypedTime(1767268800_000_000, TimeClass.ABSOLUTE_UTC)
    eng.admit_atom(make_atom("branch_a", 90.0, t0, scope, ["SRC_1"], time=tt), t0)
    eng.admit_atom(make_atom("branch_a", 95.0, t0, scope, ["SRC_2"], time=tt), t0)

    a = eng.evaluate(iid, "2026-01-01T12:00:05Z")
    # Scalar verdict collapses min(SUSPECT, UNKNOWN) -> UNKNOWN
    assert a.integrity_state == S.UNKNOWN
    # Yet EvalOutput.content preserves exact per-role state + UNRESOLVED_CONFLICT witness!
    assert a.content["roles"]["branch_a"]["timeline"][0]["state"] == "SUSPECT"
    assert a.content["roles"]["branch_b"]["timeline"][0]["state"] == "UNKNOWN"
    assert any(w["code"] == "UNRESOLVED_CONFLICT" for w in a.content["witnesses"])
    md = _project_multidim(a.content)
    assert md == {
        "availability": "PARTIAL",
        "consistency": "CONFLICTED",
        "corroboration": "UNCORROBORATED",
        "finality": "OPEN",
    }


def test_missing_vs_contradictory_stalled_and_common_cause_closure():
    """Verify missing (UNKNOWN->DEGRADED/STALLED) vs contradiction (SUSPECT) and transitive DAG common cause."""
    t0 = "2026-01-01T12:00:00Z"
    scope = {"session_id": "s1", "driver_id": "1", "lap_number": "3"}
    reg = OriginRegistry({
        "SRC_P1": ["SHARED_TIMING"],
        "SRC_P2": ["SHARED_TIMING"],
        "SRC_INDEP": [],
    })
    eng = IntegrityEngine(reg, EngineConfig())
    eng.register_contract(parse_contract(_contract_spec(two_branch=False, formula="branch_a", resilience_req=1)))
    iid_miss = eng.open_decision("audit_contract", scope, t0)
    sc4 = {**scope, "lap_number": "4"}
    iid_cc = eng.open_decision("audit_contract", sc4, t0)

    tt = TypedTime(1767268800_000_000, TimeClass.ABSOLUTE_UTC)
    assert eng.admit_atom(make_atom("branch_a", 88.0, t0, sc4, ["SRC_P1"], time=tt), t0).accepted
    assert eng.admit_atom(make_atom("branch_a", 88.02, t0, sc4, ["SRC_P2"], time=tt), t0).accepted

    # 1. Missing evidence pre-deadline is UNKNOWN
    a_open = eng.evaluate(iid_miss, "2026-01-01T12:00:05Z")
    assert a_open.integrity_state == S.UNKNOWN
    assert a_open.content["witnesses"] == []

    # 2. Two seemingly distinct feeds sharing transitive upstream SHARED_TIMING have depth=0 & single point of failure
    a_cc = eng.evaluate(iid_cc, "2026-01-01T12:00:05Z")
    assert a_cc.content["roles"]["branch_a"]["source_depth"] == 0
    assert a_cc.integrity_state == S.SUSPECT
    codes = {w["code"] for w in a_cc.content["witnesses"]}
    assert "COMMON_CAUSE_EXPOSURE" in codes
    assert "INSUFFICIENT_RESILIENCE" in codes

    # Adding truly disjoint independent source within simultaneity window (observed_at <= +2s) cures depth to 1 -> HEALTHY
    assert eng.admit_atom(
        make_atom("branch_a", 88.01, "2026-01-01T12:00:01Z", sc4, ["SRC_INDEP"], time=tt),
        "2026-01-01T12:00:06Z",
    ).accepted
    a_ok = eng.evaluate(iid_cc, "2026-01-01T12:00:06Z")
    assert a_ok.content["roles"]["branch_a"]["source_depth"] == 1
    assert a_ok.integrity_state == S.HEALTHY

    # 3. Late STALLED guard transitions open missing decision to DEGRADED even before deadline
    for origin in ("SRC_1", "SRC_2", "SRC_P1", "SRC_P2", "SRC_INDEP"):
        eng.admit_guard(make_guard(origin, "STALLED", "2026-01-01T12:00:08Z"), "2026-01-01T12:00:08Z")
    a_stalled = eng.evaluate(iid_miss, "2026-01-01T12:00:08Z")
    assert a_stalled.integrity_state == S.DEGRADED


def test_supersession_authority_finality_quarantine_and_bitemporal_consistency():
    """Verify unauthorized supersession blocked, pre-admission quarantine preserves ledger, and as_of read-only invariance."""
    t0 = "2026-01-01T12:00:00Z"
    sc = {"session_id": "s1", "driver_id": "44", "lap_number": "10"}
    eng = IntegrityEngine(OriginRegistry({}), EngineConfig(auto_open=False))
    eng.register_contract(parse_contract(_contract_spec(two_branch=False, formula="branch_a")))
    iid_fin = eng.open_decision("audit_contract", sc, t0)

    tt = TypedTime(1767268800_000_000, TimeClass.ABSOLUTE_UTC)
    atom_orig = make_atom("branch_a", 89.0, t0, sc, ["SRC_1"], processor_family_id="proc_A", time=tt)
    eng.admit_atom(atom_orig, t0)

    # Unauthorized origin + different processor family cannot supersede atom_orig
    atom_unauth = make_atom(
        "branch_a", 89.5, "2026-01-01T12:00:01Z", sc, ["SRC_2"],
        processor_family_id="proc_B", supersedes=atom_orig.atom_id, time=tt,
    )
    eng.admit_atom(atom_unauth, "2026-01-01T12:00:01Z")
    a_conflict = eng.evaluate(iid_fin, "2026-01-01T12:00:02Z")
    assert a_conflict.integrity_state == S.SUSPECT
    assert any(w["code"] == "UNRESOLVED_CONFLICT" for w in a_conflict.content["witnesses"])

    # Authorized same-origin replacement cleanly supersedes atom_orig without triggering false conflict against itself
    spec2 = _contract_spec(two_branch=False, formula="branch_a")
    spec2["roles"]["branch_a"]["freshness"] = {"soft_age_s": 120, "hard_age_s": 300}
    eng2 = IntegrityEngine(OriginRegistry({}), EngineConfig(auto_open=False))
    eng2.register_contract(parse_contract(spec2))
    iid_fin2 = eng2.open_decision("audit_contract", sc, t0)
    a1 = make_atom("branch_a", 89.0, t0, sc, ["SRC_1"], processor_family_id="proc_A", time=tt)
    a2 = make_atom("branch_a", 89.05, "2026-01-01T12:00:02Z", sc, ["SRC_1"], processor_family_id="proc_A", supersedes=a1.atom_id, time=tt)
    eng2.admit_atom(a1, t0)
    r_before = eng2.evaluate(iid_fin2, "2026-01-01T12:00:01Z")
    eng2.admit_atom(a2, "2026-01-01T12:00:02Z")
    # Seal past cutoff (deadline 15s + lateness 60s = 75s), still within hard_age=300s
    r_sealed = eng2.evaluate(iid_fin2, "2026-01-01T12:01:20Z")
    assert r_sealed.integrity_state == S.HEALTHY
    assert r_sealed.content["finality_status"] == "FINAL"

    # Post-finality arrival is quarantined BEFORE ledger mutation
    ledger_count_before = eng2.ledger.counts()["atoms"]
    late_atom = make_atom("branch_a", 99.0, "2026-01-01T12:01:25Z", sc, ["SRC_2"], time=tt)
    adm = eng2.admit_atom(late_atom, "2026-01-01T12:01:25Z")
    assert adm.accepted is False
    assert adm.status == "QUARANTINED"
    assert adm.code == "POST_FINALITY_QUARANTINED"
    assert eng2.ledger.counts()["atoms"] == ledger_count_before

    # Bitemporal as_of query recovers exact prior revision without mutating current clock or chain
    past = eng2.as_of(iid_fin2, "2026-01-01T12:00:01Z")
    assert past is not None and past.record_hash == r_before.record_hash
    assert all(v == "OK" for v in eng2.verify().values())
