"""Unit + scenario tests. Each scenario maps to a failure class from the review of the old engine."""
import copy
import pytest
import yaml

from sia_core import (ContractRejected, EngineConfig, IntegrityEngine, OriginRegistry, TimeClass, TypedTime, estimate_bias,
                      fmt_instant, jcs, load_contract_yaml, make_atom, make_fact, make_guard, parse_contract, parse_instant,
                      sec_to_us, sha256_hex, validate_contract, verify_chain)
from sia_core.algebra import (FULL, Timeline, and_state, k_of_n_state, or_state, set_and, set_comb, set_or, sset)
from sia_core.timeclass import conversion_path, resolve_time
from sia_core.verdict import explain
from helpers import *


def codes(rec):
    return {w["code"] for w in rec.witnesses}


# =============================================================================== canon / time
class TestCanon:
    @pytest.mark.parametrize("val,expected", [
        (1e21, "1e+21"), (1e-7, "1e-7"), (0.000001, "0.000001"), (4.5, "4.5"), (2e-3, "0.002"), (1e30, "1e+30"),
        (333333333.3333333, "333333333.3333333"), (123456789012345680000.0, "123456789012345680000"),
        (1e-27, "1e-27"), (-0.0, "0"), (100.0, "100"), (0.5, "0.5"), (-1.5e25, "-1.5e+25"), (1e21 - 1e5, "999999999999999900000")])
    def test_rfc8785_number_vectors(self, val, expected):
        assert jcs(val) == expected

    def test_key_order_and_escapes(self):
        assert jcs({"b": 1, "a": [True, None], "10": "x", "9": "y"}) == '{"10":"x","9":"y","a":[true,null],"b":1}'
        assert jcs("a\"b\\c\n\u0001/é") == '"a\\"b\\\\c\\n\\u0001/é"'

    def test_nan_and_unsupported_rejected(self):
        with pytest.raises(ValueError):
            jcs(float("nan"))
        with pytest.raises(TypeError):
            jcs({"x": {1, 2}})

    def test_sha256_known_vector(self):
        assert sha256_hex({"a": 1}) == "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"

    def test_mixed_timestamp_formats_order_correctly(self):
        """Regression: old code compared ISO strings, where 'Z' sorts after '.'."""
        a, b = "2026-06-07T13:00:00Z", "2026-06-07T13:00:00.500Z"
        assert a > b                                    # string order is WRONG ...
        assert parse_instant(a) < parse_instant(b)      # ... integer order is right
        assert parse_instant("2026-06-07T13:00:00+00:00") == parse_instant(a)
        assert parse_instant("2026-06-07T18:30:00+05:30") == parse_instant(a)

    def test_naive_timestamp_rejected_and_roundtrip(self):
        with pytest.raises(ValueError):
            parse_instant("2026-06-07T13:00:00")
        us = parse_instant("2026-06-07T13:00:00.123456Z")
        assert fmt_instant(us) == "2026-06-07T13:00:00.123456Z"
        assert parse_instant(fmt_instant(us)) == us


# =============================================================================== algebra
class TestAlgebra:
    ALL = list(S)

    def test_lattice_laws_exhaustive(self):
        for a in self.ALL:
            assert and_state(a, a) == a and or_state(a, a) == a
            for b in self.ALL:
                assert and_state(a, b) == and_state(b, a) and or_state(a, b) == or_state(b, a)
                assert and_state(a, or_state(a, b)) == a and or_state(a, and_state(a, b)) == a          # absorption
                for c in self.ALL:
                    assert and_state(a, and_state(b, c)) == and_state(and_state(a, b), c)
                    assert or_state(a, or_state(b, c)) == or_state(or_state(a, b), c)

    def test_k_of_n_bounds(self):
        for xs in [(S.HEALTHY, S.SUSPECT, S.DEGRADED), (S.UNKNOWN, S.UNKNOWN, S.HEALTHY)]:
            assert k_of_n_state(1, *xs) == or_state(*xs) and k_of_n_state(len(xs), *xs) == and_state(*xs)
        with pytest.raises(ValueError):
            k_of_n_state(4, S.HEALTHY, S.SUSPECT, S.DEGRADED)

    def test_superposition_sets_are_sound_and_collapse(self):
        a, b = sset("SUSPECT", "HEALTHY"), FULL
        assert set_and(sset("SUSPECT"), b) == frozenset({S.DEGRADED, S.UNKNOWN, S.SUSPECT})   # AND can never exceed its weakest child
        assert set_or(a, b) == frozenset({S.SUSPECT, S.HEALTHY})
        assert set_and(sset("DEGRADED"), FULL) == sset("DEGRADED")               # collapse: decisive child fixes the result
        assert set_comb("K_OF_N", 2, [sset("HEALTHY"), sset("HEALTHY"), FULL]) == sset("HEALTHY")

    def test_timeline_before_first_breakpoint_is_unknown_not_retro_extended(self):
        tl = Timeline([(100, S.HEALTHY)])
        assert tl.state_at(99) == S.UNKNOWN and tl.state_at(100) == S.HEALTHY
        both = Timeline.combine([tl, Timeline([(200, S.HEALTHY)])], min)
        assert both.state_at(150) == S.UNKNOWN and both.state_at(200) == S.HEALTHY    # old code said HEALTHY at 150

    def test_timeline_merge_and_clip(self):
        tl = Timeline([(10, S.HEALTHY), (20, S.HEALTHY), (30, S.SUSPECT), (30, S.DEGRADED)])
        assert tl.bps == ((10, S.HEALTHY), (30, S.DEGRADED))
        assert tl.clip(40).bps == ((40, S.DEGRADED),)


