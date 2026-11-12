"""Property / adversarial tests for the claims the SIA design makes (Phase 4 of the roadmap)."""
import random

import pytest

from sia_core import make_atom, make_fact, verify_chain
from helpers import *


def build(order_seed=None, ticks=(7,), extra=()):
    """Same evidence, optional shuffled admission order within one knowledge instant."""
    e = engine(pit_speed_contract(), lap_time_contract())
    pit = e.open_decision("pit_speed", SC, T0, known_at=T0)
    lap = e.open_decision("lap_time", SC, T0, known_at=T0)
    items = [
        ("atom", atom("timing_speed", 61.2, 5, ["PITWALL"], unit="kph")),
        ("atom", atom("vehicle_speed", 61.0, 5.1, ["CAR_SENSOR"], unit="kph")),
        ("atom", atom("configured_distance", 2615.0, 1, ["TIMING_CONFIG"], scope=SESSION, unit="cm")),
        ("fact", make_fact("track_geometry", SESSION, 2615.0, ["SURVEY"], unit="cm")),
        ("fact", make_fact("calibration_bias", SESSION, 0.001, ["POP_MONITOR"], unit="ratio")),
        ("atom", atom("lap_record", 90.10, 5, ["PITWALL"])),
        ("atom", atom("lap_record", 90.11, 5.2, ["CAR_SENSOR"])),
        ("atom", atom("lap_record", 90.12, 5.3, ["GPS"])),
    ]
    if order_seed is not None:
        random.Random(order_seed).shuffle(items)
    for kind, it in items:
        (e.admit_atom if kind == "atom" else e.admit_fact)(it, ts(6))
    last = None
    for t in ticks:
        last = [e.evaluate(pit, ts(t)), e.evaluate(lap, ts(t))]
    return e, last


class TestDeterminism:
    def test_order_invariance_within_a_knowledge_instant(self):
        _, ref = build()
        for seed in range(12):
            _, got = build(order_seed=seed)
            assert [g.content_hash for g in got] == [r.content_hash for r in ref]
            assert [g.record_hash for g in got] == [r.record_hash for r in ref]

    def test_two_engines_same_inputs_same_hash_chain(self):
        (_, a), (_, b) = build(ticks=(7, 20, 40, 95, 200)), build(ticks=(7, 20, 40, 95, 200))
        assert [x.record_hash for x in a] == [x.record_hash for x in b]

    def test_replay_equivalence_rebuilding_from_the_ledger_reproduces_every_record(self):
        e1, _ = build(ticks=(7, 40, 95, 200))
        e2 = engine(pit_speed_contract(), lap_time_contract())
        for iid in e1.instances:
            e2.open_decision(e1.instances[iid].contract_id, e1.instances[iid].scope_dict, e1.instances[iid].opens_at, known_at=e1.instances[iid].registered_at)
        recs = sorted([(r.seq, r.kt, "atom", r.atom) for rs in e1.ledger._atoms.values() for r in rs] +
                      [(r.seq, r.kt, "fact", r.fact) for rs in e1.ledger._facts.values() for r in rs], key=lambda x: x[0])
        for _s, kt, kind, it in recs:
            (e2.admit_atom if kind == "atom" else e2.admit_fact)(it, kt)
        for t in (7, 40, 95, 200):
            e2.tick(ts(t))
        for iid in e1.instances:
            assert [a.record_hash for a in e1.history(iid)] == [a.record_hash for a in e2.history(iid)]

    def test_final_content_hash_is_independent_of_evaluation_cadence(self):
        _, fast = build(ticks=tuple(range(7, 200, 3)) + (200,))
        _, slow = build(ticks=(200,))
        assert [f.content_hash for f in fast] == [s.content_hash for s in slow]

    def test_duplicate_admission_is_idempotent(self):
        e, first = build()
        before = e.ledger.counts()
        a = atom("lap_record", 90.10, 5, ["PITWALL"])
        assert e.admit_atom(a, ts(8)).status == "DUPLICATE"
        assert e.ledger.counts() == before
        again = e.evaluate("lap_time@S1|44|12", ts(9))
        assert again.content_hash == first[1].content_hash

    def test_reevaluating_unchanged_knowledge_never_mints_revisions(self):
        e, _ = build()
        for t in range(8, 80, 4):
            e.evaluate("lap_time@S1|44|12", ts(t))
        assert len(e.history("lap_time@S1|44|12")) == 1


