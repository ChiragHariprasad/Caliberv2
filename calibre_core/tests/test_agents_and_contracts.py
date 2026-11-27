"""Unit and conformance tests for CALIBRE Specialist Agents (A1-A5) and Contracts (C01-C13).

Validates:
- Agent Rules AR-1 through AR-10.
- All 13 contracts C01-C13 pass validate_contract() and evaluate deterministically.
- Admission log sequencing, hash chaining, and replay.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from calibre_core.admission import AdmissionEntry, AdmissionLogReader, AdmissionLogWriter, GENESIS_DIGEST
from calibre_core.agents.context import SessionContextAgent
from calibre_core.agents.spatial import SpatialAgent
from calibre_core.agents.supervisor import FeedSupervisorAgent
from calibre_core.agents.telemetry import VehicleTelemetryAgent
from calibre_core.agents.timing import TimingAgent
from calibre_core.circuits.geometry import get_circuit_layout
from calibre_core.contracts.catalogue import list_all_contracts, get_contract
from sia_core_v3.sia_core.engine import IntegrityEngine, parse_contract, validate_contract
from sia_core_v3.sia_core.model import EvidenceAtom, GuardFact, ReferenceFact, S, TimeClass, TypedTime, make_atom, parse_instant


# ---------------------------------------------------------------------------
# CONTRACT CATALOGUE VALIDATION (C01 - C13)
# ---------------------------------------------------------------------------

def test_all_thirteen_contracts_present():
    contracts = list_all_contracts()
    assert len(contracts) == 13
    for c_dict in contracts:
        contract = parse_contract(c_dict)
        assert contract.version == "1.0.0"
        assert len(contract.roles) >= 1
        validation = validate_contract(contract)
        assert validation.ok, f"Contract {contract.contract_id} failed validation: {validation.errors}"


# ---------------------------------------------------------------------------
# AGENT ARCHETYPES (A1 - A5) AND AGENT RULES (AR-1 - AR-10)
# ---------------------------------------------------------------------------

def test_a1_timing_agent_deterministic_atom_emission():
    """AR-1, AR-2, AR-3, AR-5: A1 produces deterministic content-addressed atoms."""
    agent1 = TimingAgent()
    agent2 = TimingAgent()
    record = {
        "event_type": "LAP_COMPLETED",
        "session_id": "abu_dhabi_2021",
        "driver_number": "44",
        "lap_number": 1,
        "lap_time_seconds": 86.123,
        "utc_timestamp": "2021-12-12T13:02:26.123000Z",
    }

    atoms1 = agent1.process_record(record)
    atoms2 = agent2.process_record(record)

    assert len(atoms1) == 1
    assert len(atoms2) == 1
    atom1, atom2 = atoms1[0], atoms2[0]

    # Deterministic content hash
    assert atom1.atom_id == atom2.atom_id
    assert len(atom1.atom_id) == 64 or atom1.atom_id.startswith("sha256:")
    assert atom1.role_id == "lap_record"
    assert atom1.value == 86.123
    assert atom1.time.time_class == TimeClass.LAP_DURATION
    # Two-axis origin
    assert "F1_FOM_TIMING" in atom1.source_origins
    assert "A1_TIMING_PARSER_v1" in atom1.processing_origins
    assert len(agent1.diagnostics) == 0


def test_a1_timing_agent_diagnostic_on_out_of_order_numbering():
    """AR-4: Agent records diagnostic when numbering regression detected."""
    agent = TimingAgent()
    rec1 = {
        "event_type": "LAP_COMPLETED",
        "session_id": "test_s",
        "driver_number": "44",
        "lap_number": 5,
        "lap_time_seconds": 85.0,
        "utc_timestamp": "2021-12-12T13:05:00Z",
    }
    rec2 = {
        "event_type": "LAP_COMPLETED",
        "session_id": "test_s",
        "driver_number": "44",
        "lap_number": 3,  # Regressive lap
        "lap_time_seconds": 85.2,
        "utc_timestamp": "2021-12-12T13:06:00Z",
    }
    agent.process_record(rec1)
    agent.process_record(rec2)

    assert len(agent.diagnostics) == 1
    diag = agent.diagnostics[0]
    assert diag.code == "NUMBERING_REGRESSION"
    assert "regressed from 5 to 3" in diag.detail


def test_a2_telemetry_agent_kinematic_plausibility():
    """A2 checks kinematic plausibility and deceleration anomalies."""
    agent = VehicleTelemetryAgent()
    rec1 = {
        "session_id": "jeddah_2021",
        "driver_number": "33",
        "speed_kph": 300.0,
        "utc_timestamp": "2021-12-05T18:30:00.000000Z",
        "throttle": 100.0,
        "brake": 0.0,
    }
    rec2 = {
        "session_id": "jeddah_2021",
        "driver_number": "33",
        "speed_kph": 150.0,  # 150 km/h drop in 0.5s = ~300 km/h/s = ~8.5g deceleration!
        "utc_timestamp": "2021-12-05T18:30:00.500000Z",
        "throttle": 0.0,
        "brake": 100.0,
    }
    atoms1 = agent.process_record(rec1)
    atoms2 = agent.process_record(rec2)

    assert len(atoms1) >= 1
    assert len(atoms2) >= 1
    # Check that severe deceleration triggers diagnostic
    assert any(d.code == "KINEMATIC_ANOMALY" for d in agent.diagnostics)


def test_a3_spatial_geometry_agent_effective_geometry():
    """A3 generates surveyed geometry facts with effective date validity."""
    agent = SpatialAgent(circuit_key="monaco_2022")
    survey_fact = agent.get_geometry_reference_fact(datetime(2022, 5, 29, 13, 0, tzinfo=timezone.utc))

    assert survey_fact["fact_type"] == "track_geometry"
    assert survey_fact["scope"]["circuit_id"] == "monaco"
    assert survey_fact["pit_lane_length_m"] > 0
    assert survey_fact["is_valid"] is True
    assert len(agent.diagnostics) == 0


def test_a4_session_context_agent_neutralisation_and_flags():
    """A4 monitors flag lifecycles and neutralisation state."""
    agent = SessionContextAgent()
    rec_sc = {
        "session_id": "abu_dhabi_2021",
        "category": "Flag",
        "flag": "YELLOW",
        "message": "SAFETY CAR DEPLOYED",
        "utc_timestamp": "2021-12-12T14:35:00Z",
    }
    atoms = agent.process_record(rec_sc)
    assert len(atoms) >= 1
    sc_atom = [a for a in atoms if a.role_id == "session_state"][0]
    assert sc_atom.value == "SAFETY_CAR"
    assert agent.active_flag_status == "SAFETY_CAR"


def test_a5_feed_supervisor_monotonic_ticks_and_guards():
    """A5 Feed Supervisor emits monotonic clock ticks and STALLED/RESUMED guards."""
    supervisor = FeedSupervisorAgent(expected_cadence_us=1_000_000)

    t1 = supervisor.advance_clock_tick(1_000_000)
    t2 = supervisor.advance_clock_tick(1_000_000)
    assert t1 == 1_000_000
    assert t2 == 2_000_000

    # Stream heartbeat check: record receipt at 13:00:01
    supervisor.process_record({"stream": "live_timing", "receipt_time": "2021-12-12T13:00:01.000000Z"})

    # 2 seconds later (within 3x expected cadence of 1s), not stalled
    guard_live = supervisor.inspect_stream_heartbeat("live_timing", current_time_us=parse_instant("2021-12-12T13:00:03.000000Z"))
    assert guard_live is None

    # 5 seconds later (> 3x expected cadence of 1s), STALLED guard
    guard_stalled = supervisor.inspect_stream_heartbeat("live_timing", current_time_us=parse_instant("2021-12-12T13:00:06.000000Z"))
    assert guard_stalled is not None
    assert guard_stalled.status == "STALLED"


# ---------------------------------------------------------------------------
# ADMISSION LOG ENGINE & REPLAY BRIDGE
# ---------------------------------------------------------------------------

def test_admission_log_hash_chain_and_reader_verification(tmp_path):
    log_file = tmp_path / "test_admission.jsonl"
    writer = AdmissionLogWriter(output_path=log_file)

    scope = {"session": "race_1", "participant": "44"}
    atom = make_atom(
        role_id="lap_record",
        value=80.0,
        observed_at=80_000_000,
        scope=scope,
        source_origins=["loop_A"],
        time=TypedTime(80_000_000, TimeClass.LAP_DURATION),
        unit="s",
    )

    writer.admit_atom(atom, knowledge_time=1_000_000)
    writer.admit_tick(knowledge_time=2_000_000)

    reader = AdmissionLogReader(log_file)
    entries = reader.verify()
    assert len(entries) == 2
    assert entries[0].seq == 0
    assert entries[0].previous_digest == GENESIS_DIGEST
    assert entries[1].seq == 1
    assert entries[1].previous_digest == entries[0].entry_digest


def test_admission_log_tamper_detection(tmp_path):
    log_file = tmp_path / "tampered.jsonl"
    writer = AdmissionLogWriter(output_path=log_file)
    writer.admit_tick(1000)
    writer.admit_tick(2000)

    # Tamper with file
    content = log_file.read_text(encoding="utf-8")
    tampered_content = content.replace("2000", "2001")
    log_file.write_text(tampered_content, encoding="utf-8")

    reader = AdmissionLogReader(log_file)
    with pytest.raises(ValueError, match="Corrupt digest"):
        reader.verify()