# =============================================================================== typed time
class TestTypedTime:
    def test_paths_and_illegal_classes(self):
        p = conversion_path(TimeClass.LAP_RELATIVE, TimeClass.ABSOLUTE_UTC)
        assert [x[2] for x in p] == ["lap_start", "session_t0"]
        for bad in (TimeClass.LAP_DURATION, TimeClass.RECEIPT_TIME_ONLY, TimeClass.PROCESSING_TIME, TimeClass.UNKNOWN):
            assert conversion_path(bad, TimeClass.SESSION_ELAPSED) is None
            assert conversion_path(TimeClass.SESSION_ELAPSED, bad) is None

    def test_resolution_inherits_uncertainty_grade_and_never_invents_reference(self):
        f = lap_start_fact(3600.0, grade=S.SUSPECT, uncertainty_us=2000)
        t = TypedTime(sec_to_us(30), TimeClass.LAP_RELATIVE, 1000)
        r = resolve_time(t, TimeClass.SESSION_ELAPSED, lambda ft: (f, False, frozenset()) if ft == "lap_start" else None)
        assert r.time.value == sec_to_us(3630) and r.time.uncertainty_us == 3000 and r.grade == S.SUSPECT
        miss = resolve_time(t, TimeClass.SESSION_ELAPSED, lambda ft: None)
        assert miss.time is None and miss.missing == ("lap_start",)
        assert resolve_time(TypedTime(1, TimeClass.LAP_DURATION), TimeClass.SESSION_ELAPSED, lambda ft: None).illegal


# =============================================================================== contracts
class TestContractValidation:
    def val(self, d, reg=None):
        return validate_contract(parse_contract(d), reg)

    def test_good_contract_passes(self):
        assert self.val(pit_speed_contract()).ok

    def test_orphan_and_undefined_roles(self):
        v = self.val(contract("x", "a", {"a": role(), "b": role()}))
        assert "E_V01_ORPHAN_ROLE" in v.codes()
        v = self.val(contract("x", "AND(a, zzz)", {"a": role()}))
        assert "E_V01_UNDEFINED_ROLE" in v.codes()

    def test_arity_and_k(self):
        v = self.val(contract("x", "AND(a)", {"a": role()}))
        assert "E_V02_INVALID_ARITY" in v.codes()
        v = self.val(contract("x", "K_OF_N(3, a, b)", {"a": role(), "b": role()}))
        assert "E_V02_INVALID_K_THRESHOLD" in v.codes()

    def test_scope_hierarchy_and_time_class_and_freshness(self):
        v = self.val(contract("x", "a", {"a": role(scope_class="SECTOR")}, scope="DRIVER_LAP"))
        assert "E_V07_SCOPE_FINER_THAN_DECISION" in v.codes()
        v = self.val(contract("x", "a", {"a": role(time_class_required="LAP_DURATION")}))
        assert "E_V04_ILLEGAL_TIME_CLASS" in v.codes()
        v = self.val(contract("x", "a", {"a": role(freshness={"soft_age_s": 10, "hard_age_s": 5})}))
        assert "E_V05_INVALID_FRESHNESS" in v.codes()

    def test_constraint_checks(self):
        bad = contract("x", "a", {"a": role()}, constraints=[{"id": "c", "kind": "abs_diff", "operands": ["a", "nope"], "tolerance": 1}])
        assert "E_V08_BAD_CONSTRAINT" in self.val(bad).codes()
        bad = contract("x", "AND(a, b, c)", {"a": role(), "b": role(), "c": role()},
                       constraints=[{"id": "i", "kind": "interval", "duration": "a", "start": "b", "end": "c", "time_class": "SESSION_ELAPSED", "tolerance": 1}])
        assert "E_V04_ILLEGAL_TIME_CLASS" in self.val(bad).codes()      # start/end must declare a semantic time class

    def test_mandatory_corroboration_feasibility_and_common_upstream(self):
        co = {"mode": "MANDATORY", "min_source_depth": 1}
        r1 = contract("x", "a", {"a": role(corroboration=co, admissible_source_origins=["PITWALL"])})
        assert "E_V09_IMPOSSIBLE_SOURCE_DEPTH" in self.val(r1).codes()
        r2 = contract("x", "a", {"a": role(corroboration=co, admissible_source_origins=["PITWALL", "TRACINGINSIGHTS"])})
        assert self.val(r2).ok                                            # no lineage known -> cannot object
        assert "E_V10_COMMON_UPSTREAM_INDEPENDENCE_OVERCLAIM" in self.val(r2, registry()).codes()   # derived, not hard-coded
        r3 = contract("x", "a", {"a": role(corroboration=co, admissible_source_origins=["PITWALL", "CAR_SENSOR"])})
        assert self.val(r3, registry()).ok

    def test_engine_refuses_invalid_contract(self):
        with pytest.raises(ContractRejected):
            IntegrityEngine(registry()).register_contract(contract("x", "AND(a)", {"a": role()}))

    def test_yaml_loader_and_definition_hash_binds_contract(self):
        y = yaml.safe_dump(lap_time_contract())
        c1, c2 = load_contract_yaml(y), parse_contract(lap_time_contract())
        assert c1.definition_hash == c2.definition_hash
        other = lap_time_contract(); other["roles"]["lap_record"]["agreement"]["tolerance"] = 0.06
        assert parse_contract(other).definition_hash != c1.definition_hash