class TestFailClosed:
    @pytest.mark.parametrize("seed", range(25))
    def test_missing_required_role_is_never_healthy_at_any_time(self, seed):
        rnd = random.Random(seed)
        c = contract("two", "AND(a, b)", {"a": role(), "b": role()})
        e = engine(c)
        iid = e.open_decision("two", SC, T0, known_at=T0)
        for _ in range(rnd.randint(1, 4)):
            e.admit_atom(atom("a", round(rnd.uniform(0, 100), 1), rnd.uniform(0, 30), [rnd.choice(["PITWALL", "CAR_SENSOR", "GPS"])]), ts(31))
        for t in sorted(rnd.uniform(31, 400) for _ in range(8)):
            assert e.evaluate(iid, ts(t)).integrity_state != S.HEALTHY

    def test_unknown_role_and_wrong_scope_evidence_never_support_a_decision(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0, known_at=T0)
        e.admit_atom(atom("some_other_role", 90.1, 5, ["PITWALL"]), ts(6))
        e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"], scope={**SC, "driver_id": "1"}), ts(6))
        e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"], scope={**SC, "session_id": "S2"}), ts(6))
        assert e.evaluate(iid, ts(40)).integrity_state == S.DEGRADED

    def test_low_quality_and_inadmissible_origin_evidence_is_refused_with_witness(self):
        c = contract("lt", "lap_record", {"lap_record": role(admissible_source_origins=["PITWALL"])})
        e = engine(c)
        iid = e.open_decision("lt", SC, T0, known_at=T0)
        e.admit_atom(atom("lap_record", 90.1, 5, ["GPS"]), ts(6))
        e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"], quality_grade=S.DEGRADED), ts(6))
        r = e.evaluate(iid, ts(40))
        w = {x["code"] for x in r.witnesses}
        assert r.integrity_state == S.DEGRADED and {"INADMISSIBLE_ORIGIN", "LOW_QUALITY_EVIDENCE"} <= w

    def test_suspect_grade_atom_caps_the_role(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0)
        e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"], quality_grade=S.SUSPECT), ts(6))
        assert e.evaluate(iid, ts(7)).integrity_state == S.SUSPECT

    def test_future_dated_observation_is_suspect(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0)
        e.admit_atom(atom("lap_record", 90.1, 600, ["PITWALL"]), ts(6))             # claims to be from 10 minutes in the future
        r = e.evaluate(iid, ts(7))
        assert "FUTURE_DATED_OBSERVATION" in {x["code"] for x in r.witnesses} and r.integrity_state != S.HEALTHY

    def test_search_budget_overflow_fails_closed_not_open(self):
        e = IntegrityEngine(registry(), EngineConfig(M_max=3)) if False else None
        from sia_core import EngineConfig, IntegrityEngine as IE
        e = IE(registry(), EngineConfig(M_max=3))
        e.register_contract(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0)
        for i in range(6):
            e.admit_atom(atom("lap_record", 90.1, 5 + i * 0.05, [f"SRC{i}"]), ts(6))
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.UNKNOWN and "SEARCH_BUDGET_EXCEEDED" in {x["code"] for x in r.witnesses}
        assert e.evaluate(iid, ts(200)).finality_status == "FINAL"                 # overflow no longer blocks finality forever


class TestEnvelopeSoundness:
    @pytest.mark.parametrize("seed", range(150))
    def test_current_state_always_lies_within_the_previously_published_envelope(self, seed):
        """Late evidence (arriving before the cutoff, about the past) can never push the state outside the earlier envelope."""
        rnd = random.Random(seed)
        c = contract("env", rnd.choice(["AND(a, b)", "OR(a, b)", "K_OF_N(2, a, b, c)", "AND(a, OR(b, c))"]),
                     {n: role(freshness=rnd.choice([None, {"soft_age_s": 8, "hard_age_s": 20}])) if False else role() for n in "abc"})
        from sia_core.contract import parse_contract, roles_of
        used = roles_of(parse_contract(c).formula)
        c["roles"] = {n: c["roles"][n] for n in used}
        if rnd.random() < 0.4:
            c["fault_model"] = {"resilience_requirement": 1}                      # exercise the resilience cap too
        if rnd.random() < 0.3:
            c["fault_model"] = {**c.get("fault_model", {}), "diagnosis_budget": 1}
        e = engine(c)
        iid = e.open_decision("env", SC, T0, known_at=T0)
        srcs = ["PITWALL", "CAR_SENSOR", "GPS", "A", "B"]

        def feed(k_lo, k_hi, obs_hi):
            for _ in range(rnd.randint(0, 3)):
                kt = rnd.uniform(k_lo, k_hi)
                e.admit_atom(atom(rnd.choice(sorted(used)), rnd.choice([90.0, 90.0, 90.0, 95.0]), rnd.uniform(0, min(obs_hi, kt)),
                                  [rnd.choice(srcs)]), ts(kt))
        K1 = rnd.uniform(5, 85)
        feed(0, K1, K1)
        r1 = e.evaluate(iid, ts(K1))
        env = set(r1.content["envelope"]["alternatives"])
        assert r1.integrity_state.name in env
        feed(K1 + 0.001, 89.0, K1)                                                  # more evidence about times <= K1, before cutoff
        r2 = e.evaluate(iid, ts(rnd.uniform(K1, 89.5)))
        assert r2.state_at(ts(K1)).name in env, (seed, env, r2.state_at(ts(K1)).name)


class TestEndToEndChainAcrossManyDecisions:
    def test_many_laps_independent_chains_all_verify(self):
        e = engine(lap_time_contract())
        for lap in range(1, 11):
            sc = {**SC, "lap_number": lap}
            iid = e.open_decision("lap_time", sc, ts(lap * 100), known_at=ts(lap * 100))
            e.admit_atom(atom("lap_record", 90.0 + lap * 0.01, lap * 100 + 5, ["PITWALL"], scope=sc), ts(lap * 100 + 6))
            e.admit_atom(atom("lap_record", 90.0 + lap * 0.01, lap * 100 + 5, ["CAR_SENSOR"], scope=sc), ts(lap * 100 + 6))
            e.tick(ts(lap * 100 + 7))
        e.tick(ts(2000))
        assert all(v == "OK" for v in e.verify().values()) and len(e.verify()) == 10
        assert all(e.history(i)[-1].finality_status == "FINAL" for i in e.instances)
