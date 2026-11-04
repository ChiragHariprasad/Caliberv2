from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class PositionMode(StrEnum):
    MEASURED_GPS = "MEASURED_GPS"
    TIMING_ESTIMATED = "TIMING_ESTIMATED"
    INTERPOLATED_DISPLAY = "INTERPOLATED_DISPLAY"


class Corner(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    number: int
    name: str
    x: float
    y: float
    sector: int
    apex_speed_kmh: float | None = None


class DRSZone(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    zone_id: int
    detection_point: list[float]  # [x, y]
    activation_point: list[float]  # [x, y]
    length_meters: float


class PitLaneGeometry(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    entry_point: list[float]  # [x, y]
    exit_point: list[float]   # [x, y]
    path: list[list[float]]   # list of [x, y]
    speed_limit_kmh: int = 60


class SectorBoundary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    sector_number: int
    start_progress: float  # 0.0 to 1.0
    end_progress: float    # 0.0 to 1.0
    checkpoint: list[float]  # [x, y]


class CircuitGeometry(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    circuit_id: str
    name: str
    country: str
    city: str
    layout_id: str
    layout_version: str
    length_meters: float
    track_direction: str  # CLOCKWISE, COUNTER_CLOCKWISE, FIGURE_EIGHT
    coordinate_reference_system: str = "LOCAL_NORMALIZED_1000"
    source_attribution: str
    checksum_sha256: str
    centreline: list[list[float]]  # list of [x, y] points forming closed loop
    inner_boundary: list[list[float]] = Field(default_factory=list)
    outer_boundary: list[list[float]] = Field(default_factory=list)
    corners: list[Corner]
    sectors: list[SectorBoundary]
    pit_lane: PitLaneGeometry
    start_finish_line: list[list[float]]  # [[x1, y1], [x2, y2]]
    drs_zones: list[DRSZone] = Field(default_factory=list)
    view_box: dict[str, float] = Field(
        default_factory=lambda: {"min_x": 0.0, "min_y": 0.0, "width": 1000.0, "height": 650.0}
    )

