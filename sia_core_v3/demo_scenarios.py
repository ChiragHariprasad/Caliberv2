"""Narrated end-to-end scenarios. Run:  PYTHONPATH=. python demo_scenarios.py"""
import sys, json
sys.path.insert(0, "tests")
from helpers import *
from sia_core import explain, estimate_bias, make_guard, make_fact, verify_chain, TypedTime, TimeClass, sec_to_us

def banner(t): print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)

banner("1. MONACO-STYLE: wrong configured loop distance (2692 cm vs 2615 cm surveyed) + 2.9% speed inflation")
e = engine(pit_speed_contract())
iid = e.open_decision("pit_speed", SC, T0)
e.admit_atom(atom("timing_speed", 62.9, 5, ["PITWALL"], unit="kph"), ts(6))
e.admit_atom(atom("vehicle_speed", 61.1, 5.1, ["CAR_SENSOR"], unit="kph"), ts(6))
e.admit_atom(atom("configured_distance", 2692.0, 1, ["TIMING_CONFIG"], scope=SESSION, unit="cm"), ts(6))
e.admit_fact(make_fact("track_geometry", SESSION, 2615.0, ["SURVEY"], unit="cm"), ts(6))
e.admit_fact(make_fact("calibration_bias", SESSION, 0.001, ["POP_MONITOR"], unit="ratio"), ts(6))
print(explain(e.evaluate(iid, ts(7))))

banner("2. SYSTEMIC FAULT: this passage looks fine, but the session-wide population shows a +2.9% bias (423 passages)")
pairs = [(60 + (i % 5) * 0.1, (60 + (i % 5) * 0.1) * 1.029) for i in range(423)]
bias = estimate_bias(pairs, 0.015, 30, SESSION, ["POP_MONITOR"])
e = engine(pit_speed_contract()); iid = e.open_decision("pit_speed", SC, T0)
e.admit_atom(atom("timing_speed", 61.2, 5, ["PITWALL"], unit="kph"), ts(6))
e.admit_atom(atom("vehicle_speed", 61.1, 5.1, ["CAR_SENSOR"], unit="kph"), ts(6))
e.admit_atom(atom("configured_distance", 2615.0, 1, ["TIMING_CONFIG"], scope=SESSION, unit="cm"), ts(6))
e.admit_fact(make_fact("track_geometry", SESSION, 2615.0, ["SURVEY"], unit="cm"), ts(6)); e.admit_fact(bias, ts(6))
print("population fact:", bias.note)
print(explain(e.evaluate(iid, ts(7))))

banner("3. COMMON CAUSE: Pitwall + TracingInsights 'agree' but share the F1 timing upstream (resilience requirement k=1)")
e = engine(lap_time_contract(fault={"resilience_requirement": 1})); iid = e.open_decision("lap_time", SC, T0)
e.admit_atom(atom("lap_record", 90.10, 5, ["PITWALL"]), ts(6)); e.admit_atom(atom("lap_record", 90.11, 5.1, ["TRACINGINSIGHTS"]), ts(6))
print(explain(e.evaluate(iid, ts(7))))

banner("4. CONFLICT DIAGNOSIS: three independent sources, one outlier, diagnosis budget f=1")
c = contract("speed", "v", {"v": role(agreement={"metric": "abs_diff", "unit": "kph", "tolerance": 0.5})}, fault={"diagnosis_budget": 1})
e = engine(c); iid = e.open_decision("speed", SC, T0)
for i, (o, v) in enumerate([("A", 60.1), ("B", 63.0), ("C", 60.0)]): e.admit_atom(atom("v", v, 5 + i * .1, [o], unit="kph"), ts(6))
print(explain(e.evaluate(iid, ts(7))))

banner("5. SILENT FEED + LATE EVIDENCE + BITEMPORAL HISTORY")
e = engine(lap_time_contract()); iid = e.open_decision("lap_time", SC, T0, known_at=T0)
for t in (10, 35): r = e.evaluate(iid, ts(t)); print(f"K=+{t}s  state={r.integrity_state.name}  (rev {r.revision_number})")
e.admit_atom(atom("lap_record", 90.1, 20, ["PITWALL"]), ts(50)); e.admit_atom(atom("lap_record", 90.1, 20, ["CAR_SENSOR"]), ts(50))
r = e.evaluate(iid, ts(55)); print(f"K=+55s  state={r.integrity_state.name}  (rev {r.revision_number}, reason={r.reason})")
f = e.evaluate(iid, ts(200)); print(f"K=+200s state={f.integrity_state.name}  finality={f.finality_status}  (rev {f.revision_number})")
print("as known at +40s, state for valid time +40s :", e.index.state_as_of(iid, ts(40), ts(40)).name)
print("as known at +60s, state for valid time +40s :", e.index.state_as_of(iid, ts(40), ts(60)).name, " <- corrected retroactively, old belief preserved")
print("chain verification:", e.verify())
e.admit_atom(atom("lap_record", 70.0, 5, ["GPS"]), ts(300))
print("post-finality evidence quarantined:", e.finality_violations)
print("\nfinal verdict (compat dict, truncated):")
d = f.to_dict(); print(json.dumps({k: d[k] for k in ("decision_instance_id","integrity_state","resolution_maturity","finality_status","decision_maturity","primary_binding_witness","verdict_hash","record_hash","previous_record_hash")}, indent=2))

banner("6. TYPED TIME: lap-relative sample needs lap_start; wrong-lap reference is refused; LAP_DURATION is never a timestamp")
c = contract("aligned_lap", "lap_sample", {"lap_sample": role(time_class_required="SESSION_ELAPSED")})
e = engine(c); iid = e.open_decision("aligned_lap", SC, T0, known_at=T0)
e.admit_atom(atom("lap_sample", 61.0, 5, ["PITWALL"], time=TypedTime(sec_to_us(30), TimeClass.LAP_RELATIVE)), ts(6))
e.admit_atom(atom("lap_sample", 61.0, 5, ["CAR_SENSOR"], time=TypedTime(sec_to_us(92.1), TimeClass.LAP_DURATION)), ts(6))
e.admit_fact(lap_start_fact(3500.0, scope={**SC, "lap_number": 11}), ts(7))
print(explain(e.evaluate(iid, ts(35))))
