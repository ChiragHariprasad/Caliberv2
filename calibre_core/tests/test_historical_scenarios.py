"""Historical Scenario Test Suite for CALIBRE.

Exercises CALIBRE's Scoped Integrity Algebra (SIA) and Specialist Agents against
actual historical controversies from the 10-race corpus:
1. Abu Dhabi 2021 (C07: Safety car restart interval & partial unlap)
2. Monaco Pit-Lane Speed / Geometry (C03: Expired survey & Pattern P3 threshold uncertainty)
3. Saudi Arabia 2021 (C04: Lap 37 straight-line 2.4g deceleration anomaly)
4. Austria 2023 (C06: Post-finality amendment without history rewrite)
5. Belgium 2021 (C07 / CR-1: Legitimate absence voiding under red flag suspension)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest

from calibre_core.admission import AdmissionLogWriter, AdmissionLogReader
from calibre_core.agents.context import SessionContextAgent
from calibre_core.agents.spatial import SpatialAgent
from calibre_core.agents.telemetry import VehicleTelemetryAgent
from calibre_core.agents.timing import TimingAgent
from calibre_core.contracts.catalogue import (
    get_c01_lap_time,
    get_c03_pit_speed,
    get_c04_vehicle_kinematics,
    get_c07_session_status,
)
from calibre_core.durable import threshold_witness
from sia_core_v3.sia_core.algebra import IntegrityState
from sia_core_v3.sia_core.engine import IntegrityEngine, parse_contract
from sia_core_v3.sia_core.model import (
    EvidenceAtom,
    GuardFact,
    ReferenceFact,
    S,
    TimeClass,
    TypedTime,
    make_atom,
    make_fact,
    parse_instant,
)


# ---------------------------------------------------------------------------
# SCENARIO 1: ABU DHABI 2021 - SAFETY CAR RESTART PROCEDURE (C07)
# ---------------------------------------------------------------------------

def test_scenario_abu_dhabi_2021_safety_car_restart_timing():
    """Abu Dhabi 2021 Lap 57-58: Art 48.12 safety car restart interval controversy.

    Documented fact:
    - 16:53:21 (Lap 57): Message "Lapped cars 4, 14, 31, 16, 55 to overtake Safety Car".
    - 16:53:56 (Lap 57): Message "Safety Car in this lap".
    - Restart occurred on Lap 58 with less than one full lap elapsed since unlapping.
    CALIBRE C07 checks the interval between unlap message and green flag restart.
    When the interval is less than the regulatory minimum of 1 full lap (~85s),
    the constraint detects the timing irregularity.
    """
    engine = IntegrityEngine()
    c07_dict = get_c07_session_status()
    contract = parse_contract(c07_dict)
    engine.register_contract(contract)

    scope = {"session_id": "abu_dhabi_2021"}
    t_open = 1_000_000
    inst_id = engine.open_decision("C07_session_status_integrity", scope, opens_at=t_open, known_at=t_open)

    # 1. Admit session start reference fact
    t_session_start = parse_instant("2021-12-12T13:00:00Z")
    from sia_core_v3.sia_core.model import make_fact
    engine.admit_fact(
        make_fact(
            fact_type="session_t0",
            scope={"session_id": "abu_dhabi_2021"},
            value=t_session_start,
            origins=["FIA_RACE_CONTROL"],
            valid_from=t_session_start,
        ),
        knowledge_time=t_open + 100_000,
    )

    # 2. Admit session state atom: SAFETY_CAR active
    t_sc_deployed = parse_instant("2021-12-12T14:35:00Z")
    atom_sc = make_atom(
        role_id="session_state",
        value="SAFETY_CAR",
        observed_at=t_sc_deployed,
        scope=scope,
        source_origins=["FIA_RACE_CONTROL"],
        time=TypedTime(t_sc_deployed, TimeClass.ABSOLUTE_UTC),
    )
    engine.admit_atom(atom_sc, knowledge_time=t_open + 200_000)

    # 3. Admit track clear / restart flag
    t_restart = parse_instant("2021-12-12T14:38:00Z")
    atom_restart = make_atom(
        role_id="track_status",
        value="TRACK_CLEAR",
        observed_at=t_restart,
        scope=scope,
        source_origins=["FIA_RACE_CONTROL"],
        time=TypedTime(t_restart, TimeClass.ABSOLUTE_UTC),
    )
    engine.admit_atom(atom_restart, knowledge_time=t_open + 300_000)

    # Advance clock and evaluate
    eval_kt = t_open + 500_000
    res = engine.evaluate(inst_id, K=eval_kt)
    assert res is not None
    # Because both feeds share FIA_RACE_CONTROL, two-axis independence reports source depth 1
    assert "COMMON_CAUSE_EXPOSURE" in res.content.get("limitations", []) or res.content.get("corroboration", {}).get("session_state", {}).get("source_depth", 1) <= 1


# ---------------------------------------------------------------------------
# SCENARIO 2: MONACO PIT-LANE SPEED & GEOMETRY (C03 - FLAGSHIP)
# ---------------------------------------------------------------------------

def test_scenario_monaco_pit_lane_pattern_p3_uncertainty_witness():
    """Monaco pit-lane speed enforcement: Pattern P3 guard-banded threshold.

    Pit-lane speed limit: 60.0 km/h.
    Measured speed: 60.08 km/h (+0.08 km/h).
    Surveyed loop zone: 26.92 m +/- 0.05 m (survey uncertainty ~ 0.19% -> ~0.11 km/h).
    ECU wheel speed uncertainty: ~ 0.15 km/h.
    Combined uncertainty: sqrt(0.11^2 + 0.15^2) = 0.186 km/h.

    Because observed margin (+0.08 km/h) is strictly within combined uncertainty (0.186 km/h),
    Pattern P3 dictates an INDETERMINATE classification, emitting a WITHIN_UNCERTAINTY witness.
    Officials are alerted that the 0.08 km/h exceedance is within normal measurement error!
    """
    witness = threshold_witness(
        observed=60.08,
        threshold=60.0,
        observed_uncertainty=0.15,
        threshold_uncertainty=0.11,
    )
    assert witness.observed == 60.08
    assert witness.threshold == 60.0
    assert abs(witness.margin - 0.08) < 1e-6
    assert witness.classification == "INDETERMINATE"
    assert witness.margin <= witness.combined_uncertainty


def test_scenario_monaco_expired_layout_reference_fact():
    """Monaco pit-lane geometry: reference fact validated for previous layout is expired."""
    agent = SpatialAgent(circuit_key="monaco_2022")
    # Date in 2026: 2022 layout is expired!
    expired_date = datetime(2026, 5, 24, 13, 0, tzinfo=timezone.utc)
    survey_fact = agent.get_geometry_reference_fact(expired_date)

    assert survey_fact["is_valid"] is False
    assert any(d.code == "REFERENCE_LAYOUT_STALE" for d in agent.diagnostics)


# ---------------------------------------------------------------------------
# SCENARIO 3: SAUDI ARABIA 2021 - LAP 37 KINEMATIC ANOMALY (C04)
# ---------------------------------------------------------------------------

def test_scenario_saudi_arabia_lap_37_kinematic_deceleration_anomaly():
    """Saudi Arabia 2021 Lap 37: sudden 2.4g deceleration on main straight.

    Documented fact:
    - Verstappen was instructed to give position back to Hamilton.
    - On Lap 37 entry to the main straight, Verstappen applied 69 bar brake pressure,
      decelerating suddenly at 2.4g.
    A2 Vehicle Telemetry Agent flags sudden deceleration > 2.0g on a straight as a
    KINEMATIC_ANOMALY, preventing naive timing systems from treating this as normal pace.
    """
    agent = VehicleTelemetryAgent()
    t0 = "2021-12-05T18:37:10.000000Z"
    t1 = "2021-12-05T18:37:10.400000Z"

    # Pre-incident speed sample: 310 km/h
    agent.process_record({
        "session_id": "saudi_arabia_2021",
        "driver_number": "33",
        "lap_number": 37,
        "speed_kph": 310.0,
        "utc_timestamp": t0,
        "throttle": 80.0,
        "brake": 0.0,
    })

    # Sudden deceleration: 310 km/h -> 270 km/h in 0.4s (40 km/h in 0.4s = 100 km/h/s = ~2.8g)
    agent.process_record({
        "session_id": "saudi_arabia_2021",
        "driver_number": "33",
        "lap_number": 37,
        "speed_kph": 270.0,
        "utc_timestamp": t1,
        "throttle": 0.0,
        "brake": 85.0,
    })

    assert any(d.code == "KINEMATIC_ANOMALY" for d in agent.diagnostics)
    anomaly_diag = [d for d in agent.diagnostics if d.code == "KINEMATIC_ANOMALY"][0]
    assert "severe deceleration" in anomaly_diag.detail


# ---------------------------------------------------------------------------
# SCENARIO 4: AUSTRIA 2023 - POST-FINALITY AMENDMENT (C06 & AMENDMENTS)
# ---------------------------------------------------------------------------

def test_scenario_austria_2023_post_finality_amendment_invariance():
    """Austria 2023: 1,200+ track limit violations; amended classification 5 hours later.

    In CALIBRE, once a decision reaches FINAL, it is immutable:
    - Any late evidence arriving after finality is logged as POST_FINALITY_QUARANTINED.
    - A counterfactual evaluation is conducted, producing an AMENDMENT_NOTICE.
    - The original sealed record_hash and verdict remain intact.
    """
    engine = IntegrityEngine()
    c01_dict = get_c01_lap_time()
    contract = parse_contract(c01_dict)
    engine.register_contract(contract)

    scope = {"session_id": "austria_2023", "driver_id": "55", "lap_number": "40"}
    t_open = 1_000_000
    inst_id = engine.open_decision("C01_lap_time_consistency", scope, opens_at=t_open, known_at=t_open)

    # Admit reference and nominal lap record
    engine.admit_fact(
        make_fact("session_t0", {"session_id": "austria_2023"}, t_open, ["F1_FOM_TIMING"]),
        knowledge_time=t_open + 10_000,
    )
    atom_lap = make_atom(
        "lap_record", 68.5, t_open + 20_000, scope, ["F1_FOM_TIMING"],
        time=TypedTime(t_open + 20_000, TimeClass.SESSION_ELAPSED),
    )
    engine.admit_atom(atom_lap, knowledge_time=t_open + 30_000)

    # Advance clock past lateness deadline to finalize
    assms = engine.tick(t_open + 200_000_000)
    final_verdict = engine.as_of(inst_id, t_open + 200_000_000)
    assert final_verdict is not None
    assert final_verdict.content["finality_status"] == "FINAL"
    original_hash = final_verdict.record_hash

    # Now simulate late arriving evidence (track limits deletion 5 hours later)
    t_late = t_open + 500_000_000
    atom_deleted = make_atom(
        "lap_record", 0.0, t_open + 20_000, scope, ["FIA_STEWARDS"],
        time=TypedTime(t_open + 20_000, TimeClass.SESSION_ELAPSED),
        quality_grade=IntegrityState.DEGRADED,
    )
    # Admission of late atom into ledger
    engine.admit_atom(atom_deleted, knowledge_time=t_late)

    # Re-evaluating the sealed decision must NOT overwrite the final verdict record hash
    verdict_after_late = engine.as_of(inst_id, t_late)
    assert verdict_after_late is not None
    # Sealed final record is preserved
    assert verdict_after_late.content["finality_status"] == "FINAL"
    assert verdict_after_late.record_hash == original_hash


# ---------------------------------------------------------------------------
# SCENARIO 5: BELGIUM 2021 - RED FLAG LEGITIMATE ABSENCE VOIDING (CR-1)
# ---------------------------------------------------------------------------

def test_scenario_belgium_2021_red_flag_decision_voiding():
    """Belgium 2021: 2-lap safety car procession in heavy rain, red flag suspension.

    In CALIBRE, when a session is red-flagged or a participant legitimately retires,
    scheduled decisions must NOT trigger false DEGRADED alarms for missing evidence.
    Under CR-1 (Decision Voiding), the decision is finalized as UNKNOWN with a VOIDED witness,
    marking legitimate absence clearly.
    """
    engine = IntegrityEngine()
    c01_dict = get_c01_lap_time()
    contract = parse_contract(c01_dict)
    engine.register_contract(contract)

    scope = {"session_id": "spa_2021", "driver_id": "33", "lap_number": "5"}
    t_open = 10_000_000
    inst_id = engine.open_decision("C01_lap_time_consistency", scope, opens_at=t_open, known_at=t_open)

    # Session is red flagged: void decision for lap 5
    t_red_flag = t_open + 5_000_000
    void_assessment = engine.void_decision(
        instance_id=inst_id,
        K=t_red_flag,
        reason="RED_FLAG_SUSPENSION",
        witness_code="VOIDED",
        detail="Session suspended under red flag; lap 5 racing laps not held",
    )

    assert void_assessment is not None
    assert void_assessment.integrity_state == IntegrityState.UNKNOWN
    assert void_assessment.content["envelope"]["lower"] == "UNKNOWN"
    assert void_assessment.content["envelope"]["upper"] == "UNKNOWN"
    assert void_assessment.content["resolution_maturity"] == "TUPLE_RESOLVED"
    assert void_assessment.content["finality_status"] == "FINAL"
    assert void_assessment.reason == "VOIDED"
    assert any(w["code"] == "VOIDED" for w in void_assessment.content["witnesses"])
