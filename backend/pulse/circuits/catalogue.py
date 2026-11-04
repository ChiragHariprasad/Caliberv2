from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from pulse.circuits.models import CircuitGeometry, PositionMode

logger = logging.getLogger("pulse.circuits")

_DATA_DIR = Path(__file__).parent / "data"
_CIRCUITS_CACHE: dict[str, CircuitGeometry] = {}


def load_all_circuits() -> dict[str, CircuitGeometry]:
    """Loads and validates all circuit geometries from the catalogue storage."""
    global _CIRCUITS_CACHE
    if _CIRCUITS_CACHE:
        return _CIRCUITS_CACHE

    circuits: dict[str, CircuitGeometry] = {}
    if not _DATA_DIR.exists():
        logger.warning("Circuit data directory not found: %s", _DATA_DIR)
        return {}

    for file in _DATA_DIR.glob("*.json"):
        try:
            content = file.read_text(encoding="utf-8")
            data = json.loads(content)
            geom = CircuitGeometry.model_validate(data)
            circuits[geom.circuit_id] = geom
            logger.info("Loaded circuit geometry [%s] (v%s, checksum %s)", geom.circuit_id, geom.layout_version, geom.checksum_sha256[:8])
        except Exception as e:
            logger.error("Failed to load circuit file %s: %s", file, e, exc_info=True)

    _CIRCUITS_CACHE = circuits
    return _CIRCUITS_CACHE


def get_circuit(circuit_id: str) -> CircuitGeometry | None:
    """Retrieves a specific circuit geometry by ID (e.g., 'monaco', 'silverstone', 'suzuka')."""
    circuits = load_all_circuits()
    return circuits.get(circuit_id.lower())


def list_circuits() -> list[dict[str, Any]]:
    """Returns metadata summary of all available circuits in the catalogue."""
    circuits = load_all_circuits()
    return [
        {
            "circuit_id": c.circuit_id,
            "name": c.name,
            "country": c.country,
            "city": c.city,
            "layout_id": c.layout_id,
            "layout_version": c.layout_version,
            "length_meters": c.length_meters,
            "corners_count": len(c.corners),
            "track_direction": c.track_direction,
            "checksum_sha256": c.checksum_sha256,
            "source_attribution": c.source_attribution,
        }
        for c in circuits.values()
    ]


def interpolate_track_position(circuit: CircuitGeometry, progress: float) -> tuple[float, float]:
    """
    Interpolates a 2D coordinate (x, y) along the circuit centreline based on fractional lap progress (0.0 to 1.0).
    Performs distance-weighted linear interpolation along cumulative segment lengths.
    """
    pts = circuit.centreline
    n = len(pts)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (pts[0][0], pts[0][1])

    # Normalize progress into [0.0, 1.0)
    p = progress % 1.0
    if p < 0:
        p += 1.0

    # Calculate cumulative segment distances
    distances = []
    total_len = 0.0
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        distances.append(dist)
        total_len += dist

    if total_len == 0:
        return (pts[0][0], pts[0][1])

    target_dist = p * total_len
    accum = 0.0

    for i in range(n):
        seg_len = distances[i]
        if accum + seg_len >= target_dist or i == n - 1:
            fraction = (target_dist - accum) / seg_len if seg_len > 0 else 0.0
            fraction = max(0.0, min(1.0, fraction))
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            x = p1[0] + fraction * (p2[0] - p1[0])
            y = p1[1] + fraction * (p2[1] - p1[1])
            return (round(x, 2), round(y, 2))
        accum += seg_len

    return (pts[0][0], pts[0][1])


def resolve_driver_position(
    circuit: CircuitGeometry,
    progress: float | None = None,
    measured_gps: list[float] | None = None,
    in_pit: bool = False,
) -> tuple[float, float, PositionMode]:
    """
    Resolves driver rendering coordinates while strictly maintaining provenance and mode:
    - MEASURED_GPS: True measured physical vehicle coordinate.
    - TIMING_ESTIMATED: Derived from timing line transponders / lap distance progress.
    - INTERPOLATED_DISPLAY: Pit-lane progression or track path interpolation.
    """
    if in_pit:
        path = circuit.pit_lane.path
        if path:
            idx = int((progress or 0.5) * (len(path) - 1))
            idx = max(0, min(len(path) - 1, idx))
            return (path[idx][0], path[idx][1], PositionMode.TIMING_ESTIMATED)

    if measured_gps and len(measured_gps) >= 2:
        return (measured_gps[0], measured_gps[1], PositionMode.MEASURED_GPS)

    if progress is not None:
        x, y = interpolate_track_position(circuit, progress)
        return (x, y, PositionMode.TIMING_ESTIMATED)

    # Fallback to start/finish line
    if circuit.start_finish_line:
        p = circuit.start_finish_line[0]
        return (p[0], p[1], PositionMode.TIMING_ESTIMATED)

    return (0.0, 0.0, PositionMode.TIMING_ESTIMATED)