# =============================================================================== ledger / admission
class TestLedger:
    def test_duplicate_is_idempotent_and_id_is_content_addressed(self):
        e = engine(lap_time_contract())
        a = atom("lap_record", 90.1, 5, ["PITWALL"])
        assert e.admit_atom(a, ts(6)).accepted
        assert e.admit_atom(a, ts(7)).status == "DUPLICATE"
        assert e.ledger.counts()["atoms"] == 1
        assert make_atom("lap_record", 90.1, ts(5), SC, ["PITWALL"]).atom_id == a.atom_id

    def test_tampered_atom_rejected(self):
        e = engine(lap_time_contract())
        a = atom("lap_record", 90.1, 5, ["PITWALL"])
        forged = type(a)(**{**a.__dict__, "value": 80.0})
        assert e.admit_atom(forged, ts(6)).code == "ID_CONTENT_MISMATCH"

    def test_missing_provenance_nonfinite_and_regression_rejected(self):
        e = engine(lap_time_contract())
        assert e.admit_atom(atom("lap_record", 90.1, 5, []), ts(6)).code == "MISSING_PROVENANCE"
        assert e.admit_atom(atom("lap_record", float("nan"), 5, ["PITWALL"]), ts(6)).code == "MALFORMED_VALUE"
        assert e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"]), ts(10)).accepted
        assert e.admit_atom(atom("lap_record", 90.2, 6, ["CAR_SENSOR"]), ts(9)).code == "KNOWLEDGE_TIME_REGRESSION"
        assert len(e.ledger.rejections) == 3


# =============================================================================== scenarios
class TestScenarioHealthyAndSilent:
    def test_two_independent_sources_agree_then_finalize(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0)
        e.admit_atom(atom("lap_record", 90.10, 5, ["PITWALL"]), ts(6))
        e.admit_atom(atom("lap_record", 90.12, 5.2, ["CAR_SENSOR"]), ts(6))
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.HEALTHY and r.resolution_maturity == "OPEN"            # provisional
        assert r.content["roles"]["lap_record"]["source_depth"] == 1
        f = e.evaluate(iid, ts(200))
        assert f.integrity_state == S.HEALTHY and f.finality_status == "FINAL" and f.resolution_maturity == "TUPLE_RESOLVED"
        assert f.content["envelope"]["alternatives"] == ["HEALTHY"]
        assert e.verify() == {iid: "OK"}

    def test_silent_feed_unknown_then_degraded_then_final_not_forever_unknown(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0, known_at=T0)
        assert e.evaluate(iid, ts(10)).integrity_state == S.UNKNOWN
        assert e.evaluate(iid, ts(31)).integrity_state == S.DEGRADED          # deadline 30s, nothing ever arrived
        f = e.evaluate(iid, ts(100))
        assert f.integrity_state == S.DEGRADED and f.finality_status == "FINAL"   # old code: stuck UNKNOWN forever
        assert len(e.history(iid)) == 2                                         # no churn from the 31s tick

    def test_auto_open_freezes_slot_from_first_evidence_and_scope_is_enforced(self):
        e = engine(lap_time_contract())
        e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"]), ts(6))
        e.admit_atom(atom("lap_record", 70.0, 5, ["PITWALL"], scope={**SC, "lap_number": 13}), ts(6))   # another lap
        assert sorted(e.instances) == ["lap_time@S1|44|12", "lap_time@S1|44|13"]
        r12 = e.evaluate("lap_time@S1|44|12", ts(7))
        assert r12.content["roles"]["lap_record"]["support_atom_ids"] == [atom("lap_record", 90.1, 5, ["PITWALL"]).atom_id]


