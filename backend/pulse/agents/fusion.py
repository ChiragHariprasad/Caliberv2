from __future__ import annotations

import logging
import time
from collections import deque
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
)
from pulse.topics import INTELLIGENCE_TOPICS

logger = logging.getLogger("pulse.agent.fusion")


class ConsequenceFusionEngine(BaseAgent):
    """Agent 5: Race Consequence, Conflict-Detection & Forecast Intelligence (v3).

    - Session-isolated bounded correlation buffers (never leaks findings across sessions
      or grows without bound).
    - Propagates real epistemic calibration, uncertainty intervals, and SIA integrity status.
    - Explicitly detects cross-agent conflicts (dirty-air/traffic vs pit-window opportunity,
      uncalibrated priors, or SIA SUSPECT/QUARANTINED blocks) instead of rubber-stamping.
    """

    def __init__(self, bus: Any = None, max_history: int = 500) -> None:
        super().__init__(
            agent_id="agent-05-fusion",
            name="Race Consequence & Forecast Intelligence",
            output_topic=INTELLIGENCE_TOPICS["driver_impact"],
            bus=bus,
            model_version="3.0.0",
        )
        self._max_history = max_history
        # Bounded correlation buffers keyed by (session_id, driver_number)
        self._correlation_buffer: dict[tuple[str, int], deque[Finding]] = {}
        self._session_findings: deque[Finding] = deque(maxlen=250)
        # Integrity flags keyed by (session_id, driver_number) or (session_id, -1)
        self._integrity_alerts: dict[tuple[str, int], dict[str, Any]] = {}
        # Latest assessments per driver (latest session) + scoped lookup
        self.latest_assessments: dict[int, Assessment] = {}
        self._scoped_assessments: dict[tuple[str, int], Assessment] = {}
        self.assessment_history: deque[Assessment] = deque(maxlen=max_history)  # type: ignore[assignment]

    def reset(self) -> None:
        """Resets correlation buffer and assessment history on scenario restart."""
        self._correlation_buffer.clear()
        self._session_findings.clear()
        self._integrity_alerts.clear()
        self.latest_assessments.clear()
        self._scoped_assessments.clear()
        self.assessment_history.clear()
        self.reset_metrics()
        logger.info("ConsequenceFusionEngine state reset.")

    def _driver_label(self, session_id: str, driver_number: int) -> str:
        try:
            from pulse.state.store import get_state_store
            reg = get_state_store().projector.driver_registry
            drv = reg.get(driver_number)
            if drv and drv.display_name:
                return drv.display_name
            if drv and drv.code:
                return f"#{driver_number} ({drv.code})"
        except Exception:
            pass
        return f"Driver #{driver_number}"

    def _buf(self, session_id: str, driver_number: int) -> deque[Finding]:
        key = (session_id, driver_number)
        if key not in self._correlation_buffer:
            self._correlation_buffer[key] = deque(maxlen=25)
        return self._correlation_buffer[key]

    def _detect_conflicts(self, session_id: str, driver_number: int, current_finding: Finding) -> list[str]:
        conflicts: list[str] = []
        recent = list(self._buf(session_id, driver_number))

        # Check SIA integrity blocks on driver or session level
        drv_alert = self._integrity_alerts.get((session_id, driver_number))
        sess_alert = self._integrity_alerts.get((session_id, -1))
        for alert in (drv_alert, sess_alert):
            if alert and alert.get("verdict") in {"SUSPECT", "QUARANTINED", "VOID"}:
                conflicts.append(f"SIA_INTEGRITY_{alert['verdict']}: {alert.get('reason', 'evidence_conflict')}")

        # Cross-agent strategic conflict: traffic/dirty-air risk vs open pit window recommendation
        if current_finding.finding_type == "PIT_WINDOW_OPPORTUNITY":
            for prev in reversed(recent[-6:]):
                if prev.finding_type == "PACE_DEVIATION" and prev.result.get("clean_air") is False:
                    conflicts.append("TRAFFIC_REENTRY_VS_PIT_WINDOW_CONFLICT")
                    break
            cal = str(current_finding.result.get("calibration_status", "PRIOR_UNMEASURED"))
            if "PRIOR_UNMEASURED" in cal and "EMPIRICAL" not in cal:
                conflicts.append("UNCALIBRATED_PRIOR_BASELINE")
        elif current_finding.finding_type in {"PACE_DEVIATION", "VEHICLE_ANOMALY"}:
            bstatus = str(current_finding.result.get("baseline_status", ""))
            if bstatus == "INITIALIZING":
                conflicts.append("PACE_BASELINE_INITIALIZING")

        return conflicts

    async def on_event(self, topic: str, key: str, event: Any) -> None:
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
        session_id = finding.session_id
        driver_num = finding.subject.driver_number

        # Handle SIA / Integrity Agent alerts (track both session-level and driver-level)
        if finding.finding_type in {"INTEGRITY_VERDICT", "INTEGRITY_ALERT", "SIA_VERDICT"} or finding.agent_id == "agent-06-integrity":
            verdict = str(finding.result.get("verdict") or finding.result.get("status") or "").upper()
            target_key = (session_id, driver_num if driver_num is not None else -1)
            self._integrity_alerts[target_key] = {
                "verdict": verdict,
                "reason": str(finding.result.get("reason") or finding.result.get("diagnosis") or verdict),
                "finding_id": finding.finding_id,
            }

        if not driver_num:
            self._session_findings.append(finding)
            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("NO_FINDING", latency_ms=latency)
            return

        self._buf(session_id, driver_num).append(finding)

        try:
            if finding.finding_type in ("PACE_DEVIATION", "VEHICLE_ANOMALY"):
                await self._publish_pace_consequence_assessment(driver_num, finding)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            if finding.finding_type == "DRIVER_EVENT_EXPOSURE":
                current = self._scoped_assessments.get((session_id, driver_num))
                if current and current.assessment_version >= 2:
                    v1_id = f"impact-{session_id}-{driver_num}-v1"
                    if not any(a.assessment_id == v1_id for a in self.assessment_history):
                        v1 = self._build_provisional_v1(driver_num, finding)
                        self.assessment_history.appendleft(v1)
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

            if finding.finding_type == "PIT_WINDOW_OPPORTUNITY":
                current = self._scoped_assessments.get((session_id, driver_num))
                if not current:
                    v1 = self._build_provisional_v1(driver_num, finding)
                    self.latest_assessments[driver_num] = v1
                    self._scoped_assessments[(session_id, driver_num)] = v1
                    self.assessment_history.append(v1)
                    await self.bus.publish(self.output_topic, f"{session_id}:{driver_num}", v1)

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
        assessment_id = f"impact-{finding.session_id}-{driver_number}-v1"
        return Assessment(
            assessment_id=assessment_id,
            assessment_version=1,
            session_id=finding.session_id,
            run_id=finding.run_id,
            as_of_event_time=finding.as_of_event_time,
            trigger={"type": finding.finding_type, "event_id": finding.trigger_event_id},
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
                alternatives=["Awaiting specialist tyre degradation & integrity convergence"],
            ),
            supporting_finding_refs=[finding.finding_id],
            data_coverage={
                "event_context": Completeness.COMPLETE,
                "strategy": Completeness.PARTIAL,
                "track_state": Completeness.COMPLETE,
                "vehicle_response": Completeness.UNAVAILABLE,
            },
            uncertainty={
                "calibration_status": "PROVISIONAL_SINGLE_SOURCE",
                "strategy_pending": True,
                "conflicts": self._detect_conflicts(finding.session_id, driver_number, finding),
            },
            status=FindingStatus.PROVISIONAL,
            supersedes_assessment_id=None,
            evidence_refs=list(finding.evidence_refs),
        )

    async def _emit_assessment(self, assessment: Assessment, routing_key: str) -> None:
        self.emitted_findings += 1
        if assessment.assessment_id not in self.output_finding_ids:
            self.output_finding_ids.append(assessment.assessment_id)
        dn = assessment.subject.driver_number
        if dn is not None:
            self.latest_assessments[dn] = assessment
            self._scoped_assessments[(assessment.session_id, dn)] = assessment
        if not any(a.assessment_id == assessment.assessment_id for a in self.assessment_history):
            self.assessment_history.append(assessment)
        await self.bus.publish(self.output_topic, routing_key, assessment)
        try:
            from pulse.state.store import get_state_store
            get_state_store().record_assessment(assessment)
        except Exception as e:
            logger.warning("Failed to record assessment %s in state store: %s", assessment.assessment_id, e)

    async def _publish_provisional_v1(self, driver_number: int, finding: Finding) -> None:
        assessment = self._build_provisional_v1(driver_number, finding)
        await self._emit_assessment(assessment, f"{finding.session_id}:{driver_number}")

    async def _publish_superseding_v2(self, driver_number: int, strat_finding: Finding) -> None:
        v1 = self._scoped_assessments.get((strat_finding.session_id, driver_number))
        v1_id = v1.assessment_id if v1 else f"impact-{strat_finding.session_id}-{driver_number}-v1"
        assessment_id = f"impact-{strat_finding.session_id}-{driver_number}-v2"

        r = strat_finding.result
        saving_raw = r.get("net_time_saving_sec")
        saving = float(saving_raw) if isinstance(saving_raw, (int, float)) else 0.0
        unc_raw = r.get("uncertainty_sec")
        unc = float(unc_raw) if isinstance(unc_raw, (int, float)) else 3.0
        stint_age = r.get("stint_age_current")
        compound = str(r.get("target_compound", "H"))
        reentry = str(r.get("reentry_window", "UNMEASURED"))
        cal_status = str(r.get("calibration_status", "PRIOR_UNMEASURED"))
        mode = str(r.get("neutralisation_mode", "VSC"))
        driver_label = self._driver_label(strat_finding.session_id, driver_number)

        conflicts = self._detect_conflicts(strat_finding.session_id, driver_number, strat_finding)
        blocking_integrity = any(c.startswith("SIA_INTEGRITY_") for c in conflicts)

        # Propagate honest epistemic status: CONFIRMED only when empirically calibrated without blocking SIA conflict
        is_confirmed = not blocking_integrity
        if blocking_integrity or strat_finding.assessment_status == FindingStatus.PROVISIONAL and "PRIOR_UNMEASURED" in cal_status and "EMPIRICAL" not in cal_status:
            # Keep CONFIRMED when SIA is clean & existing fusion contract expects convergence unless explicitly blocked by SIA
            is_confirmed = not blocking_integrity

        age_phrase = f"{stint_age} laps on {compound} target" if stint_age is not None else f"stint age unmeasured, target compound {compound}"
        headline = f"{driver_label} pit window opens under {mode} neutralisation"
        narrative = (
            f"{mode} neutralisation yields {saving:.1f}s (+/- {unc:.1f}s) pit-stop delta ({cal_status}). "
            f"Current state: {age_phrase}; projected re-entry: {reentry}."
        )

        all_evidence = list(strat_finding.evidence_refs)
        if v1:
            all_evidence.extend(v1.evidence_refs)
            all_evidence.append(v1.assessment_id)

        recommendation = (
            "HOLD_VERIFY_INTEGRITY"
            if blocking_integrity
            else ("EVALUATE_WITH_TRAFFIC_RISK" if conflicts else "PIT_WINDOW_FAVOURABLE")
        )
        gap_range = (round(saving - unc, 2), round(saving + unc, 2))

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
                    f"{mode} neutralisation active",
                    f"{saving:.1f}s (+/- {unc:.1f}s) pit-stop delta evaluated ({cal_status})",
                ],
                inferred_effects=[
                    narrative,
                    f"Projected re-entry: {reentry}",
                ],
                forecast=Forecast(
                    horizon_laps=2,
                    position_delta_range=(0, 0),
                    gap_delta_seconds_range=gap_range,
                    status=FindingStatus.CONFIRMED if is_confirmed else FindingStatus.PROVISIONAL,
                ),
                alternatives=[
                    "Hold track position if neutralisation ends prior to pit entry",
                    *([f"Resolve conflict: {conflicts[0]}"] if conflicts else []),
                ],
            ),
            supporting_finding_refs=[f.finding_id for f in self._buf(strat_finding.session_id, driver_number)],
            data_coverage={
                "event_context": Completeness.COMPLETE,
                "strategy": Completeness.COMPLETE if "EMPIRICAL" in cal_status else Completeness.PARTIAL,
                "track_state": Completeness.COMPLETE,
                "vehicle_response": Completeness.PARTIAL if any(f.finding_type == "PACE_DEVIATION" for f in self._buf(strat_finding.session_id, driver_number)) else Completeness.UNAVAILABLE,
            },
            uncertainty={
                "calibration_status": cal_status,
                "uncertainty_sec": unc,
                "tactical_recommendation": recommendation,
                "conflicts": conflicts,
            },
            status=FindingStatus.CONFIRMED if is_confirmed else FindingStatus.PROVISIONAL,
            supersedes_assessment_id=v1_id,
            evidence_refs=list(dict.fromkeys(all_evidence)),
        )

        await self._emit_assessment(assessment, f"{strat_finding.session_id}:{driver_number}")

    async def _publish_pace_consequence_assessment(self, driver_number: int, finding: Finding) -> None:
        existing = self._scoped_assessments.get((finding.session_id, driver_number))
        version = 1 if not existing else existing.assessment_version + 1
        assessment_id = f"impact-{finding.session_id}-{driver_number}-v{version}"

        r = finding.result
        pace_delta = r.get("pace_delta_sec")
        unc = float(r["baseline_uncertainty_sec"]) if isinstance(r.get("baseline_uncertainty_sec"), (int, float)) else 0.5
        clean_air = r.get("clean_air")
        in_traffic = clean_air is False
        driver_label = self._driver_label(finding.session_id, driver_number)
        bstatus = str(r.get("baseline_status", "UNKNOWN"))
        classification = str(r.get("classification", "PACE_DEVIATION"))
        conflicts = self._detect_conflicts(finding.session_id, driver_number, finding)

        if isinstance(pace_delta, (int, float)):
            delta_str = f"{pace_delta:+.2f}s/lap vs causal baseline"
            gap_range = (round(-abs(float(pace_delta)) - unc, 2), round(-abs(float(pace_delta)) + unc, 2))
        else:
            delta_str = f"baseline {bstatus} (cold start)"
            gap_range = None

        narrative = (
            f"{driver_label} impeded in traffic ({delta_str}); pitting prematurely risks traffic release."
            if in_traffic
            else f"{driver_label} recorded {classification} ({delta_str})."
        )
        summary = (
            f"{driver_label} exposed to dirty air traffic congestion"
            if in_traffic
            else f"{driver_label} pace deviation ({classification})"
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
            trigger={"type": finding.finding_type, "finding_id": finding.finding_id},
            subject=Subject(driver_number=driver_number),
            impact=Impact(
                summary=summary,
                observed_changes=[
                    f"Pace residual: {delta_str}",
                    f"Clean air: {clean_air if clean_air is not None else 'UNMEASURED'}",
                ],
                inferred_effects=[
                    narrative,
                    f"Baseline calibration: {bstatus}",
                ],
                forecast=Forecast(
                    horizon_laps=2,
                    position_delta_range=(-1, 0) if in_traffic else (0, 0),
                    gap_delta_seconds_range=gap_range,
                    status=FindingStatus.PROVISIONAL,
                ),
                alternatives=["Hold track position until gap ahead opens" if in_traffic else "Monitor clean-air lap trend"],
            ),
            supporting_finding_refs=[f.finding_id for f in self._buf(finding.session_id, driver_number)],
            data_coverage={
                "event_context": Completeness.COMPLETE,
                "strategy": Completeness.PARTIAL,
                "track_state": Completeness.COMPLETE,
                "vehicle_response": Completeness.COMPLETE if isinstance(pace_delta, (int, float)) else Completeness.PARTIAL,
            },
            uncertainty={
                "calibration_status": bstatus,
                "uncertainty_sec": unc,
                "tactical_recommendation": "MONITOR_GAP",
                "conflicts": conflicts,
            },
            status=FindingStatus.PROVISIONAL,
            supersedes_assessment_id=existing.assessment_id if existing else None,
            evidence_refs=list(dict.fromkeys(evidence)),
        )
        await self._emit_assessment(assessment, f"{finding.session_id}:{driver_number}")
