"""Shared builders for SIA core tests and the scenario demo."""
from __future__ import annotations

from sia_core import (IntegrityEngine, IntegrityState, OriginRegistry, TimeClass, TypedTime, fmt_instant, make_atom, make_fact,
                      parse_instant, sec_to_us)

S = IntegrityState
T0 = "2026-06-07T13:00:00Z"
T0US = parse_instant(T0)
SC = {"session_id": "S1", "driver_id": "44", "lap_number": 12}
SESSION = {"session_id": "S1"}


def ts(sec: float) -> str:
    """ISO instant ``sec`` seconds after T0."""
    return fmt_instant(T0US + sec_to_us(sec))


def registry() -> OriginRegistry:
    return OriginRegistry({
        "PITWALL": ["F1_FOM_TIMING"], "TRACINGINSIGHTS": ["F1_FOM_TIMING"],
        "CAR_SENSOR": [], "GPS": [], "WEATHER_FEED": [], "SURVEY": [], "TIMING_CONFIG": ["F1_FOM_TIMING"],
        "A": [], "B": [], "C": [], "POP_MONITOR": ["F1_FOM_TIMING"],
    })


def role(**kw):
    base = {"kind": "evidence", "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.05},
            "slot": {"deadline_s": 30, "allowed_lateness_s": 60}}
    base.update(kw)
    return base


def contract(cid, formula, roles, scope="DRIVER_LAP", constraints=None, fault=None, window=1.0, limitations=None):
    d = {"contract_id": cid, "version": "1.0.0", "epoch": 1, "decision_type": cid.upper(),
         "decision_scope": {"scope_class": scope}, "formula": formula, "roles": roles, "simultaneity_window_s": window}
    if constraints:
        d["constraints"] = constraints
    if fault:
        d["fault_model"] = fault
    if limitations:
        d["limitations"] = limitations
    return d


def engine(*contracts, reg=None) -> IntegrityEngine:
    e = IntegrityEngine(reg or registry())
    for c in contracts:
        e.register_contract(c)
    return e


def atom(role_id, value, at, origins, scope=SC, **kw):
    return make_atom(role_id, value, ts(at) if isinstance(at, (int, float)) else at, scope, origins, **kw)


# ------------------------------------------------------------------ canonical contracts used across tests
def lap_time_contract(fault=None, corroboration=None):
    r = role()
    if corroboration:
        r["corroboration"] = corroboration
    return contract("lap_time", "lap_record", {"lap_record": r}, fault=fault)


def pit_speed_contract(with_bias=True):
    roles = {
        "timing_speed": role(agreement={"metric": "abs_diff", "unit": "kph", "tolerance": 0.5}),
        "vehicle_speed": role(agreement={"metric": "abs_diff", "unit": "kph", "tolerance": 0.5}),
        "configured_distance": role(scope_class="SESSION", agreement={"metric": "abs_diff", "unit": "cm", "tolerance": 0.5}),
        "geometry_distance_ref": {"kind": "reference", "fact_type": "track_geometry", "scope_class": "SESSION",
                                  "agreement": {"metric": "abs_diff", "unit": "cm", "tolerance": 0.5}},
    }
    formula = "AND(timing_speed, vehicle_speed, configured_distance, geometry_distance_ref"
    if with_bias:
        roles["calibration_bias_ref"] = {"kind": "reference", "fact_type": "calibration_bias", "scope_class": "SESSION"}
        formula += ", calibration_bias_ref"
    formula += ")"
    cons = [
        {"id": "speed_vs_vehicle", "kind": "ratio", "operands": ["timing_speed", "vehicle_speed"], "tolerance": 0.015},
        {"id": "distance_vs_geometry", "kind": "abs_diff", "operands": ["configured_distance", "geometry_distance_ref"], "tolerance": 5},
    ]
    return contract("pit_speed", formula, roles, constraints=cons)


def lap_consistency_contract(end_class="SESSION_ELAPSED"):
    roles = {
        "lap_record": role(agreement={"metric": "abs_diff", "unit": "s", "tolerance": 0.001}),
        "lap_end": role(value_time_class=end_class, agreement={"metric": "abs_diff", "unit": "s", "tolerance": 0.001}),
        "lap_start_ref": {"kind": "reference", "fact_type": "lap_start", "value_time_class": "SESSION_ELAPSED", "scope_class": "DRIVER_LAP"},
    }
    cons = [{"id": "lap_time_equals_end_minus_start", "kind": "interval", "duration": "lap_record", "start": "lap_start_ref",
             "end": "lap_end", "time_class": "SESSION_ELAPSED", "tolerance": 0.05}]
    return contract("lap_consistency", "AND(lap_record, lap_end, lap_start_ref)", roles, constraints=cons)


def lap_start_fact(session_elapsed_s, scope=SC, origins=("PITWALL",), **kw):
    return make_fact("lap_start", scope, sec_to_us(session_elapsed_s), origins, unit="us", **kw)


def t0_fact(origins=("PITWALL",), scope=SESSION):
    return make_fact("session_t0", scope, T0US, origins, unit="us")
