from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pulse.contracts import (
    Completeness,
    EventEnvelope,
    EventTime,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
)
from pulse.topics import raw_topic_for_event


def create_envelope(
    event_id: str,
    event_type: str,
    elapsed_ms: int,
    session_id: str = "sim-2026-monaco",
    run_id: str = "run-vsc-001",
    driver_number: int | None = None,
    segment_id: str | None = None,
    payload: dict[str, Any] | None = None,
    base_time: datetime | None = None,
) -> EventEnvelope:
    base = base_time or datetime(2026, 5, 24, 14, 0, 0, tzinfo=UTC)
    event_time = base + timedelta(milliseconds=elapsed_ms)

    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        source=SourceRef(
            provider="PULSE_SIMULATOR",
            adapter="deterministic_vsc_v1",
            source_record_id=f"src-{event_id}",
            capture_id="pulse-sim-monaco-v1",
        ),
        run=RunContext(
            run_id=run_id,
            session_instance_id=session_id,
            mode=RunMode.SIMULATED,
        ),
        session=SessionRef(
            season=2026,
            meeting_id="monaco-gp",
            session_id=session_id,
            session_type="RACE",
        ),
        time=EventTime(
            event_time_utc=event_time,
            session_elapsed_ms=elapsed_ms,
            replay_clock_ms=elapsed_ms,
            time_domain="SIMULATED_EVENT_TIME",
        ),
        subject=Subject(driver_number=driver_number, segment_id=segment_id),
        payload=payload or {},
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )


def build_vsc_scenario() -> list[EventEnvelope]:
    """Builds the canonical VSC demonstration scenario script."""
    events: list[EventEnvelope] = []

    # 0s: Session starts
    events.append(
        create_envelope(
            event_id="evt-001",
            event_type="SESSION_STARTED",
            elapsed_ms=0,
            payload={"lap": 24, "total_laps": 57, "meeting": "Monaco Grand Prix"},
        )
    )

    # 2s: Baseline positions
    for dn, pos, gap, iv, mom in [
        (16, 1, "LEADER", "—", 86),
        (4, 2, "+2.481", "+2.481", 64),
        (1, 3, "+4.067", "+1.586", 52),
        (44, 4, "+8.742", "+4.675", 28),
        (81, 5, "+10.036", "+1.294", 46),
    ]:
        events.append(
            create_envelope(
                event_id=f"evt-pos-base-{dn}",
                event_type="POSITION_UPDATE",
                elapsed_ms=2000,
                driver_number=dn,
                payload={"position": pos, "gap": gap, "interval": iv, "momentum": mom},
            )
        )

    # 4s: Sector updates
    events.append(
        create_envelope(
            event_id="evt-track-001",
            event_type="TRACK_STATUS_UPDATE",
            elapsed_ms=4000,
            payload={"sector_index": 0, "condition": "Dry · clear", "tone": "dry"},
        )
    )

    # 6s: Lap time completed by leader Leclerc
    events.append(
        create_envelope(
            event_id="evt-lap-16-24",
            event_type="LAP_COMPLETED",
            elapsed_ms=6000,
            driver_number=16,
            payload={"lap_number": 24, "lap_time_str": "1:15.821", "sector1_sec": 19.4, "sector2_sec": 34.1},
        )
    )

    # 11s: VSC DEPLOYED at Nouvelle Chicane
    events.append(
        create_envelope(
            event_id="evt-vsc-deploy-001",
            event_type="VSC_DEPLOYED",
            elapsed_ms=11000,
            segment_id="nouvelle-chicane",
            payload={
                "reason": "Incident at Nouvelle Chicane involving barrier debris.",
                "affected_sectors": ["Sector 2"],
                "speed_delta_imposed": 0.60,
            },
        )
    )

    # 12s: Leader Leclerc approaches Pit Entry under VSC
    events.append(
        create_envelope(
            event_id="evt-pos-vsc-16",
            event_type="POSITION_UPDATE",
            elapsed_ms=12000,
            driver_number=16,
            payload={
                "position": 1,
                "gap": "LEADER",
                "interval": "—",
                "momentum": 92,
                "pit_lane_entry_distance_m": 85,
            },
        )
    )

    # 14s: Leclerc enters pit lane
    events.append(
        create_envelope(
            event_id="evt-pit-entry-16",
            event_type="PIT_ENTRY",
            elapsed_ms=14000,
            driver_number=16,
            payload={"pit_stop_planned": True, "fitted_compound_expected": "H"},
        )
    )

    # 16s: Pit stop completed - Hard tyres fitted
    events.append(
        create_envelope(
            event_id="evt-tyre-fit-16",
            event_type="TYRE_FITTED",
            elapsed_ms=16000,
            driver_number=16,
            payload={"compound": "H", "stint_number": 2, "stop_time_sec": 2.2},
        )
    )

    # 18s: VSC ENDING
    events.append(
        create_envelope(
            event_id="evt-vsc-ending-001",
            event_type="VSC_ENDING",
            elapsed_ms=18000,
            payload={"notice": "Track cleared. Virtual Safety Car ending."},
        )
    )

    # 20s: VSC ENDED
    events.append(
        create_envelope(
            event_id="evt-vsc-ended-001",
            event_type="VSC_ENDED",
            elapsed_ms=20000,
            payload={"status": "GREEN_FLAG", "racing_resumed": True},
        )
    )

    # 22s: Leclerc retains P1 with fresh Hards
    events.append(
        create_envelope(
            event_id="evt-pos-post-16",
            event_type="POSITION_UPDATE",
            elapsed_ms=22000,
            driver_number=16,
            payload={"position": 1, "gap": "+3.105 ahead of Norris", "momentum": 95},
        )
    )

    return events

