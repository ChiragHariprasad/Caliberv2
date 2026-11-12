"""Default F1 Decision Evidence Contracts for PULSE.

Each contract dict conforms to the SIA Core v3 ``parse_contract()`` schema:
  - contract_id, version, epoch, decision_type
  - decision_scope: {scope_class}
  - formula: str (AST text)
  - roles: {name: {kind, scope_class, time_class_required, agreement, freshness, slot, corroboration, ...}}
  - constraints: [{id, kind, operands, tolerance, ...}]
  - fault_model: {diagnosis_budget, resilience_requirement, report_k}
  - simultaneity_window_s

Public API
----------
get_default_contracts()       -> list[dict]   all contracts
load_contracts_for_session()  -> list[dict]   filtered by session type
get_contract_by_id()          -> dict | None  single contract lookup
"""
from __future__ import annotations

from typing import Any

_VERSION = "1.0.0"
_EPOCH = 1
_WINDOW_S = 2.0


def _lap_time_contract() -> dict[str, Any]:
    """DRIVER_LAP: validates lap timing with multi-source corroboration."""
    return {
        "contract_id": "lap_time",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "lap_time_validation",
        "decision_scope": {"scope_class": "DRIVER_LAP"},
        "formula": "AND(lap_record, lap_start, session_t0)",
        "simultaneity_window_s": _WINDOW_S,
        "roles": {
            "lap_record": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["PITWALL", "TRACINGINSIGHTS", "CAR_SENSOR", "GPS"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.15},
                "freshness": {"soft_age_s": 10, "hard_age_s": 30},
                "slot": {"deadline_s": 15, "allowed_lateness_s": 60},
                "corroboration": {"mode": "MANDATORY", "min_source_depth": 1, "min_processing_depth": 0},
            },
            "lap_start": {
                "kind": "reference",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "SESSION_ELAPSED",
                "fact_type": "lap_start",
                "agreement": {"metric": "discrete_equality"},
                "freshness": {},
                "slot": {"deadline_s": 20, "allowed_lateness_s": 60},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "session_t0": {
                "kind": "reference",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "fact_type": "session_t0",
                "agreement": {"metric": "discrete_equality"},
                "freshness": {},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [
            {"id": "lap_time_bounds", "kind": "bounds", "operands": ["lap_record"], "lo": 1.0, "hi": 300.0},
        ],
        "fault_model": {"diagnosis_budget": 1, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def _pit_speed_contract() -> dict[str, Any]:
    """SECTOR: validates pit lane speed with cross-check against vehicle telemetry."""
    return {
        "contract_id": "pit_speed",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "pit_speed_validation",
        "decision_scope": {"scope_class": "SECTOR"},
        "formula": "AND(timing_speed, vehicle_speed, configured_distance, track_geometry, calibration_bias)",
        "simultaneity_window_s": _WINDOW_S,
        "roles": {
            "timing_speed": {
                "kind": "evidence",
                "scope_class": "SECTOR",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["PITWALL", "TRACINGINSIGHTS"],
                "agreement": {"metric": "abs_diff", "unit": "kph", "tolerance": 0.5},
                "freshness": {"soft_age_s": 5, "hard_age_s": 15},
                "slot": {"deadline_s": 10, "allowed_lateness_s": 30},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "vehicle_speed": {
                "kind": "evidence",
                "scope_class": "SECTOR",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["CAR_SENSOR"],
                "agreement": {"metric": "abs_diff", "unit": "kph", "tolerance": 0.5},
                "freshness": {"soft_age_s": 5, "hard_age_s": 15},
                "slot": {"deadline_s": 10, "allowed_lateness_s": 30},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "configured_distance": {
                "kind": "evidence",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["TIMING_CONFIG"],
                "agreement": {"metric": "discrete_equality", "unit": "cm"},
                "freshness": {},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "track_geometry": {
                "kind": "reference",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "fact_type": "track_geometry",
                "agreement": {"metric": "discrete_equality", "unit": "cm"},
                "freshness": {},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "calibration_bias": {
                "kind": "reference",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "fact_type": "calibration_bias",
                "agreement": {"metric": "abs_diff", "unit": "ratio", "tolerance": 0.01},
                "freshness": {},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [
            {"id": "speed_ratio", "kind": "ratio", "operands": ["timing_speed", "vehicle_speed"], "tolerance": 0.03},
            {"id": "distance_check", "kind": "abs_diff", "operands": ["configured_distance", "track_geometry"], "tolerance": 10.0},
        ],
        "fault_model": {"diagnosis_budget": 1, "resilience_requirement": 1, "report_k": 1},
        "limitations": [],
    }


def _sector_time_contract() -> dict[str, Any]:
    """SECTOR: validates sector timing data."""
    return {
        "contract_id": "sector_time",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "sector_time_validation",
        "decision_scope": {"scope_class": "SECTOR"},
        "formula": "sector_record",
        "simultaneity_window_s": _WINDOW_S,
        "roles": {
            "sector_record": {
                "kind": "evidence",
                "scope_class": "SECTOR",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["PITWALL", "TRACINGINSIGHTS", "CAR_SENSOR"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.1},
                "freshness": {"soft_age_s": 10, "hard_age_s": 30},
                "slot": {"deadline_s": 15, "allowed_lateness_s": 45},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [
            {"id": "sector_time_bounds", "kind": "bounds", "operands": ["sector_record"], "lo": 0.5, "hi": 120.0},
        ],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def _driver_position_contract() -> dict[str, Any]:
    """DRIVER_LAP: validates driver position reports."""
    return {
        "contract_id": "driver_position",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "position_validation",
        "decision_scope": {"scope_class": "DRIVER_LAP"},
        "formula": "position_report",
        "simultaneity_window_s": _WINDOW_S,
        "roles": {
            "position_report": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["PITWALL", "TRACINGINSIGHTS", "FIA_OFFICIAL"],
                "agreement": {"metric": "discrete_equality", "unit": "enum"},
                "freshness": {"soft_age_s": 15, "hard_age_s": 45},
                "slot": {"deadline_s": 20, "allowed_lateness_s": 60},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def _weather_contract() -> dict[str, Any]:
    """SESSION: validates weather observation data."""
    return {
        "contract_id": "weather_observation",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "weather_validation",
        "decision_scope": {"scope_class": "SESSION"},
        "formula": "weather_reading",
        "simultaneity_window_s": 5.0,
        "roles": {
            "weather_reading": {
                "kind": "evidence",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["WEATHER_SERVICE", "PITWALL", "FIA_OFFICIAL"],
                "agreement": {"metric": "abs_diff", "unit": "celsius", "tolerance": 1.0},
                "freshness": {"soft_age_s": 60, "hard_age_s": 120},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_ALL_CONTRACTS: dict[str, callable] = {
    "lap_time": _lap_time_contract,
    "pit_speed": _pit_speed_contract,
    "sector_time": _sector_time_contract,
    "driver_position": _driver_position_contract,
    "weather_observation": _weather_contract,
}

_SESSION_CONTRACTS: dict[str, list[str]] = {
    "RACE": ["lap_time", "pit_speed", "sector_time", "driver_position", "weather_observation"],
    "QUALIFYING": ["lap_time", "sector_time", "driver_position", "weather_observation"],
    "SPRINT": ["lap_time", "pit_speed", "sector_time", "driver_position", "weather_observation"],
    "PRACTICE": ["lap_time", "sector_time", "weather_observation"],
    "FP1": ["lap_time", "sector_time", "weather_observation"],
    "FP2": ["lap_time", "sector_time", "weather_observation"],
    "FP3": ["lap_time", "sector_time", "weather_observation"],
}


def get_default_contracts() -> list[dict[str, Any]]:
    """Return all default contracts as raw dicts for ``parse_contract()``."""
    return [fn() for fn in _ALL_CONTRACTS.values()]


def load_contracts_for_session(session_type: str = "RACE") -> list[dict[str, Any]]:
    """Return contracts applicable to the given session type."""
    key = session_type.upper()
    ids = _SESSION_CONTRACTS.get(key, _SESSION_CONTRACTS["RACE"])
    return [_ALL_CONTRACTS[cid]() for cid in ids if cid in _ALL_CONTRACTS]


def get_contract_by_id(contract_id: str) -> dict[str, Any] | None:
    """Return a single contract dict by its ID, or None."""
    fn = _ALL_CONTRACTS.get(contract_id)
    return fn() if fn else None
