from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pulse.contracts import EventEnvelope

logger = logging.getLogger("pulse.projections")

# Official FIA Formula 1 Entry List & Identity Catalogue
DRIVER_META: dict[int, dict[str, str]] = {
    16: {"name": "Charles Leclerc", "initials": "CL", "team": "Ferrari", "color": "#E80020"},
    4: {"name": "Lando Norris", "initials": "LN", "team": "McLaren", "color": "#FF8000"},
    1: {"name": "Max Verstappen", "initials": "MV", "team": "Red Bull Racing", "color": "#3671C6"},
    44: {"name": "Lewis Hamilton", "initials": "LH", "team": "Ferrari", "color": "#E80020"},
    81: {"name": "Oscar Piastri", "initials": "OP", "team": "McLaren", "color": "#FF8000"},
    63: {"name": "George Russell", "initials": "GR", "team": "Mercedes", "color": "#27F4D2"},
    12: {"name": "Kimi Antonelli", "initials": "KA", "team": "Mercedes", "color": "#27F4D2"},
    14: {"name": "Fernando Alonso", "initials": "FA", "team": "Aston Martin", "color": "#229971"},
    18: {"name": "Lance Stroll", "initials": "LS", "team": "Aston Martin", "color": "#229971"},
    23: {"name": "Alexander Albon", "initials": "AA", "team": "Williams", "color": "#64C4FF"},
    55: {"name": "Carlos Sainz", "initials": "CS", "team": "Williams", "color": "#64C4FF"},
    10: {"name": "Pierre Gasly", "initials": "PG", "team": "Alpine", "color": "#0093CC"},
    7: {"name": "Jack Doohan", "initials": "JD", "team": "Alpine", "color": "#0093CC"},
    22: {"name": "Yuki Tsunoda", "initials": "YT", "team": "Racing Bulls", "color": "#6692FF"},
    30: {"name": "Liam Lawson", "initials": "LL", "team": "Racing Bulls", "color": "#6692FF"},
    27: {"name": "Nico Hülkenberg", "initials": "NH", "team": "Kick Sauber", "color": "#52E252"},
    5: {"name": "Gabriel Bortoleto", "initials": "GB", "team": "Kick Sauber", "color": "#52E252"},
    11: {"name": "Sergio Perez", "initials": "SP", "team": "Red Bull Racing", "color": "#3671C6"},
    87: {"name": "Oliver Bearman", "initials": "OB", "team": "Haas", "color": "#B6BABD"},
    31: {"name": "Esteban Ocon", "initials": "EO", "team": "Haas", "color": "#B6BABD"},
    2: {"name": "Logan Sargeant", "initials": "LS", "team": "Williams", "color": "#64C4FF"},
    21: {"name": "Nyck de Vries", "initials": "ND", "team": "AlphaTauri", "color": "#5E8FAA"},
    3: {"name": "Daniel Ricciardo", "initials": "DR", "team": "AlphaTauri", "color": "#5E8FAA"},
    20: {"name": "Kevin Magnussen", "initials": "KM", "team": "Haas", "color": "#B6BABD"},
    24: {"name": "Zhou Guanyu", "initials": "ZG", "team": "Alfa Romeo", "color": "#C92D4B"},
    77: {"name": "Valtteri Bottas", "initials": "VB", "team": "Alfa Romeo", "color": "#C92D4B"},
}


def _generate_synthetic_telemetry_history(base_speed: float, gear: int, rpm: int) -> list[dict[str, Any]]:
    """Generates a realistic 20-point historical telemetry trace for the driver time-series plot."""
    history = []
    for i in range(20):
        t_offset = -(20 - i) * 0.5  # -10s to 0s in 0.5s increments
        noise = (i % 3 - 1) * 3.5
        spd = max(60.0, min(330.0, base_speed + noise + ((i % 5) * 4.0)))
        throttle = min(100.0, max(0.0, 95.0 + ((i % 4) - 2) * 5.0)) if spd > 180 else 40.0
        brake = 0.0 if throttle > 20 else 85.0
        g = max(1, min(8, gear + (1 if i > 12 else 0)))
        r = max(4000, min(12500, int(rpm + (i % 6 - 3) * 200)))
        history.append({
            "time_offset_s": round(t_offset, 1),
            "speed": round(spd, 1),
            "throttle": round(throttle, 1),
            "brake": round(brake, 1),
            "gear": g,
            "rpm": r,
            "drs": 1 if spd > 250 else 0,
        })
    return history


