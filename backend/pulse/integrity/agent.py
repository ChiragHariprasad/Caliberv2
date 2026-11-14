"""IntegrityAgent (Agent 6): SIA Core v3 decision-scoped integrity evaluation.

Subscribes to all normalised PULSE event streams and feeds them into the
deterministic SIA integrity engine. Emits integrity findings and maintains
the hash-chained verdict history with bitemporal queries.

Architecture:
  - On each event: translate → admit atom → evaluate open decisions → emit findings
  - On tick (clock advance): re-evaluate all open decisions (catches stale evidence, silent feeds)
  - Exposes the full SIA engine for API queries (verdicts, history, chain verification)

The agent never reads a wall clock internally. All time is derived from the
event stream, making live and replay runs bit-for-bit comparable.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Ensure sia_core_v3 is importable
_SIA_ROOT = str(Path(__file__).resolve().parents[3] / "sia_core_v3")
if _SIA_ROOT not in sys.path:
    sys.path.insert(0, _SIA_ROOT)

from sia_core import (
    IntegrityEngine,
    OriginRegistry,
    IntegrityState,
    make_fact,
    explain as sia_explain,
    parse_instant,
    fmt_instant,
    sec_to_us,
    ScopeClass,
    ContractRejected,
)
from sia_core.evaluator import EngineConfig
from sia_core.verdict import Assessment as SIAAssessment

from pulse.agents.base import BaseAgent
from pulse.contracts import (
    EventEnvelope,
    Finding,
    FindingStatus,
    Interpretation,
    Subject,
    utc_now,
)
from pulse.integrity.bridge import (
    build_origin_registry,
    build_scope_for_contract,
    envelope_to_atom,
    extract_scope,
    map_event_to_roles,
    role_to_contract,
    sia_assessment_to_dict,
    DEFAULT_ORIGINS,
)
from pulse.integrity.contracts import load_contracts_for_session

logger = logging.getLogger("pulse.integrity.agent")


INTEGRITY_TOPIC = "pulse.agent.integrity.findings.v1"


class IntegrityAgent(BaseAgent):
    """Agent 6: Decision-scoped evidence integrity evaluation using SIA Core v3.

    Maintains a deterministic IntegrityEngine instance per session. Evidence
    atoms are admitted from normalised events, and integrity assessments are
    produced as hash-chained, bitemporally-indexed verdicts.
    """

    def __init__(
        self,
        bus=None,
        origins: dict[str, list[str]] | None = None,
        session_type: str = "RACE",
    ) -> None:
        super().__init__(
            agent_id="agent-06-integrity",
            name="SIA Integrity Engine",
            output_topic=INTEGRITY_TOPIC,
            bus=bus,
            model_version="3.0.0",
        )
        self._origins = origins or DEFAULT_ORIGINS
        self._session_type = session_type
        self._registry = build_origin_registry(self._origins)
        self._engine = IntegrityEngine(
            registry=self._registry,
            config=EngineConfig(auto_open=True),
        )
        self._session_id: str | None = None
        self._session_t0_admitted = False
        self._knowledge_time_us: int = 0
        self._contract_ids: list[str] = []

        # Register default contracts
        self._register_contracts(session_type)

    # ------------------------------------------------------------------
    # Contract management
    # ------------------------------------------------------------------

    def _register_contracts(self, session_type: str) -> None:
        """Register all contracts for the given session type."""
        contracts = load_contracts_for_session(session_type)
        self._contract_ids.clear()
        for cdata in contracts:
            try:
                c = self._engine.register_contract(cdata)
                self._contract_ids.append(c.contract_id)
                logger.info("Registered integrity contract: %s v%s", c.contract_id, c.version)
            except ContractRejected as exc:
                logger.error("Contract rejected: %s — %s", cdata.get("contract_id"), exc)
            except Exception as exc:
                logger.error("Failed to register contract %s: %s", cdata.get("contract_id"), exc)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset engine state for a new session."""
        self._engine = IntegrityEngine(
            registry=self._registry,
            config=EngineConfig(auto_open=True),
        )
        self._session_t0_admitted = False
        self._knowledge_time_us = 0
        self._contract_ids.clear()
        self._register_contracts(self._session_type)
        self.reset_metrics()
        logger.info("IntegrityAgent reset for new session.")

    def set_session_type(self, session_type: str) -> None:
        """Change session type and re-register contracts."""
        self._session_type = session_type
        self.reset()

    # ------------------------------------------------------------------
    # Time management
    # ------------------------------------------------------------------

    def _event_knowledge_time(self, envelope: EventEnvelope) -> str:
        """Derive a monotonically non-decreasing knowledge time from the event.

        Uses ingest_time_utc as the knowledge time (when the engine learned of it).
        Ensures monotonicity by taking the max with previous knowledge time.
        """
        kt_us = parse_instant(envelope.time.ingest_time_utc.isoformat())
        kt_us = max(kt_us, self._knowledge_time_us)
        self._knowledge_time_us = kt_us
        return fmt_instant(kt_us)

    def _event_eval_instant(self, envelope: EventEnvelope) -> str:
        """Derive the evaluation instant K from the event.

        Uses ingest_time_utc as K (the moment we evaluate).
        """
        kt_us = parse_instant(envelope.time.ingest_time_utc.isoformat())
        kt_us = max(kt_us, self._knowledge_time_us)
        return fmt_instant(kt_us)

    # ------------------------------------------------------------------
    # Reference fact management
    # ------------------------------------------------------------------

    def _maybe_admit_session_t0(self, envelope: EventEnvelope) -> None:
        """Admit session_t0 reference fact on first event or SESSION_STARTED."""
        if self._session_t0_admitted:
            return

        et = envelope.event_type.upper()
        if et == "SESSION_STARTED" or not self._session_t0_admitted:
            scope = {"session_id": str(envelope.session.session_id or envelope.run.session_instance_id)}
            t0_us = parse_instant(envelope.time.event_time_utc.isoformat())
            kt = self._event_knowledge_time(envelope)
            try:
                fact = make_fact(
                    fact_type="session_t0",
                    scope=scope,
                    value=t0_us,
                    origins=["PULSE_PIPELINE"],
                    unit="us",
                )
                adm = self._engine.admit_fact(fact, kt)
                if adm.accepted:
                    self._session_t0_admitted = True
                    self._session_id = scope["session_id"]
                    logger.info("Admitted session_t0 fact for session %s", scope["session_id"])
            except Exception as exc:
                logger.warning("Failed to admit session_t0: %s", exc)

    def _maybe_admit_lap_start(self, envelope: EventEnvelope) -> None:
        """Admit lap_start reference fact when a LAP_COMPLETED event arrives."""
        if envelope.event_type.upper() not in ("LAP_COMPLETED", "DRIVER_LAP_DATA"):
            return

        scope = extract_scope(envelope)
        if "lap_number" not in scope or "driver_id" not in scope or "session_id" not in scope:
            return

        # lap_start time = event_time (start of the lap that just completed)
        p = envelope.payload
        lap_time_s = None
        for k in ("lap_time_seconds", "lap_time", "last_lap_seconds", "duration_s"):
            if k in p and p[k] is not None:
                lap_time_s = float(p[k])
                break

        if lap_time_s is None:
            return

        # The lap started at (event_time - lap_duration)
        event_us = parse_instant(envelope.time.event_time_utc.isoformat())
        lap_start_us = event_us - sec_to_us(lap_time_s)

        # Express as session-elapsed if possible
        if envelope.time.session_elapsed_ms is not None:
            elapsed_us = envelope.time.session_elapsed_ms * 1000
            start_elapsed = elapsed_us - sec_to_us(lap_time_s)
            value = max(0, start_elapsed)
        else:
            value = lap_start_us

        kt = self._event_knowledge_time(envelope)
        try:
            fact = make_fact(
                fact_type="lap_start",
                scope=scope,
                value=int(value),
                origins=["PULSE_PIPELINE"],
                unit="us",
            )
            self._engine.admit_fact(fact, kt)
        except Exception as exc:
            logger.debug("Failed to admit lap_start fact: %s", exc)

    # ------------------------------------------------------------------
    # Core event processing
    # ------------------------------------------------------------------

    async def on_event(self, topic: str, key: str, event: EventEnvelope) -> None:
        """Process an incoming normalised event through the integrity engine."""
        t0 = time.monotonic()
        self.record_input(event.event_id, eligible=True, run_id=event.run.run_id)

        try:
            # Admit reference facts
            self._maybe_admit_session_t0(event)
            self._maybe_admit_lap_start(event)

            # Map event to roles
            roles = map_event_to_roles(event.event_type)
            if not roles:
                self.record_outcome("FILTERED", (time.monotonic() - t0) * 1000)
                return

            kt = self._event_knowledge_time(event)
            K = self._event_eval_instant(event)
            atoms_admitted = 0

            for role_id in roles:
                atom = envelope_to_atom(event, role_id)
                if atom is None:
                    continue

                # Admit the atom
                adm = self._engine.admit_atom(atom, kt)
                if adm.accepted:
                    atoms_admitted += 1

            if atoms_admitted == 0:
                self.record_outcome("NO_FINDING", (time.monotonic() - t0) * 1000)
                return

            # Evaluate all open decisions (tick)
            assessments = self._engine.tick(K)

            # Emit findings for each assessment
            for assessment in assessments:
                await self._emit_integrity_finding(assessment, event)

            latency = (time.monotonic() - t0) * 1000
            if assessments:
                self.record_outcome("FINDING_EMITTED", latency)
            else:
                self.record_outcome("NO_FINDING", latency)

        except Exception as exc:
            logger.error("IntegrityAgent error processing event %s: %s", event.event_id, exc, exc_info=True)
            self.record_outcome("ERROR", (time.monotonic() - t0) * 1000)

    # ------------------------------------------------------------------
    # Finding emission
    # ------------------------------------------------------------------

    async def _emit_integrity_finding(self, assessment: SIAAssessment, trigger_event: EventEnvelope) -> None:
        """Convert a SIA Assessment into a PULSE Finding and emit it."""
        d = sia_assessment_to_dict(assessment)
        state = d.get("integrity_state", "UNKNOWN")

        finding = Finding(
            finding_id=f"integrity-{uuid4().hex[:12]}",
            finding_version=assessment.revision_number,
            agent_id=self.agent_id,
            finding_type="INTEGRITY_ASSESSMENT",
            session_id=trigger_event.session.session_id or trigger_event.run.session_instance_id,
            run_id=trigger_event.run.run_id,
            subject=trigger_event.subject,
            trigger_event_id=trigger_event.event_id,
            as_of_event_time=trigger_event.time.event_time_utc,
            interpretation=Interpretation.DERIVED,
            result={
                "integrity_state": state,
                "decision_instance_id": d.get("decision_instance_id"),
                "contract_id": (d.get("contract") or {}).get("id"),
                "resolution_maturity": d.get("resolution_maturity"),
                "finality_status": d.get("finality_status"),
                "verdict_hash": d.get("verdict_hash"),
                "record_hash": d.get("record_hash"),
                "primary_witness": d.get("primary_binding_witness"),
                "witness_count": len(d.get("witnesses") or []),
                "envelope": d.get("envelope"),
                "scope": d.get("scope"),
            },
            uncertainty={
                "integrity_state": state,
                "decision_maturity": d.get("decision_maturity"),
                "revision_number": assessment.revision_number,
                "limitations": d.get("limitations") or [],
            },
            evidence_refs=[trigger_event.event_id],
            model_version=self.model_version,
            assessment_status=(
                FindingStatus.CONFIRMED if state == "HEALTHY"
                else FindingStatus.UNRESOLVED if state in ("SUSPECT", "UNKNOWN")
                else FindingStatus.PROVISIONAL
            ),
            reason_codes=[w.get("code", "") for w in (d.get("witnesses") or [])[:5]],
        )

        await self.emit_finding(finding)

    def initialize_session_grid(self, session_id: str, drivers: list[Any]) -> None:
        """Pre-opens decisions across active contracts for all drivers in the session grid."""
        self._session_id = session_id
        now_us = self._knowledge_time_us if self._knowledge_time_us > 0 else 0
        K = fmt_instant(now_us)

        # Weather contract (SESSION scope)
        if "weather_observation" in self._engine.contracts:
            try:
                self._engine.open_decision("weather_observation", {"session_id": session_id}, K, auto=True)
            except Exception as e:
                logger.debug("Failed opening weather decision: %s", e)

        driver_nums = []
        for d in drivers:
            if isinstance(d, dict):
                dn = d.get("number") or d.get("driver_number")
            else:
                dn = d
            if dn is not None:
                driver_nums.append(str(dn))

        if not driver_nums:
            driver_nums = [str(n) for n in [1, 4, 16, 44, 81, 63, 55, 11, 14, 23, 18, 10, 31, 22, 27, 20, 77, 24, 2, 21]]

        for dn_str in driver_nums:
            # lap_time contract (DRIVER_LAP scope)
            if "lap_time" in self._engine.contracts:
                try:
                    self._engine.open_decision("lap_time", {"session_id": session_id, "driver_id": dn_str, "lap_number": "1"}, K, auto=True)
                except Exception as e:
                    logger.debug("Failed opening lap_time for driver %s: %s", dn_str, e)

            # driver_position contract (DRIVER_LAP scope)
            if "driver_position" in self._engine.contracts:
                try:
                    self._engine.open_decision("driver_position", {"session_id": session_id, "driver_id": dn_str, "lap_number": "1"}, K, auto=True)
                except Exception as e:
                    logger.debug("Failed opening driver_position for driver %s: %s", dn_str, e)

            # sector_time contract (SECTOR scope)
            if "sector_time" in self._engine.contracts:
                try:
                    self._engine.open_decision("sector_time", {"session_id": session_id, "driver_id": dn_str, "lap_number": "1", "sector_number": "1"}, K, auto=True)
                except Exception as e:
                    logger.debug("Failed opening sector_time for driver %s: %s", dn_str, e)

            # pit_speed contract (SECTOR scope)
            if "pit_speed" in self._engine.contracts:
                try:
                    self._engine.open_decision("pit_speed", {"session_id": session_id, "driver_id": dn_str, "lap_number": "1", "sector_number": "1"}, K, auto=True)
                except Exception as e:
                    logger.debug("Failed opening pit_speed for driver %s: %s", dn_str, e)

        # Initial deterministic evaluation tick
        try:
            self._engine.tick(K)
        except Exception as e:
            logger.debug("Initial grid tick: %s", e)

    def _find_instance_id(self, instance_id: str) -> str | None:
        """Finds a matching decision instance ID, supporting aliases and prefix formats."""
        if instance_id in self._engine.instances:
            return instance_id

        # Clean prefix and check direct match
        clean = instance_id.replace("dec-", "").replace("dec_", "")
        if clean in self._engine.instances:
            return clean

        # Attempt to match by contract and driver
        matched_cid = None
        for cid_candidate in self._engine.contracts:
            if cid_candidate in clean or cid_candidate.replace("_", "-") in clean:
                matched_cid = cid_candidate
                break

        parts = clean.split("-")
        cid = matched_cid or parts[0]
        dnum = None
        for p in parts[1:]:
            if p.startswith("d") and p[1:].isdigit():
                dnum = p[1:]
                break
            elif p.isdigit():
                dnum = p
                break

        for iid, inst in self._engine.instances.items():
            scope_map = inst.scope_dict if hasattr(inst, "scope_dict") else dict(inst.scope)
            if inst.contract_id == cid or cid in inst.contract_id:
                if dnum is not None:
                    if str(scope_map.get("driver_id")) == str(dnum):
                        return iid
                else:
                    return iid
        return None

    def _ensure_decision_instance(self, instance_id: str) -> str | None:
        """Dynamically ensures a decision instance exists for on-demand inspection."""
        clean = instance_id.replace("dec-", "").replace("dec_", "")
        matched_cid = None
        for cid_candidate in self._engine.contracts:
            if cid_candidate in clean or cid_candidate.replace("_", "-") in clean:
                matched_cid = cid_candidate
                break

        parts = clean.split("-")
        cid = matched_cid or parts[0]
        dnum = "1"
        for p in parts[1:]:
            if p.startswith("d") and p[1:].isdigit():
                dnum = p[1:]
                break
            elif p.isdigit():
                dnum = p
                break

        sid = self._session_id or "f1-session"
        now_us = self._knowledge_time_us if self._knowledge_time_us > 0 else 0
        K = fmt_instant(now_us)

        for avail_cid in self._engine.contracts:
            if avail_cid == cid or cid in avail_cid:
                c = self._engine.contracts[avail_cid]
                if c.scope_class == ScopeClass.SESSION:
                    scope = {"session_id": sid}
                elif c.scope_class in (ScopeClass.DRIVER_SESSION, ScopeClass.DRIVER_LAP):
                    scope = {"session_id": sid, "driver_id": str(dnum), "lap_number": "1"}
                else:
                    scope = {"session_id": sid, "driver_id": str(dnum), "lap_number": "1", "sector_number": "1"}
                try:
                    iid = self._engine.open_decision(avail_cid, scope, K, auto=True)
                    try:
                        self._engine.evaluate(iid, K)
                    except Exception:
                        pass
                    return iid
                except Exception as e:
                    logger.debug("Failed dynamic decision open: %s", e)
        return None

    # ------------------------------------------------------------------
    # Public query API (used by the router)
    # ------------------------------------------------------------------

    @property
    def engine(self) -> IntegrityEngine:
        """Direct access to the SIA IntegrityEngine for API queries."""
        return self._engine

    def get_all_verdicts(self) -> list[dict[str, Any]]:
        """Return the latest verdict for every tracked decision instance."""
        results = []
        for iid in sorted(self._engine.instances):
            chain = self._engine.history(iid)
            if chain:
                latest = chain[-1]
                results.append(sia_assessment_to_dict(latest))
        return results

    def get_verdict(self, instance_id: str) -> dict[str, Any] | None:
        """Return the latest verdict for a specific decision instance."""
        real_iid = self._find_instance_id(instance_id)
        if real_iid:
            chain = self._engine.history(real_iid)
            if chain:
                return sia_assessment_to_dict(chain[-1])

        opened_iid = self._ensure_decision_instance(instance_id)
        if opened_iid:
            K = fmt_instant(max(0, self._knowledge_time_us))
            try:
                self._engine.tick(K)
            except Exception:
                pass
            chain = self._engine.history(opened_iid)
            if chain:
                return sia_assessment_to_dict(chain[-1])
        return None

    def get_verdict_history(self, instance_id: str) -> list[dict[str, Any]]:
        """Return the full revision history for a decision instance."""
        real_iid = self._find_instance_id(instance_id)
        if not real_iid:
            real_iid = self._ensure_decision_instance(instance_id)
        target_id = real_iid or instance_id
        chain = self._engine.history(target_id)
        if not chain:
            now_us = self._knowledge_time_us if self._knowledge_time_us > 0 else 0
            K = fmt_instant(now_us)
            try:
                self._engine.evaluate(target_id, K)
                chain = self._engine.history(target_id)
            except Exception:
                pass
        return [sia_assessment_to_dict(a) for a in chain]

    def get_verdict_as_of(self, instance_id: str, knowledge_time: str) -> dict[str, Any] | None:
        """Bitemporal query: what did we conclude as known at K?"""
        real_iid = self._find_instance_id(instance_id)
        if not real_iid:
            real_iid = self._ensure_decision_instance(instance_id)
        target_id = real_iid or instance_id
        try:
            a = self._engine.as_of(target_id, knowledge_time)
        except Exception:
            chain = self._engine.history(target_id)
            a = chain[-1] if chain else None
        if a is None:
            chain = self._engine.history(target_id)
            if not chain:
                now_us = self._knowledge_time_us if self._knowledge_time_us > 0 else 0
                K = fmt_instant(now_us)
                try:
                    self._engine.evaluate(target_id, K)
                    chain = self._engine.history(target_id)
                    a = chain[-1] if chain else None
                except Exception:
                    pass
            else:
                a = chain[-1]
        if a is None:
            return None
        return sia_assessment_to_dict(a)

    def verify_chains(self) -> dict[str, str]:
        """Verify hash-chain integrity for all decision instances."""
        return self._engine.verify()

    def explain_verdict(self, instance_id: str) -> str | None:
        """Generate a template-based explanation for the latest verdict."""
        real_iid = self._find_instance_id(instance_id)
        if not real_iid:
            real_iid = self._ensure_decision_instance(instance_id)
        target_id = real_iid or instance_id
        chain = self._engine.history(target_id)
        if not chain:
            now_us = self._knowledge_time_us if self._knowledge_time_us > 0 else 0
            K = fmt_instant(now_us)
            try:
                self._engine.evaluate(target_id, K)
                chain = self._engine.history(target_id)
            except Exception:
                pass
        if not chain:
            return None
        return sia_explain(chain[-1])

    def get_decisions(self) -> list[dict[str, Any]]:
        """Return metadata for all tracked decision instances."""
        results = []
        for iid, inst in sorted(self._engine.instances.items()):
            sealed = iid in self._engine._sealed
            chain = self._engine.history(iid)
            results.append({
                "instance_id": iid,
                "contract_id": inst.contract_id,
                "scope": dict(inst.scope),
                "opens_at": fmt_instant(inst.opens_at),
                "auto": inst.auto,
                "sealed": sealed,
                "revision_count": len(chain),
                "latest_state": sia_assessment_to_dict(chain[-1]).get("integrity_state") if chain else None,
            })
        return results

    def get_contracts(self) -> list[dict[str, Any]]:
        """Return registered contracts with metadata."""
        return [
            {
                "contract_id": c.contract_id,
                "version": c.version,
                "epoch": c.epoch,
                "decision_type": c.decision_type,
                "scope_class": c.scope_class.value,
                "formula": c.formula_str,
                "role_count": len(c.roles),
                "constraint_count": len(c.constraints),
                "definition_hash": c.definition_hash,
            }
            for c in self._engine.contracts.values()
        ]

    def get_ledger_stats(self) -> dict[str, Any]:
        """Return ledger statistics."""
        counts = self._engine.ledger.counts()
        return {
            **counts,
            "clock": fmt_instant(self._engine.ledger.clock) if self._engine.ledger.clock > -(1 << 62) else None,
            "finality_violations": self._engine.finality_violations,
            "contract_history": self._engine.contract_history,
        }

    def get_summary(self) -> dict[str, Any]:
        """Return a high-level integrity summary across all decisions."""
        verdicts = self.get_all_verdicts()
        state_counts = {"HEALTHY": 0, "SUSPECT": 0, "UNKNOWN": 0, "DEGRADED": 0}
        for v in verdicts:
            st = v.get("integrity_state", "UNKNOWN")
            state_counts[st] = state_counts.get(st, 0) + 1

        overall = "HEALTHY"
        if state_counts["DEGRADED"] > 0:
            overall = "DEGRADED"
        elif state_counts["SUSPECT"] > 0:
            overall = "SUSPECT"
        elif state_counts["UNKNOWN"] > 0:
            overall = "UNKNOWN"

        return {
            "overall_state": overall,
            "decision_count": len(verdicts),
            "state_distribution": state_counts,
            "contract_count": len(self._engine.contracts),
            "ledger": self._engine.ledger.counts(),
            "finality_violations": len(self._engine.finality_violations),
            "chain_verified": all(v == "OK" for v in self.verify_chains().values()) if verdicts else True,
        }

