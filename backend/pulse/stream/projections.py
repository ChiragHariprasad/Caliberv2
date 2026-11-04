from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pulse.contracts import EventEnvelope

logger = logging.getLogger("pulse.projections")

DRIVER_META = {
    16: {"name": "Charles Leclerc", "initials": "CL", "team": "Ferrari"},
    4: {"name": "Lando Norris", "initials": "LN", "team": "McLaren"},
    1: {"name": "Max Verstappen", "initials": "MV", "team": "Red Bull Racing"},
    44: {"name": "Lewis Hamilton", "initials": "LH", "team": "Ferrari"},
    81: {"name": "Oscar Piastri", "initials": "OP", "team": "McLaren"},
    63: {"name": "George Russell", "initials": "GR", "team": "Mercedes"},
    55: {"name": "Carlos Sainz", "initials": "CS", "team": "Williams"},
    14: {"name": "Fernando Alonso", "initials": "FA", "team": "Aston Martin"},
}


class RaceStateProjector:
    """Projects canonical stream events into live consumer-facing race state."""

    def __init__(self) -> None:
        self.session_instance_id: str = "pulse-sim-001"
        self.session_name: str = "Monaco Grand Prix"
        self.session_type: str = "Race Intelligence"
        self.current_lap: int = 24
        self.total_laps: int = 57
        self.active_event: str = "GREEN_FLAG"
        self.active_event_display: str = "Green Flag"
        self.active_lifecycle: str = "NONE"
        self.elapsed_time: str = "01:11:50"
        self.data_mode: str = "SIMULATED"
        self.last_event_time: datetime | None = None

        # Drivers state keyed by driver_number
        self.drivers: dict[int, dict[str, Any]] = {
            16: {
                "number": 16,
                "initials": "CL",
                "name": "Charles Leclerc",
                "team": "Ferrari",
                "position": 1,
                "gap": "LEADER",
                "interval": "—",
                "tyre": "M",
                "stint": 1,
                "tyreAge": 23,
                "lastLap": "1:15.821",
                "momentum": 86,
                "impact": {"tone": "positive", "label": "Leading comfortably"},
            },
            4: {
                "number": 4,
                "initials": "LN",
                "name": "Lando Norris",
                "team": "McLaren",
                "position": 2,
                "gap": "+2.481",
                "interval": "+2.481",
                "tyre": "H",
                "stint": 1,
                "tyreAge": 23,
                "lastLap": "1:16.040",
                "momentum": 64,
                "impact": {"tone": "neutral", "label": "Holding gap"},
            },
            1: {
                "number": 1,
                "initials": "MV",
                "name": "Max Verstappen",
                "team": "Red Bull Racing",
                "position": 3,
                "gap": "+4.067",
                "interval": "+1.586",
                "tyre": "H",
                "stint": 1,
                "tyreAge": 23,
                "lastLap": "1:16.132",
                "momentum": 52,
                "impact": {"tone": "neutral", "label": "Pressuring P2"},
            },
            44: {
                "number": 44,
                "initials": "LH",
                "name": "Lewis Hamilton",
                "team": "Ferrari",
                "position": 4,
                "gap": "+8.742",
                "interval": "+4.675",
                "tyre": "M",
                "stint": 1,
                "tyreAge": 23,
                "lastLap": "1:16.286",
                "momentum": 28,
                "impact": {"tone": "negative", "label": "Traffic risk"},
            },
            81: {
                "number": 81,
                "initials": "OP",
                "name": "Oscar Piastri",
                "team": "McLaren",
                "position": 5,
                "gap": "+10.036",
                "interval": "+1.294",
                "tyre": "H",
                "stint": 1,
                "tyreAge": 23,
                "lastLap": "1:16.401",
                "momentum": 46,
                "impact": {"tone": "neutral", "label": "Managing pace"},
            },
        }

        # Sectors
        self.sectors: list[dict[str, Any]] = [
            {"id": "s1", "label": "Sector 1", "condition": "Dry · clear", "tone": "dry", "confidence": 96},
            {"id": "s2", "label": "Sector 2", "condition": "Dry · active", "tone": "dry", "confidence": 98},
            {"id": "s3", "label": "Sector 3", "condition": "Dry · clear", "tone": "dry", "confidence": 92},
        ]

        # Timeline events
        self.timeline: list[dict[str, Any]] = []

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

        elif event_type == "VSC_DEPLOYED":
            self.active_event = "VSC"
            self.active_event_display = "Virtual Safety Car"
            self.active_lifecycle = "ACTIVE"
            self.sectors[1]["condition"] = "Dry · VSC Delta Active"
            self.sectors[1]["tone"] = "neutral"
            detail = p.get("reason", "Neutralisation triggered by incident at Nouvelle Chicane.")
            self._add_timeline(envelope.event_id, "VSC Deployed", detail, "control", active=True)

        elif event_type == "VSC_ENDING":
            self.active_lifecycle = "ENDING"
            self.active_event_display = "VSC Ending"
            self._add_timeline(envelope.event_id, "VSC Ending", "Track clear; prepare for green flag resumption.", "control", active=True)

        elif event_type == "VSC_ENDED":
            self.active_event = "GREEN_FLAG"
            self.active_event_display = "Green Flag"
            self.active_lifecycle = "ENDED"
            self.sectors[1]["condition"] = "Dry · Full Pace"
            self.sectors[1]["tone"] = "dry"
            for item in self.timeline:
                item["active"] = False
            self._add_timeline(envelope.event_id, "Green Flag Resumed", "VSC period concluded.", "control")

        elif event_type == "SAFETY_CAR_DEPLOYED":
            self.active_event = "SAFETY_CAR"
            self.active_event_display = "Safety Car Deployed"
            self.active_lifecycle = "ACTIVE"
            self._add_timeline(envelope.event_id, "Safety Car Deployed", p.get("reason", "Physical Safety Car on track."), "control", active=True)

        elif event_type == "POSITION_UPDATE":
            dn = envelope.subject.driver_number
            if dn:
                if dn not in self.drivers:
                    self.drivers[dn] = {
                        "number": dn,
                        "initials": f"D{dn}",
                        "name": f"Driver #{dn}",
                        "team": "Independent",
                        "position": len(self.drivers) + 1,
                        "gap": "+0.000",
                        "interval": "+0.000",
                        "tyre": "M",
                        "stint": 1,
                        "tyreAge": 0,
                        "lastLap": "—",
                        "momentum": 50,
                        "impact": {"tone": "neutral", "label": "Running"},
                    }
                if "position" in p:
                    self.drivers[dn]["position"] = p["position"]
                if "gap" in p:
                    self.drivers[dn]["gap"] = p["gap"]
                if "interval" in p:
                    self.drivers[dn]["interval"] = p["interval"]
                if "momentum" in p:
                    self.drivers[dn]["momentum"] = p["momentum"]

        elif event_type == "LAP_COMPLETED":
            dn = envelope.subject.driver_number
            if dn:
                if dn not in self.drivers:
                    self.drivers[dn] = {
                        "number": dn,
                        "initials": f"D{dn}",
                        "name": f"Driver #{dn}",
                        "team": "Independent",
                        "position": len(self.drivers) + 1,
                        "gap": "+0.000",
                        "interval": "+0.000",
                        "tyre": "M",
                        "stint": 1,
                        "tyreAge": 0,
                        "lastLap": "—",
                        "momentum": 50,
                        "impact": {"tone": "neutral", "label": "Running"},
                    }
                self.drivers[dn]["lastLap"] = p.get("lap_time_str", self.drivers[dn].get("lastLap", "—"))
                self.drivers[dn]["tyreAge"] = self.drivers[dn].get("tyreAge", 0) + 1
                if dn == 16:
                    self.current_lap = p.get("lap_number", self.current_lap + 1)

        elif event_type in {"TYRE_FITTED", "PIT_STOP"}:
            dn = envelope.subject.driver_number
            if dn and dn in self.drivers:
                self.drivers[dn]["tyre"] = p.get("compound", "H")
                self.drivers[dn]["stint"] = p.get("stint_number", self.drivers[dn]["stint"] + 1)
                self.drivers[dn]["tyreAge"] = 0
                self._add_timeline(envelope.event_id, f"Driver #{dn} Pit Stop", f"Switched to {self.drivers[dn]['tyre']} compound.", "strategy")

        elif event_type == "PIT_ENTRY":
            dn = envelope.subject.driver_number
            self._add_timeline(envelope.event_id, f"Driver #{dn} Pit Entry", "Car entered pit lane.", "strategy")

        elif event_type == "WEATHER_OBSERVATION":
            air = p.get("air_temp_c", 24.0)
            trk = p.get("track_temp_c", 34.0)
            rain = p.get("rain_risk_percent", 0.0)
            condition_str = f"Track: {trk:.1f}°C · Air: {air:.1f}°C"
            if rain > 30:
                condition_str += f" · Rain Risk {rain:.0f}%"
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
        # Retain last 30 timeline events
        if len(self.timeline) > 30:
            self.timeline.pop()

    def get_ordered_drivers(self) -> list[dict[str, Any]]:
        return sorted(self.drivers.values(), key=lambda d: d.get("position", 99))

