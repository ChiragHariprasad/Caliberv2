"""CALIBRE F1 Contract Catalogue (C01 through C13).

Full implementation of the 13 Decision Evidence Contracts conforming to the
Scoped Integrity Algebra (SIA) specification, covering Failure Taxonomy E1–E17
and Contract Patterns P1–P9.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

_VERSION = "1.0.0"
_EPOCH = 1


def get_c01_lap_time() -> dict[str, Any]:
    """C01: Lap-time consistency (Patterns P1, P6)."""
    return {
        "contract_id": "C01_lap_time_consistency",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "lap_time_validation",
        "decision_scope": {"scope_class": "DRIVER_LAP"},
        "formula": "AND(lap_record, session_t0)",
        "simultaneity_window_s": 2.0,
        "roles": {
            "lap_record": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "SESSION_ELAPSED",
                "value_time_class": "LAP_DURATION",
                "admissible_source_origins": ["F1_FOM_TIMING", "PITWALL", "TRACINGINSIGHTS", "CAR_ECU"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.15},
                "freshness": {"soft_age_s": 15, "hard_age_s": 45},
                "slot": {"deadline_s": 20, "allowed_lateness_s": 60},
                "corroboration": {"mode": "MANDATORY", "min_source_depth": 1, "min_processing_depth": 0},
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
            {"id": "lap_bounds", "kind": "bounds", "operands": ["lap_record"], "lo": 50.0, "hi": 300.0},
        ],
        "fault_model": {"diagnosis_budget": 1, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c02_sector_sum() -> dict[str, Any]:
    """C02: Sector-sum consistency (Pattern P1)."""
    return {
        "contract_id": "C02_sector_sum_consistency",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "sector_sum_validation",
        "decision_scope": {"scope_class": "DRIVER_LAP"},
        "formula": "AND(s1_record, s2_record, s3_record, lap_record)",
        "simultaneity_window_s": 2.0,
        "roles": {
            "s1_record": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "SESSION_ELAPSED",
                "admissible_source_origins": ["F1_FOM_TIMING", "PITWALL"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.05},
                "freshness": {},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 60},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "s2_record": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "SESSION_ELAPSED",
                "admissible_source_origins": ["F1_FOM_TIMING", "PITWALL"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.05},
                "freshness": {},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 60},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "s3_record": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "SESSION_ELAPSED",
                "admissible_source_origins": ["F1_FOM_TIMING", "PITWALL"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.05},
                "freshness": {},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 60},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "lap_record": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "SESSION_ELAPSED",
                "admissible_source_origins": ["F1_FOM_TIMING", "PITWALL"],
                "agreement": {"metric": "abs_diff", "unit": "s", "tolerance": 0.05},
                "freshness": {},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 60},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [
            {
                "id": "sector_sum_linear",
                "kind": "linear",
                "operands": ["s1_record", "s2_record", "s3_record", "lap_record"],
                "coeffs": [1.0, 1.0, 1.0, -1.0],
                "tolerance": 0.05,
            }
        ],
        "fault_model": {"diagnosis_budget": 1, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c03_pit_speed() -> dict[str, Any]:
    """C03: Pit-lane speed integrity - Flagship Contract (Patterns P1, P2, P3, P4, P8)."""
    return {
        "contract_id": "C03_pit_lane_speed_integrity",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "pit_speed_validation",
        "decision_scope": {"scope_class": "SECTOR"},
        "formula": "AND(timing_speed, vehicle_speed, track_geometry, calibration_bias)",
        "simultaneity_window_s": 2.0,
        "roles": {
            "timing_speed": {
                "kind": "evidence",
                "scope_class": "SECTOR",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["F1_FOM_TIMING", "PITWALL", "TRACINGINSIGHTS"],
                "agreement": {"metric": "abs_diff", "unit": "kph", "tolerance": 0.5},
                "freshness": {"soft_age_s": 10, "hard_age_s": 30},
                "slot": {"deadline_s": 15, "allowed_lateness_s": 45},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "vehicle_speed": {
                "kind": "evidence",
                "scope_class": "SECTOR",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["CAR_ECU"],
                "agreement": {"metric": "abs_diff", "unit": "kph", "tolerance": 0.5},
                "freshness": {"soft_age_s": 10, "hard_age_s": 30},
                "slot": {"deadline_s": 15, "allowed_lateness_s": 45},
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
            {
                "id": "speed_cross_check_ratio",
                "kind": "ratio",
                "operands": ["timing_speed", "vehicle_speed"],
                "tolerance": 0.03,  # 3% tolerance
            },
            {
                "id": "pit_limit_bounds_with_margin",
                "kind": "bounds",
                "operands": ["timing_speed"],
                "lo": 0.0,
                "hi": 80.0,
                "uncertainty": 0.15,  # Pattern P3: ±0.15 kph guard-band uncertainty
            },
        ],
        "fault_model": {"diagnosis_budget": 1, "resilience_requirement": 1, "report_k": 1},
        "limitations": [],
    }


def get_c04_vehicle_kinematics() -> dict[str, Any]:
    """C04: Vehicle kinematic plausibility (Pattern P1)."""
    return {
        "contract_id": "C04_vehicle_kinematics",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "kinematics_validation",
        "decision_scope": {"scope_class": "SECTOR"},
        "formula": "kinematic_flags",
        "simultaneity_window_s": 1.0,
        "roles": {
            "kinematic_flags": {
                "kind": "evidence",
                "scope_class": "SECTOR",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["CAR_ECU"],
                "agreement": {"metric": "discrete_equality"},
                "freshness": {"soft_age_s": 5, "hard_age_s": 15},
                "slot": {"deadline_s": 10, "allowed_lateness_s": 30},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [
            {"id": "plausibility_check", "kind": "bounds", "operands": ["kinematic_flags"], "lo": 1.0, "hi": 1.0}
        ],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c05_telemetry_alignment() -> dict[str, Any]:
    """C05: Telemetry time alignment (Pattern P6)."""
    return {
        "contract_id": "C05_telemetry_alignment",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "alignment_validation",
        "decision_scope": {"scope_class": "DRIVER_LAP"},
        "formula": "AND(vehicle_speed, session_t0)",
        "simultaneity_window_s": 2.0,
        "roles": {
            "vehicle_speed": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["CAR_ECU"],
                "agreement": {"metric": "abs_diff", "unit": "kph", "tolerance": 1.0},
                "freshness": {"soft_age_s": 15, "hard_age_s": 45},
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
            {"id": "speed_physical_bounds", "kind": "bounds", "operands": ["vehicle_speed"], "lo": 0.0, "hi": 380.0}
        ],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c06_position_track() -> dict[str, Any]:
    """C06: Position and track consistency (Patterns P1, P2, P6)."""
    return {
        "contract_id": "C06_position_track_consistency",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "spatial_validation",
        "decision_scope": {"scope_class": "DRIVER_LAP"},
        "formula": "AND(gate_crossing, track_geometry)",
        "simultaneity_window_s": 2.0,
        "roles": {
            "gate_crossing": {
                "kind": "evidence",
                "scope_class": "DRIVER_LAP",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["CAR_POSITION"],
                "agreement": {"metric": "abs_diff", "unit": "us", "tolerance": 50000},
                "freshness": {"soft_age_s": 20, "hard_age_s": 60},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 90},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
            "track_geometry": {
                "kind": "reference",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "fact_type": "track_geometry",
                "agreement": {"metric": "discrete_equality"},
                "freshness": {},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            },
        },
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c07_session_status() -> dict[str, Any]:
    """C07: Session-status integrity (Patterns P1, P5)."""
    return {
        "contract_id": "C07_session_status_integrity",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "status_validation",
        "decision_scope": {"scope_class": "SESSION"},
        "formula": "session_state",
        "simultaneity_window_s": 2.0,
        "roles": {
            "session_state": {
                "kind": "evidence",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["FIA_RACE_CONTROL"],
                "agreement": {"metric": "discrete_equality"},
                "freshness": {"soft_age_s": 30, "hard_age_s": 90},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 120},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c08_incident_timing() -> dict[str, Any]:
    """C08: Incident timing & hazard verification (Pattern P6)."""
    return {
        "contract_id": "C08_incident_timing",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "incident_validation",
        "decision_scope": {"scope_class": "SESSION"},
        "formula": "session_state",
        "simultaneity_window_s": 2.0,
        "roles": {
            "session_state": {
                "kind": "evidence",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["FIA_RACE_CONTROL"],
                "agreement": {"metric": "discrete_equality"},
                "freshness": {"soft_age_s": 15, "hard_age_s": 45},
                "slot": {"deadline_s": 20, "allowed_lateness_s": 60},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c09_weather_reporting() -> dict[str, Any]:
    """C09: Weather reporting (Pattern P5)."""
    return {
        "contract_id": "C09_weather_reporting",
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
                "admissible_source_origins": ["WEATHER_SERVICE", "FIA_RACE_CONTROL"],
                "agreement": {"metric": "abs_diff", "unit": "celsius", "tolerance": 1.0},
                "freshness": {"soft_age_s": 60, "hard_age_s": 180},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 180},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [
            {"id": "temperature_bounds", "kind": "bounds", "operands": ["weather_reading"], "lo": -10.0, "hi": 60.0}
        ],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c10_weather_advisory() -> dict[str, Any]:
    """C10: Weather-dependent advisory - shows scope locality (Pattern P5)."""
    return {
        "contract_id": "C10_weather_advisory",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "advisory_validation",
        "decision_scope": {"scope_class": "SESSION"},
        "formula": "weather_reading",
        "simultaneity_window_s": 5.0,
        "roles": {
            "weather_reading": {
                "kind": "evidence",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["WEATHER_SERVICE"],
                "agreement": {"metric": "abs_diff", "unit": "celsius", "tolerance": 2.0},
                "freshness": {"soft_age_s": 30, "hard_age_s": 60},
                "slot": {"deadline_s": 30, "allowed_lateness_s": 90},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": ["SCOPE_LOCAL_WEATHER_ONLY"],
    }


def get_c11_feed_integrity() -> dict[str, Any]:
    """C11: Feed-source integrity (Patterns P5, P9)."""
    return {
        "contract_id": "C11_feed_integrity",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "feed_validation",
        "decision_scope": {"scope_class": "SESSION"},
        "formula": "feed_health",
        "simultaneity_window_s": 2.0,
        "roles": {
            "feed_health": {
                "kind": "evidence",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "admissible_source_origins": ["FEED_SUPERVISOR_TAP"],
                "agreement": {"metric": "abs_diff", "unit": "ratio", "tolerance": 0.05},
                "freshness": {"soft_age_s": 5, "hard_age_s": 15},
                "slot": {"deadline_s": 10, "allowed_lateness_s": 30},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [
            {"id": "health_ratio_check", "kind": "bounds", "operands": ["feed_health"], "lo": 0.8, "hi": 1.0}
        ],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c12_monitor_health() -> dict[str, Any]:
    """C12: Monitor health (Patterns P4, P9)."""
    return {
        "contract_id": "C12_monitor_health",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "monitor_validation",
        "decision_scope": {"scope_class": "SESSION"},
        "formula": "calibration_bias",
        "simultaneity_window_s": 2.0,
        "roles": {
            "calibration_bias": {
                "kind": "reference",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "fact_type": "calibration_bias",
                "agreement": {"metric": "abs_diff", "unit": "ratio", "tolerance": 0.02},
                "freshness": {},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 180},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [
            {"id": "bias_drift_bounds", "kind": "bounds", "operands": ["calibration_bias"], "lo": -0.05, "hi": 0.05}
        ],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


def get_c13_rule_regime() -> dict[str, Any]:
    """C13: Rule-regime consistency (Pattern P8)."""
    return {
        "contract_id": "C13_rule_regime_consistency",
        "version": _VERSION,
        "epoch": _EPOCH,
        "decision_type": "regime_validation",
        "decision_scope": {"scope_class": "SESSION"},
        "formula": "track_geometry",
        "simultaneity_window_s": 2.0,
        "roles": {
            "track_geometry": {
                "kind": "reference",
                "scope_class": "SESSION",
                "time_class_required": "ABSOLUTE_UTC",
                "fact_type": "track_geometry",
                "agreement": {"metric": "discrete_equality"},
                "freshness": {},
                "slot": {"deadline_s": 60, "allowed_lateness_s": 180},
                "corroboration": {"mode": "INFORMATIONAL"},
            }
        },
        "constraints": [],
        "fault_model": {"diagnosis_budget": 0, "resilience_requirement": 0, "report_k": 1},
        "limitations": [],
    }


_CATALOGUE: Dict[str, callable] = {
    "C01": get_c01_lap_time,
    "C02": get_c02_sector_sum,
    "C03": get_c03_pit_speed,
    "C04": get_c04_vehicle_kinematics,
    "C05": get_c05_telemetry_alignment,
    "C06": get_c06_position_track,
    "C07": get_c07_session_status,
    "C08": get_c08_incident_timing,
    "C09": get_c09_weather_reporting,
    "C10": get_c10_weather_advisory,
    "C11": get_c11_feed_integrity,
    "C12": get_c12_monitor_health,
    "C13": get_c13_rule_regime,
}


def get_contract(cid: str) -> dict[str, Any] | None:
    fn = _CATALOGUE.get(cid)
    return fn() if fn else None


def list_all_contracts() -> list[dict[str, Any]]:
    return [fn() for fn in _CATALOGUE.values()]

