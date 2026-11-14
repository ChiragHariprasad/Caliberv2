from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SessionMetadata(BaseModel):
    """Authoritative metadata describing a race session and its data availability."""
    session_id: str
    season: int
    grand_prix_name: str
    circuit_id: str
    session_type: str
    capture_id: str | None = None
    available_feeds: list[str] = Field(default_factory=list)
    entry_list_count: int = 0
    session_duration_ms: int = 0
    total_laps: int = 0
    source_provenance: str
    availability_status: str  # "AVAILABLE_HISTORICAL", "AVAILABLE_SIMULATION", "NO_SESSION_DATA"
    description: str = ""


SESSION_REGISTRY: dict[str, SessionMetadata] = {
    # 1. Monaco
    "f1-2026-monaco-sim": SessionMetadata(
        session_id="f1-2026-monaco-sim",
        season=2026,
        grand_prix_name="Formula 1 Grand Prix de Monaco",
        circuit_id="monaco",
        session_type="RACE",
        capture_id="f1-2026-monaco-sim",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=3600000,
        total_laps=78,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Full 78-lap Monaco Grand Prix with second-by-second micro-sector telemetry, VSC deployment, and pit window compression.",
    ),
    # 2. Silverstone
    "f1-2023-silverstone-race": SessionMetadata(
        session_id="f1-2023-silverstone-race",
        season=2023,
        grand_prix_name="Formula 1 British Grand Prix 2023",
        circuit_id="silverstone",
        session_type="RACE",
        capture_id="f1-2023-silverstone-race",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=3600000,
        total_laps=52,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Full 52-lap British Grand Prix with second-by-second continuous telemetry, pit stops, and safety car neutralisation.",
    ),
    # 3. Suzuka
    "f1-2026-suzuka-race": SessionMetadata(
        session_id="f1-2026-suzuka-race",
        season=2026,
        grand_prix_name="Formula 1 Japanese Grand Prix",
        circuit_id="suzuka",
        session_type="RACE",
        capture_id="f1-2026-suzuka-race",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=3600000,
        total_laps=53,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Full 53-lap Japanese Grand Prix at Suzuka with second-by-second high-density telemetry across all 20 drivers.",
    ),
    # 4. Abu Dhabi (Yas Marina)
    "f1-2021-abu-dhabi": SessionMetadata(
        session_id="f1-2021-abu-dhabi",
        season=2021,
        grand_prix_name="Formula 1 Abu Dhabi Grand Prix 2021",
        circuit_id="yas_marina",
        session_type="RACE",
        capture_id="f1-2021-abu-dhabi",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=1800000,
        total_laps=58,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Landmark 2021 season finale: Safety Car unlapping procedure dispute (Art 48.12) & final lap title battle.",
    ),
    # 5. Belgium (Spa-Francorchamps)
    "f1-2021-belgium": SessionMetadata(
        session_id="f1-2021-belgium",
        season=2021,
        grand_prix_name="Formula 1 Belgian Grand Prix 2021",
        circuit_id="spa",
        session_type="RACE",
        capture_id="f1-2021-belgium",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=1800000,
        total_laps=44,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Extreme rain event at Spa-Francorchamps: Safety Car formation laps, red flags, and half-points classification.",
    ),
    # 6. Saudi Arabia (Jeddah)
    "f1-2021-saudi-arabia": SessionMetadata(
        session_id="f1-2021-saudi-arabia",
        season=2021,
        grand_prix_name="Formula 1 Saudi Arabian Grand Prix 2021",
        circuit_id="jeddah",
        session_type="RACE",
        capture_id="f1-2021-saudi-arabia",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=1800000,
        total_laps=50,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Inaugural high-speed Jeddah Corniche street race: multiple red flags and Lap 37 69-bar brake telemetry incident.",
    ),
    # 7. Austria (Red Bull Ring)
    "f1-2023-austria": SessionMetadata(
        session_id="f1-2023-austria",
        season=2023,
        grand_prix_name="Formula 1 Austrian Grand Prix 2023",
        circuit_id="red_bull_ring",
        session_type="RACE",
        capture_id="f1-2023-austria",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=1800000,
        total_laps=71,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Red Bull Ring: 1,200+ track limit violations, post-race petition for review, and amended classification.",
    ),
    # 8. Australia (Albert Park)
    "f1-2023-australia": SessionMetadata(
        session_id="f1-2023-australia",
        season=2023,
        grand_prix_name="Formula 1 Australian Grand Prix 2023",
        circuit_id="albert_park",
        session_type="RACE",
        capture_id="f1-2023-australia",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=1800000,
        total_laps=58,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Chaotic Melbourne race with 3 red flags, late standing restart collisions, and countback procession to the flag.",
    ),
    # 9. United States (COTA)
    "f1-2024-united-states": SessionMetadata(
        session_id="f1-2024-united-states",
        season=2024,
        grand_prix_name="Formula 1 United States Grand Prix 2024",
        circuit_id="cota",
        session_type="RACE",
        capture_id="f1-2024-united-states",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=1800000,
        total_laps=56,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="Austin COTA: Lap 52 Turn 12 apex ownership battle, driving standards guidelines, and penalty assessment.",
    ),
    # 10. Las Vegas (Las Vegas Strip)
    "f1-2023-las-vegas": SessionMetadata(
        session_id="f1-2023-las-vegas",
        season=2023,
        grand_prix_name="Formula 1 Las Vegas Grand Prix 2023",
        circuit_id="las_vegas",
        session_type="RACE",
        capture_id="f1-2023-las-vegas",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "POSITION_TELEMETRY",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=1800000,
        total_laps=50,
        source_provenance="FIA_OFFICIAL_TIMING_AND_TELEMETRY",
        availability_status="AVAILABLE_HISTORICAL",
        description="High-speed Las Vegas Strip street circuit: water valve cover track failure and 350+ km/h slipstream racing.",
    ),
    # 11. Suzuka Preview
    "f1-2026-suzuka-preview": SessionMetadata(
        session_id="f1-2026-suzuka-preview",
        season=2026,
        grand_prix_name="Suzuka Preview · Homologated Geometry",
        circuit_id="suzuka",
        session_type="PREVIEW_ONLY",
        capture_id=None,
        available_feeds=[],
        entry_list_count=0,
        session_duration_ms=0,
        total_laps=53,
        source_provenance="PREVIEW_GEOMETRY_CATALOGUE",
        availability_status="NO_SESSION_DATA",
        description="Circuit geometry asset available. No historical capture or simulated session data loaded.",
    ),
    # 12. Unloaded Preview
    "f1-unloaded-preview": SessionMetadata(
        session_id="f1-unloaded-preview",
        season=2026,
        grand_prix_name="Formula 1 Unloaded Preview",
        circuit_id="suzuka",
        session_type="PREVIEW_ONLY",
        capture_id=None,
        available_feeds=[],
        entry_list_count=0,
        session_duration_ms=0,
        total_laps=0,
        source_provenance="PREVIEW_GEOMETRY_CATALOGUE",
        availability_status="NO_SESSION_DATA",
        description="Circuit geometry asset available. No historical capture or simulated session data loaded.",
    ),
}


def list_sessions() -> list[SessionMetadata]:
    """Returns all registered Formula 1 sessions in the system."""
    return list(SESSION_REGISTRY.values())


def get_session_by_id(session_id: str) -> SessionMetadata | None:
    """Finds a session by its unique session identifier."""
    return SESSION_REGISTRY.get(session_id)


def get_default_session_for_circuit(circuit_id: str) -> SessionMetadata | None:
    """Finds the default session associated with a given circuit identifier."""
    for s in SESSION_REGISTRY.values():
        if s.circuit_id.lower() == circuit_id.lower():
            return s
    return None