class TestScenarioStaleAndStationaryWatermark:
    def test_freshness_expiry_via_run_clock_without_new_events(self):
        wc = contract("weather_report", "weather", {"weather": role(scope_class="SESSION", freshness={"soft_age_s": 5, "hard_age_s": 15},
                      agreement={"metric": "abs_diff", "unit": "celsius", "tolerance": 0.5})}, scope="SESSION")
        e = engine(wc)
        iid = e.open_decision("weather_report", SESSION, T0)
        e.admit_atom(atom("weather", 24.0, 1, ["WEATHER_FEED"], scope=SESSION), ts(1))
        got = [e.evaluate(iid, ts(t)).integrity_state for t in (3, 7, 17)]       # no events: only run-clock ticks
        assert got == [S.HEALTHY, S.SUSPECT, S.DEGRADED]
        h = e.history(iid)
        assert h[0].state_at(ts(10)) == S.SUSPECT and h[0].state_at(ts(17)) == S.DEGRADED   # revision 1 already predicted the expiries
        assert len(h) == 2 and h[1].reason == "CLOCK_EVENT"                      # only the envelope widening at hard expiry is recorded; soft expiry mints nothing


class TestScenarioTypedTimeAndReferences:
    def aligned(self):
        return contract("aligned_lap", "lap_sample", {"lap_sample": role(time_class_required="SESSION_ELAPSED")})

    def sample(self, tt):
        return atom("lap_sample", 61.0, 5, ["PITWALL"], time=tt)

    def test_missing_lap_start_blocks_alignment_wrong_lap_fact_ignored_late_fact_revises_history(self):
        e = engine(self.aligned())
        iid = e.open_decision("aligned_lap", SC, T0, known_at=T0)
        e.admit_atom(self.sample(TypedTime(sec_to_us(30), TimeClass.LAP_RELATIVE)), ts(6))
        e.admit_fact(lap_start_fact(3500.0, scope={**SC, "lap_number": 11}), ts(7))         # wrong lap
        r1 = e.evaluate(iid, ts(35))
        assert r1.integrity_state == S.DEGRADED and "MISSING_REFERENCE_FACT" in codes(r1)
        e.admit_fact(lap_start_fact(3600.0), ts(40))                                        # correct lap, late but within lateness
        r2 = e.evaluate(iid, ts(45))
        assert r2.integrity_state == S.HEALTHY and r2.reason == "EVIDENCE_CHANGE"
        # bitemporal: as known at +35 the verdict for valid time +35 was DEGRADED; as known at +45 it is HEALTHY
        assert e.index.state_as_of(iid, ts(35), ts(35)) == S.DEGRADED
        assert e.index.state_as_of(iid, ts(35), ts(45)) == S.HEALTHY
        assert verify_chain(e.history(iid))[0]

    def test_illegal_time_classes_are_named_not_silently_dropped(self):
        for bad in (TimeClass.LAP_DURATION, TimeClass.RECEIPT_TIME_ONLY, TimeClass.PROCESSING_TIME):
            e = engine(self.aligned())
            iid = e.open_decision("aligned_lap", SC, T0, known_at=T0)
            e.admit_atom(self.sample(TypedTime(5, bad)), ts(6))
            r = e.evaluate(iid, ts(40))
            assert r.integrity_state == S.DEGRADED and "ILLEGAL_TIME_CLASS" in codes(r)

    def test_time_basis_mismatch_detects_wrong_lap_mapping(self):
        c = contract("aligned_lap", "lap_sample", {"lap_sample": role(time_class_required="SESSION_ELAPSED", time_check_tolerance_s=1.0)})
        e = engine(c)
        iid = e.open_decision("aligned_lap", SC, T0, known_at=T0)
        e.admit_fact(t0_fact(), ts(1)); e.admit_fact(lap_start_fact(3600.0), ts(1))
        # sample says 30s into the lap (=> session 3630s) but its absolute stamp says it happened at T0+5s
        e.admit_atom(self.sample(TypedTime(sec_to_us(30), TimeClass.LAP_RELATIVE)), ts(6))
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and "TIME_BASIS_MISMATCH" in codes(r)