class RaceStateProjector:
    """Projects canonical stream events into live consumer-facing race state across all 20+ grid entries."""

    def __init__(self) -> None:
        self.session_instance_id: str = "pulse-sim-001"
        self.circuit_id: str = "monaco"
        self.session_name: str = "Monaco Grand Prix"
        self.session_type: str = "Race Intelligence"
        self.current_lap: int = 24
        self.total_laps: int = 57
        self.active_event: str = "GREEN_FLAG"
        self.active_event_display: str = "Green Flag"
        self.active_lifecycle: str = "NONE"
        self.status: str = "Green Flag"
        self.elapsed_time: str = "01:11:50"
        self.data_mode: str = "SIMULATED"
        self.pipeline_status: str = "CONNECTED"
        self.last_event_time: datetime | None = None

        # Full 20-driver initial grid state
        self.drivers: dict[int, dict[str, Any]] = self._init_full_grid()

        # Circuit Sectors
        self.sectors: list[dict[str, Any]] = [
            {"id": "s1", "label": "Sector 1", "condition": "Dry · clear", "tone": "dry", "confidence": 96},
            {"id": "s2", "label": "Sector 2", "condition": "Dry · active", "tone": "dry", "confidence": 98},
            {"id": "s3", "label": "Sector 3", "condition": "Dry · clear", "tone": "dry", "confidence": 92},
        ]

        # Analytical Timeline (PULSE Domain)
        self.timeline: list[dict[str, Any]] = []

        # Official Race Control & Stewarding Notices (Official Domain)
        self.official_notices: list[dict[str, Any]] = self._init_official_notices()

    @property
    def driver_registry(self) -> dict[int, dict[str, Any]]:
        return self.drivers

    def _init_full_grid(self) -> dict[int, dict[str, Any]]:
        """Constructs the baseline 20-driver grid with realistic positions, gaps, tyre compounds, and telemetry channels."""
        grid_definitions = [
            (16, 1, "LEADER", "—", "M", 1, 23, "1:15.821", 0.88, "ACTIVE", 285.4, 7, 11850, "Leading comfortably"),
            (4, 2, "+2.481", "+2.481", "H", 1, 23, "1:16.040", 0.84, "ACTIVE", 282.1, 7, 11720, "Holding gap to leader"),
            (1, 3, "+4.067", "+1.586", "H", 1, 23, "1:16.132", 0.81, "ACTIVE", 286.0, 7, 11900, "Pressuring P2"),
            (44, 4, "+8.742", "+4.675", "M", 1, 23, "1:16.286", 0.74, "ACTIVE", 281.0, 7, 11680, "Traffic risk"),
            (81, 5, "+10.036", "+1.294", "H", 1, 23, "1:16.401", 0.70, "ACTIVE", 280.2, 7, 11640, "Managing tyre deg"),
            (63, 6, "+14.219", "+4.183", "M", 1, 22, "1:16.512", 0.64, "ACTIVE", 278.9, 7, 11580, "Pushing in clean air"),
            (12, 7, "+17.850", "+3.631", "H", 1, 22, "1:16.704", 0.58, "ACTIVE", 277.5, 7, 11510, "Defending position"),
            (14, 8, "+21.114", "+3.264", "M", 1, 21, "1:16.890", 0.52, "ACTIVE", 276.1, 6, 11420, "Conserving tyres"),
            (55, 9, "+24.502", "+3.388", "H", 1, 21, "1:16.945", 0.47, "ACTIVE", 275.0, 6, 11390, "Close pursuit"),
            (23, 10, "+28.190", "+3.688", "M", 1, 20, "1:17.082", 0.42, "ACTIVE", 274.2, 6, 11320, "In the points"),
            (10, 11, "+31.840", "+3.650", "H", 1, 20, "1:17.190", 0.38, "ACTIVE", 273.5, 6, 11280, "Hunting P10"),
            (7, 12, "+35.200", "+3.360", "M", 1, 19, "1:17.310", 0.33, "ACTIVE", 272.0, 6, 11200, "Stable pace"),
            (22, 13, "+39.450", "+4.250", "H", 1, 19, "1:17.480", 0.28, "ACTIVE", 271.2, 6, 11150, "Tyre graining"),
            (30, 14, "+43.110", "+3.660", "M", 1, 18, "1:17.620", 0.24, "PIT_LANE", 60.0, 2, 4800, "In pit lane for stop"),
            (18, 15, "+47.800", "+4.690", "H", 1, 18, "1:17.750", 0.19, "ACTIVE", 270.0, 6, 11090, "Defending against P16"),
            (27, 16, "+51.230", "+3.430", "M", 1, 17, "1:17.890", 0.15, "ACTIVE", 269.4, 6, 11050, "Pace dropping"),
            (5, 17, "+55.600", "+4.370", "H", 1, 17, "1:18.020", 0.11, "ACTIVE", 268.0, 6, 11000, "Blue flags approaching"),
            (11, 18, "+1 LAP", "+1 LAP", "M", 2, 8, "1:17.150", 0.07, "ACTIVE", 275.8, 6, 11400, "Recovery drive"),
            (87, 19, "+1 LAP", "+12.4s", "H", 1, 16, "1:18.320", 0.03, "ACTIVE", 266.5, 6, 10920, "Managing balance"),
            (31, 20, "OUT", "DNF", "S", 1, 8, "1:18.910", 0.00, "RETIRED", 0.0, 0, 0, "Retired · Lap 8 contact"),
        ]

        drivers = {}
        for num, pos, gap, interval, tyre, stint, tyre_age, last_lap, progress, status, spd, gear, rpm, label in grid_definitions:
            meta = DRIVER_META.get(num, {"name": f"Driver #{num}", "initials": f"D{num}", "team": "Independent", "color": "#718096"})
            is_retired = status in {"RETIRED", "DNS"}
            quality = "UNAVAILABLE" if is_retired else "AVAILABLE"

            channels = {
                "speed": {"value": None if is_retired else spd, "unit": "km/h", "source": "CAN_BUS/ECU", "freshness_ms": 110, "quality": quality},
                "throttle": {"value": None if is_retired else (98.0 if spd > 100 else 0.0), "unit": "%", "source": "CAN_BUS/ECU", "freshness_ms": 110, "quality": quality},
                "brake": {"value": None if is_retired else (0.0 if spd > 100 else 60.0), "unit": "%", "source": "HYDRAULIC_PRESSURE", "freshness_ms": 110, "quality": quality},
                "gear": {"value": None if is_retired else gear, "unit": "GEAR", "source": "GEARBOX_SENSOR", "freshness_ms": 110, "quality": quality},
                "rpm": {"value": None if is_retired else rpm, "unit": "RPM", "source": "ENGINE_CRANK", "freshness_ms": 110, "quality": quality},
                "drs": {"value": None if is_retired else (1 if spd > 250 else 0), "unit": "STATUS", "source": "FIA_DRS_TELEMETRY", "freshness_ms": 110, "quality": quality},
                "tyre_compound": {"value": tyre, "unit": "COMPOUND", "source": "TYRE_RFID", "freshness_ms": 250, "quality": "AVAILABLE"},
                "stint_age": {"value": tyre_age, "unit": "LAPS", "source": "TIMING_LOOPS", "freshness_ms": 250, "quality": "AVAILABLE"},
                "gap": {"value": gap, "unit": "INTERVAL", "source": "TIMING_TRANSPONDER", "freshness_ms": 90, "quality": "AVAILABLE"},
                "interval": {"value": interval, "unit": "INTERVAL", "source": "TIMING_TRANSPONDER", "freshness_ms": 90, "quality": "AVAILABLE"},
            }

            tone = "positive" if pos <= 3 else ("negative" if pos >= 15 or is_retired else "neutral")

            drivers[num] = {
                "number": num,
                "initials": meta["initials"],
                "name": meta["name"],
                "team": meta["team"],
                "teamColor": meta["color"],
                "position": pos,
                "gap": gap,
                "interval": interval,
                "tyre": tyre,
                "stint": stint,
                "tyreAge": tyre_age,
                "lastLap": last_lap,
                "status": status,
                "progress": progress,
                "positionMode": "TIMING_ESTIMATED",
                "freshnessSeconds": 0.25,
                "impact": {"tone": tone, "label": label},
                "telemetry": channels,
                "history": [] if is_retired else _generate_synthetic_telemetry_history(spd, gear, rpm),
            }

        return drivers

    def load_session_entry_list(self, entries: list[dict[str, Any]]) -> None:
        """
        Dynamically initializes the driver grid for a session.
        Accepts arbitrary driver entry lists (e.g. 18, 20, 22).
        Handles DNS, RETIRED, PIT_LANE, and ACTIVE drivers with explicit quality states.
        """
        new_drivers: dict[int, dict[str, Any]] = {}
        for idx, entry in enumerate(entries):
            num = int(entry.get("number") or entry.get("driver_number") or (idx + 1))
            meta = DRIVER_META.get(num, {})
            name = entry.get("name") or meta.get("name", f"Driver #{num}")
            team = entry.get("team") or meta.get("team", "Formula 1 Team")
            color = entry.get("teamColor") or meta.get("color", "#718096")
            initials = entry.get("initials") or meta.get("initials") or "".join([w[0] for w in name.split()[:2]]).upper()
            status = entry.get("status", "ACTIVE")
            pos = entry.get("position", idx + 1)
            is_inactive = status in {"DNS", "RETIRED"}
            quality = "UNAVAILABLE" if is_inactive else "AVAILABLE"

            has_real_telemetry = entry.get("has_telemetry", False)
            if has_real_telemetry and "telemetry" in entry:
                channels = entry["telemetry"]
                history = entry.get("history", [])
            else:
                spd = 0.0 if is_inactive else entry.get("speed", 250.0)
                gear = 0 if is_inactive else entry.get("gear", 6)
                rpm = 0 if is_inactive else entry.get("rpm", 10500)
                channels = {
                    "speed": {"value": None if is_inactive else spd, "unit": "km/h", "source": "TIMING_LOOP", "freshness_ms": 100, "quality": quality},
                    "throttle": {"value": None if is_inactive else 90.0, "unit": "%", "source": "CAN_BUS/ECU", "freshness_ms": 100, "quality": quality},
                    "brake": {"value": None if is_inactive else 0.0, "unit": "%", "source": "HYDRAULIC_PRESSURE", "freshness_ms": 100, "quality": quality},
                    "gear": {"value": None if is_inactive else gear, "unit": "GEAR", "source": "GEARBOX_SENSOR", "freshness_ms": 100, "quality": quality},
                    "rpm": {"value": None if is_inactive else rpm, "unit": "RPM", "source": "ENGINE_CRANK", "freshness_ms": 100, "quality": quality},
                    "drs": {"value": None if is_inactive else 0, "unit": "STATUS", "source": "FIA_DRS_TELEMETRY", "freshness_ms": 100, "quality": quality},
                    "tyre_compound": {"value": entry.get("tyre", "M"), "unit": "COMPOUND", "source": "TYRE_RFID", "freshness_ms": 250, "quality": "AVAILABLE"},
                    "stint_age": {"value": entry.get("tyreAge", 0), "unit": "LAPS", "source": "TIMING_LOOPS", "freshness_ms": 250, "quality": "AVAILABLE"},
                    "gap": {"value": entry.get("gap", "—"), "unit": "INTERVAL", "source": "TIMING_TRANSPONDER", "freshness_ms": 100, "quality": "AVAILABLE"},
                    "interval": {"value": entry.get("interval", "—"), "unit": "INTERVAL", "source": "TIMING_TRANSPONDER", "freshness_ms": 100, "quality": "AVAILABLE"},
                }
                history = [] if (is_inactive or self.data_mode != "SIMULATED") else _generate_synthetic_telemetry_history(spd, gear, rpm)

            tone = "positive" if pos <= 3 else ("negative" if pos >= 15 or is_inactive else "neutral")
            label = entry.get("label") or ("Did Not Start" if status == "DNS" else ("Retired" if status == "RETIRED" else "Running"))

            new_drivers[num] = {
                "number": num,
                "initials": initials,
                "name": name,
                "team": team,
                "teamColor": color,
                "position": pos,
                "gap": entry.get("gap", "—"),
                "interval": entry.get("interval", "—"),
                "tyre": entry.get("tyre", "M"),
                "stint": entry.get("stint", 1),
                "tyreAge": entry.get("tyreAge", 0),
                "lastLap": entry.get("lastLap", "—"),
                "status": status,
                "progress": entry.get("progress", 0.0),
                "positionMode": entry.get("positionMode", "TIMING_ESTIMATED"),
                "freshnessSeconds": entry.get("freshnessSeconds", 0.3),
                "impact": {"tone": tone, "label": label},
                "telemetry": channels,
                "history": history,
            }
        self.drivers = new_drivers

    def _init_official_notices(self) -> list[dict[str, Any]]:
        """Initialises historical official FIA Race Control messages and stewards' decisions."""
        return [
            {
                "notice_id": "RC-NOTE-006",
                "timestamp_utc": "2026-05-24T13:12:34Z",
                "category": "SAFETY_CAR",
                "flag": "YELLOW",
                "title": "VIRTUAL SAFETY CAR DEPLOYED",
                "detail": "Virtual Safety Car deployed due to stopped car at exit of Nouvelle Chicane.",
                "driver_numbers": [16, 4, 1, 44],
                "regulatory_reference": "FIA F1 Sporting Regulations Art 56.4",
                "source": "FIA Race Control Central / Official Noticeboard",
                "status": "OFFICIAL_PUBLISHED",
            },
            {
                "notice_id": "RC-NOTE-005",
                "timestamp_utc": "2026-05-24T13:11:50Z",
                "category": "INCIDENT",
                "flag": "YELLOW",
                "title": "INCIDENT NOTED — TURN 10",
                "detail": "Turn 10 incident involving Car 31 (OCO) noted by Race Control.",
                "driver_numbers": [31],
                "regulatory_reference": "FIA F1 Sporting Regulations Art 54.1",
                "source": "FIA Stewards Bulletin",
                "status": "OFFICIAL_PUBLISHED",
            },
            {
                "notice_id": "RC-NOTE-004",
                "timestamp_utc": "2026-05-24T13:08:12Z",
                "category": "INVESTIGATION",
                "flag": "CLEAR",
                "title": "STEWARDS INVESTIGATION — PIT LANE SPEED",
                "detail": "Car 30 (LAW) under investigation for alleged pit lane speeding (Pit Lane Speed limit: 60 km/h).",
                "driver_numbers": [30],
                "regulatory_reference": "FIA F1 Sporting Regulations Art 34.7",
                "source": "FIA Stewards Panel",
                "status": "OFFICIAL_PUBLISHED",
            },
            {
                "notice_id": "RC-NOTE-003",
                "timestamp_utc": "2026-05-24T12:45:00Z",
                "category": "FLAG",
                "flag": "GREEN",
                "title": "RACE START — GREEN FLAG",
                "detail": "Formation lap completed. Standing start approved. Green flag racing.",
                "driver_numbers": [],
                "regulatory_reference": "FIA F1 Sporting Regulations Art 44.1",
                "source": "FIA Race Director",
                "status": "OFFICIAL_PUBLISHED",
            },
            {
                "notice_id": "RC-NOTE-002",
                "timestamp_utc": "2026-05-24T12:30:00Z",
                "category": "WEATHER",
                "flag": "CLEAR",
                "title": "OFFICIAL WEATHER REPORT",
                "detail": "Air Temp: 22.4°C · Track Temp: 34.2°C · Humidity: 58% · Rain Risk: 10%.",
                "driver_numbers": [],
                "regulatory_reference": "Meteo France Official Track Forecast",
                "source": "Official FIA Meteorological Service",
                "status": "OFFICIAL_PUBLISHED",
            },
            {
                "notice_id": "RC-NOTE-001",
                "timestamp_utc": "2026-05-24T12:00:00Z",
                "category": "GRID",
                "flag": "CLEAR",
                "title": "OFFICIAL STARTING GRID CONFIRMED",
                "detail": "All 20 cars passed technical scrutineering and parc fermé inspections.",
                "driver_numbers": [],
                "regulatory_reference": "FIA Technical Regulations Art 3",
                "source": "FIA Technical Delegate",
                "status": "OFFICIAL_PUBLISHED",
            },
        ]

    def apply_event(self, envelope: EventEnvelope) -> None:
        self.last_event_time = envelope.time.event_time_utc
        self.data_mode = envelope.run.mode.value if hasattr(envelope.run.mode, "value") else str(envelope.run.mode)

        if envelope.time.session_elapsed_ms is not None:
            secs = envelope.time.session_elapsed_ms // 1000
            hrs = secs // 3600
            mins = (secs % 3600) // 60
            s = secs % 60
            self.elapsed_time = f"{hrs:02d}:{mins:02d}:{s:02d}"

        event_type = envelope.event_type.upper()
        p = envelope.payload

        if event_type == "SESSION_STARTED":
            self.session_instance_id = envelope.session.session_id
            self.current_lap = p.get("lap", 1)
            self.total_laps = p.get("total_laps", 57)
            self._add_timeline(envelope.event_id, "Session Started", "Green flag racing underway.", "control")
            self._add_official_notice(
                f"RC-{envelope.event_id[:8]}",
                envelope.time.event_time_utc.isoformat(),
                "FLAG",
                "GREEN",
                "Session Green Flag",
                "Race commenced under green flag conditions.",
                [],
                "FIA F1 Sporting Regulations Art 44.1",
            )

        elif event_type == "VSC_DEPLOYED":
            self.active_event = "VSC"
            self.active_event_display = "Virtual Safety Car"
            self.active_lifecycle = "ACTIVE"
            self.sectors[1]["condition"] = "Dry · VSC Delta Active"
            self.sectors[1]["tone"] = "neutral"
            detail = p.get("reason", "Neutralisation triggered by stopped vehicle.")
            self._add_timeline(envelope.event_id, "VSC Deployed", detail, "control", active=True)
            self._add_official_notice(
                f"RC-{envelope.event_id[:8]}",
                envelope.time.event_time_utc.isoformat(),
                "SAFETY_CAR",
                "YELLOW",
                "VIRTUAL SAFETY CAR DEPLOYED",
                f"Neutralisation active: {detail}. Delta time enforced across all sectors.",
                p.get("affected_drivers", [16, 44]),
                "FIA F1 Sporting Regulations Art 56.4",
            )

        elif event_type == "VSC_ENDING":
            self.active_lifecycle = "ENDING"
            self.active_event_display = "VSC Ending"
            self._add_timeline(envelope.event_id, "VSC Ending", "Track clear; prepare for green flag resumption.", "control", active=True)
            self._add_official_notice(
                f"RC-{envelope.event_id[:8]}",
                envelope.time.event_time_utc.isoformat(),
                "SAFETY_CAR",
                "YELLOW",
                "VIRTUAL SAFETY CAR ENDING",
                "Track clear. Delta time requirement ending.",
                [],
                "FIA F1 Sporting Regulations Art 56.8",
            )

        elif event_type == "VSC_ENDED":
            self.active_event = "GREEN_FLAG"
            self.active_event_display = "Green Flag"
            self.active_lifecycle = "ENDED"
            self.sectors[1]["condition"] = "Dry · Full Pace"
            self.sectors[1]["tone"] = "dry"
            for item in self.timeline:
                item["active"] = False
            self._add_timeline(envelope.event_id, "Green Flag Resumed", "VSC period concluded.", "control")
            self._add_official_notice(
                f"RC-{envelope.event_id[:8]}",
                envelope.time.event_time_utc.isoformat(),
                "FLAG",
                "GREEN",
                "TRACK CLEAR — GREEN FLAG RESUMED",
                "Full racing speeds resumed across all sectors.",
                [],
                "FIA F1 Sporting Regulations Art 56.9",
            )

        elif event_type == "SAFETY_CAR_DEPLOYED":
            self.active_event = "SAFETY_CAR"
            self.active_event_display = "Safety Car Deployed"
            self.active_lifecycle = "ACTIVE"
            self._add_timeline(envelope.event_id, "Safety Car Deployed", p.get("reason", "Physical Safety Car on track."), "control", active=True)
            self._add_official_notice(
                f"RC-{envelope.event_id[:8]}",
                envelope.time.event_time_utc.isoformat(),
                "SAFETY_CAR",
                "YELLOW",
                "SAFETY CAR DEPLOYED",
                p.get("reason", "Physical Safety Car deployed on track."),
                [],
                "FIA F1 Sporting Regulations Art 55",
            )

        elif event_type == "POSITION_UPDATE":
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                if "position" in p:
                    self.drivers[dn]["position"] = p["position"]
                if "gap" in p:
                    self.drivers[dn]["gap"] = p["gap"]
                if "interval" in p:
                    self.drivers[dn]["interval"] = p["interval"]
                if "progress" in p:
                    self.drivers[dn]["progress"] = p["progress"]

        elif event_type == "LAP_COMPLETED":
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                if "last_lap_seconds" in p:
                    self.drivers[dn]["lastLap"] = p["last_lap_seconds"]
                elif "lap_time" in p:
                    self.drivers[dn]["lastLap"] = p["lap_time"]
                elif "time" in p:
                    self.drivers[dn]["lastLap"] = p["time"]

                if isinstance(self.drivers[dn]["lastLap"], (int, float)):
                    mins = int(self.drivers[dn]["lastLap"]) // 60
                    secs = self.drivers[dn]["lastLap"] % 60
                    self.drivers[dn]["lastLap"] = f"{mins}:{secs:06.3f}"

                if "position" in p:
                    self.drivers[dn]["position"] = p["position"]
                if "gap" in p:
                    self.drivers[dn]["gap"] = p["gap"]
                if "interval" in p:
                    self.drivers[dn]["interval"] = p["interval"]
                if "tyre_age" in p:
                    self.drivers[dn]["tyreAge"] = p["tyre_age"]
                else:
                    self.drivers[dn]["tyreAge"] = self.drivers[dn].get("tyreAge", 0) + 1

                lap_val = p.get("lap")
                if lap_val:
                    self.current_lap = max(self.current_lap, int(lap_val))
                elif dn in {1, 16, 44}:
                    self.current_lap = max(self.current_lap, self.drivers[dn]["tyreAge"])

        elif event_type in {"RACE_CONTROL_NOTICE", "RACE_CONTROL_MESSAGE"}:
            cat = p.get("category", "NOTICE")
            flag = p.get("flag", "CLEAR")
            title = p.get("title", "Race Control Notice")
            detail = p.get("detail", "")
            drivers = p.get("affected_drivers", [])
            ref = p.get("regulatory_reference", "FIA F1 Sporting Regulations")

            if "VSC" in title or "VIRTUAL" in title:
                self.active_event = "VSC"
                self.active_event_display = "Virtual Safety Car"
                self.active_lifecycle = "ACTIVE"
            elif "SAFETY CAR" in title and "ENDING" not in title and "IN THIS LAP" not in title:
                self.active_event = "SAFETY_CAR"
                self.active_event_display = "Safety Car Deployed"
                self.active_lifecycle = "ACTIVE"
            elif "CHEQUERED" in title:
                self.active_event = "CHEQUERED_FLAG"
                self.active_event_display = "Chequered Flag"
                self.active_lifecycle = "CONCLUDED"
            elif "GREEN" in title or "CLEAR" in title:
                self.active_event = "GREEN_FLAG"
                self.active_event_display = "Green Flag"
                self.active_lifecycle = "ENDED"

            self._add_official_notice(
                f"RC-{envelope.event_id[:8]}",
                envelope.time.event_time_utc.isoformat(),
                cat,
                flag,
                title,
                detail,
                drivers,
                ref,
            )
            self._add_timeline(envelope.event_id, title, detail, "control")

        elif event_type in {"TRACK_STATUS_GREEN", "GREEN_FLAG_RESUMED"}:
            self.active_event = "GREEN_FLAG"
            self.active_event_display = "Green Flag"
            self.active_lifecycle = "ENDED"
            for s in self.sectors:
                s["condition"] = "Dry · Green Flag"
                s["tone"] = "dry"
            for item in self.timeline:
                item["active"] = False
            self._add_timeline(envelope.event_id, "Track Clear — Green Flag Resumed", "Racing resumed.", "control")
            self._add_official_notice(
                f"RC-{envelope.event_id[:8]}",
                envelope.time.event_time_utc.isoformat(),
                "FLAG",
                "GREEN",
                "TRACK CLEAR — GREEN FLAG RESUMED",
                "Racing resumed across all sectors.",
                [],
                "FIA F1 Sporting Regulations Art 55.14",
            )

        elif event_type in {"TYRE_FITTED", "PIT_STOP"}:
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                compound = p.get("compound", "H")
                self.drivers[dn]["tyre"] = compound
                self.drivers[dn]["stint"] = p.get("stint_number", self.drivers[dn]["stint"] + 1)
                self.drivers[dn]["tyreAge"] = 0
                self.drivers[dn]["status"] = "ACTIVE"
                self.drivers[dn]["telemetry"]["tyre_compound"]["value"] = compound
                self.drivers[dn]["telemetry"]["stint_age"]["value"] = 0
                self._add_timeline(envelope.event_id, f"Driver #{dn} Pit Stop", f"Switched to {compound} compound.", "strategy")

        elif event_type == "PIT_ENTRY":
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                self.drivers[dn]["status"] = "PIT_LANE"
                self.drivers[dn]["telemetry"]["speed"]["value"] = 60.0
                self.drivers[dn]["telemetry"]["gear"]["value"] = 2
                self._add_timeline(envelope.event_id, f"Driver #{dn} Pit Entry", "Car entered pit lane.", "strategy")

        elif event_type == "PIT_EXIT":
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                self.drivers[dn]["status"] = "ACTIVE"
                self.drivers[dn]["telemetry"]["speed"]["value"] = p.get("speed", 220.0)
                self.drivers[dn]["telemetry"]["gear"]["value"] = p.get("gear", 5)
                self._add_timeline(envelope.event_id, f"Driver #{dn} Pit Exit", "Car rejoined the track.", "strategy")

        elif event_type == "DRIVER_RETIRED":
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                reason = p.get("reason", "DNF")
                self.drivers[dn]["status"] = "RETIRED"
                self.drivers[dn]["impact"] = {"tone": "negative", "label": f"Retired: {reason}"}
                for ch in self.drivers[dn]["telemetry"].values():
                    ch["quality"] = "UNAVAILABLE"
                    ch["value"] = None
                self.drivers[dn]["history"] = []
                self._add_timeline(envelope.event_id, f"Driver #{dn} Retired", f"Car retired: {reason}", "control")
                self._add_official_notice(
                    f"RC-RET-{dn}",
                    envelope.time.event_time_utc.isoformat(),
                    "INCIDENT",
                    "YELLOW",
                    f"CAR #{dn} RETIRED FROM SESSION",
                    f"Car #{dn} stopped and retired: {reason}.",
                    [dn],
                    "FIA F1 Sporting Regulations Art 26",
                )

        elif event_type == "DRIVER_DNS":
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                self.drivers[dn]["status"] = "DNS"
                self.drivers[dn]["impact"] = {"tone": "negative", "label": "Did Not Start"}
                for ch in self.drivers[dn]["telemetry"].values():
                    ch["quality"] = "UNAVAILABLE"
                    ch["value"] = None
                self.drivers[dn]["history"] = []
                self._add_timeline(envelope.event_id, f"Driver #{dn} DNS", "Car did not start the session.", "control")

        elif event_type == "SESSION_ENTRY_LIST":
            entries = p.get("entries", [])
            if entries:
                self.load_session_entry_list(entries)

        elif event_type == "TELEMETRY_UPDATE":
            dn = envelope.subject.driver_number
            if dn:
                self._ensure_driver(dn)
                channels = p.get("channels", {})
                for ch_name, ch_data in channels.items():
                    if ch_name in self.drivers[dn]["telemetry"]:
                        self.drivers[dn]["telemetry"][ch_name].update(ch_data)
                if "history_point" in p:
                    self.drivers[dn]["history"].append(p["history_point"])
                    if len(self.drivers[dn]["history"]) > 20:
                        self.drivers[dn]["history"].pop(0)

        elif event_type == "WEATHER_OBSERVATION":
            air = p.get("air_temp_c", 22.0)
            trk = p.get("track_temp_c", 33.5)
            rain = p.get("rain_risk_percent", 10.0)
            for s in self.sectors:
                if rain > 50:
                    s["condition"] = "Damp · Rain incoming"
                    s["tone"] = "wet"
                else:
                    s["condition"] = f"Dry · {trk:.1f}°C"
                    s["tone"] = "dry"

        elif event_type == "TRACK_STATUS_UPDATE":
            sec_idx = p.get("sector_index", 0)
            if 0 <= sec_idx < len(self.sectors):
                self.sectors[sec_idx]["condition"] = p.get("condition", self.sectors[sec_idx]["condition"])
                self.sectors[sec_idx]["tone"] = p.get("tone", self.sectors[sec_idx]["tone"])

    def _ensure_driver(self, dn: int) -> None:
        if dn not in self.drivers:
            meta = DRIVER_META.get(dn, {"name": f"Driver #{dn}", "initials": f"D{dn}", "team": "Independent", "color": "#718096"})
            self.drivers[dn] = {
                "number": dn,
                "initials": meta["initials"],
                "name": meta["name"],
                "team": meta["team"],
                "teamColor": meta["color"],
                "position": len(self.drivers) + 1,
                "gap": "+0.000",
                "interval": "+0.000",
                "tyre": "M",
                "stint": 1,
                "tyreAge": 0,
                "lastLap": "—",
                "status": "ACTIVE",
                "progress": 0.5,
                "positionMode": "TIMING_ESTIMATED",
                "freshnessSeconds": 0.3,
                "impact": {"tone": "neutral", "label": "Running"},
                "telemetry": {
                    "speed": {"value": 260.0, "unit": "km/h", "source": "CAN_BUS/ECU", "freshness_ms": 120, "quality": "AVAILABLE"},
                    "throttle": {"value": 90.0, "unit": "%", "source": "CAN_BUS/ECU", "freshness_ms": 120, "quality": "AVAILABLE"},
                    "brake": {"value": 0.0, "unit": "%", "source": "HYDRAULIC_PRESSURE", "freshness_ms": 120, "quality": "AVAILABLE"},
                    "gear": {"value": 6, "unit": "GEAR", "source": "GEARBOX_SENSOR", "freshness_ms": 120, "quality": "AVAILABLE"},
                    "rpm": {"value": 11000, "unit": "RPM", "source": "ENGINE_CRANK", "freshness_ms": 120, "quality": "AVAILABLE"},
                    "drs": {"value": 0, "unit": "STATUS", "source": "FIA_DRS_TELEMETRY", "freshness_ms": 120, "quality": "AVAILABLE"},
                    "tyre_compound": {"value": "M", "unit": "COMPOUND", "source": "TYRE_RFID", "freshness_ms": 250, "quality": "AVAILABLE"},
                    "stint_age": {"value": 0, "unit": "LAPS", "source": "TIMING_LOOPS", "freshness_ms": 250, "quality": "AVAILABLE"},
                    "gap": {"value": "+0.000", "unit": "INTERVAL", "source": "TIMING_TRANSPONDER", "freshness_ms": 100, "quality": "AVAILABLE"},
                    "interval": {"value": "+0.000", "unit": "INTERVAL", "source": "TIMING_TRANSPONDER", "freshness_ms": 100, "quality": "AVAILABLE"},
                },
                "history": _generate_synthetic_telemetry_history(260.0, 6, 11000),
            }

    def _add_timeline(self, event_id: str, title: str, detail: str, event_type: str, active: bool = False) -> None:
        if active:
            for item in self.timeline:
                item["active"] = False
        self.timeline.insert(
            0,
            {
                "id": event_id,
                "time": self.elapsed_time,
                "title": title,
                "detail": detail,
                "type": event_type,
                "active": active,
            },
        )
        if len(self.timeline) > 40:
            self.timeline.pop()

    def _add_official_notice(
        self,
        notice_id: str,
        timestamp_utc: str,
        category: str,
        flag: str,
        title: str,
        detail: str,
        driver_numbers: list[int],
        regulatory_reference: str,
    ) -> None:
        self.official_notices.insert(
            0,
            {
                "notice_id": notice_id,
                "timestamp_utc": timestamp_utc,
                "category": category,
                "flag": flag,
                "title": title,
                "detail": detail,
                "driver_numbers": driver_numbers,
                "regulatory_reference": regulatory_reference,
                "source": "FIA Race Control Central / Official Noticeboard",
                "status": "OFFICIAL_PUBLISHED",
            },
        )
        if len(self.official_notices) > 50:
            self.official_notices.pop()

    def get_ordered_drivers(self) -> list[dict[str, Any]]:
        return sorted(self.drivers.values(), key=lambda d: d.get("position", 99))

    def get_driver_telemetry(self, driver_number: int) -> dict[str, Any] | None:
        driver = self.drivers.get(driver_number)
        if not driver:
            return None
        return {
            "driver_number": driver["number"],
            "name": driver["name"],
            "team": driver["team"],
            "team_color": driver["teamColor"],
            "position": driver["position"],
            "status": driver["status"],
            "channels": driver["telemetry"],
            "history": driver["history"],
            "updated_at": self.last_event_time.isoformat() if self.last_event_time else datetime.now(UTC).isoformat(),
        }

    def get_official_notices(self) -> list[dict[str, Any]]:
        return self.official_notices
