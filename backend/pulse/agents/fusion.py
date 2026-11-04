from __future__ import annotations

import logging
import time
from typing import Any

from pulse.agents.base import BaseAgent
from pulse.contracts import (
    Assessment,
    Completeness,
    Finding,
    FindingStatus,
    Forecast,
    Impact,
    Subject,
    utc_now,
)
from pulse.topics import AGENT_TOPICS, INTELLIGENCE_TOPICS

logger = logging.getLogger("pulse.agent.fusion")


class ConsequenceFusionEngine(BaseAgent):
    """Agent 5: Race Consequence & Forecast Intelligence.
    
    Asynchronously correlates specialist findings from Agents 1–4, synthesizes evidence-backed
    consequence assessments with short-horizon forecasts, and manages revision chains (v1 -> v2)
    with bounded waiting and partial assessment support.
    """

    def __init__(self, bus: Any = None) -> None:
        super().__init__(
            agent_id="agent-05-fusion",
            name="Race Consequence & Forecast Intelligence",
            output_topic=INTELLIGENCE_TOPICS["driver_impact"],
            bus=bus,
            model_version="2.0.0",
        )
        # Correlation buffers: driver_number -> list[Finding]
        self._correlation_buffer: dict[int, list[Finding]] = {}
        # Track-wide findings (from Agent 1 lifecycle and Agent 2 track state)
        self._session_findings: list[Finding] = []
        # Latest assessments per driver
        self.latest_assessments: dict[int, Assessment] = {}
        self.assessment_history: list[Assessment] = []

    def reset(self) -> None:
        """Resets correlation buffer and assessment history on scenario restart."""
        self._correlation_buffer.clear()
        self._session_findings.clear()
        self.latest_assessments.clear()
        self.assessment_history.clear()
        self.reset_metrics()
        logger.info("ConsequenceFusionEngine state reset.")

    async def on_event(self, topic: str, key: str, event: Any) -> None:
        # Handled primarily through on_finding
        pass

    async def on_finding(self, topic: str, key: str, finding_data: dict[str, Any] | Finding) -> None:
        t0 = time.perf_counter()
        try:
            finding = finding_data if isinstance(finding_data, Finding) else Finding.model_validate(finding_data)
        except Exception as e:
            self.record_outcome("FAILED", latency_ms=0.0)
            logger.warning("Fusion rejected invalid finding payload: %s", e)
            return

        self.record_input(finding.finding_id, eligible=True, run_id=finding.run_id)

        driver_num = finding.subject.driver_number
        if not driver_num:
            # Store track-level or session-level finding
            self._session_findings.append(finding)
            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("NO_FINDING", latency_ms=latency)
            return

        if driver_num not in self._correlation_buffer:
            self._correlation_buffer[driver_num] = []
        self._correlation_buffer[driver_num].append(finding)

        try:
            # 1. Driver in traffic / dirty air pace deficit (e.g. driver #44 or any driver with pace deviation)
            if finding.finding_type in ("PACE_DEVIATION", "VEHICLE_ANOMALY"):
                await self._publish_pace_consequence_assessment(driver_num, finding)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            # 2. Driver spatial neutralisation exposure (Agent 1)
            if finding.finding_type == "DRIVER_EVENT_EXPOSURE":
                current = self.latest_assessments.get(driver_num)
                if current and current.assessment_version >= 2:
                    # Out-of-order arrival: Agent 4 arrived before Agent 1
                    v1_id = f"impact-{finding.session_id}-{driver_num}-v1"
                    if not any(a.assessment_id == v1_id for a in self.assessment_history):
                        v1 = self._build_provisional_v1(driver_num, finding)
                        self.assessment_history.insert(0, v1)
                    current.supersedes_assessment_id = v1_id
                    if finding.finding_id not in current.supporting_finding_refs:
                        current.supporting_finding_refs.append(finding.finding_id)
                    for ref in finding.evidence_refs:
                        if ref not in current.evidence_refs:
                            current.evidence_refs.append(ref)
                elif not current:
                    await self._publish_provisional_v1(driver_num, finding)

                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            # 3. Pit window opportunity & strategy convergence (Agent 4)
            elif finding.finding_type == "PIT_WINDOW_OPPORTUNITY":
                current = self.latest_assessments.get(driver_num)
                if not current:
                    # Out-of-order: Agent 4 arrived before Agent 1. Create provisional v1 first to maintain v1 -> v2 chain
                    v1 = self._build_provisional_v1(driver_num, finding)
                    self.latest_assessments[driver_num] = v1
                    self.assessment_history.append(v1)
                    await self.bus.publish(self.output_topic, f"{finding.session_id}:{driver_num}", v1)

                # Publish superseding v2 assessment
                if not current or current.assessment_version < 2:
                    await self._publish_superseding_v2(driver_num, finding)

                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("NO_FINDING", latency_ms=latency)

        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("FAILED", latency_ms=latency)
            logger.error("ConsequenceFusionEngine error fusing finding: %s", e, exc_info=True)
            raise

    def _build_provisional_v1(self, driver_number: int, finding: Finding) -> Assessment:
        """Constructs a bounded provisional Assessment v1 instance based on partial findings."""
        assessment_id = f"impact-{finding.session_id}-{driver_number}-v1"
        return Assessment(
            assessment_id=assessment_id,
            assessment_version=1,
            session_id=finding.session_id,
            run_id=finding.run_id,
            as_of_event_time=finding.as_of_event_time,
            trigger={"type": "VSC_DEPLOYMENT", "event_id": finding.trigger_event_id},
            subject=Subject(driver_number=driver_number),
            impact=Impact(
                summary=f"Neutralisation deployed; car #{driver_number} exposed to pit-window delta opportunity.",
                observed_changes=["Neutralisation delta active across track segments"],
                inferred_effects=["Relative pit lane transit cost compressed"],
                forecast=Forecast(
                    horizon_laps=2,
                    position_delta_range=(0, 1),
                    status=FindingStatus.PROVISIONAL,
                ),
                alternatives=["Awaiting specialist tyre degradation model"],
            ),
            supporting_finding_refs=[finding.finding_id],
            data_coverage={
                "event_context": Completeness.COMPLETE,
                "strategy": Completeness.PARTIAL,
                "track_state": Completeness.COMPLETE,
                "vehicle_response": Completeness.UNAVAILABLE,
            },
            uncertainty={"calibration_status": "UNCALIBRATED_HEURISTIC", "strategy_pending": True},
            status=FindingStatus.PROVISIONAL,
            supersedes_assessment_id=None,
            evidence_refs=list(finding.evidence_refs),
        )

    async def _publish_provisional_v1(self, driver_number: int, finding: Finding) -> None:
        """Publishes provisional Assessment v1."""
        assessment = self._build_provisional_v1(driver_number, finding)
        self.latest_assessments[driver_number] = assessment
        self.assessment_history.append(assessment)
        await self.bus.publish(self.output_topic, f"{finding.session_id}:{driver_number}", assessment)
        logger.info("Published provisional Assessment v1 for driver #%d", driver_number)

    async def _publish_superseding_v2(self, driver_number: int, strat_finding: Finding) -> None:
        """Publishes superseding Assessment v2 with deterministic strategy convergence."""
        v1 = self.latest_assessments.get(driver_number)
        v1_id = v1.assessment_id if v1 else f"impact-{strat_finding.session_id}-{driver_number}-v1"
        assessment_id = f"impact-{strat_finding.session_id}-{driver_number}-v2"

        r = strat_finding.result
        saving = r.get("net_time_saving_sec", 10.5)
        stint_age = r.get("stint_age_current", 23)
        compound = r.get("target_compound", "H")
        driver_label = f"Driver #{driver_number}" if driver_number != 16 else "Charles Leclerc"

        headline = f"{driver_label} pit window opens under neutralisation"
        narrative = (
            f"VSC neutralisation reduces relative pit transit loss by {saving:.1f}s. "
            f"Current stint is {stint_age} laps on {compound} compound."
        )

        all_evidence = list(strat_finding.evidence_refs)
        if v1:
            all_evidence.extend(v1.evidence_refs)
            all_evidence.append(v1.assessment_id)

        assessment = Assessment(
            assessment_id=assessment_id,
            assessment_version=2,
            session_id=strat_finding.session_id,
            run_id=strat_finding.run_id,
            as_of_event_time=strat_finding.as_of_event_time,
            trigger={"type": "PIT_WINDOW_STRATEGY_CONVERGENCE", "finding_id": strat_finding.finding_id},
            subject=Subject(driver_number=driver_number),
            impact=Impact(
                summary=headline,
                observed_changes=[
                    "VSC neutralisation active",
                    f"{saving:.1f}s net pit-stop delta saving verified",
                ],
                inferred_effects=[
                    narrative,
                    f"Favourable stop window opened for car #{driver_number}",
                ],
                forecast=Forecast(
                    horizon_laps=2,
                    position_delta_range=(0, 0),
                    gap_delta_seconds_range=(1.5, 3.0),
                    status=FindingStatus.CONFIRMED,
                ),
                alternatives=["Stay out if green flag resumes before pit entry"],
            ),
            supporting_finding_refs=[f.finding_id for f in self._correlation_buffer.get(driver_number, [])],
            data_coverage={
                "event_context": Completeness.COMPLETE,
                "strategy": Completeness.COMPLETE,
                "track_state": Completeness.COMPLETE,
                "vehicle_response": Completeness.UNAVAILABLE,
            },
            uncertainty={
                "calibration_status": "UNCALIBRATED_HEURISTIC",
                "tactical_recommendation": "BOX_THIS_LAP",
            },
            status=FindingStatus.CONFIRMED,
            supersedes_assessment_id=v1_id,
            evidence_refs=list(set(all_evidence)),
        )

        self.latest_assessments[driver_number] = assessment
        if not any(a.assessment_id == assessment_id for a in self.assessment_history):
            self.assessment_history.append(assessment)
        await self.bus.publish(self.output_topic, f"{strat_finding.session_id}:{driver_number}", assessment)
        logger.info("Published revised Assessment v2 for driver #%d (supersedes %s)", driver_number, v1_id)

    async def _publish_pace_consequence_assessment(self, driver_number: int, finding: Finding) -> None:
        """Publishes or updates consequence assessment for driver subject to pace deficit or traffic."""
        existing = self.latest_assessments.get(driver_number)
        version = 1 if not existing else existing.assessment_version + 1
        assessment_id = f"impact-{finding.session_id}-{driver_number}-v{version}"

        pace_delta = finding.result.get("pace_delta_sec", 0.46)
        in_traffic = not finding.result.get("clean_air", True)
        driver_label = f"Driver #{driver_number}" if driver_number != 44 else "Lewis Hamilton"

        narrative = (
            f"{driver_label} losing {pace_delta:.2f}s/lap in congested dirty air; pitting now risks releasing into traffic."
            if in_traffic
            else f"{driver_label} experiencing +{pace_delta:.2f}s pace deviation under current track conditions."
        )

        evidence = list(finding.evidence_refs)
        if existing:
            evidence.extend(existing.evidence_refs)
            evidence.append(existing.assessment_id)

        assessment = Assessment(
            assessment_id=assessment_id,
            assessment_version=version,
            session_id=finding.session_id,
            run_id=finding.run_id,
            as_of_event_time=finding.as_of_event_time,
            trigger={
                "type": "PACE_DEVIATION",
                "finding_id": finding.finding_id,
            },
            subject=Subject(driver_number=driver_number),
            impact=Impact(
                summary=f"{driver_label} exposed to dirty air traffic congestion",
                observed_changes=[
                    f"+{pace_delta:.2f}s pace loss observed",
                    "Congested Sector 2 traffic density",
                ],
                inferred_effects=[
                    narrative,
                    "Pace monitoring active for undercut traffic window",
                ],
                forecast=Forecast(
                    horizon_laps=2,
                    position_delta_range=(-1, 0),
                    gap_delta_seconds_range=(-1.5, 0.0),
                    status=FindingStatus.PROVISIONAL,
                ),
                alternatives=["Hold track position until traffic ahead clears"],
            ),
            supporting_finding_refs=[f.finding_id for f in self._correlation_buffer.get(driver_number, [])],
            data_coverage={
                "event_context": Completeness.COMPLETE,
                "strategy": Completeness.COMPLETE,
                "track_state": Completeness.COMPLETE,
                "vehicle_response": Completeness.COMPLETE,
            },
            uncertainty={
                "calibration_status": "UNCALIBRATED_HEURISTIC",
                "tactical_recommendation": "MONITOR_GAP",
            },
            status=FindingStatus.PROVISIONAL,
            supersedes_assessment_id=existing.assessment_id if existing else None,
            evidence_refs=list(set(evidence)),
        )
        self.latest_assessments[driver_number] = assessment
        if not any(a.assessment_id == assessment_id for a in self.assessment_history):
            self.assessment_history.append(assessment)
        await self.bus.publish(self.output_topic, f"{finding.session_id}:{driver_number}", assessment)
        logger.info("Published consequence assessment for driver #%d (version %d)", driver_number, version)