class TestScenarioCorroborationAndCommonCause:
    def feed(self, e, iid, origins):
        for i, o in enumerate(origins):
            e.admit_atom(atom("lap_record", 90.1 + i * 0.01, 5 + i * 0.1, [o[0]], processing_origins=[o[1]]), ts(6))

    def mandatory(self):
        return lap_time_contract(corroboration={"mode": "MANDATORY", "min_source_depth": 1})

    def test_duplicate_processors_on_one_source_are_not_independent_corroboration(self):
        e = engine(self.mandatory())
        iid = e.open_decision("lap_time", SC, T0)
        self.feed(e, iid, [("PITWALL", "proc_A"), ("PITWALL", "proc_B")])
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and "INSUFFICIENT_CORROBORATION" in codes(r)
        assert r.content["roles"]["lap_record"]["processing_depth"] == 1 and r.content["roles"]["lap_record"]["source_depth"] == 0

    def test_two_providers_sharing_one_upstream_are_not_independent(self):
        e = engine(self.mandatory())
        iid = e.open_decision("lap_time", SC, T0)
        self.feed(e, iid, [("PITWALL", "a1"), ("TRACINGINSIGHTS", "a2")])
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and r.content["roles"]["lap_record"]["source_depth"] == 0

    def test_truly_independent_sources_satisfy_mandatory_corroboration(self):
        e = engine(self.mandatory())
        iid = e.open_decision("lap_time", SC, T0)
        self.feed(e, iid, [("PITWALL", "a1"), ("CAR_SENSOR", "a2")])
        assert e.evaluate(iid, ts(7)).integrity_state == S.HEALTHY

    def test_common_cause_exposure_derived_from_lineage_and_resilience_requirement(self):
        e = engine(lap_time_contract(fault={"resilience_requirement": 1}))
        iid = e.open_decision("lap_time", SC, T0)
        self.feed(e, iid, [("PITWALL", "a1"), ("TRACINGINSIGHTS", "a2")])
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and {"INSUFFICIENT_RESILIENCE", "COMMON_CAUSE_EXPOSURE"} <= codes(r)
        assert r.content["resilience"]["critical_origins"] == ["S:F1_FOM_TIMING"]
        assert any(x.startswith("UNMODELLED_COMMON_CAUSE") for x in r.content["limitations"])   # derived, not hard-coded

    def test_resilience_shortfall_is_not_final_while_slots_are_open_and_a_late_independent_source_cures_it(self):
        e = engine(lap_time_contract(fault={"resilience_requirement": 1}))
        iid = e.open_decision("lap_time", SC, T0)
        self.feed(e, iid, [("PITWALL", "a1"), ("TRACINGINSIGHTS", "a2")])
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and r.resolution_maturity == "OPEN" and "HEALTHY" in r.content["envelope"]["alternatives"]
        e.admit_atom(atom("lap_record", 90.1, 5.2, ["CAR_SENSOR"]), ts(20))            # an independent source arrives late (< cutoff)
        r2 = e.evaluate(iid, ts(21))
        assert r2.integrity_state == S.HEALTHY and r2.content["resilience"]["critical_origins"] == []
        f = e.evaluate(iid, ts(200))
        assert f.integrity_state == S.HEALTHY and f.finality_status == "FINAL"

    def test_independent_pair_survives_loss_of_any_one_origin_but_not_two(self):
        e = engine(lap_time_contract(fault={"resilience_requirement": 1, "report_k": 2}))
        iid = e.open_decision("lap_time", SC, T0)
        self.feed(e, iid, [("PITWALL", "a1"), ("CAR_SENSOR", "a2")])
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.HEALTHY and r.content["resilience"]["critical_origins"] == []
        assert r.content["resilience"]["profile"]["1"] == "HEALTHY" and r.content["resilience"]["profile"]["2"] != "HEALTHY"


class TestScenarioConflictDiagnosis:
    def run(self, vals, budget):
        c = contract("speed", "v", {"v": role(agreement={"metric": "abs_diff", "unit": "kph", "tolerance": 0.5})},
                     fault={"diagnosis_budget": budget})
        e = engine(c)
        iid = e.open_decision("speed", SC, T0)
        for i, (o, v) in enumerate(vals):
            e.admit_atom(atom("v", v, 5 + i * 0.1, [o], unit="kph"), ts(6))
        return e.evaluate(iid, ts(7))

    def test_three_sources_outlier_is_excluded_only_when_every_minimal_diagnosis_agrees(self):
        r = self.run([("A", 60.1), ("B", 63.0), ("C", 60.0)], budget=1)
        assert r.integrity_state == S.HEALTHY and r.content["diagnosis"]["result"] == "EXCLUDED_FAULTS"
        assert len(r.content["diagnosis"]["excluded_items"]) == 1
        assert "EXCLUDED_FAULTY_ORIGIN" in codes(r)

    def test_two_sources_conflict_is_ambiguous_never_picks_a_winner(self):
        r = self.run([("A", 60.1), ("B", 63.0)], budget=1)
        assert r.integrity_state == S.SUSPECT and r.content["diagnosis"]["result"] == "DIAGNOSIS_AMBIGUOUS"
        assert r.content["diagnosis"]["excluded_items"] == []

    def test_zero_budget_conflict_is_suspect(self):
        r = self.run([("A", 60.1), ("B", 63.0), ("C", 60.0)], budget=0)
        assert r.integrity_state == S.SUSPECT and r.content["diagnosis"]["result"] == "FAULT_BUDGET_EXCEEDED"


