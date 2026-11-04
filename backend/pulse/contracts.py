from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunMode(StrEnum):
    SIMULATED = "SIMULATED"
    REPLAY = "REPLAY"
    LIVE = "LIVE"


class Interpretation(StrEnum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    PREDICTED = "PREDICTED"


class Completeness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class UnitValidation(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FindingStatus(StrEnum):
    PROVISIONAL = "PROVISIONAL"
    CONFIRMED = "CONFIRMED"
    SUPERSEDED = "SUPERSEDED"
    UNRESOLVED = "UNRESOLVED"
    WITHDRAWN = "WITHDRAWN"


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class PulseModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True, protected_namespaces=())


class SourceRef(PulseModel):
    provider: str
    adapter: str
    source_record_id: str
    capture_id: str
    licence_reference: str | None = None


class RunContext(PulseModel):
    run_id: str
    session_instance_id: str
    mode: RunMode


class SessionRef(PulseModel):
    season: int
    meeting_id: str
    session_id: str
    session_type: str = "RACE"


class EventTime(PulseModel):
    event_time_utc: datetime
    session_elapsed_ms: int | None = Field(default=None, ge=0)
    ingest_time_utc: datetime = Field(default_factory=utc_now)
    replay_clock_ms: int | None = Field(default=None, ge=0)
    time_domain: str = "EVENT_TIME"

    @field_validator("event_time_utc", "ingest_time_utc")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)


class Subject(PulseModel):
    driver_number: int | None = Field(default=None, ge=1, le=99)
    segment_id: str | None = None


class Quality(PulseModel):
    interpretation: Interpretation
    completeness: Completeness = Completeness.COMPLETE
    missing_fields: list[str] = Field(default_factory=list)
    unit_validation: UnitValidation = UnitValidation.PASSED


class EventEnvelope(PulseModel):
    event_id: str
    event_type: str
    schema_version: int = Field(default=1, ge=1)
    source: SourceRef
    run: RunContext
    session: SessionRef
    time: EventTime
    subject: Subject = Field(default_factory=Subject)
    payload: dict[str, Any] = Field(default_factory=dict)
    quality: Quality


class Finding(PulseModel):
    finding_id: str
    finding_version: int = Field(default=1, ge=1)
    agent_id: str
    finding_type: str
    session_id: str
    run_id: str
    subject: Subject = Field(default_factory=Subject)
    trigger_event_id: str | None = None
    as_of_event_time: datetime
    interpretation: Interpretation
    result: dict[str, Any] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    model_version: str = "0.1.0"
    assessment_status: FindingStatus = FindingStatus.PROVISIONAL
    supersedes_finding_id: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


class Forecast(PulseModel):
    horizon_laps: int = Field(default=2, ge=1, le=3)
    position_delta_range: tuple[int, int] | None = None
    gap_delta_seconds_range: tuple[float, float] | None = None
    status: FindingStatus = FindingStatus.PROVISIONAL


class Impact(PulseModel):
    summary: str
    affected_segments: list[str] = Field(default_factory=list)
    observed_changes: list[str] = Field(default_factory=list)
    inferred_effects: list[str] = Field(default_factory=list)
    forecast: Forecast
    alternatives: list[str] = Field(default_factory=list)


class Assessment(PulseModel):
    assessment_id: str
    assessment_version: int = Field(default=1, ge=1)
    session_id: str
    run_id: str
    as_of_event_time: datetime
    trigger: dict[str, Any]
    subject: Subject
    impact: Impact
    supporting_finding_refs: list[str] = Field(default_factory=list)
    data_coverage: dict[str, Completeness | str] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    status: FindingStatus = FindingStatus.PROVISIONAL
    supersedes_assessment_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class DriverState(PulseModel):
    session_instance_id: str
    driver_number: int
    code: str = ""
    display_name: str = ""
    team: str = ""
    position: int | None = None
    gap_seconds: float | None = None
    interval_seconds: float | None = None
    lap: int | None = None
    last_lap_seconds: float | None = None
    tyre_compound: str | None = None
    stint_age: int | None = None
    pit_status: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class RunRecord(PulseModel):
    run_id: str
    session_instance_id: str
    mode: RunMode
    status: RunStatus = RunStatus.CREATED
    replay_speed: float = 1.0
    scenario: str | None = None
    created_at_utc: datetime = Field(default_factory=utc_now)
    last_event_time_utc: datetime | None = None
    source_summary: dict[str, str] = Field(default_factory=dict)


class PipelineHealth(PulseModel):
    status: str
    kafka_connected: bool
    transport: str
    processed_events: int = 0
    duplicate_events: int = 0
    last_event_time_utc: datetime | None = None
    active_agents: list[str] = Field(default_factory=list)
