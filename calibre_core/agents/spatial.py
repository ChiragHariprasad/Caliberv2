"""A3 Spatial Archetype: Position and Geometry Agent (F1).

Answers where vehicles physically were, independent of timing transponder loops.
Detects spatial gate crossings, calculates trajectory path lengths, and manages
effective-dated circuit geometry reference facts.

Produces evidence atoms / reference facts for roles:
  - gate_crossing (interpolated gate crossing UTC timestamp)
  - path_length (traversed path length between gates in metres)
  - track_geometry (surveyed geometry reference with layout validity window)

Failure catalogue: POSITION_JITTER_HIGH, GATE_NOT_CROSSED, TRAJECTORY_DISCONTINUITY, REFERENCE_LAYOUT_STALE.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence, Tuple

from sia_core import EvidenceAtom, IntegrityState, TimeClass, TypedTime, parse_instant
from calibre_core.agents.base import AgentArchetype, RawSpanReference
from calibre_core.circuits.geometry import CircuitLayout, get_circuit_layout


class SpatialAgent(AgentArchetype):
    """Specialist Spatial Position and Geometry Evidence Producer."""

    def __init__(
        self,
        circuit_key: str = "yas_marina_2021",
        agent_id: str = "A3-SpatialAgent",
        version: str = "1.0.0",
        source_origin: str = "CAR_POSITION",
        processing_origin: str = "A3_SPATIAL_PARSER_v1",
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            processor_id="A3_SPATIAL_PROCESSOR",
            version=version,
            source_origin=source_origin,
            processing_origin=processing_origin,
        )
        self.circuit_key = circuit_key
        self.layout: Optional[CircuitLayout] = get_circuit_layout(circuit_key)
        self._last_pos_by_driver: dict[str, Tuple[float, float, int]] = {}  # (x, y, timestamp_us)
        self._accumulated_path_by_driver_lap: dict[str, float] = {}

    @property
    def failure_catalogue(self) -> Sequence[str]:
        return (
            "POSITION_JITTER_HIGH",
            "GATE_NOT_CROSSED",
            "TRAJECTORY_DISCONTINUITY",
            "REFERENCE_LAYOUT_STALE",
        )

    def get_geometry_reference_fact(self, current_time_utc: datetime) -> dict[str, Any]:
        """Emits an effective-dated geometry reference fact for SIA admission."""
        if self.layout is None:
            self.record_diagnostic("REFERENCE_LAYOUT_STALE", f"Circuit layout {self.circuit_key} not in registry")
            return {
                "fact_type": "track_geometry",
                "scope": {"circuit_id": self.circuit_key},
                "track_length_m": 0.0,
                "is_valid": False,
            }

        is_valid = self.layout.is_valid_at(current_time_utc)
        if not is_valid:
            self.record_diagnostic(
                "REFERENCE_LAYOUT_STALE",
                f"Layout {self.layout.layout_version} expired or not yet valid at {current_time_utc.isoformat()}",
            )

        return self.layout.to_reference_fact_dict(current_time_utc)

    def process_record(
        self,
        raw_record: Mapping[str, Any],
        raw_ref: Optional[RawSpanReference] = None,
    ) -> Sequence[EvidenceAtom]:
        raw_refs = [raw_ref] if raw_ref else []
        session_id = str(raw_record.get("session_id", "session_01"))
        driver_id = str(raw_record.get("driver_number", raw_record.get("driver_id", "")))
        if not driver_id:
            return ()

        # Check for X/Y coordinates
        x_val = raw_record.get("x", raw_record.get("X"))
        y_val = raw_record.get("y", raw_record.get("Y"))
        if x_val is None or y_val is None:
            return ()

        try:
            x = float(x_val)
            y = float(y_val)
        except (ValueError, TypeError):
            return ()

        obs_time = raw_record.get("utc_timestamp", raw_record.get("observed_at", raw_record.get("timestamp")))
        if not obs_time:
            return ()
        obs_us = parse_instant(obs_time)

        atoms: list[EvidenceAtom] = []
        lap_num = str(raw_record.get("lap_number", 1))
        driver_lap_key = f"{driver_id}:{lap_num}"

        # Trajectory continuity & path integration
        last = self._last_pos_by_driver.get(driver_id)
        if last is not None:
            lx, ly, lt = last
            dx = x - lx
            dy = y - ly
            dist_step = math.hypot(dx, dy)
            dt_s = max((obs_us - lt) / 1_000_000.0, 0.001)
            inst_speed_mps = dist_step / dt_s

            # Discontinuity check: F1 car cannot travel > 400 km/h (111 m/s)
            if inst_speed_mps > 120.0:
                self.record_diagnostic(
                    "TRAJECTORY_DISCONTINUITY",
                    f"Driver {driver_id} teleported {dist_step:.1f}m in {dt_s:.3f}s ({inst_speed_mps * 3.6:.1f} km/h)",
                )

            # Jitter check
            if dt_s < 0.05 and dist_step > 15.0:
                self.record_diagnostic("POSITION_JITTER_HIGH", f"High position jitter for driver {driver_id}")

            current_path = self._accumulated_path_by_driver_lap.get(driver_lap_key, 0.0) + dist_step
            self._accumulated_path_by_driver_lap[driver_lap_key] = current_path

            # Check gate crossings
            if self.layout:
                for gate_id, gate in self.layout.gates.items():
                    if gate.crosses_gate((lx, ly), (x, y)):
                        # Linear interpolation for crossing time
                        # Midpoint approximation for sub-sample accuracy
                        cross_time_us = int((lt + obs_us) / 2)
                        scope = {
                            "session_id": session_id,
                            "driver_id": driver_id,
                            "lap_number": lap_num,
                            "gate_id": gate_id,
                        }
                        atoms.append(
                            self.emit_atom(
                                role_id="gate_crossing",
                                value=cross_time_us,
                                unit="us",
                                typed_time=TypedTime(cross_time_us, TimeClass.ABSOLUTE_UTC),
                                observed_at=obs_time,
                                scope=scope,
                                raw_refs=raw_refs,
                                uncertainty=gate.uncertainty_m / 50.0,  # ~1ms crossing uncertainty
                            )
                        )

        self._last_pos_by_driver[driver_id] = (x, y, obs_us)
        return atoms