class TestScenarioMonacoAndSystemicFaults:
    def feed(self, e, iid, configured=2615.0, timing=61.2, vehicle=61.0, geometry=2615.0, bias=None, at=6):
        e.admit_atom(atom("timing_speed", timing, 5, ["PITWALL"], unit="kph"), ts(at))
        e.admit_atom(atom("vehicle_speed", vehicle, 5.1, ["CAR_SENSOR"], unit="kph"), ts(at))
        e.admit_atom(atom("configured_distance", configured, 1, ["TIMING_CONFIG"], scope=SESSION, unit="cm"), ts(at))
        e.admit_fact(make_fact("track_geometry", SESSION, geometry, ["SURVEY"], unit="cm"), ts(at))
        if bias is not None:
            e.admit_fact(bias, ts(at))

    def good_bias(self):
        return make_fact("calibration_bias", SESSION, 0.001, ["POP_MONITOR"], unit="ratio")

    def setup(self, with_bias=True):
        e = engine(pit_speed_contract(with_bias), contract("pit_entry_basic", "timing_speed", {"timing_speed": role(agreement={"metric": "abs_diff", "unit": "kph", "tolerance": 0.5})}))
        return e, e.open_decision("pit_speed", SC, T0), e.open_decision("pit_entry_basic", SC, T0)

    def test_consistent_configuration_is_healthy(self):
        e, iid, _ = self.setup()
        self.feed(e, iid, bias=self.good_bias())
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.HEALTHY and r.content["constraints"]["distance_vs_geometry"]

    def test_monaco_wrong_configured_distance_is_caught_by_geometry_constraint(self):
        e, iid, _ = self.setup()
        self.feed(e, iid, configured=2692.0, bias=self.good_bias())                # 2692 cm configured vs 2615 cm surveyed
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and "CONSTRAINT_VIOLATION" in codes(r)
        assert "distance_vs_geometry" in r.to_dict()["primary_binding_witness"] or "77" in r.to_dict()["primary_binding_witness"]

    def test_speed_inflation_vs_independent_vehicle_measurement(self):
        e, iid, _ = self.setup()
        self.feed(e, iid, timing=62.9, vehicle=61.1, bias=self.good_bias())        # ~2.9% inflation
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT
        assert any("speed_vs_vehicle" in w["detail"] or w["role"] == "speed_vs_vehicle" for w in r.witnesses)

    def test_population_bias_makes_session_wide_fault_visible_and_locality_keeps_other_decisions_clean(self):
        pairs = [(60 + (i % 5) * 0.1, (60 + (i % 5) * 0.1) * 1.029) for i in range(423)]
        bias = estimate_bias(pairs, 0.015, 30, SESSION, ["POP_MONITOR"])
        assert bias.grade == S.SUSPECT and "flagged=423" in bias.note
        e, iid, basic = self.setup()
        self.feed(e, iid, timing=61.2, vehicle=61.1, bias=bias)                    # this passage's own checks all pass
        e.admit_atom(atom("timing_speed", 61.2, 5, ["PITWALL"], unit="kph"), ts(6))
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and "REFERENCE_FACT_GRADE" in codes(r)   # systemic bias flagged
        assert e.evaluate(basic, ts(7)).integrity_state == S.HEALTHY                   # contract without that role is untouched

    def test_bias_monitor_needs_enough_samples_and_healthy_population_passes(self):
        assert estimate_bias([(60, 61)] * 3, 0.015, 30, SESSION, ["POP_MONITOR"]).grade == S.UNKNOWN
        assert estimate_bias([(60, 60.2)] * 40, 0.015, 30, SESSION, ["POP_MONITOR"]).grade == S.HEALTHY


