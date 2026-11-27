"""A4 Context Archetype: Session Context Agent (F1).

Maintains macro situational awareness, session state intervals (Green, Yellow, VSC, SC, Red),
driver operational status (Running, Pit, Retired), race-control message bindings,
and authoritative rule-regime facts.

Produces evidence atoms / reference facts for roles:
  - session_state (interval status)
  - session_t0 (session start reference fact)
  - participant_status (running, retired, in_pit)
  - rule_regime (event-specific rule limits with effective dates)
  - weather_reading (air/track temperature, humidity, rainfall)

Failure catalogue: UNKNOWN_FLAG_STATUS, SCOPE_UNRESOLVED, RULE_MISMATCH, PARSING_AMBIGUOUS.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

from sia_core import EvidenceAtom, IntegrityState, TimeClass, TypedTime, parse_instant
from calibre_core.agents.base import AgentArchetype, RawSpanReference


class SessionContextAgent(AgentArchetype):
    """Specialist Session Context and Regulatory Regime Evidence Producer."""

    def __init__(
        self,
        agent_id: str = "A4-SessionContextAgent",
        version: str = "1.0.0",
        source_origin: str = "FIA_RACE_CONTROL",
        processing_origin: str = "A4_CONTEXT_PARSER_v1",
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            processor_id="A4_CONTEXT_PROCESSOR",
            version=version,
            source_origin=source_origin,
            processing_origin=processing_origin,
        )
        self.active_flag_status = "TRACK_CLEAR"
        self.participant_statuses: dict[str, str] = {}  # driver_id -> RUNNING / RETIRED / IN_PIT

    @property
    def failure_catalogue(self) -> Sequence[str]:
        return (
            "UNKNOWN_FLAG_STATUS",
            "SCOPE_UNRESOLVED",
            "RULE_MISMATCH",
            "PARSING_AMBIGUOUS",
        )

    def process_record(
        self,
        raw_record: Mapping[str, Any],
        raw_ref: Optional[RawSpanReference] = None,
    ) -> Sequence[EvidenceAtom]:
        raw_refs = [raw_ref] if raw_ref else []
        session_id = str(raw_record.get("session_id", "session_01"))
        atoms: list[EvidenceAtom] = []

        obs_time = raw_record.get("utc_timestamp", raw_record.get("observed_at", raw_record.get("Time", "2021-12-12T13:00:00Z")))
        obs_us = parse_instant(obs_time)

        # 1. Race Control Message Processing
        if "Message" in raw_record or "message" in raw_record:
            msg_text = str(raw_record.get("Message", raw_record.get("message", ""))).upper()
            flag = str(raw_record.get("Flag", raw_record.get("flag", ""))).upper()

            # Determine neutralisation state
            new_status = self.active_flag_status
            if "SAFETY CAR DEPLOYED" in msg_text or flag == "SAFETY_CAR":
                new_status = "SAFETY_CAR"
            elif "VIRTUAL SAFETY CAR DEPLOYED" in msg_text or "VSC DEPLOYED" in msg_text:
                new_status = "VIRTUAL_SAFETY_CAR"
            elif "RED FLAG" in msg_text or flag == "RED":
                new_status = "RED_FLAG"
            elif "TRACK CLEAR" in msg_text or "GREEN FLAG" in msg_text or flag == "CLEAR":
                new_status = "GREEN"
            elif "SAFETY CAR IN THIS LAP" in msg_text:
                new_status = "SAFETY_CAR_ENDING"

            self.active_flag_status = new_status

            # Extract driver reference if present (e.g. "CAR 33", "CAR 44")
            driver_match = re.search(r"\bCAR\s+(\d+)\b", msg_text)
            driver_id = driver_match.group(1) if driver_match else None

            # Detect retirements
            if "RETIRED" in msg_text or "STOPPED" in msg_text:
                if driver_id:
                    self.participant_statuses[driver_id] = "RETIRED"

            scope = {"session_id": session_id}
            if driver_id:
                scope["driver_id"] = driver_id

            atoms.append(
                self.emit_atom(
                    role_id="session_state",
                    value=new_status,
                    unit="enum",
                    typed_time=TypedTime(obs_us, TimeClass.ABSOLUTE_UTC),
                    observed_at=obs_time,
                    scope=scope,
                    raw_refs=raw_refs,
                )
            )

        # 2. Weather Reading Processing
        elif "air_temp_c" in raw_record or "AirTemp" in raw_record:
            air_temp = float(raw_record.get("air_temp_c", raw_record.get("AirTemp", 20.0)))
            track_temp = float(raw_record.get("track_temp_c", raw_record.get("TrackTemp", 25.0)))
            scope = {"session_id": session_id}
            atoms.append(
                self.emit_atom(
                    role_id="weather_reading",
                    value=air_temp,
                    unit="celsius",
                    typed_time=TypedTime(obs_us, TimeClass.ABSOLUTE_UTC),
                    observed_at=obs_time,
                    scope=scope,
                    raw_refs=raw_refs,
                    uncertainty=0.2,
                )
            )

        return atoms

