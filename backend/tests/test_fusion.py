from datetime import UTC, datetime
import pytest
from unittest.mock import AsyncMock

from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.contracts import Finding, FindingStatus, Interpretation, Subject


@pytest.mark.asyncio
async def test_fusion_engine_provisional_v1_and_superseding_v2():
    mock_bus = AsyncMock()
    fusion = ConsequenceFusionEngine(bus=mock_bus)

    now = datetime.now(UTC)

    # 1. Agent 1 emits exposure finding -> triggers v1
    exp_finding = Finding(
        finding_id="finding-exp-1",
        agent_id="agent-01-event-control",
        finding_type="DRIVER_EVENT_EXPOSURE",
        session_id="sim-monaco",
        run_id="run-01",
        subject=Subject(driver_number=16),
        trigger_event_id="evt-vsc-1",
        as_of_event_time=now,
        interpretation=Interpretation.DERIVED,
        result={"driver_number": 16, "exposure_level": "CRITICAL_OPPORTUNITY"},
        evidence_refs=["evt-vsc-1"],
    )

    await fusion.on_finding("pulse.agent.event_context.findings.v1", "sim-monaco:16", exp_finding)

    assert 16 in fusion.latest_assessments
    v1 = fusion.latest_assessments[16]
    assert v1.assessment_version == 1
    assert v1.status == FindingStatus.PROVISIONAL
    assert v1.supersedes_assessment_id is None

    # 2. Agent 4 emits tyre strategy finding -> triggers superseding v2
    strat_finding = Finding(
        finding_id="finding-strat-1",
        agent_id="agent-04-tyre-strategy",
        finding_type="PIT_WINDOW_OPPORTUNITY",
        session_id="sim-monaco",
        run_id="run-01",
        subject=Subject(driver_number=16),
        trigger_event_id="evt-vsc-1",
        as_of_event_time=now,
        interpretation=Interpretation.DERIVED,
        result={
            "driver_number": 16,
            "target_compound": "H",
            "stint_age_current": 23,
            "net_time_saving_sec": 10.5,
            "gap_to_p2_sec": 2.48,
        },
        evidence_refs=["evt-vsc-1", "stint-med-23"],
    )

    await fusion.on_finding("pulse.agent.tyre_strategy.findings.v1", "sim-monaco:16", strat_finding)

    assert 16 in fusion.latest_assessments
    v2 = fusion.latest_assessments[16]
    assert v2.assessment_version == 2
    assert v2.status == FindingStatus.CONFIRMED
    assert v2.supersedes_assessment_id == v1.assessment_id
    assert len(fusion.assessment_history) == 2