class TestScenarioIntervalConstraint:
    def run(self, rec_val, end_val, end_class="SESSION_ELAPSED", extra=()):
        e = engine(lap_consistency_contract(end_class))
        iid = e.open_decision("lap_consistency", SC, T0, known_at=T0)
        e.admit_fact(lap_start_fact(3600.0), ts(2))
        for f in extra:
            e.admit_fact(f, ts(2))
        e.admit_atom(atom("lap_record", rec_val, 5, ["PITWALL"]), ts(6))
        e.admit_atom(atom("lap_end", end_val, 5.1, ["CAR_SENSOR"]), ts(6))
        return e, iid

    def test_lap_time_equals_end_minus_start(self):
        e, iid = self.run(92.3, 3692.3)
        assert e.evaluate(iid, ts(7)).integrity_state == S.HEALTHY
        e, iid = self.run(95.0, 3692.3)
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and "CONSTRAINT_VIOLATION" in codes(r)

    def test_typed_conversion_lap_relative_end_is_converted_through_lap_start(self):
        e, iid = self.run(92.3, 92.3, end_class="LAP_RELATIVE")
        assert e.evaluate(iid, ts(7)).integrity_state == S.HEALTHY

    def test_missing_session_t0_makes_constraint_unevaluable_then_degraded(self):
        end_abs = T0US / 1e6 + 3692.3
        e, iid = self.run(92.3, end_abs, end_class="ABSOLUTE_UTC")
        r = e.evaluate(iid, ts(10))
        assert r.integrity_state == S.UNKNOWN and "CONSTRAINT_UNEVALUABLE" in codes(r)
        assert e.evaluate(iid, ts(95)).integrity_state == S.DEGRADED               # never silently HEALTHY
        e2, iid2 = self.run(92.3, end_abs, end_class="ABSOLUTE_UTC", extra=[t0_fact()])
        assert e2.evaluate(iid2, ts(10)).integrity_state == S.HEALTHY


class TestScenarioLocalityGuardsAndBounds:
    def test_weather_outage_degrades_only_decisions_that_depend_on_weather(self):
        wc = contract("weather_report", "weather", {"weather": role(scope_class="SESSION", admissible_source_origins=["WEATHER_FEED"],
                      agreement={"metric": "abs_diff", "unit": "celsius", "tolerance": 0.5})}, scope="SESSION")
        e = engine(wc, lap_time_contract())
        w = e.open_decision("weather_report", SESSION, T0, known_at=T0)
        lap = e.open_decision("lap_time", SC, T0, known_at=T0)
        e.admit_guard(make_guard("WEATHER_FEED", "STALLED", ts(2)), ts(3))        # supervisor says: weather feed silent since +2s
        e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"]), ts(6))
        assert e.evaluate(w, ts(5)).integrity_state == S.DEGRADED                  # early degrade, before the 30s deadline
        assert e.evaluate(lap, ts(7)).integrity_state == S.HEALTHY

    def test_guard_on_shared_upstream_stalls_every_dependent_origin(self):
        wc = contract("t", "x", {"x": role(scope_class="SESSION", admissible_source_origins=["PITWALL", "TRACINGINSIGHTS"])}, scope="SESSION")
        e = engine(wc)
        iid = e.open_decision("t", SESSION, T0, known_at=T0)
        e.admit_guard(make_guard("F1_FOM_TIMING", "STALLED", ts(1)), ts(2))
        assert e.evaluate(iid, ts(4)).integrity_state == S.DEGRADED

    def test_physical_plausibility_bounds(self):
        c = contract("sp", "v", {"v": role(agreement={"metric": "abs_diff", "unit": "kph", "tolerance": 1})},
                     constraints=[{"id": "plausible", "kind": "bounds", "operands": ["v"], "lo": 0, "hi": 400}])
        e = engine(c)
        iid = e.open_decision("sp", SC, T0)
        e.admit_atom(atom("v", 1000.0, 5, ["PITWALL"], unit="kph"), ts(6))
        r = e.evaluate(iid, ts(7))
        assert r.integrity_state == S.SUSPECT and "CONSTRAINT_VIOLATION" in codes(r)

    def test_k_of_n_and_or_formulas_follow_lattice_semantics(self):
        c = contract("k", "K_OF_N(2, a, b, c)", {n: role() for n in "abc"})
        e = engine(c)
        iid = e.open_decision("k", SC, T0)
        for n, o in zip("ab", ["PITWALL", "CAR_SENSOR"]):
            e.admit_atom(atom(n, 1.0, 5, [o]), ts(6))
        assert e.evaluate(iid, ts(7)).integrity_state == S.HEALTHY                  # 2 of 3 healthy suffices while c is still pending
        assert e.evaluate(iid, ts(200)).integrity_state == S.HEALTHY                # c degraded at deadline, 2-of-3 still holds


