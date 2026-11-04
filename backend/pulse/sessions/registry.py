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
    "f1-2023-silverstone-race": SessionMetadata(
        session_id="f1-2023-silverstone-race",
        season=2023,
        grand_prix_name="Formula 1 Aramco British Grand Prix 2023",
        circuit_id="silverstone",
        session_type="RACE",
        capture_id="pulse-capture-f1-2023-silverstone-race-v1",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "LAP_TIMING",
            "PIT_STOPS",
            "RACE_CONTROL_NOTICES",
            "WEATHER_OBSERVATIONS",
        ],
        entry_list_count=20,
        session_duration_ms=4845000,
        total_laps=52,
        source_provenance="JOLPICA_F1_AND_FIA_OFFICIAL",
        availability_status="AVAILABLE_HISTORICAL",
        description="Complete 52-lap historical Grand Prix with 20 drivers, 24 pit stops, and 10 FIA race control notices.",
    ),
    "f1-2026-monaco-sim": SessionMetadata(
        session_id="f1-2026-monaco-sim",
        season=2026,
        grand_prix_name="Formula 1 Grand Prix de Monaco 2026",
        circuit_id="monaco",
        session_type="SIMULATED_RACE",
        capture_id="pulse-sim-v1",
        available_feeds=[
            "SESSION_ENTRY_LIST",
            "SIMULATED_VSC_SCENARIO",
            "SYNTHETIC_TIMING",
        ],
        entry_list_count=20,
        session_duration_ms=36000,
        total_laps=78,
        source_provenance="PULSE_DETERMINISTIC_SIMULATOR",
        availability_status="AVAILABLE_SIMULATION",
        description="Deterministic 9-step VSC tactical scenario demonstrating pit window compression at Nouvelle Chicane.",
    ),
    "f1-2026-suzuka-preview": SessionMetadata(
        session_id="f1-2026-suzuka-preview",
        season=2026,
        grand_prix_name="Formula 1 Lenovo Japanese Grand Prix 2026",
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

