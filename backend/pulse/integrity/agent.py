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
    SIAWALStore,
    make_atom,
    make_fact,
    make_guard,
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
    quality_grade,
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
        wal_path: str | Path | None = None,
        session_id: str = "default",
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
        self._wal_path = Path(wal_path) if wal_path else None
        self._wal: SIAWALStore | None = (
            SIAWALStore(self._wal_path, session_id=session_id) if self._wal_path else None
        )
        self._registry = build_origin_registry(self._origins)
        self._engine = IntegrityEngine(
            registry=self._registry,
            config=EngineConfig(auto_open=True),
            wal=self._wal,
        )
        self._session_id: str | None = session_id if session_id != "default" else None
        self._session_t0_admitted = False
        self._session_t0_official = False
        self._session_t0_fact_id: str | None = None
        self._session_t0_value: int | None = None
        self._knowledge_time_us: int = 0
        self._contract_ids: list[str] = []
        self._last_emitted_sigs: dict[str, tuple[str, int]] = {}
        self._cached_chain_rev_sig: int = -1
        self._cached_chain_verified: bool = True
        self._verified_chain_lengths: dict[str, int] = {}
        self._last_pos_state: dict[tuple[str, int, int], tuple[Any, str | None, int]] = {}

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

    def set_session_id(self, session_id: str) -> None:
        """Bind active session ID on both agent state and SQLite WAL partition."""
        self._session_id = session_id
        if self._wal is not None:
            self._wal.session_id = session_id

    def reset(self) -> None:
        """Reset engine state cleanly for a new session or replay run."""
        if self._wal is not None:
            if getattr(self._wal, "is_closed", False):
                self._wal = None
            else:
                self._wal.clear_session()
        self._engine = IntegrityEngine(
            registry=self._registry,
            config=EngineConfig(auto_open=True),
            wal=self._wal,
        )
        self._session_t0_admitted = False
        self._session_t0_official = False
        self._session_t0_fact_id = None
        self._session_t0_value = None
        self._knowledge_time_us = 0
        self._contract_ids.clear()
        self._last_emitted_sigs.clear()
        self._cached_chain_rev_sig = -1
        self._cached_chain_verified = True
        self._verified_chain_lengths.clear()
        self._last_pos_state.clear()
        self._register_contracts(self._session_type)
        self.reset_metrics()
        logger.info("IntegrityAgent reset for new session.")

    def restore_from_wal(self) -> bool:
        """Recover ledger, decisions, quarantine log, and hash-chains from SQLite WAL if present."""
        if self._wal is None:
            return False
        restored = self._wal.load_engine(registry=self._registry, config=EngineConfig(auto_open=True))
        counts = restored.ledger.counts()
        if restored.instances or counts.get("atoms", 0) > 0 or counts.get("facts", 0) > 0:
            restored.wal = self._wal
            self._engine = restored
            self._contract_ids = list(restored.contracts.keys())
            if restored.ledger.clock > 0:
                self._knowledge_time_us = restored.ledger.clock
            self._last_emitted_sigs.clear()
            for did in restored.index.decisions():
                head = restored.index.head(did)
                if head is not None:
                    self._last_emitted_sigs[did] = (head.record_hash, head.revision_number)
            t0_facts = restored.ledger.facts("session_t0")
            if t0_facts:
                last_t0 = t0_facts[-1].fact
                self._session_t0_admitted = True
                self._session_t0_fact_id = last_t0.fact_id
                self._session_t0_value = int(last_t0.value) if isinstance(last_t0.value, (int, float)) else None
                self._session_t0_official = not (last_t0.note or "").lower().startswith("provisional")
            else:
                self._session_t0_admitted = False
                self._session_t0_official = False
                self._session_t0_fact_id = None
                self._session_t0_value = None
            self._cached_chain_rev_sig = -1
            self._verified_chain_lengths.clear()
            self._last_pos_state.clear()
            return True
        return False

    def close(self) -> None:
        """Close and detach any SQLite WAL handle bound to this agent."""
        if self._wal is not None:
            try:
                self._wal.close()
            finally:
                self._wal = None
                self._engine.wal = None

    def set_wal_paused(self, paused: bool) -> None:
        """Pause per-event WAL commits during bulk historical seek rebuilds, syncing once when resumed."""
        if paused:
            self._engine.wal = None
        else:
            wal = self._wal if (self._wal is not None and not getattr(self._wal, "is_closed", False)) else None
            self._engine.wal = wal
            if wal is not None:
                wal.sync_engine(self._engine)

    def export_checkpoint(self) -> dict[str, Any]:
        """Export full IntegrityAgent + SIA Core v3 state for keyframe replay checkpoints."""
        return {
            "engine_blob": self._engine.export_state(),
            "session_id": self._session_id,
            "session_type": self._session_type,
            "session_t0_admitted": self._session_t0_admitted,
            "session_t0_official": self._session_t0_official,
            "session_t0_fact_id": self._session_t0_fact_id,
            "session_t0_value": self._session_t0_value,
            "knowledge_time_us": self._knowledge_time_us,
            "contract_ids": list(self._contract_ids),
            "last_emitted_sigs": dict(self._last_emitted_sigs),
            "cached_chain_rev_sig": self._cached_chain_rev_sig,
            "cached_chain_verified": self._cached_chain_verified,
            "verified_chain_lengths": dict(self._verified_chain_lengths),
            "last_pos_state": dict(self._last_pos_state),
            "metrics": {
                "run_id": self.run_id,
                "inputs_received": self.inputs_received,
                "eligible_inputs": self.eligible_inputs,
                "successfully_processed": self.successfully_processed,
                "emitted_findings": self.emitted_findings,
                "valid_no_finding_outcomes": self.valid_no_finding_outcomes,
                "insufficient_data_outcomes": self.insufficient_data_outcomes,
                "filtered_inputs": self.filtered_inputs,
                "failures": self.failures,
                "retries": self.retries,
                "last_processed_event_id": self.last_processed_event_id,
                "last_outcome": self.last_outcome,
                "output_finding_ids": list(self.output_finding_ids),
            },
        }

    def restore_checkpoint(self, ckpt: dict[str, Any]) -> None:
        """Restore IntegrityAgent + SIA Core v3 state from a keyframe checkpoint."""
        self._engine.restore_state(ckpt["engine_blob"])
        self._session_id = ckpt["session_id"]
        self._session_type = ckpt["session_type"]
        self._session_t0_admitted = ckpt["session_t0_admitted"]
        self._session_t0_official = ckpt.get("session_t0_official", ckpt["session_t0_admitted"])
        self._session_t0_fact_id = ckpt.get("session_t0_fact_id")
        self._session_t0_value = ckpt.get("session_t0_value")
        self._knowledge_time_us = ckpt["knowledge_time_us"]
        self._contract_ids = list(ckpt["contract_ids"])
        self._last_emitted_sigs = dict(ckpt["last_emitted_sigs"])
        self._cached_chain_rev_sig = ckpt["cached_chain_rev_sig"]
        self._cached_chain_verified = ckpt["cached_chain_verified"]
        self._verified_chain_lengths = dict(ckpt.get("verified_chain_lengths", {}))
        self._last_pos_state = dict(ckpt.get("last_pos_state", {}))
        m = ckpt["metrics"]
        self.run_id = m["run_id"]
        self.inputs_received = m["inputs_received"]
        self.eligible_inputs = m["eligible_inputs"]
        self.successfully_processed = m["successfully_processed"]
        self.emitted_findings = m["emitted_findings"]
        self.valid_no_finding_outcomes = m["valid_no_finding_outcomes"]
        self.insufficient_data_outcomes = m["insufficient_data_outcomes"]
        self.filtered_inputs = m["filtered_inputs"]
        self.failures = m["failures"]
        self.retries = m["retries"]
        self.last_processed_event_id = m["last_processed_event_id"]
        self.last_outcome = m["last_outcome"]
        self.output_finding_ids = list(m["output_finding_ids"])

    def set_session_type(self, session_type: str) -> None:
        """Change session type and re-register contracts."""
        self._session_type = session_type
        self.reset()

    # ------------------------------------------------------------------
    # Time management
    # ------------------------------------------------------------------

    def _event_knowledge_time(self, envelope: EventEnvelope) -> str:
        """Derive a monotonically non-decreasing knowledge time from the event.

        Historical/replay runs never leak host wall-clock defaults: if ``ingest_time_utc`` was omitted
        (defaulted at model construction) or sits days after a historical ``event_time_utc``, fall back
        deterministically to ``event_time_utc``. Explicit bitemporal delays during a session are preserved.
        """
        evt_us = parse_instant(envelope.time.event_time_utc.isoformat())
        fields_set = getattr(envelope.time, "model_fields_set", set())
        raw_ingest = envelope.time.ingest_time_utc
        if raw_ingest is None or (
            "ingest_time_utc" not in fields_set and parse_instant(raw_ingest.isoformat()) - evt_us > 86_400_000_000
        ):
            kt_us = evt_us
        else:
            ing_us = parse_instant(raw_ingest.isoformat())
            # In replay mode, also guard against stale/corrupted synthetic ingest wall-clocks years away
            if str(getattr(envelope.run.mode, "value", envelope.run.mode)).upper() == "REPLAY" and (ing_us - evt_us) > 86_400_000_000:
                kt_us = evt_us
            else:
                kt_us = ing_us
        kt_us = max(kt_us, self._knowledge_time_us)
        self._knowledge_time_us = kt_us
        return fmt_instant(kt_us)

    def _event_eval_instant(self, envelope: EventEnvelope) -> str:
        """Derive deterministic evaluation instant K aligned with active clock policy."""
        return self._event_knowledge_time(envelope)

    # ------------------------------------------------------------------
    # Reference fact management
    # ------------------------------------------------------------------

    def _maybe_admit_session_t0(self, envelope: EventEnvelope) -> None:
        """Admit session_t0 reference fact, letting authoritative SESSION_STARTED supersede provisional order."""
        et = envelope.event_type.upper()
        is_official = (et == "SESSION_STARTED")
        if self._session_t0_official or (self._session_t0_admitted and not is_official):
            return

        scope = {"session_id": str(envelope.session.session_id or envelope.run.session_instance_id)}
        t0_us = parse_instant(envelope.time.event_time_utc.isoformat())
        if is_official and self._session_t0_admitted and self._session_t0_value == t0_us:
            self._session_t0_official = True
            return

        kt = self._event_knowledge_time(envelope)
        supersedes_id = self._session_t0_fact_id if (is_official and self._session_t0_admitted) else None
        note = (
            "authoritative_session_started_superseding_provisional"
            if supersedes_id
            else ("official_session_started" if is_official else "provisional_first_event")
        )
        try:
            fact = make_fact(
                fact_type="session_t0",
                scope=scope,
                value=t0_us,
                origins=["PULSE_PIPELINE"],
                unit="us",
                supersedes=supersedes_id,
                note=note,
            )
            adm = self._engine.admit_fact(fact, kt)
            if adm.accepted:
                self._session_t0_admitted = True
                self._session_t0_fact_id = fact.fact_id
                self._session_t0_value = t0_us
                if is_official:
                    self._session_t0_official = True
                self._session_id = scope["session_id"]
                logger.info("Admitted session_t0 fact (%s) for session %s", note, scope["session_id"])
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
        for k in ("lap_time_seconds", "last_lap_seconds", "duration_s", "lap_time"):
            if k in p and p[k] is not None:
                val = p[k]
                if isinstance(val, (int, float)):
                    lap_time_s = float(val)
                    break
                elif isinstance(val, str):
                    try:
                        v = val.strip()
                        if ":" in v:
                            parts = v.split(":")
                            lap_time_s = float(parts[0]) * 60 + float(parts[1])
                        else:
                            lap_time_s = float(v)
                        break
                    except (ValueError, TypeError):
                        pass

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

            # Throttle redundant healthy 1Hz telemetry/position heartbeats to prevent O(N^2) revision growth,
            # while admitting immediately on lap transitions, rank/status changes, anomalies, or >=12s heartbeats.
            if set(roles) <= {"position_report", "vehicle_speed"}:
                p = event.payload or {}
                sid = str(event.session.session_id or event.run.session_instance_id or "")
                dn = event.subject.driver_number
                if dn is not None:
                    lap_raw = p.get("lap_number") or p.get("lap") or p.get("current_lap") or 1
                    try:
                        lap_i = int(lap_raw)
                    except (TypeError, ValueError):
                        lap_i = 1
                    pos_val = p.get("position")
                    status_val = str(p.get("status")) if p.get("status") is not None else None
                    spd_val = p.get("speed") if p.get("speed") is not None else p.get("speed_kph")
                    is_anomalous = (
                        quality_grade(event) != IntegrityState.HEALTHY
                        or (isinstance(pos_val, (int, float)) and not (1 <= int(pos_val) <= 24))
                        or (isinstance(spd_val, (int, float)) and (spd_val < 0 or spd_val > 375))
                    )
                    kt_us = parse_instant(kt)
                    state_key = (sid, int(dn), lap_i)
                    prev_state = self._last_pos_state.get(state_key)
                    if (
                        not is_anomalous
                        and prev_state is not None
                        and prev_state[0] == pos_val
                        and prev_state[1] == status_val
                        and (kt_us - prev_state[2]) < 12_000_000
                    ):
                        self.record_outcome("NO_FINDING", (time.monotonic() - t0) * 1000)
                        return
                    self._last_pos_state[state_key] = (pos_val, status_val, kt_us)

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

            # Emit findings only when a decision verdict revision/hash changed
            emitted_any = False
            for assessment in assessments:
                if await self._emit_integrity_finding(assessment, event):
                    emitted_any = True

            latency = (time.monotonic() - t0) * 1000
            if emitted_any:
                self.record_outcome("FINDING_EMITTED", latency)
            else:
                self.record_outcome("NO_FINDING", latency)

        except Exception as exc:
            logger.error("IntegrityAgent error processing event %s: %s", event.event_id, exc, exc_info=True)
            self.record_outcome("ERROR", (time.monotonic() - t0) * 1000)

    # ------------------------------------------------------------------
    # Finding emission
    # ------------------------------------------------------------------

    async def _emit_integrity_finding(self, assessment: SIAAssessment, trigger_event: EventEnvelope) -> bool:
        """Convert a SIA Assessment into a PULSE Finding and emit it when changed."""
        did = assessment.content.get("decision_instance_id")
        sig = (assessment.record_hash, assessment.revision_number)
        if did and self._last_emitted_sigs.get(did) == sig:
            return False
        if did:
            self._last_emitted_sigs[did] = sig
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
        return True

    def initialize_session_grid(self, session_id: str, drivers: list[Any]) -> None:
        """Configures active session ID and driver context.
        Decision instances are dynamically opened as evidence arrives (or on-demand during
        active replay), preventing false-alarm DEGRADED states caused by premature epoch-0
        slot deadline expirations."""
        self._session_id = session_id
        logger.info("IntegrityAgent session initialized for %s with %d drivers", session_id, len(drivers))

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
        if self._knowledge_time_us <= 0:
            return None
        now_us = self._knowledge_time_us
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
        """Return the latest verdict for every tracked decision instance (read-only, enriched)."""
        results = []
        for iid in sorted(self._engine.instances):
            chain = self._engine.history(iid)
            if chain:
                latest = chain[-1]
                cid = (latest.content.get("contract") or {}).get("id")
                c = self._engine.contracts.get(cid) if cid else None
                results.append(sia_assessment_to_dict(latest, ledger=self._engine.ledger, contract=c))
        return results

    def get_verdict(self, instance_id: str) -> dict[str, Any] | None:
        """Return the latest verdict for a specific decision instance without mutating ledger state."""
        real_iid = self._find_instance_id(instance_id)
        if real_iid:
            chain = self._engine.history(real_iid)
            if chain:
                latest = chain[-1]
                cid = (latest.content.get("contract") or {}).get("id")
                c = self._engine.contracts.get(cid) if cid else None
                return sia_assessment_to_dict(latest, ledger=self._engine.ledger, contract=c)
        return None

    def get_verdict_history(self, instance_id: str) -> list[dict[str, Any]]:
        """Return the full revision history for a decision instance (read-only)."""
        real_iid = self._find_instance_id(instance_id)
        if not real_iid:
            return []
        chain = self._engine.history(real_iid)
        out = []
        for a in chain:
            cid = (a.content.get("contract") or {}).get("id")
            c = self._engine.contracts.get(cid) if cid else None
            out.append(sia_assessment_to_dict(a, ledger=self._engine.ledger, contract=c))
        return out

    def get_verdict_as_of(self, instance_id: str, knowledge_time: str) -> dict[str, Any] | None:
        """Bitemporal query: what did we conclude as known at K? (strictly read-only)."""
        real_iid = self._find_instance_id(instance_id)
        if not real_iid:
            return None
        try:
            a = self._engine.as_of(real_iid, knowledge_time)
        except Exception:
            a = None
        if a is None:
            return None
        cid = (a.content.get("contract") or {}).get("id")
        c = self._engine.contracts.get(cid) if cid else None
        return sia_assessment_to_dict(a, ledger=self._engine.ledger, contract=c)

    def verify_chains(self) -> dict[str, str]:
        """Verify hash-chain integrity for all decision instances."""
        return self._engine.verify()

    def explain_verdict(self, instance_id: str) -> str | None:
        """Generate a template-based explanation for the latest verdict (read-only)."""
        real_iid = self._find_instance_id(instance_id)
        if not real_iid:
            return None
        chain = self._engine.history(real_iid)
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
        """Return registered contracts with full role and constraint metadata."""
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
                "roles": {
                    rname: {
                        "kind": r.kind.value if hasattr(r.kind, "value") else str(r.kind),
                        "scope_class": r.scope_class.value if hasattr(r.scope_class, "value") else str(r.scope_class),
                        "admissible_source_origins": list(getattr(r, "admissible_source_origins", ()) or ()),
                        "corroboration_mode": getattr(getattr(r, "corroboration", None), "mode", "INFORMATIONAL").value
                        if hasattr(getattr(getattr(r, "corroboration", None), "mode", None), "value")
                        else str(getattr(getattr(r, "corroboration", None), "mode", "INFORMATIONAL")),
                    }
                    for rname, r in c.roles.items()
                },
                "constraints": [
                    {
                        "id": getattr(cs, "id", None),
                        "kind": getattr(cs, "kind", None),
                        "operands": list(getattr(cs, "operands", ()) or ()),
                        "lo": (getattr(cs, "params", {}) or {}).get("lo"),
                        "hi": (getattr(cs, "params", {}) or {}).get("hi"),
                        "tolerance": (getattr(cs, "params", {}) or {}).get("tolerance", (getattr(cs, "params", {}) or {}).get("tol")),
                        "uncertainty": (getattr(cs, "params", {}) or {}).get("uncertainty"),
                    }
                    for cs in c.constraints
                ],
                "limitations": list(getattr(c, "limitations", ()) or ()),
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
        """Return a high-level integrity summary across all decisions without mutating ledger state."""
        state_counts = {"HEALTHY": 0, "SUSPECT": 0, "UNKNOWN": 0, "DEGRADED": 0}
        total_decisions = 0
        rev_sig = 0
        for iid in self._engine.instances:
            chain = self._engine.index._chains.get(iid)
            if not chain:
                continue
            total_decisions += 1
            rev_sig += len(chain)
            latest = chain[-1]
            st = latest.integrity_state.name if hasattr(latest.integrity_state, "name") else str(latest.integrity_state)
            state_counts[st] = state_counts.get(st, 0) + 1

        overall = "HEALTHY"
        if state_counts["DEGRADED"] > 0:
            overall = "DEGRADED"
        elif state_counts["SUSPECT"] > 0:
            overall = "SUSPECT"
        elif state_counts["UNKNOWN"] > 0:
            overall = "UNKNOWN"

        cache_sig = hash((total_decisions, rev_sig, len(self._engine.finality_violations)))
        if self._cached_chain_rev_sig != cache_sig:
            if hasattr(self._engine, "verify_incremental"):
                self._cached_chain_verified = self._engine.verify_incremental(self._verified_chain_lengths) if total_decisions else True
            else:
                self._cached_chain_verified = all(v == "OK" for v in self.verify_chains().values()) if total_decisions else True
            self._cached_chain_rev_sig = cache_sig

        return {
            "overall_state": overall,
            "decision_count": total_decisions,
            "state_distribution": state_counts,
            "contract_count": len(self._engine.contracts),
            "ledger": self._engine.ledger.counts(),
            "finality_violations": len(self._engine.finality_violations),
            "quarantined_count": len(self._engine.quarantined_items),
            "chain_verified": self._cached_chain_verified,
        }

    def run_lab_scenario(self, scenario_id: str) -> dict[str, Any]:
        """Execute an isolated SIA Core v3 LAB fault scenario without mutating active session state."""
        from pulse.integrity.contracts import get_contract_by_id

        reg = OriginRegistry({
            "PITWALL": ["F1_FOM_TIMING"],
            "TRACINGINSIGHTS": ["F1_FOM_TIMING"],
            "CAR_SENSOR": [],
            "TIMING_CONFIG": [],
            "SURVEY": [],
            "POP_MONITOR": [],
        })
        eng = IntegrityEngine(registry=reg, config=EngineConfig(auto_open=False))
        sid = scenario_id.lower().strip()
        if sid in {"monaco", "monaco_pit_bias", "pit_bias"}:
            eng.register_contract(get_contract_by_id("pit_speed"))
            sc = {"session_id": "lab-monaco-bias", "driver_id": "16", "lap_number": "1", "sector_number": "1"}
            iid = eng.open_decision("pit_speed", sc, "2026-05-24T13:00:00Z")
            eng.admit_atom(make_atom("timing_speed", 61.2, "2026-05-24T13:00:05Z", sc, ["PITWALL"], unit="kph"), "2026-05-24T13:00:06Z")
            eng.admit_atom(make_atom("vehicle_speed", 61.0, "2026-05-24T13:00:05.100Z", sc, ["CAR_SENSOR"], unit="kph"), "2026-05-24T13:00:06Z")
            eng.admit_atom(make_atom("configured_distance", 2692.0, "2026-05-24T13:00:01Z", sc, ["TIMING_CONFIG"], unit="cm"), "2026-05-24T13:00:06Z")
            sess_sc = {"session_id": "lab-monaco-bias"}
            eng.admit_fact(make_fact("track_geometry", sess_sc, 2615.0, ["SURVEY"], unit="cm"), "2026-05-24T13:00:06Z")
            eng.admit_fact(make_fact("calibration_bias", sess_sc, 0.001, ["POP_MONITOR"], unit="ratio"), "2026-05-24T13:00:06Z")
            res = eng.evaluate(iid, "2026-05-24T13:00:07Z")
            return {
                "scenario_id": "monaco_pit_bias",
                "regime": "LAB / ISOLATED_SCENARIO",
                "verdict": sia_assessment_to_dict(res, ledger=eng.ledger, contract=eng.contracts["pit_speed"]),
                "explanation": sia_explain(res),
            }
        if sid in {"late_ref", "late_reference_fact", "late_evidence"}:
            eng.register_contract(get_contract_by_id("lap_time"))
            sc = {"session_id": "lab-late-ref", "driver_id": "44", "lap_number": "12"}
            iid = eng.open_decision("lap_time", sc, "2026-05-24T13:00:00Z", known_at="2026-05-24T13:00:00Z")
            eng.admit_fact(make_fact("session_t0", {"session_id": "lab-late-ref"}, parse_instant("2026-05-24T13:00:00Z"), ["PITWALL"], unit="us"), "2026-05-24T13:00:00Z")
            eng.admit_fact(make_fact("lap_start", sc, parse_instant("2026-05-24T13:00:05Z"), ["PITWALL"], unit="us"), "2026-05-24T13:00:05Z")
            eng.evaluate(iid, "2026-05-24T13:00:35Z")
            eng.admit_atom(make_atom("lap_record", 90.1, "2026-05-24T13:00:20Z", sc, ["PITWALL"], unit="s"), "2026-05-24T13:00:50Z")
            res = eng.evaluate(iid, "2026-05-24T13:00:55Z")
            return {
                "scenario_id": "late_reference_fact",
                "regime": "LAB / ISOLATED_SCENARIO",
                "verdict": sia_assessment_to_dict(res, ledger=eng.ledger, contract=eng.contracts["lap_time"]),
                "explanation": sia_explain(res),
            }
        # Default: silent_feed_guard
        eng.register_contract(get_contract_by_id("lap_time"))
        sc = {"session_id": "lab-silent-feed", "driver_id": "1", "lap_number": "5"}
        iid = eng.open_decision("lap_time", sc, "2026-05-24T13:00:00Z", known_at="2026-05-24T13:00:00Z")
        eng.admit_guard(make_guard("F1_FOM_TIMING", "STALLED", "2026-05-24T13:00:02Z"), "2026-05-24T13:00:03Z")
        res = eng.evaluate(iid, "2026-05-24T13:00:25Z")
        return {
            "scenario_id": "silent_feed_guard",
            "regime": "LAB / ISOLATED_SCENARIO",
            "verdict": sia_assessment_to_dict(res, ledger=eng.ledger, contract=eng.contracts["lap_time"]),
            "explanation": sia_explain(res),
        }