class TestScenarioFinalityAndAudit:
    def final_engine(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0)
        e.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"]), ts(6))
        e.admit_atom(atom("lap_record", 90.1, 5, ["CAR_SENSOR"]), ts(6))
        e.evaluate(iid, ts(7))
        return e, iid, e.evaluate(iid, ts(200))

    def test_post_finality_evidence_is_quarantined_logged_and_never_mutates_verdict(self):
        e, iid, fin = self.final_engine()
        assert fin.finality_status == "FINAL"
        e.admit_atom(atom("lap_record", 70.0, 5, ["GPS"]), ts(300))
        again = e.evaluate(iid, ts(400))
        assert again.record_hash == fin.record_hash and again.content_hash == fin.content_hash
        assert e.finality_violations[0]["code"] == "POST_FINALITY_QUARANTINED" and e.finality_violations[0]["decision_instance_id"] == iid

    def test_late_evidence_inside_lateness_window_is_admitted_with_witness(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0, known_at=T0)
        assert e.evaluate(iid, ts(35)).integrity_state == S.DEGRADED
        e.admit_atom(atom("lap_record", 90.1, 20, ["PITWALL"]), ts(50))             # arrives 20s after the slot deadline
        r = e.evaluate(iid, ts(55))
        assert r.integrity_state == S.HEALTHY and "LATE_EVIDENCE_ADMITTED" in codes(r) and r.reason == "LATE_EVIDENCE"
        assert e.as_of(iid, ts(40)).state_at(ts(40)) == S.DEGRADED                  # history preserved, not overwritten

    def test_evidence_after_cutoff_is_ignored_even_before_sealing(self):
        e = engine(lap_time_contract())
        iid = e.open_decision("lap_time", SC, T0, known_at=T0)
        e.admit_atom(atom("lap_record", 90.1, 95, ["PITWALL"]), ts(95))             # cutoff is +90s
        r = e.evaluate(iid, ts(100))
        assert r.integrity_state == S.DEGRADED and r.finality_status == "FINAL"

    def test_hash_chain_detects_tampering_and_reordering(self):
        e, iid, _ = self.final_engine()
        chain = e.history(iid)
        assert verify_chain(chain)[0] and len(chain) >= 2 and chain[1].previous_record_hash == chain[0].record_hash
        forged = copy.deepcopy(chain[0].content); forged["witnesses"] = []; forged["resolution_maturity"] = "TUPLE_RESOLVED"
        bad = type(chain[0])(**{**chain[0].__dict__, "content": forged})
        assert "tampered" in verify_chain([bad] + chain[1:])[1]
        assert not verify_chain(list(reversed(chain)))[0]

    def test_record_hash_commits_to_previous_link_and_knowledge_time(self):
        from sia_core.verdict import make_record
        c = {"x": 1}
        base = make_record(c, 2, "a" * 64, 1000, "EVIDENCE_CHANGE")[1]
        assert base != make_record(c, 2, "b" * 64, 1000, "EVIDENCE_CHANGE")[1]      # previous link is hashed
        assert base != make_record(c, 2, "a" * 64, 1001, "EVIDENCE_CHANGE")[1]      # knowledge time is hashed
        assert base != make_record(c, 3, "a" * 64, 1000, "EVIDENCE_CHANGE")[1]      # revision number is hashed
        assert make_record(c, 2, "a" * 64, 1000, "EVIDENCE_CHANGE")[0] == make_record(c, 9, "z" * 64, 5, "X")[0]   # content hash ignores the envelope of the chain

    def test_contract_change_creates_new_revision_and_binds_definition_hash(self):
        e, iid, _ = self.final_engine()
        e2 = engine(lap_time_contract())
        i2 = e2.open_decision("lap_time", SC, T0)
        e2.admit_atom(atom("lap_record", 90.1, 5, ["PITWALL"]), ts(6))
        r1 = e2.evaluate(i2, ts(7))
        newc = lap_time_contract(); newc["version"] = "1.1.0"; newc["roles"]["lap_record"]["agreement"]["tolerance"] = 0.2
        e2.register_contract(newc)
        r2 = e2.evaluate(i2, ts(8))
        assert r2.reason == "CONTRACT_CHANGE" and r2.content["contract"]["version"] == "1.1.0" and r2.revision_number == 2

    def test_explanation_and_compat_dict_fields(self):
        e, iid, fin = self.final_engine()
        text = explain(fin)
        assert "HEALTHY" in text and "FINAL" in text and "lap_record" in text
        d = fin.to_dict()
        for k in ("integrity_state", "corroboration_depth" if False else "validity_timeline", "primary_binding_witness", "witness_set",
                  "limiting_children", "resolution_maturity", "finality_status", "verdict_hash", "record_hash", "previous_record_hash",
                  "decision_maturity", "knowledge_time"):
            assert k in d
        assert d["decision_maturity"] == "FINAL"
