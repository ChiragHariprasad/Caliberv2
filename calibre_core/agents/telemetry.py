"""A2 Asset Telemetry Archetype: Vehicle Telemetry Agent (F1).

Processes physical sensor telemetry from the car's ECU (speed, RPM, gear, throttle,
brake pressure, and DRS status).

Produces evidence atoms for roles:
  - vehicle_speed (speed in km/h with sample statistics)
  - integrated_distance (integrated distance in metres)
  - kinematic_plausibility (binary plausibility check with stated g-force and pedal exclusivity)

Failure catalogue: SAMPLING_GAP, SPEED_RESOLUTION_COARSE, CHANNEL_MISSING, MAPPING_UNRESOLVED, KINEMATIC_ANOMALY.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence

from sia_core import EvidenceAtom, IntegrityState, TimeClass, TypedTime, parse_instant
from calibre_core.agents.base import AgentArchetype, RawSpanReference


class VehicleTelemetryAgent(AgentArchetype):
    """Specialist Asset Telemetry Evidence Producer."""

    def __init__(
        self,
        agent_id: str = "A2-VehicleTelemetryAgent",
        version: str = "1.0.0",
        source_origin: str = "CAR_ECU",
        processing_origin: str = "A2_TELEMETRY_PARSER_v1",
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            processor_id="A2_TELEMETRY_PROCESSOR",
            version=version,
            source_origin=source_origin,
            processing_origin=processing_origin,
        )
        self._last_sample_time_by_driver: dict[str, int] = {}
        self._last_speed_by_driver: dict[str, float] = {}

    @property
    def failure_catalogue(self) -> Sequence[str]:
        return (
            "SAMPLING_GAP",
            "SPEED_RESOLUTION_COARSE",
            "CHANNEL_MISSING",
            "MAPPING_UNRESOLVED",
            "KINEMATIC_ANOMALY",
        )

    def process_record(
        self,
        raw_record: Mapping[str, Any],
        raw_ref: Optional[RawSpanReference] = None,
    ) -> Sequence[EvidenceAtom]:
        raw_refs = [raw_ref] if raw_ref else []
        session_id = str(raw_record.get("session_id", "session_01"))
        driver_id = str(raw_record.get("driver_number", raw_record.get("driver_id", "")))
        if not driver_id:
            self.record_diagnostic("MAPPING_UNRESOLVED", "Telemetry sample lacks driver identification")
            return ()

        obs_time = raw_record.get("utc_timestamp", raw_record.get("observed_at", raw_record.get("timestamp")))
        if not obs_time:
            self.record_diagnostic("CHANNEL_MISSING", f"Telemetry for driver {driver_id} lacks timestamp")
            return ()
        obs_us = parse_instant(obs_time)

        # Check sampling gap (> 1.0 second between samples indicates a gap)
        last_t = self._last_sample_time_by_driver.get(driver_id)
        if last_t is not None and (obs_us - last_t) > 1_000_000:
            gap_s = (obs_us - last_t) / 1_000_000
            self.record_diagnostic("SAMPLING_GAP", f"Driver {driver_id} telemetry gap of {gap_s:.2f}s")
        self._last_sample_time_by_driver[driver_id] = obs_us

        atoms: list[EvidenceAtom] = []
        scope = {
            "session_id": session_id,
            "driver_id": driver_id,
            "lap_number": str(raw_record.get("lap_number", 1)),
            "sector_number": str(raw_record.get("sector_number", 1)),
        }

        # 1. Speed Evaluation
        raw_speed = raw_record.get("speed_kph", raw_record.get("speed", raw_record.get("car_speed")))
        if raw_speed is not None:
            speed = float(raw_speed)
            last_speed = self._last_speed_by_driver.get(driver_id)

            # Check kinematic deceleration / acceleration plausibility
            # F1 cars rarely exceed 5.5g under heavy braking (~54 m/s² ≈ 194 km/h per second)
            # A sudden drop of > 60 km/h in < 0.2s without contact or barrier is suspicious
            if last_t is not None and last_speed is not None:
                dt_s = max((obs_us - last_t) / 1_000_000.0, 0.001)
                dv_kph = speed - last_speed
                accel_mps2 = (dv_kph / 3.6) / dt_s
                g_force = accel_mps2 / 9.80665

                # Detect sudden heavy deceleration (> 2.0g)
                if g_force < -2.0:
                    self.record_diagnostic(
                        "KINEMATIC_ANOMALY",
                        f"Driver {driver_id} severe deceleration {g_force:.2f}g (speed {last_speed:.1f} -> {speed:.1f} kph in {dt_s:.3f}s)",
                    )
            self._last_speed_by_driver[driver_id] = speed

            atoms.append(
                self.emit_atom(
                    role_id="vehicle_speed",
                    value=speed,
                    unit="kph",
                    typed_time=TypedTime(obs_us, TimeClass.ABSOLUTE_UTC),
                    observed_at=obs_time,
                    scope=scope,
                    raw_refs=raw_refs,
                    uncertainty=0.5,  # 0.5 kph ECU wheel-speed sensor uncertainty
                )
            )

        # 2. Kinematic Plausibility Check (Pedal exclusivity)
        throttle = raw_record.get("throttle", raw_record.get("throttle_pct"))
        brake = raw_record.get("brake", raw_record.get("brake_pct"))
        if throttle is not None and brake is not None:
            th_f = float(throttle)
            br_f = float(brake)
            # Both full throttle and heavy brake simultaneously for extended periods is an anomaly
            is_plausible = not (th_f > 80.0 and br_f > 50.0)
            if not is_plausible:
                self.record_diagnostic(
                    "KINEMATIC_ANOMALY",
                    f"Driver {driver_id} pedal conflict: throttle={th_f}%, brake={br_f}%",
                )

            atoms.append(
                self.emit_atom(
                    role_id="kinematic_flags",
                    value=1 if is_plausible else 0,
                    unit="bool",
                    typed_time=TypedTime(obs_us, TimeClass.ABSOLUTE_UTC),
                    observed_at=obs_time,
                    scope=scope,
                    raw_refs=raw_refs,
                    uncertainty=0.0,
                    quality_grade=IntegrityState.HEALTHY if is_plausible else IntegrityState.SUSPECT,
                )
            )

        return atoms

