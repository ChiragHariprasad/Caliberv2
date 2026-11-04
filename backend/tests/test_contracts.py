from datetime import UTC, datetime
import pytest
from pydantic import ValidationError

from pulse.contracts import (
    Assessment,
    Completeness,
    EventEnvelope,
    EventTime,
    Finding,
    FindingStatus,
    Forecast,
    Impact,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
)


def test_event_envelope_valid():
    now = datetime.now(UTC)
    env = EventEnvelope(
        event_id="evt-100",
        event_type="VSC_DEPLOYED",
        source=SourceRef(
            provider="PULSE_SIMULATOR",
            adapter="vsc_v1",
            source_record_id="rec-1",
            capture_id="cap-1",
        ),
        run=RunContext(
            run_id="run-1",
            session_instance_id="sess-1",
            mode=RunMode.SIMULATED,
        ),
        session=SessionRef(
            season=2026,
            meeting_id="monaco",
            session_id="sess-1",
        ),
        time=EventTime(
            event_time_utc=now,
            session_elapsed_ms=10000,
            replay_clock_ms=10000,
        ),
        subject=Subject(driver_number=16),
        payload={"reason": "debris on track"},
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )
    assert env.event_id == "evt-100"
    assert env.subject.driver_number == 16
    assert env.time.session_elapsed_ms == 10000
    assert env.time.replay_clock_ms == 10000


def test_timestamp_requires_timezone():
    naive_time = datetime(2026, 5, 24, 14, 0, 0)  # No tzinfo
    with pytest.raises(ValidationError):
        EventTime(event_time_utc=naive_time)


def test_finding_contract():
    now = datetime.now(UTC)
    finding = Finding(
        finding_id="f-1",
        agent_id="agent-01-event-control",
        finding_type="RACE_EVENT_LIFECYCLE",
        session_id="sess-1",
        run_id="run-1",
        as_of_event_time=now,
        interpretation=Interpretation.OBSERVED,
        result={"lifecycle": "ACTIVE"},
        evidence_refs=["evt-100"],
    )
    assert finding.finding_id == "f-1"
    assert finding.assessment_status == FindingStatus.PROVISIONAL


def test_assessment_contract_with_revisions():
    now = datetime.now(UTC)
    v1 = Assessment(
        assessment_id="a-1-v1",
        assessment_version=1,
        session_id="sess-1",
        run_id="run-1",
        as_of_event_time=now,
        trigger={"type": "VSC"},
        subject=Subject(driver_number=16),
        impact=Impact(
            summary="VSC pit window opportunity",
            forecast=Forecast(horizon_laps=2, position_delta_range=(0, 1)),
        ),
        status=FindingStatus.PROVISIONAL,
    )

    v2 = Assessment(
        assessment_id="a-1-v2",
        assessment_version=2,
        session_id="sess-1",
        run_id="run-1",
        as_of_event_time=now,
        trigger={"type": "STRATEGY_UPDATE"},
        subject=Subject(driver_number=16),
        impact=Impact(
            summary="VSC pit window confirmed with 10.5s delta advantage",
            forecast=Forecast(horizon_laps=2, position_delta_range=(0, 0)),
        ),
        status=FindingStatus.CONFIRMED,
        supersedes_assessment_id="a-1-v1",
    )

    assert v1.assessment_version == 1
    assert v2.assessment_version == 2
    assert v2.supersedes_assessment_id == "a-1-v1"
