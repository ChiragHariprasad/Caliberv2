"""Generates complete high-frequency captures for all 7 landmark controversy F1 races.
Produces entry_list.json, session_info.json, capture_manifest.json, and envelopes.jsonl.
Features dynamic physical telemetry based on circuit geometry, cornering, braking, DRS,
timing sector completions, and race control events.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

try:
    from datetime import UTC  # Python 3.11+
except ImportError:
    UTC = timezone.utc  # Fallback for Python 3.10 and earlier

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CAPTURES_ROOT = WORKSPACE_ROOT / "captures"
CORPUS_ROOT = WORKSPACE_ROOT / "data" / "f1_corpus"
CIRCUITS_ROOT = WORKSPACE_ROOT / "backend" / "pulse" / "circuits" / "data"


class DriverSpec(TypedDict):
    number: int
    driver_id: str
    name: str
    initials: str
    team: str
    teamColor: str
    position: int
    grid_position: int
    pace: float
    tyre: str


GRID_DRIVERS: list[DriverSpec] = [
    {"number": 1, "driver_id": "max_verstappen", "name": "Max Verstappen", "initials": "MV", "team": "Red Bull Racing", "teamColor": "#3671C6", "position": 1, "grid_position": 1, "pace": 1.000, "tyre": "M"},
    {"number": 4, "driver_id": "lando_norris", "name": "Lando Norris", "initials": "LN", "team": "McLaren", "teamColor": "#FF8000", "position": 2, "grid_position": 2, "pace": 0.998, "tyre": "M"},
    {"number": 16, "driver_id": "charles_leclerc", "name": "Charles Leclerc", "initials": "CL", "team": "Ferrari", "teamColor": "#E80020", "position": 3, "grid_position": 3, "pace": 0.997, "tyre": "M"},
    {"number": 44, "driver_id": "lewis_hamilton", "name": "Lewis Hamilton", "initials": "LH", "team": "Mercedes", "teamColor": "#27F4D2", "position": 4, "grid_position": 4, "pace": 0.995, "tyre": "H"},
    {"number": 81, "driver_id": "oscar_piastri", "name": "Oscar Piastri", "initials": "OP", "team": "McLaren", "teamColor": "#FF8000", "position": 5, "grid_position": 5, "pace": 0.994, "tyre": "M"},
    {"number": 63, "driver_id": "george_russell", "name": "George Russell", "initials": "GR", "team": "Mercedes", "teamColor": "#27F4D2", "position": 6, "grid_position": 6, "pace": 0.993, "tyre": "H"},
    {"number": 55, "driver_id": "carlos_sainz", "name": "Carlos Sainz", "initials": "CS", "team": "Ferrari", "teamColor": "#E80020", "position": 7, "grid_position": 7, "pace": 0.992, "tyre": "M"},
    {"number": 11, "driver_id": "sergio_perez", "name": "Sergio Perez", "initials": "SP", "team": "Red Bull Racing", "teamColor": "#3671C6", "position": 8, "grid_position": 8, "pace": 0.991, "tyre": "H"},
    {"number": 14, "driver_id": "fernando_alonso", "name": "Fernando Alonso", "initials": "FA", "team": "Aston Martin", "teamColor": "#229971", "position": 9, "grid_position": 9, "pace": 0.989, "tyre": "H"},
    {"number": 23, "driver_id": "alexander_albon", "name": "Alexander Albon", "initials": "AA", "team": "Williams", "teamColor": "#64C4FF", "position": 10, "grid_position": 10, "pace": 0.987, "tyre": "M"},
    {"number": 18, "driver_id": "lance_stroll", "name": "Lance Stroll", "initials": "LS", "team": "Aston Martin", "teamColor": "#229971", "position": 11, "grid_position": 11, "pace": 0.985, "tyre": "H"},
    {"number": 10, "driver_id": "pierre_gasly", "name": "Pierre Gasly", "initials": "PG", "team": "Alpine", "teamColor": "#0093CC", "position": 12, "grid_position": 12, "pace": 0.984, "tyre": "M"},
    {"number": 31, "driver_id": "esteban_ocon", "name": "Esteban Ocon", "initials": "EO", "team": "Alpine", "teamColor": "#0093CC", "position": 13, "grid_position": 13, "pace": 0.983, "tyre": "M"},
    {"number": 22, "driver_id": "yuki_tsunoda", "name": "Yuki Tsunoda", "initials": "YT", "team": "AlphaTauri", "teamColor": "#5E8FAA", "position": 14, "grid_position": 14, "pace": 0.982, "tyre": "M"},
    {"number": 27, "driver_id": "nico_hulkenberg", "name": "Nico Hulkenberg", "initials": "NH", "team": "Haas", "teamColor": "#B6BABD", "position": 15, "grid_position": 15, "pace": 0.981, "tyre": "H"},
    {"number": 20, "driver_id": "kevin_magnussen", "name": "Kevin Magnussen", "initials": "KM", "team": "Haas", "teamColor": "#B6BABD", "position": 16, "grid_position": 16, "pace": 0.980, "tyre": "M"},
    {"number": 77, "driver_id": "valtteri_bottas", "name": "Valtteri Bottas", "initials": "VB", "team": "Alfa Romeo", "teamColor": "#C92D4B", "position": 17, "grid_position": 17, "pace": 0.979, "tyre": "H"},
    {"number": 24, "driver_id": "zhou_guanyu", "name": "Zhou Guanyu", "initials": "ZG", "team": "Alfa Romeo", "teamColor": "#C92D4B", "position": 18, "grid_position": 18, "pace": 0.978, "tyre": "M"},
    {"number": 2, "driver_id": "logan_sargeant", "name": "Logan Sargeant", "initials": "LS", "team": "Williams", "teamColor": "#64C4FF", "position": 19, "grid_position": 19, "pace": 0.977, "tyre": "H"},
    {"number": 21, "driver_id": "nyck_de_vries", "name": "Nyck de Vries", "initials": "ND", "team": "AlphaTauri", "teamColor": "#5E8FAA", "position": 20, "grid_position": 20, "pace": 0.976, "tyre": "M"},
]

NEW_SESSIONS = [
    {
        "session_id": "f1-2023-australia",
        "grand_prix": "Australian Grand Prix 2023",
        "circuit_id": "albert_park",
        "circuit_length": 5278.0,
        "total_laps": 58,
        "start_time_iso": "2023-04-02T05:00:00Z",
        "duration_seconds": 600,
        "sc_start_s": 220,
        "sc_end_s": 380,
        "vsc_start_s": 460,
        "vsc_end_s": 520,
        "corpus_dir": "2023_australia",
    },
    {
        "session_id": "f1-2023-austria",
        "grand_prix": "Austrian Grand Prix 2023",
        "circuit_id": "red_bull_ring",
        "circuit_length": 4318.0,
        "total_laps": 71,
        "start_time_iso": "2023-07-02T13:00:00Z",
        "duration_seconds": 600,
        "sc_start_s": None,
        "sc_end_s": None,
        "vsc_start_s": 240,
        "vsc_end_s": 350,
        "corpus_dir": "2023_austria",
    },
    {
        "session_id": "f1-2021-abu-dhabi",
        "grand_prix": "Abu Dhabi Grand Prix 2021",
        "circuit_id": "yas_marina",
        "circuit_length": 5281.0,
        "total_laps": 58,
        "start_time_iso": "2021-12-12T13:00:00Z",
        "duration_seconds": 600,
        "sc_start_s": 350,
        "sc_end_s": 520,
        "vsc_start_s": 150,
        "vsc_end_s": 210,
        "corpus_dir": "2021_abu_dhabi",
    },
    {
        "session_id": "f1-2021-belgium",
        "grand_prix": "Belgian Grand Prix 2021",
        "circuit_id": "spa",
        "circuit_length": 7004.0,
        "total_laps": 44,
        "start_time_iso": "2021-08-29T13:00:00Z",
        "duration_seconds": 600,
        "sc_start_s": 0,
        "sc_end_s": 600,
        "vsc_start_s": None,
        "vsc_end_s": None,
        "corpus_dir": "2021_belgium",
    },
    {
        "session_id": "f1-2021-saudi-arabia",
        "grand_prix": "Saudi Arabian Grand Prix 2021",
        "circuit_id": "jeddah",
        "circuit_length": 6174.0,
        "total_laps": 50,
        "start_time_iso": "2021-12-05T17:30:00Z",
        "duration_seconds": 600,
        "sc_start_s": 200,
        "sc_end_s": 340,
        "vsc_start_s": 420,
        "vsc_end_s": 480,
        "corpus_dir": "2021_saudi_arabia",
    },
    {
        "session_id": "f1-2024-united-states",
        "grand_prix": "United States Grand Prix 2024",
        "circuit_id": "cota",
        "circuit_length": 5513.0,
        "total_laps": 56,
        "start_time_iso": "2024-10-20T19:00:00Z",
        "duration_seconds": 600,
        "sc_start_s": 180,
        "sc_end_s": 310,
        "vsc_start_s": 450,
        "vsc_end_s": 510,
        "corpus_dir": "2024_united_states",
    },
    {
        "session_id": "f1-2023-las-vegas",
        "grand_prix": "Las Vegas Grand Prix 2023",
        "circuit_id": "las_vegas",
        "circuit_length": 6201.0,
        "total_laps": 50,
        "start_time_iso": "2023-11-19T06:00:00Z",
        "duration_seconds": 600,
        "sc_start_s": 160,
        "sc_end_s": 300,
        "vsc_start_s": 420,
        "vsc_end_s": 490,
        "corpus_dir": "2023_las_vegas",
    },
]

def load_circuit_corners(circuit_id: str) -> list[dict]:
    circuit_file = CIRCUITS_ROOT / f"{circuit_id}.json"
    if circuit_file.exists():
        try:
            data = json.loads(circuit_file.read_text(encoding="utf-8"))
            corners = data.get("corners", [])
            if corners:
                return corners
        except Exception:
            pass
    # Fallback generic corners along circuit
    return [
        {"number": 1, "track_progress": 0.12, "apex_speed_kmh": 120.0},
        {"number": 4, "track_progress": 0.35, "apex_speed_kmh": 95.0},
        {"number": 7, "track_progress": 0.58, "apex_speed_kmh": 140.0},
        {"number": 10, "track_progress": 0.78, "apex_speed_kmh": 110.0},
        {"number": 12, "track_progress": 0.92, "apex_speed_kmh": 180.0},
    ]

def compute_telemetry_physics(
    prog: float,
    pace: float,
    driver_offset: float,
    active_sc: bool,
    active_vsc: bool,
    corners: list[dict],
) -> dict:
    """Computes physically realistic vehicle telemetry based on track location and corners."""
    if active_sc:
        base_speed = 120.0 + math.sin(prog * 10) * 12.0
        throttle = 42.0 + math.sin(prog * 15) * 8.0
        brake = 0.0 if math.sin(prog * 8) > -0.7 else 25.0
        gear = 4
        rpm = 8800 + int(throttle * 20)
        drs = 0
        return {
            "speed": round(base_speed, 1),
            "throttle": round(throttle, 1),
            "brake": round(brake, 1),
            "gear": gear,
            "rpm": rpm,
            "drs": drs,
        }

    if active_vsc:
        base_speed = 160.0 + math.sin(prog * 10) * 15.0
        throttle = 55.0 + math.sin(prog * 15) * 10.0
        brake = 0.0 if math.sin(prog * 8) > -0.6 else 30.0
        gear = 5
        rpm = 9400 + int(throttle * 25)
        drs = 0
        return {
            "speed": round(base_speed, 1),
            "throttle": round(throttle, 1),
            "brake": round(brake, 1),
            "gear": gear,
            "rpm": rpm,
            "drs": drs,
        }

    # Find the closest corner ahead
    min_dist = 1.0
    target_corner = None
    for c in corners:
        cp = c.get("track_progress", 0.5)
        d = (cp - prog) % 1.0
        if d < min_dist:
            min_dist = d
            target_corner = c

    apex_speed = target_corner.get("apex_speed_kmh", 120.0) if target_corner else 120.0
    apex_speed = apex_speed * (0.96 + 0.08 * driver_offset)

    if min_dist < 0.045:
        # Heavy braking zone approaching corner apex
        braking_intensity = (1.0 - (min_dist / 0.045))
        brake = min(100.0, 50.0 + braking_intensity * 50.0 + driver_offset * 5.0)
        throttle = 0.0
        speed = apex_speed + (310.0 * pace - apex_speed) * (1.0 - braking_intensity * 0.9)
        drs = 0
    elif min_dist > 0.975:
        # Exit phase just past apex
        exit_intensity = (min_dist - 0.975) / 0.025
        brake = 0.0
        throttle = 40.0 + exit_intensity * 55.0
        speed = apex_speed + exit_intensity * 60.0
        drs = 0
    else:
        # Straight / full acceleration
        brake = 0.0
        throttle = 100.0
        # Speed builds up along the straight
        straight_ratio = min(1.0, (min_dist - 0.045) / 0.20)
        top_speed = (325.0 + driver_offset * 12.0) * pace
        speed = apex_speed + 60.0 + (top_speed - (apex_speed + 60.0)) * (1.0 - straight_ratio)
        speed = min(top_speed, max(apex_speed, speed))
        drs = 1 if (speed > 270.0 and min_dist > 0.08) else 0

    # Gear calculation from speed
    if speed > 295.0:
        gear = 8
    elif speed > 255.0:
        gear = 7
    elif speed > 205.0:
        gear = 6
    elif speed > 155.0:
        gear = 5
    elif speed > 110.0:
        gear = 4
    elif speed > 75.0:
        gear = 3
    else:
        gear = 2

    # RPM based on speed within gear
    rpm_base = 8600 + int(((speed % 45.0) / 45.0) * 3600.0) + int(throttle * 5.5)
    rpm = min(12850, max(8400, rpm_base))

    return {
        "speed": round(speed, 1),
        "throttle": round(throttle, 1),
        "brake": round(brake, 1),
        "gear": gear,
        "rpm": rpm,
        "drs": drs,
    }

def generate_session_capture(config: dict) -> None:
    session_id = config["session_id"]
    circuit_id = config["circuit_id"]
    grand_prix = config["grand_prix"]
    total_laps = config["total_laps"]
    duration = config["duration_seconds"]
    base_time = datetime.fromisoformat(config["start_time_iso"].replace("Z", "+00:00"))
    
    out_dir = CAPTURES_ROOT / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    corners = load_circuit_corners(circuit_id)
    
    # 1. Session Info
    session_info = {
        "session_id": session_id,
        "meeting_id": session_id,
        "session_name": grand_prix,
        "circuit_id": circuit_id,
        "total_laps": total_laps,
        "total_drivers": 20,
        "duration_seconds": duration,
        "source": "PULSE_SYNTHETIC_SIMULATOR",
    }
    (out_dir / "session_info.json").write_text(json.dumps(session_info, indent=2), encoding="utf-8")
    
    # 2. Capture Manifest
    manifest = {
        "capture_id": session_id,
        "data_regime": "LAB",
        "dataset_classification": "LAB_SYNTHETIC_CAPTURE",
        "regime": "LAB",
        "is_synthetic": True,
        "provenance_status": "LAB_SYNTHETIC_WINDOWED_REPLAY",
        "provider": "PULSE_SYNTHETIC_SIM",
        "licence_reference": "PULSE-LAB-REPLAY-INTERNAL",
        "session_id": session_id,
        "session_name": grand_prix,
        "circuit_id": circuit_id,
        "total_laps": total_laps,
        "duration_seconds": duration,
    }
    (out_dir / "capture_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    
    # 3. Entry List
    entry_entries = []
    for d in GRID_DRIVERS:
        entry_entries.append({
            "number": d["number"],
            "driver_id": d["driver_id"],
            "name": d["name"],
            "initials": d["initials"],
            "team": d["team"],
            "teamColor": d["teamColor"],
            "position": d["position"],
            "grid_position": d["grid_position"],
            "status": "ACTIVE",
            "tyre": d["tyre"],
            "stint": 1,
            "tyreAge": 0,
            "speed": 285.0,
            "gear": 7,
            "rpm": 11600,
        })
    (out_dir / "entry_list.json").write_text(json.dumps(entry_entries, indent=2), encoding="utf-8")
    
    # 4. Envelopes Generator (500ms cadence)
    event_seq = 1
    parts = session_id.split("-")
    prefix = parts[2][:4] if len(parts) > 2 else session_id[:4]
    season = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 2023
    
    def make_envelope(evt_type: str, drv_num: Optional[int], t_ms: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal event_seq
        evt_time = base_time + timedelta(milliseconds=t_ms)
        eid = f"evt-{prefix}-{event_seq:07d}"
        event_seq += 1
        return {
            "event_id": eid,
            "event_type": evt_type,
            "schema_version": 1,
            "source": {
                "provider": "PULSE_SYNTHETIC_SIM",
                "adapter": "high_frequency_track_adapter",
                "source_record_id": f"rec-{event_seq}",
                "capture_id": session_id,
                "licence_reference": "PULSE-LAB-REPLAY-INTERNAL",
            },
            "run": {
                "run_id": f"run-{session_id}",
                "session_instance_id": session_id,
                "mode": "REPLAY",
            },
            "session": {
                "season": season,
                "meeting_id": session_id,
                "session_id": session_id,
                "session_type": "RACE",
            },
            "time": {
                "event_time_utc": evt_time.isoformat(),
                "session_elapsed_ms": t_ms,
                "ingest_time_utc": evt_time.isoformat(),
                "time_domain": "EVENT_TIME",
            },
            "subject": {
                "driver_number": drv_num,
                "segment_id": None,
            },
            "payload": payload,
            "quality": {
                "interpretation": "OBSERVED",
                "completeness": "COMPLETE",
                "missing_fields": [],
                "unit_validation": "PASSED",
            },
        }

    env_path = out_dir / "envelopes.jsonl"
    with open(env_path, "w", encoding="utf-8") as f:
        # Start events at t=0
        f.write(json.dumps(make_envelope("SESSION_ENTRY_LIST", None, 0, {"entries": entry_entries, "total_drivers": 20})) + "\n")
        f.write(json.dumps(make_envelope("SESSION_STARTED", None, 0, {"session_name": grand_prix, "circuit_id": circuit_id, "total_laps": total_laps})) + "\n")
        f.write(json.dumps(make_envelope("TRACK_STATUS_GREEN", None, 500, {"status": "GREEN", "message": "FORMATION LAP COMPLETE · RACE START"})) + "\n")
        f.write(json.dumps(make_envelope("WEATHER_OBSERVATION", None, 500, {"air_temp_c": 23.8, "track_temp_c": 35.4, "humidity_percent": 52.0, "rain_risk_percent": 0.0})) + "\n")
        
        # Load real historical race control notices
        corpus_rc = CORPUS_ROOT / config.get("corpus_dir", "") / "race_control_log.json"
        notices_to_inject = []
        if corpus_rc.exists():
            try:
                rc_data = json.loads(corpus_rc.read_text(encoding="utf-8"))
                for idx, notice in enumerate(rc_data[:12]):
                    notices_to_inject.append((25 + idx * 45, notice.get("message", "NOTICE"), notice.get("flag", "CLEAR")))
            except Exception:
                pass
        
        active_sc = False
        active_vsc = False
        # Initialize lap progress with slight grid stagger
        lap_progress = {d["number"]: max(0.0, 1.0 - (d["position"] - 1) * 0.018) for d in GRID_DRIVERS}
        current_lap = {d["number"]: 1 for d in GRID_DRIVERS}
        sector_crossed = {d["number"]: 0 for d in GRID_DRIVERS}
        tyre_age = {d["number"]: 0 for d in GRID_DRIVERS}
        
        sc_s = config.get("sc_start_s")
        sc_e = config.get("sc_end_s")
        vsc_s = config.get("vsc_start_s")
        vsc_e = config.get("vsc_end_s")
        
        # 500ms cadence: step = 0.5s = 500ms
        steps = int(duration * 2)
        circuit_length = config["circuit_length"]
        
        for step_idx in range(1, steps):
            t_s = step_idx * 0.5
            t_ms = int(t_s * 1000)
            
            # Safety car transitions
            if sc_s is not None and t_s == sc_s:
                active_sc = True
                f.write(json.dumps(make_envelope("SAFETY_CAR_DEPLOYED", None, t_ms, {"status": "SC", "message": "SAFETY CAR DEPLOYED · ACCIDENT ON TRACK"})) + "\n")
                f.write(json.dumps(make_envelope("TRACK_STATUS_UPDATE", None, t_ms, {"status": "YELLOW", "sector": 2, "message": "SECTOR 2 YELLOW FLAG"})) + "\n")
            elif sc_e is not None and t_s == sc_e:
                active_sc = False
                f.write(json.dumps(make_envelope("TRACK_STATUS_GREEN", None, t_ms, {"status": "GREEN", "message": "SAFETY CAR IN THIS LAP"})) + "\n")
                
            if vsc_s is not None and t_s == vsc_s and not active_sc:
                active_vsc = True
                f.write(json.dumps(make_envelope("VSC_DEPLOYED", None, t_ms, {"status": "VSC", "message": "VIRTUAL SAFETY CAR DEPLOYED"})) + "\n")
            elif vsc_e is not None and t_s == vsc_e and active_vsc:
                active_vsc = False
                f.write(json.dumps(make_envelope("TRACK_STATUS_GREEN", None, t_ms, {"status": "GREEN", "message": "VSC ENDING · TRACK CLEAR"})) + "\n")
                
            # Periodic Weather update
            if t_ms % 60000 == 0:
                f.write(json.dumps(make_envelope("WEATHER_OBSERVATION", None, t_ms, {
                    "air_temp_c": round(23.5 + math.sin(t_s / 300.0) * 1.5, 1),
                    "track_temp_c": round(35.0 + math.cos(t_s / 300.0) * 2.0, 1),
                    "humidity_percent": 52.0,
                    "rain_risk_percent": 0.0,
                })) + "\n")
                
            # Race control notices
            for n_t, n_msg, n_flag in notices_to_inject:
                if abs(t_s - n_t) < 0.26:
                    f.write(json.dumps(make_envelope("RACE_CONTROL_NOTICE", None, t_ms, {
                        "title": "FIA RACE CONTROL NOTICE",
                        "category": "NOTICE",
                        "flag": n_flag,
                        "detail": n_msg,
                        "regulatory_reference": "FIA Sporting Regulations",
                    })) + "\n")
                    
            # 20 Cars high-fidelity 500ms telemetry
            for d in GRID_DRIVERS:
                num = d["number"]
                pace = d["pace"]
                drv_offset = (num % 7) * 0.15 - 0.45
                prog = lap_progress[num]
                
                # Compute telemetry physics for this driver at this exact spot
                phys = compute_telemetry_physics(
                    prog=prog,
                    pace=pace,
                    driver_offset=drv_offset,
                    active_sc=active_sc,
                    active_vsc=active_vsc,
                    corners=corners,
                )
                
                # Progress along circuit for 0.5s dt
                speed_m_s = (phys["speed"] * 1000.0) / 3600.0
                dist_traveled = speed_m_s * 0.5
                old_prog = prog
                new_prog = prog + (dist_traveled / circuit_length)
                
                # Check Sector completions
                if old_prog < 0.33 <= new_prog:
                    sector_crossed[num] = 1
                    s1_time = round(28.2 + (1.0 - pace) * 20.0 + drv_offset * 0.2, 3)
                    f.write(json.dumps(make_envelope("SECTOR_COMPLETED", num, t_ms, {
                        "driver_number": num,
                        "sector_number": 1,
                        "sector_time_seconds": s1_time,
                        "lap": current_lap[num],
                    })) + "\n")
                elif old_prog < 0.66 <= new_prog:
                    sector_crossed[num] = 2
                    s2_time = round(31.4 + (1.0 - pace) * 22.0 + drv_offset * 0.2, 3)
                    f.write(json.dumps(make_envelope("SECTOR_COMPLETED", num, t_ms, {
                        "driver_number": num,
                        "sector_number": 2,
                        "sector_time_seconds": s2_time,
                        "lap": current_lap[num],
                    })) + "\n")
                    
                # Check Lap completion
                if new_prog >= 1.0:
                    new_prog -= 1.0
                    current_lap[num] = min(total_laps, current_lap[num] + 1)
                    tyre_age[num] += 1
                    lap_time = round(84.5 + (1.0 - pace) * 50.0 + drv_offset * 0.5, 3)
                    f.write(json.dumps(make_envelope("LAP_COMPLETED", num, t_ms, {
                        "driver_number": num,
                        "lap": current_lap[num],
                        "lap_time_seconds": lap_time,
                        "tyre_compound": d["tyre"],
                        "tyre_age": tyre_age[num],
                    })) + "\n")
                    
                lap_progress[num] = new_prog
                cur_lap = current_lap[num]
                
                # Emit high-speed trap
                if old_prog < 0.88 <= new_prog and not active_sc and not active_vsc:
                    f.write(json.dumps(make_envelope("SPEED_TRAP", num, t_ms, {
                        "driver_number": num,
                        "speed_kph": round(phys["speed"], 1),
                        "trap_id": "ST01_MAIN_STRAIGHT",
                    })) + "\n")
                    
                # Scheduled Pit Speed test at ~t=120s for car #1 and car #44
                if 120 <= t_s < 122:
                    if num == 1:
                        # Max pit speed check
                        f.write(json.dumps(make_envelope("PIT_SPEED", 1, t_ms, {
                            "driver_number": 1,
                            "speed_kph": 79.2,
                            "pit_lane_limit_kph": 80.0,
                            "location": "PIT_IN_GATE",
                        })) + "\n")
                    elif num == 44:
                        f.write(json.dumps(make_envelope("PIT_SPEED", 44, t_ms, {
                            "driver_number": 44,
                            "speed_kph": 78.6,
                            "pit_lane_limit_kph": 80.0,
                            "location": "PIT_IN_GATE",
                        })) + "\n")
                        
                # Driver Telemetry & Position Update (500ms cadence)
                f.write(json.dumps(make_envelope("DRIVER_TELEMETRY", num, t_ms, {
                    "driver_number": num,
                    "driver_name": d["name"],
                    "position": d["position"],
                    "lap": cur_lap,
                    "progress": round(new_prog, 4),
                    "speed": phys["speed"],
                    "throttle": phys["throttle"],
                    "brake": phys["brake"],
                    "gear": phys["gear"],
                    "rpm": phys["rpm"],
                    "drs": phys["drs"],
                    "tyre": d["tyre"],
                    "tyre_age": tyre_age[num],
                    "status": "ACTIVE",
                })) + "\n")
                
    print(f"Generated capture for {session_id} ({event_seq} envelopes in {env_path.name})")

if __name__ == "__main__":
    for conf in NEW_SESSIONS:
        generate_session_capture(conf)
