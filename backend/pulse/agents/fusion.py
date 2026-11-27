from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from pulse.agents.base import BaseAgent
from pulse.contracts import (
    Assessment,
    CleanAirStatus,
    Completeness,
    Finding,
    FindingStatus,
    Forecast,
    Impact,
    Interpretation,
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

    @staticmethod
    def _finding_missing_telemetry(finding: Finding) -> bool:
        res = finding.result or {}
        unc = finding.uncertainty or {}
        comp = str(res.get("completeness") or unc.get("completeness") or "").upper()
        return bool(res.get("missing_telemetry") is True or comp in {"MISSING", "UNAVAILABLE"})

    def _detect_conflicts(self, session_id: str, driver_number: int, current_finding: Finding) -> list[str]:
        conflicts: list[str] = []
        recent = list(self._buf(session_id, driver_number))

        # Check SIA integrity blocks on driver or session level
        drv_alert = self._integrity_alerts.get((session_id, driver_number))
        sess_alert = self._integrity_alerts.get((session_id, -1))
        for alert in (drv_alert, sess_alert):
            if not alert:
                continue
            verdict = str(alert.get("verdict", "UNKNOWN")).upper()
            if verdict in {"SUSPECT", "DEGRADED", "UNKNOWN", "QUARANTINED", "VOID"}:
                conflicts.append(f"SIA_INTEGRITY_{verdict}: {alert.get('reason', 'evidence_conflict')}")
            elif verdict == "HEALTHY" and not alert.get("finalized", False):
                conflicts.append("SIA_EVIDENCE_NOT_FINALIZED")

        res = current_finding.result or {}
        if (
            current_finding.assessment_status == FindingStatus.REJECTED
            or res.get("contradicts") is True
            or res.get("unit_validation_failed") is True
        ):
            conflicts.append("CONTRADICTING_EVIDENCE_REJECTED")

        if res.get("conflicting_evidence") is True:
            conflicts.append("CONFLICTING_DOMAIN_EVIDENCE")

        if self._finding_missing_telemetry(current_finding):
            conflicts.append("MISSING_TELEMETRY_COVERAGE")

        # Cross-agent strategic conflict: traffic/dirty-air risk vs open pit window recommendation
        if current_finding.finding_type == "PIT_WINDOW_OPPORTUNITY":
            for prev in reversed(recent[-6:]):
                prev_res = prev.result or {}
                if prev.finding_type == "PACE_DEVIATION" and (
                    prev_res.get("clean_air") is False
                    or prev_res.get("clean_air_status") == CleanAirStatus.TRAFFIC_AFFECTED.value
                ):
                    conflicts.append("TRAFFIC_REENTRY_VS_PIT_WINDOW_CONFLICT")
                    break
            for prev in recent:
                prev_res = prev.result or {}
                if prev.finding_type == "PACE_DEVIATION" and self._finding_missing_telemetry(prev):
                    conflicts.append("MISSING_TELEMETRY_COVERAGE")
                if prev.finding_type == "PACE_DEVIATION" and (
                    prev_res.get("pace_delta_sec") is None
                    or prev_res.get("baseline_status") == "INITIALIZING"
                ):
                    conflicts.append("PACE_BASELINE_INITIALIZING")

            lap_states: dict[Any, set[bool]] = {}
            for prev in recent:
                if prev.finding_type == "PACE_DEVIATION":
                    lp = (prev.result or {}).get("lap_number")
                    ca = (prev.result or {}).get("clean_air")
                    if lp is not None and isinstance(ca, bool):
                        lap_states.setdefault(lp, set()).add(ca)
            if any(len(vals) > 1 for vals in lap_states.values()):
                conflicts.append("CONFLICTING_DOMAIN_EVIDENCE")

            deg = res.get("degradation_estimate")
            sc = res.get("sample_count")
            if isinstance(sc, int) and sc < 5:
                conflicts.append("INSUFFICIENT_SAMPLE_SIZE")
            elif isinstance(deg, dict) and isinstance(deg.get("sample_laps"), int):
                if deg["sample_laps"] < 5 and str(deg.get("calibration_status", "")) in {
                    "PRIOR_UNMEASURED",
                    "INSUFFICIENT_SAMPLES",
                }:
                    conflicts.append("INSUFFICIENT_SAMPLE_SIZE")

            cal = str(res.get("calibration_status", "PRIOR_UNMEASURED"))
            if "PRIOR_UNMEASURED" in cal and "EMPIRICAL" not in cal:
                conflicts.append("UNCALIBRATED_PRIOR_BASELINE")
            if current_finding.assessment_status == FindingStatus.PROVISIONAL and "EMPIRICAL" not in cal:
                conflicts.append("UPSTREAM_PROVISIONAL_EVIDENCE")
        elif current_finding.finding_type in {"PACE_DEVIATION", "VEHICLE_ANOMALY"}:
            clean_air_status = res.get("clean_air_status")
            clean_air_flag = res.get("clean_air")
            if clean_air_status == CleanAirStatus.CLEAN_AIR_UNKNOWN.value or (
                clean_air_status is None and clean_air_flag is None and not res.get("neutralisation_active")
            ):
                conflicts.append("CLEAN_AIR_UNKNOWN_MISSING_INTERVAL")
            bstatus = str(res.get("baseline_status", ""))
            if res.get("pace_delta_sec") is None or bstatus == "INITIALIZING":
                conflicts.append("PACE_BASELINE_INITIALIZING")
            sc = res.get("sample_count", res.get("baseline_sample_count"))
            if isinstance(sc, int) and sc < 5:
                conflicts.append("INSUFFICIENT_SAMPLE_SIZE")

        return list(dict.fromkeys(conflicts))

    def _has_positive_corroboration(self, session_id: str, driver_number: int, current_finding: Finding) -> tuple[bool, bool]:
        """Returns (sia_healthy_finalized, independent_corroboration). Missing SIA is never positive evidence."""
        drv_alert = self._integrity_alerts.get((session_id, driver_number))
        sess_alert = self._integrity_alerts.get((session_id, -1))
        alerts = [a for a in (drv_alert, sess_alert) if a is not None]
        if any(str(a.get("verdict", "")).upper() != "HEALTHY" for a in alerts):
            sia_healthy_finalized = False
        else:
            sia_healthy_finalized = any(a.get("verdict") == "HEALTHY" and bool(a.get("finalized", False)) for a in alerts)

        res = current_finding.result or {}
        if res.get("independently_corroborated") is True:
            return sia_healthy_finalized, True

        recent = list(self._buf(session_id, driver_number))
        has_calibrated_pace = any(
            f.finding_type == "PACE_DEVIATION"
            and not self._finding_missing_telemetry(f)
            and (f.result or {}).get("baseline_status") == "STINT_ROLLING_CALIBRATED"
            and (f.result or {}).get("clean_air") is not None
            and ((f.result or {}).get("baseline_sample_count") or (f.uncertainty or {}).get("sample_count") or 0) >= 2
            for f in recent
        )
        distinct_calibrated_agents = len({
            f.agent_id
            for f in recent
            if f.assessment_status in {FindingStatus.CONFIRMED, FindingStatus.OBSERVED}
            and not self._finding_missing_telemetry(f)
        })
        return sia_healthy_finalized, bool(has_calibrated_pace or distinct_calibrated_agents >= 2)

    def _classify_v2_status(
        self,
        session_id: str,
        driver_number: int,
        strat_finding: Finding,
        conflicts: list[str],
    ) -> tuple[FindingStatus, str, str]:
        """Strict epistemic status policy: missing SIA alert never grants confirmation."""
        if any(
            c.startswith(("SIA_INTEGRITY_DEGRADED", "SIA_INTEGRITY_VOID", "SIA_INTEGRITY_QUARANTINED"))
            or c == "CONTRADICTING_EVIDENCE_REJECTED"
            for c in conflicts
        ):
            reason = next(
                (c for c in conflicts if c.startswith("SIA_INTEGRITY_") or c == "CONTRADICTING_EVIDENCE_REJECTED"),
                "INTEGRITY_OR_CONTRADICTION",
            )
            return FindingStatus.REJECTED, "REJECTED_INTEGRITY_BREACH", f"Blocked/rejected due to {reason}"

        blocking_integrity = any(c.startswith(("SIA_INTEGRITY_", "SIA_EVIDENCE_NOT_FINALIZED")) for c in conflicts)
        cal_status = str((strat_finding.result or {}).get("calibration_status", "PRIOR_UNMEASURED"))
        cal_empirical = "EMPIRICAL" in cal_status and "PRIOR_UNMEASURED" not in cal_status
        sia_healthy_finalized, indep_corrob = self._has_positive_corroboration(session_id, driver_number, strat_finding)

        if not conflicts and cal_empirical and (sia_healthy_finalized or indep_corrob):
            basis = "FINALIZED_SIA_AND_EMPIRICAL" if sia_healthy_finalized else "EMPIRICAL_CORROBORATED"
            return FindingStatus.CONFIRMED, "PIT_WINDOW_FAVOURABLE", basis

        if blocking_integrity:
            return FindingStatus.PROVISIONAL, "HOLD_VERIFY_INTEGRITY", "AWAITING_HEALTHY_FINALIZED_SIA"
        if any(c in {"TRAFFIC_REENTRY_VS_PIT_WINDOW_CONFLICT", "CONFLICTING_DOMAIN_EVIDENCE"} for c in conflicts):
            return FindingStatus.PROVISIONAL, "EVALUATE_WITH_TRAFFIC_RISK", "CONFLICTING_DOMAIN_SIGNALS"
        if not cal_empirical:
            return FindingStatus.PROVISIONAL, "ADVISORY_PRIOR_UNMEASURED", "UNCALIBRATED_PRIOR_BASELINE"
        return FindingStatus.PROVISIONAL, "AWAITING_CORROBORATION", "MISSING_SIA_AND_TELEMETRY_CORROBORATION"

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
        if (
            finding.finding_type in {"INTEGRITY_ASSESSMENT", "INTEGRITY_VERDICT", "INTEGRITY_ALERT", "SIA_VERDICT"}
            or finding.agent_id == "agent-06-integrity"
        ):
            raw_verdict = (
                finding.result.get("integrity_state")
                or finding.result.get("verdict")
                or finding.result.get("status")
                or "UNKNOWN"
            )
            verdict = str(raw_verdict).upper()
            finalized_flag = finding.result.get("finalized")
            finality_status = finding.result.get("finality_status")
            if finalized_flag is not None:
                is_finalized = bool(finalized_flag)
            elif finality_status is not None:
                is_finalized = str(finality_status).upper() in {"FINAL", "FINALIZED", "CLOSED"}
            else:
                is_finalized = verdict == "HEALTHY"
            target_key = (session_id, driver_num if driver_num is not None else -1)
            self._integrity_alerts[target_key] = {
                "verdict": verdict,
                "finalized": is_finalized,
                "reason": str(
                    finding.result.get("reason")
                    or finding.result.get("diagnosis")
                    or finding.result.get("primary_witness")
                    or verdict
                ),
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
        if assessment.supersedes_assessment_id:
            for prev in self.assessment_history:
                if (
                    prev.assessment_id == assessment.supersedes_assessment_id
                    and prev.status not in {FindingStatus.REJECTED, FindingStatus.WITHDRAWN, FindingStatus.SUPERSEDED}
                ):
                    prev.status = FindingStatus.SUPERSEDED
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
        resolved_status, recommendation, confirmation_basis = self._classify_v2_status(
            strat_finding.session_id, driver_number, strat_finding, conflicts
        )

        age_phrase = f"{stint_age} laps on {compound} target" if stint_age is not None else f"stint age unmeasured, target compound {compound}"
        headline = f"{driver_label} pit window opens under {mode} neutralisation"
        narrative = (
            f"{mode} neutralisation yields {saving:.1f}s (+/- {unc:.1f}s) pit-stop delta ({cal_status}). "
            f"Current state: {age_phrase}; projected re-entry: {reentry}. Status: {resolved_status.value}."
        )

        all_evidence = list(strat_finding.evidence_refs)
        if v1:
            all_evidence.extend(v1.evidence_refs)
            all_evidence.append(v1.assessment_id)

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
                    status=resolved_status,
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
                "confirmation_basis": confirmation_basis,
                "uncertainty_sec": unc,
                "tactical_recommendation": recommendation,
                "conflicts": conflicts,
            },
            status=resolved_status,
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
        clean_air_status = r.get("clean_air_status") or (
            CleanAirStatus.CLEAN_AIR_CONFIRMED.value
            if clean_air is True
            else (CleanAirStatus.TRAFFIC_AFFECTED.value if clean_air is False else CleanAirStatus.CLEAN_AIR_UNKNOWN.value)
        )

        if any(
            c.startswith(("SIA_INTEGRITY_DEGRADED", "SIA_INTEGRITY_VOID", "SIA_INTEGRITY_QUARANTINED"))
            or c == "CONTRADICTING_EVIDENCE_REJECTED"
            for c in conflicts
        ):
            pace_status = FindingStatus.REJECTED
            rec = "REJECTED_INTEGRITY_BREACH"
        elif (
            finding.interpretation == Interpretation.OBSERVED
            and not conflicts
            and clean_air_status != CleanAirStatus.CLEAN_AIR_UNKNOWN.value
        ):
            pace_status = FindingStatus.OBSERVED
            rec = "OBSERVED_MONITOR_GAP"
        elif (
            not conflicts
            and bstatus == "STINT_ROLLING_CALIBRATED"
            and self._has_positive_corroboration(finding.session_id, driver_number, finding)[0]
        ):
            pace_status = FindingStatus.CONFIRMED
            rec = "CONFIRMED_MONITOR_GAP"
        else:
            pace_status = FindingStatus.PROVISIONAL
            rec = "HOLD_VERIFY_INTEGRITY" if any(c.startswith("SIA_") for c in conflicts) else "MONITOR_GAP"

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
                    f"Clean air status: {clean_air_status}",
                ],
                inferred_effects=[
                    narrative,
                    f"Baseline calibration: {bstatus}",
                ],
                forecast=Forecast(
                    horizon_laps=2,
                    position_delta_range=(-1, 0) if in_traffic else (0, 0),
                    gap_delta_seconds_range=gap_range,
                    status=pace_status,
                ),
                alternatives=["Hold track position until gap ahead opens" if in_traffic else "Monitor clean-air lap trend"],
            ),
            supporting_finding_refs=[f.finding_id for f in self._buf(finding.session_id, driver_number)],
            data_coverage={
                "event_context": Completeness.COMPLETE,
                "strategy": Completeness.PARTIAL,
                "track_state": Completeness.COMPLETE,
                "vehicle_response": (
                    Completeness.MISSING
                    if self._finding_missing_telemetry(finding)
                    else (Completeness.COMPLETE if isinstance(pace_delta, (int, float)) and clean_air_status != CleanAirStatus.CLEAN_AIR_UNKNOWN.value else Completeness.PARTIAL)
                ),
            },
            uncertainty={
                "calibration_status": bstatus,
                "clean_air_status": clean_air_status,
                "uncertainty_sec": unc,
                "tactical_recommendation": rec,
                "conflicts": conflicts,
            },
            status=pace_status,
            supersedes_assessment_id=existing.assessment_id if existing else None,
            evidence_refs=list(dict.fromkeys(evidence)),
        )
        await self._emit_assessment(assessment, f"{finding.session_id}:{driver_number}")
