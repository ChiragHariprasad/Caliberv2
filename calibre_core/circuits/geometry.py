"""Programmatic Circuit Geometry & Gate Coordinate Representation for CALIBRE.

Provides deterministic spatial geometry, coordinate transforms, timing gate positions,
track path lengths, and effective-dated layout validity windows.

Conforms to CALIBRE v4 durable reference principles:
  - Every circuit layout has an explicit version and validity date window.
  - Survey provenance and measurement uncertainties are explicitly attached.
  - Gates (start/finish, sectors, pit-lane loops) provide spatial reference facts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class Gate:
    """A spatial detection boundary (timing loop, sector line, or pit boundary)."""
    gate_id: str
    name: str
    gate_type: str  # "LINE", "LOOP", "SPEED_TRAP"
    x1: float
    y1: float
    x2: float
    y2: float
    track_distance_m: float
    uncertainty_m: float = 0.05  # Standard survey uncertainty

    def midpoint(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def crosses_gate(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> bool:
        """Determines if the segment p1 -> p2 intersects the gate line segment."""
        def ccw(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> bool:
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

        g1 = (self.x1, self.y1)
        g2 = (self.x2, self.y2)
        return (ccw(p1, g1, g2) != ccw(p2, g1, g2)) and (ccw(p1, p2, g1) != ccw(p1, p2, g2))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "gate_type": self.gate_type,
            "midpoint": self.midpoint(),
            "track_distance_m": self.track_distance_m,
            "uncertainty_m": self.uncertainty_m,
        }


@dataclass(frozen=True)
class CircuitLayout:
    """A specific versioned track layout with effective dates and geometry provenance."""
    circuit_id: str
    name: str
    country: str
    layout_version: str
    track_length_m: float
    valid_from: datetime
    valid_to: datetime | None
    survey_provenance: str
    survey_uncertainty_m: float
    gates: Mapping[str, Gate] = field(default_factory=dict)
    pit_lane_length_m: float = 0.0
    pit_speed_limit_kph: float = 80.0

    def is_valid_at(self, instant: datetime) -> bool:
        if self.valid_from and instant < self.valid_from:
            return False
        if self.valid_to and instant > self.valid_to:
            return False
        return True

    def get_gate(self, gate_id: str) -> Gate | None:
        return self.gates.get(gate_id)

    def to_reference_fact_dict(self, instant: datetime) -> dict[str, Any]:
        """Generates a geometry reference fact dictionary for SIA admission."""
        return {
            "fact_type": "track_geometry",
            "scope": {"circuit_id": self.circuit_id, "layout_version": self.layout_version},
            "track_length_m": self.track_length_m,
            "pit_lane_length_m": self.pit_lane_length_m,
            "pit_speed_limit_kph": self.pit_speed_limit_kph,
            "survey_provenance": self.survey_provenance,
            "uncertainty_m": self.survey_uncertainty_m,
            "is_valid": self.is_valid_at(instant),
        }


# ---------------------------------------------------------------------------
# Pre-configured Circuit Layout Registry (for the 10 Corpus Races)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, CircuitLayout] = {
    # 01: Abu Dhabi (Yas Marina - 2021 reconfigured layout: removed chicanes at T5/T6 and Marina)
    "yas_marina_2021": CircuitLayout(
        circuit_id="yas_marina",
        name="Yas Marina Circuit",
        country="United Arab Emirates",
        layout_version="2021-v1",
        track_length_m=5281.0,
        valid_from=datetime(2021, 11, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        survey_provenance="FIA_CIRCUIT_HOMOLOGATION_2021_GRADE_1",
        survey_uncertainty_m=0.08,
        pit_lane_length_m=359.0,
        pit_speed_limit_kph=80.0,
        gates={
            "FINISH_LINE": Gate("FINISH_LINE", "Finish Line", "LINE", 0.0, -10.0, 0.0, 10.0, 0.0),
            "SECTOR_1": Gate("SECTOR_1", "Sector 1 Split", "LINE", 1250.0, 450.0, 1260.0, 470.0, 1420.0),
            "SECTOR_2": Gate("SECTOR_2", "Sector 2 Split", "LINE", 280.0, 1150.0, 300.0, 1160.0, 3450.0),
            "PIT_ENTRY": Gate("PIT_ENTRY", "Pit Entry Line", "LINE", -150.0, -20.0, -150.0, -5.0, 5130.0),
            "PIT_EXIT": Gate("PIT_EXIT", "Pit Exit Line", "LINE", 220.0, -5.0, 220.0, 10.0, 220.0),
        },
    ),
    # 02: Spa-Francorchamps
    "spa_2021": CircuitLayout(
        circuit_id="spa",
        name="Circuit de Spa-Francorchamps",
        country="Belgium",
        layout_version="2021-v1",
        track_length_m=7004.0,
        valid_from=datetime(2018, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2021, 12, 31, tzinfo=timezone.utc),
        survey_provenance="RACB_FIA_SURVEY_GRADE_1",
        survey_uncertainty_m=0.10,
        pit_lane_length_m=387.0,
        pit_speed_limit_kph=80.0,
    ),
    # 03: Jeddah Corniche Circuit
    "jeddah_2021": CircuitLayout(
        circuit_id="jeddah",
        name="Jeddah Corniche Circuit",
        country="Saudi Arabia",
        layout_version="2021-v1",
        track_length_m=6174.0,
        valid_from=datetime(2021, 11, 1, tzinfo=timezone.utc),
        valid_to=datetime(2022, 1, 1, tzinfo=timezone.utc),
        survey_provenance="TILKE_FIA_HOMOLOGATION_2021",
        survey_uncertainty_m=0.06,
        pit_lane_length_m=340.0,
        pit_speed_limit_kph=80.0,
    ),
    # 04: Silverstone
    "silverstone_2021": CircuitLayout(
        circuit_id="silverstone",
        name="Silverstone Circuit",
        country="United Kingdom",
        layout_version="2021-v1",
        track_length_m=5891.0,
        valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        survey_provenance="BRDC_FIA_HOMOLOGATION",
        survey_uncertainty_m=0.05,
        pit_lane_length_m=367.0,
        pit_speed_limit_kph=80.0,
    ),
    # 05: Red Bull Ring
    "red_bull_ring_2023": CircuitLayout(
        circuit_id="red_bull_ring",
        name="Red Bull Ring",
        country="Austria",
        layout_version="2023-v1",
        track_length_m=4318.0,
        valid_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        survey_provenance="AMF_FIA_GRADE_1_SURVEY",
        survey_uncertainty_m=0.04,
        pit_lane_length_m=320.0,
        pit_speed_limit_kph=80.0,
    ),
    # 06: Albert Park Melbourne
    "albert_park_2023": CircuitLayout(
        circuit_id="albert_park",
        name="Albert Park Circuit",
        country="Australia",
        layout_version="2023-v1",
        track_length_m=5278.0,
        valid_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        survey_provenance="AGPC_FIA_GRADE_1_RECONFIGURED",
        survey_uncertainty_m=0.07,
        pit_lane_length_m=281.0,
        pit_speed_limit_kph=80.0,
    ),
    # 07: Suzuka
    "suzuka_2022": CircuitLayout(
        circuit_id="suzuka",
        name="Suzuka International Racing Course",
        country="Japan",
        layout_version="2022-v1",
        track_length_m=5807.0,
        valid_from=datetime(2018, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        survey_provenance="JAF_FIA_GRADE_1",
        survey_uncertainty_m=0.05,
        pit_lane_length_m=395.0,
        pit_speed_limit_kph=80.0,
    ),
    # 08: Monaco
    "monaco_2022": CircuitLayout(
        circuit_id="monaco",
        name="Circuit de Monaco",
        country="Monaco",
        layout_version="2022-v1",
        track_length_m=3337.0,
        valid_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2024, 12, 31, tzinfo=timezone.utc),
        survey_provenance="ACM_FIA_SURVEY_ANNUAL",
        survey_uncertainty_m=0.03,
        pit_lane_length_m=301.0,
        pit_speed_limit_kph=60.0,  # Strict 60 kph limit at Monaco
    ),
    # 09: COTA Austin
    "cota_2024": CircuitLayout(
        circuit_id="cota",
        name="Circuit of the Americas",
        country="United States",
        layout_version="2024-v1",
        track_length_m=5513.0,
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        survey_provenance="USAC_FIA_RESURFACED_SURVEY_2024",
        survey_uncertainty_m=0.06,
        pit_lane_length_m=385.0,
        pit_speed_limit_kph=80.0,
    ),
    # 10: Las Vegas Strip
    "las_vegas_2023": CircuitLayout(
        circuit_id="las_vegas",
        name="Las Vegas Strip Circuit",
        country="United States",
        layout_version="2023-v1",
        track_length_m=6201.0,
        valid_from=datetime(2023, 11, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        survey_provenance="TILKE_LVGP_INAUGURAL_SURVEY",
        survey_uncertainty_m=0.08,
        pit_lane_length_m=360.0,
        pit_speed_limit_kph=80.0,
    ),
}


def get_circuit_layout(circuit_key: str) -> CircuitLayout | None:
    return _REGISTRY.get(circuit_key)


def list_circuit_layouts() -> Sequence[CircuitLayout]:
    return tuple(_REGISTRY.values())

