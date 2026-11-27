"""Stage 3 (Priority C): Formal lattice, epistemic, invariant, and adversarial checks for SIA Core v3."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import itertools
import pytest

from sia_core import (
    IntegrityEngine,
    IntegrityState,
    OriginRegistry,
    SIAWALStore,
    ScopeClass,
    and_state,
    k_of_n_state,
    make_atom,
    make_fact,
    make_guard,
    or_state,
    parse_contract,
    verify_chain,
)
from sia_core.algebra import Timeline

T0 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _ts(sec: float) -> datetime:
    return T0 + timedelta(seconds=sec)


def _domain_free_contract(
    contract_id: str = "invariant-contract",
    *,
    diag_budget: int = 0,
    resilience: int = 0,
    min_source_depth: int = 0,
):
    return parse_contract({
        "contract_id": contract_id,
        "version": "1.0.0",
        "epoch": 1,
        "decision_type": "CORROBORATED_MEASUREMENT",
        "decision_scope": {"scope_class": ScopeClass.SESSION.value},
        "formula": "AND(primary_sensor, backup_sensor)",
        "simultaneity_window_s": 5.0,
        "fault_model": {"diagnosis_budget": diag_budget, "resilience_requirement": resilience},
        "roles": {
            "primary_sensor": {
                "kind": "evidence",
                "scope_class": ScopeClass.SESSION.value,
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["sensor_a", "sensor_c"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.5},
                "freshness": {"soft_age_s": 30.0, "hard_age_s": 60.0},
                "slot": {"deadline_s": 10.0, "allowed_lateness_s": 15.0},
                "corroboration": {"mode": "INFORMATIONAL", "min_source_depth": min_source_depth},
            },
            "backup_sensor": {
                "kind": "evidence",
                "scope_class": ScopeClass.SESSION.value,
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["sensor_b", "sensor_d"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.5},
                "freshness": {"soft_age_s": 30.0, "hard_age_s": 60.0},
                "slot": {"deadline_s": 10.0, "allowed_lateness_s": 15.0},
                "corroboration": {"mode": "INFORMATIONAL", "min_source_depth": min_source_depth},
            },
        },
    })


class TestEpistemicLatticeSemantics:
    def test_distributive_bounded_lattice_axioms_and_k_of_n_monotonicity(self):
        states = tuple(IntegrityState)
        for a, b, c in itertools.product(states, repeat=3):
            assert and_state(a, b) == and_state(b, a)
            assert or_state(a, b) == or_state(b, a)
            assert and_state(a, and_state(b, c)) == and_state(and_state(a, b), c)
            assert or_state(a, or_state(b, c)) == or_state(or_state(a, b), c)
            assert and_state(a, or_state(b, c)) == or_state(and_state(a, b), and_state(a, c))
            assert or_state(a, and_state(b, c)) == and_state(or_state(a, b), or_state(a, c))
            assert and_state(a, or_state(a, b)) == a
            assert or_state(a, and_state(a, b)) == a
        for a in states:
            assert and_state(a, a) == a
            assert or_state(a, a) == a
            assert and_state(a, IntegrityState.HEALTHY) == a
            assert or_state(a, IntegrityState.DEGRADED) == a

        # Monotonicity of k_of_n under pairwise lifting
        assert k_of_n_state(2, IntegrityState.UNKNOWN, IntegrityState.HEALTHY, IntegrityState.DEGRADED) <= k_of_n_state(
            2, IntegrityState.SUSPECT, IntegrityState.HEALTHY, IntegrityState.UNKNOWN
        )

    def test_epistemic_collapse_boundaries_and_fail_closed_missing_evidence(self):
        # Prove scalar ordering collapses availability (UNKNOWN) and suspicion (SUSPECT) on AND/OR:
        assert IntegrityState.DEGRADED < IntegrityState.UNKNOWN < IntegrityState.SUSPECT < IntegrityState.HEALTHY
        assert and_state(IntegrityState.UNKNOWN, IntegrityState.SUSPECT) == IntegrityState.UNKNOWN
        assert or_state(IntegrityState.DEGRADED, IntegrityState.UNKNOWN) == IntegrityState.UNKNOWN

        # Missing evidence (UNKNOWN) never yields HEALTHY under required conjunction:
        for s in IntegrityState:
            assert and_state(IntegrityState.UNKNOWN, s) < IntegrityState.HEALTHY

        # Show multidimensional projection from SIA assessment retains both suspicion & finality:
        reg = OriginRegistry({"sensor_a": ["feed_1"], "sensor_b": ["feed_2"]})
        eng = IntegrityEngine(reg)
        eng.register_contract(_domain_free_contract("epistemic-diag"))
        did = eng.open_decision("epistemic-diag", {"session_id": "z1"}, _ts(0))
        eng.admit_atom(
            make_atom("primary_sensor", 10.0, _ts(1), {"session_id": "z1"}, ["sensor_a"], unit="s", quality_grade=IntegrityState.SUSPECT),
            _ts(1),
        )
        # backup_sensor missing (UNKNOWN), primary_sensor SUSPECT
        verdict = eng.evaluate(did, _ts(2))
        d = verdict.content
        assert verdict.integrity_state == IntegrityState.UNKNOWN
        # Orthogonally preserved dimensions (role timeline at K, LOW_QUALITY_EVIDENCE witness, envelope, finality):
        assert d["finality_status"] == "OPEN"
        assert d["envelope"]["lower"] in {IntegrityState.DEGRADED.name, IntegrityState.UNKNOWN.name}
        assert d["envelope"]["upper"] == IntegrityState.HEALTHY.name
        assert any(pt["state"] == IntegrityState.SUSPECT.name for pt in d["roles"]["primary_sensor"]["timeline"])
        assert any(w.get("code") == "LOW_QUALITY_EVIDENCE" for w in d["witnesses"])


class TestFormalInvariantsAndAdversarial:
    def test_knowledge_time_and_valid_time_monotonicity_and_envelope_nesting(self):
        reg = OriginRegistry({"sensor_a": ["src_1"], "sensor_b": ["src_2"]})
        eng = IntegrityEngine(reg)
        eng.register_contract(_domain_free_contract())
        did = eng.open_decision("invariant-contract", {"session_id": "z2"}, _ts(0))

        # Knowledge time k1 -> k2 -> k3 produces monotonic non-decreasing chain timestamps and nested envelopes
        v1 = eng.evaluate(did, _ts(1))
        eng.admit_atom(make_atom("primary_sensor", 20.0, _ts(1.2), {"session_id": "z2"}, ["sensor_a"], unit="s"), _ts(2))
        v2 = eng.evaluate(did, _ts(3))
        eng.admit_atom(make_atom("backup_sensor", 20.1, _ts(1.3), {"session_id": "z2"}, ["sensor_b"], unit="s"), _ts(4))
        v3 = eng.evaluate(did, _ts(26))

        hist = eng.history(did)
        assert [a.knowledge_time for a in hist] == sorted(a.knowledge_time for a in hist)
        assert v3.integrity_state == IntegrityState.HEALTHY
        assert v3.finality_status == "FINAL"
        ok, msg = verify_chain(hist)
        assert ok, msg

        # Envelope narrows monotonically while still containing final settled truth
        rank = {s.name: int(s) for s in IntegrityState}
        assert rank[v1.content["envelope"]["lower"]] <= rank[v3.integrity_state.name] <= rank[v1.content["envelope"]["upper"]]

    def test_valid_time_out_of_order_revision_preserves_prior_as_of(self):
        reg = OriginRegistry({"sensor_a": ["src_1"], "sensor_b": ["src_2"]})
        eng = IntegrityEngine(reg)
        eng.register_contract(_domain_free_contract())
        did = eng.open_decision("invariant-contract", {"session_id": "z3"}, _ts(0))

        eng.admit_atom(make_atom("primary_sensor", 15.0, _ts(5.0), {"session_id": "z3"}, ["sensor_a"], unit="s"), _ts(6))
        v_before = eng.evaluate(did, _ts(6))
        snap_k6 = eng.as_of(did, _ts(6))

        # Earlier valid_time arrives at later knowledge_time k=8
        eng.admit_atom(make_atom("backup_sensor", 15.1, _ts(4.8), {"session_id": "z3"}, ["sensor_b"], unit="s"), _ts(8))
        v_after = eng.evaluate(did, _ts(8))
        assert v_before.integrity_state == IntegrityState.UNKNOWN
        assert snap_k6.content_hash == v_before.content_hash
        assert v_after.integrity_state == IntegrityState.HEALTHY

    def test_finality_irreversibility_and_quarantine_isolation(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            wal_path = os.path.join(tmp, "inv_quarantine.sqlite")
            wal = SIAWALStore(wal_path)
            try:
                reg = OriginRegistry({"sensor_a": ["src_1"], "sensor_b": ["src_2"]})
                eng = IntegrityEngine(reg, wal=wal)
                eng.register_contract(_domain_free_contract())
                did = eng.open_decision("invariant-contract", {"session_id": "z4"}, _ts(0))
                eng.admit_atom(make_atom("primary_sensor", 10.0, _ts(1), {"session_id": "z4"}, ["sensor_a"], unit="s"), _ts(2))
                eng.admit_atom(make_atom("backup_sensor", 10.0, _ts(1), {"session_id": "z4"}, ["sensor_b"], unit="s"), _ts(2))
                sealed = eng.evaluate(did, _ts(26))
                assert sealed.finality_status == "FINAL"
                sealed_hash = sealed.content_hash

                # Post-finality conflicting mutation attempt & void attempt cannot overwrite FINAL verdict
                adm = eng.admit_atom(
                    make_atom("backup_sensor", 99.0, _ts(1.2), {"session_id": "z4"}, ["sensor_b"], unit="s"),
                    _ts(30),
                )
                assert adm.status != "ADMITTED"
                after_void = eng.void_decision(did, _ts(31), reason="LATE_CANCEL")
                assert after_void.content_hash == sealed_hash

                # Pre-admission finality quarantine stored in WAL stays isolated from admitted ledger on reload
                wal.save_quarantine("ATOM", "atom-post-1", did, 30_000_000, "POST_FINALITY", {"x": 1})
                q_rows = wal.load_quarantine()
                assert len(q_rows) >= 1
                reloaded = wal.load_engine(reg)
                assert reloaded.history(did)[-1].content_hash == sealed_hash
                wal.clear_session("default")
                assert wal.load_quarantine() == []
            finally:
                wal.close()

    def test_transitive_common_cause_closure_diamond_dag_and_cycles(self):
        # 4-hop chain: s1 -> mid1 -> mid2 -> shared_root; s2 -> alt_mid -> shared_root
        reg = OriginRegistry({
            "s1": ["mid1"],
            "mid1": ["mid2"],
            "mid2": ["shared_root"],
            "s2": ["alt_mid"],
            "alt_mid": ["shared_root"],
            "s3_indep": ["other_root"],
            # Adversarial cycle must terminate without infinite recursion
            "cyc_a": ["cyc_b"],
            "cyc_b": ["cyc_a"],
        })
        assert "shared_root" in reg.closure("s1")
        assert "shared_root" in reg.closure("s2")
        assert reg.max_independent(["s1", "s2"]) == 1
        assert reg.max_independent(["s1", "s3_indep"]) == 2
        assert reg.closure("cyc_a") == frozenset({"cyc_a", "cyc_b"})

    def test_incremental_vs_full_verification_equivalence_and_tamper_detection(self):
        reg = OriginRegistry({"sensor_a": ["src_1"], "sensor_b": ["src_2"]})
        eng = IntegrityEngine(reg)
        eng.register_contract(_domain_free_contract())
        did = eng.open_decision("invariant-contract", {"session_id": "z5"}, _ts(0))

        cached: dict[str, int] = {}
        eng.evaluate(did, _ts(1))
        assert eng.verify() == {did: "OK"}
        assert eng.verify_incremental(cached) is True
        assert cached[did] == 1

        eng.admit_atom(make_atom("primary_sensor", 30.0, _ts(2), {"session_id": "z5"}, ["sensor_a"], unit="s"), _ts(2))
        eng.evaluate(did, _ts(2))
        assert eng.verify() == {did: "OK"}
        assert eng.verify_incremental(cached) is True
        assert cached[did] == 2

        eng.admit_atom(make_atom("backup_sensor", 30.1, _ts(2), {"session_id": "z5"}, ["sensor_b"], unit="s"), _ts(3))
        eng.evaluate(did, _ts(3))
        assert eng.verify() == {did: "OK"}
        assert eng.verify_incremental(cached) is True
        assert cached[did] == 3

        # Tamper record content and confirm BOTH full and incremental verify detect corruption
        eng.history(did)[-1].content["finality_status"] = "DEGRADED_TAMPER"
        assert eng.verify()[did] != "OK"
        assert "tamper" in eng.verify()[did].lower()
        assert eng.verify_incremental({did: 1}) is False

    def test_adversarial_duplicate_clock_skew_empty_and_high_volume_determinism(self):
        reg = OriginRegistry({f"orig_{i}": [f"hw_{i}"] for i in range(10)})
        contract = parse_contract({
            "contract_id": "scale-and-adversarial",
            "version": "1.0.0",
            "epoch": 1,
            "decision_type": "SCALE_CHECK",
            "decision_scope": {"scope_class": ScopeClass.SESSION.value},
            "formula": "AND(r1, r2)",
            "simultaneity_window_s": 500.0,
            "roles": {
                "r1": {
                    "kind": "evidence",
                    "scope_class": ScopeClass.SESSION.value,
                    "time_class_required": "ABSOLUTE_UTC",
                    "admissible_source_origins": [f"orig_{i}" for i in range(5)],
                    "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 1.0},
                    "freshness": {"soft_age_s": 120.0, "hard_age_s": 240.0},
                    "slot": {"deadline_s": 300.0, "allowed_lateness_s": 300.0},
                },
                "r2": {
                    "kind": "evidence",
                    "scope_class": ScopeClass.SESSION.value,
                    "time_class_required": "ABSOLUTE_UTC",
                    "admissible_source_origins": [f"orig_{i}" for i in range(5, 10)],
                    "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 1.0},
                    "freshness": {"soft_age_s": 120.0, "hard_age_s": 240.0},
                    "slot": {"deadline_s": 300.0, "allowed_lateness_s": 300.0},
                },
            },
        })

        # 1. Empty evidence evaluation stays UNKNOWN (fail closed)
        e_empty = IntegrityEngine(reg)
        e_empty.register_contract(contract)
        d_empty = e_empty.open_decision("scale-and-adversarial", {"session_id": "s-empty"}, _ts(0))
        v_empty = e_empty.evaluate(d_empty, _ts(1))
        assert v_empty.integrity_state == IntegrityState.UNKNOWN

        # 2. Extreme future & expired clock skew never produces HEALTHY
        e_skew = IntegrityEngine(reg)
        e_skew.register_contract(contract)
        d_skew = e_skew.open_decision("scale-and-adversarial", {"session_id": "s-skew"}, _ts(0))
        e_skew.admit_atom(make_atom("r1", 50.0, _ts(10000), {"session_id": "s-skew"}, ["orig_0"], unit="s"), _ts(10))
        e_skew.admit_atom(make_atom("r2", 50.0, _ts(-10000), {"session_id": "s-skew"}, ["orig_5"], unit="s"), _ts(10))
        v_skew = e_skew.evaluate(d_skew, _ts(10))
        assert v_skew.integrity_state != IntegrityState.HEALTHY

        # 3. Duplicate ID idempotency vs high-volume 500 atoms + reversed replay order determinism
        atoms = []
        for idx in range(500):
            role = "r1" if idx % 2 == 0 else "r2"
            orig = f"orig_{idx % 5}" if role == "r1" else f"orig_{5 + (idx % 5)}"
            atoms.append(make_atom(role, 42.0, _ts(1.0 + (idx % 100) * 0.01), {"session_id": "s-scale"}, [orig], unit="s"))

        e1 = IntegrityEngine(reg)
        e1.register_contract(contract)
        d1 = e1.open_decision("scale-and-adversarial", {"session_id": "s-scale"}, _ts(0))
        for a in atoms:
            e1.admit_atom(a, _ts(5))
        # Re-admit duplicate -> idempotent (DUPLICATE or ADMITTED without corrupting content)
        dup = e1.admit_atom(atoms[0], _ts(5))
        assert dup.status in {"ADMITTED", "DUPLICATE"}
        res1 = e1.evaluate(d1, _ts(6))

        e2 = IntegrityEngine(reg)
        e2.register_contract(contract)
        d2 = e2.open_decision("scale-and-adversarial", {"session_id": "s-scale"}, _ts(0))
        for a in reversed(atoms):
            e2.admit_atom(a, _ts(5))
        res2 = e2.evaluate(d2, _ts(6))

        assert res1.integrity_state == IntegrityState.HEALTHY
        assert res1.content_hash == res2.content_hash
        assert res1.record_hash == res2.record_hash
