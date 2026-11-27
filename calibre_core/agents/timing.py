"""A1 Measurement Archetype: Timing Agent (F1).

Collects and parses raw timing feeds (transponder loops, lap completion records,
sector durations, pit stops, and speed trap observations).

Produces evidence atoms for roles:
  - lap_record (duration in seconds)
  - sector_record (duration in seconds)
  - timing_speed (speed trap velocity in km/h)
  - pit_event (pit entry/exit timestamps)

Failure catalogue: SCHEMA_DRIFT, UNPARSEABLE_TIME, NUMBERING_REGRESSION, DUPLICATE_RECORD, UNIT_UNKNOWN.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from sia_core import EvidenceAtom, IntegrityState, TimeClass, TypedTime, parse_instant
from calibre_core.agents.base import AgentArchetype, RawSpanReference


class TimingAgent(AgentArchetype):
    """Specialist Timing Evidence Producer."""

    def __init__(
        self,
        agent_id: str = "A1-TimingAgent",
        version: str = "1.0.0",
        source_origin: str = "F1_FOM_TIMING",
        processing_origin: str = "A1_TIMING_PARSER_v1",
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            processor_id="A1_TIMING_PROCESSOR",
            version=version,
            source_origin=source_origin,
            processing_origin=processing_origin,
        )
        self._last_lap_by_driver: dict[str, int] = {}
        self._seen_records: set[str] = set()

    @property
    def failure_catalogue(self) -> Sequence[str]:
        return (
            "SCHEMA_DRIFT",
            "UNPARSEABLE_TIME",
            "NUMBERING_REGRESSION",
            "DUPLICATE_RECORD",
            "UNIT_UNKNOWN",
            "CUMULATIVE_GAP_DETECTED",
        )

    def process_record(
        self,
        raw_record: Mapping[str, Any],
        raw_ref: Optional[RawSpanReference] = None,
    ) -> Sequence[EvidenceAtom]:
        raw_refs = [raw_ref] if raw_ref else []
        event_type = raw_record.get("event_type", raw_record.get("type", ""))
        session_id = str(raw_record.get("session_id", "session_01"))
        driver_id = str(raw_record.get("driver_number", raw_record.get("driver_id", "")))

        atoms: list[EvidenceAtom] = []

        # Deduplication check
        rec_key = f"{event_type}:{session_id}:{driver_id}:{raw_record.get('lap_number')}:{raw_record.get('sector_number')}:{raw_record.get('timestamp')}"
        if rec_key in self._seen_records:
            self.record_diagnostic("DUPLICATE_RECORD", f"Repeated record key {rec_key}")
            return ()
        self._seen_records.add(rec_key)

        # 1. Lap Completed
        if event_type in ("LAP_COMPLETED", "DRIVER_LAP_DATA") or "lap_time_seconds" in raw_record:
            lap_num = raw_record.get("lap_number")
            if lap_num is None:
                self.record_diagnostic("SCHEMA_DRIFT", "Lap record missing lap_number")
                return ()
            lap_num = int(lap_num)

            # Check numbering regression
            last_lap = self._last_lap_by_driver.get(driver_id, 0)
            if lap_num < last_lap:
                self.record_diagnostic(
                    "NUMBERING_REGRESSION",
                    f"Driver {driver_id} lap regressed from {last_lap} to {lap_num}",
                )
            self._last_lap_by_driver[driver_id] = max(last_lap, lap_num)

            lap_time = raw_record.get("lap_time_seconds", raw_record.get("duration_s"))
            if lap_time is None:
                self.record_diagnostic("UNPARSEABLE_TIME", f"Missing lap duration for driver {driver_id} lap {lap_num}")
                return ()
            try:
                lap_time_float = float(lap_time)
            except (ValueError, TypeError):
                self.record_diagnostic("UNPARSEABLE_TIME", f"Invalid lap duration value: {lap_time}")
                return ()

            obs_time = raw_record.get("utc_timestamp", raw_record.get("observed_at", raw_record.get("timestamp")))
            if not obs_time:
                obs_time = "2021-12-12T13:00:00Z"

            scope = {"session_id": session_id, "driver_id": driver_id, "lap_number": str(lap_num)}
            atoms.append(
                self.emit_atom(
                    role_id="lap_record",
                    value=lap_time_float,
                    unit="s",
                    typed_time=TypedTime(int(lap_time_float * 1_000_000), TimeClass.LAP_DURATION),
                    observed_at=obs_time,
                    scope=scope,
                    raw_refs=raw_refs,
                    uncertainty=0.001,  # 1 ms transponder resolution
                )
            )

        # 2. Sector Completed
        elif event_type in ("SECTOR_COMPLETED", "SECTOR_TIME") or "sector_time_seconds" in raw_record:
            sec_num = raw_record.get("sector_number", 1)
            lap_num = raw_record.get("lap_number", 1)
            sec_time = raw_record.get("sector_time_seconds", raw_record.get("duration_s"))
            if sec_time is not None:
                scope = {
                    "session_id": session_id,
                    "driver_id": driver_id,
                    "lap_number": str(lap_num),
                    "sector_number": str(sec_num),
                }
                obs_time = raw_record.get("utc_timestamp", raw_record.get("observed_at", "2021-12-12T13:00:00Z"))
                atoms.append(
                    self.emit_atom(
                        role_id="sector_record",
                        value=float(sec_time),
                        unit="s",
                        typed_time=TypedTime(int(float(sec_time) * 1_000_000), TimeClass.LAP_DURATION),
                        observed_at=obs_time,
                        scope=scope,
                        raw_refs=raw_refs,
                        uncertainty=0.001,
                    )
                )

        # 3. Speed Trap
        elif event_type in ("SPEED_TRAP", "PIT_SPEED") or "speed_kph" in raw_record:
            speed = float(raw_record.get("speed_kph", raw_record.get("speed", 0.0)))
            scope = {
                "session_id": session_id,
                "driver_id": driver_id,
                "lap_number": str(raw_record.get("lap_number", 1)),
                "sector_number": str(raw_record.get("sector_number", 1)),
            }
            obs_time = raw_record.get("utc_timestamp", raw_record.get("observed_at", "2021-12-12T13:00:00Z"))
            atoms.append(
                self.emit_atom(
                    role_id="timing_speed",
                    value=speed,
                    unit="kph",
                    typed_time=TypedTime(parse_instant(obs_time), TimeClass.ABSOLUTE_UTC),
                    observed_at=obs_time,
                    scope=scope,
                    raw_refs=raw_refs,
                    uncertainty=0.1,  # 0.1 kph loop timing uncertainty
                )
            )

        return atoms

