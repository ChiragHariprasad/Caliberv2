"""IntegrityEngine: stateful facade over the pure evaluator.

Owns the ledger, the scheduled decision instances, the append-only revision chains and the
bitemporal index. All time is passed in explicitly (no wall-clock reads), so live and replay
runs are bit-for-bit comparable.
"""
from __future__ import annotations

from dataclasses import replace
import pickle
from typing import Any, Dict, List, Mapping, Optional

from .algebra import IntegrityState as S
from .canon import NEG_INF, POS_INF, fmt_instant, parse_instant
from .contract import Contract, Validation, parse_contract, validate_contract
from .evaluator import EngineConfig, evaluate_decision
from .ledger import Admission, Ledger
from .model import (DecisionInstance, EvidenceAtom, GuardFact, OriginRegistry, ReferenceFact, SCOPE_FIELDS,
                    norm_scope, scope_in, scope_projection)
from .verdict import GENESIS, Assessment, BitemporalIndex, explain, make_record, revision_diff, verify_chain

try:
    from .wal import SIAWALStore
except Exception:  # pragma: no cover
    SIAWALStore = None  # type: ignore


class ContractRejected(ValueError):
    def __init__(self, validation: Validation):
        self.validation = validation
        super().__init__("; ".join(f"[{c}] {m}" for c, m in validation.errors))


class IntegrityEngine:
    def __init__(
        self,
        registry: Optional[OriginRegistry] = None,
        config: Optional[EngineConfig] = None,
        wal: Optional[Any] = None,
    ):
        self.registry = registry or OriginRegistry()
        self.cfg = config or EngineConfig()
        self.wal = wal
        self.ledger = Ledger()
        self.contracts: Dict[str, Contract] = {}
        self._contract_raw: Dict[str, dict] = {}
        self.instances: Dict[str, DecisionInstance] = {}
        self._open_instances: set[str] = set()
        self.index = BitemporalIndex()
        self._sealed: Dict[str, Assessment] = {}
        self._last_eval: Dict[str, int] = {}
        self._dirty: set[str] = set()
        self._next_wake: Dict[str, int] = {}
        self._last_tick_K: int = NEG_INF
        self._guard_scan_idx: int = 0
        self.finality_violations: List[dict] = []
        self.quarantined_items: List[dict] = []
        self.contract_history: List[dict] = []

    def export_state(self) -> bytes:
        """Serialize complete in-memory SIA state (ledger, chains, instances, registry) for fast keyframe checkpoints."""
        state = {
            "registry": self.registry,
            "cfg": self.cfg,
            "ledger": self.ledger,
            "contracts": self.contracts,
            "_contract_raw": self._contract_raw,
            "instances": self.instances,
            "_open_instances": self._open_instances,
            "index": self.index,
            "_sealed": self._sealed,
            "_last_eval": self._last_eval,
            "_dirty": self._dirty,
            "_next_wake": self._next_wake,
            "_last_tick_K": self._last_tick_K,
            "_guard_scan_idx": self._guard_scan_idx,
            "finality_violations": self.finality_violations,
            "quarantined_items": self.quarantined_items,
            "contract_history": self.contract_history,
        }
        return pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)

    def restore_state(self, blob: bytes) -> None:
        """Restore in-memory SIA state from a checkpoint blob while preserving the WAL handle."""
        state = pickle.loads(blob)
        self.registry = state["registry"]
        self.cfg = state["cfg"]
        self.ledger = state["ledger"]
        self.contracts = state["contracts"]
        self._contract_raw = state["_contract_raw"]
        self.instances = state["instances"]
        self._open_instances = state["_open_instances"]
        self.index = state["index"]
        self._sealed = state["_sealed"]
        self._last_eval = state["_last_eval"]
        self._dirty = state["_dirty"]
        self._next_wake = state["_next_wake"]
        self._last_tick_K = state["_last_tick_K"]
        self._guard_scan_idx = state["_guard_scan_idx"]
        self.finality_violations = state["finality_violations"]
        self.quarantined_items = state["quarantined_items"]
        self.contract_history = state["contract_history"]

    # ------------------------------------------------------------------ contracts
    def register_contract(self, contract: Contract | Mapping[str, Any]) -> Contract:
        raw_dict = dict(contract) if isinstance(contract, Mapping) else None
        c = parse_contract(contract) if isinstance(contract, Mapping) else contract
        v = validate_contract(c, self.registry)
        if not v.ok:
            raise ContractRejected(v)
        self.contracts[c.contract_id] = c
        if raw_dict is not None:
            self._contract_raw[c.contract_id] = raw_dict
            if self.wal is not None:
                self.wal.save_contract(raw_dict)
        self.contract_history.append(c.ref)
        return c

    # ------------------------------------------------------------------ decision instances
    def open_decision(self, contract_id: str, scope: Mapping[str, Any], opens_at, *, auto: bool = False, known_at=None) -> str:
        c = self.contracts[contract_id]
        proj = scope_projection(scope, c.scope_class)
        if proj is None:
            raise ValueError(f"scope {dict(scope)} lacks fields {SCOPE_FIELDS[c.scope_class]} for {c.scope_class.value}")
        iid = f"{contract_id}@" + "|".join(proj[f] for f in SCOPE_FIELDS[c.scope_class])
        if iid not in self.instances:
            reg = parse_instant(known_at) if known_at is not None else (self.ledger.clock if self.ledger.clock > NEG_INF else parse_instant(opens_at))
            inst = DecisionInstance(iid, contract_id, norm_scope(proj), parse_instant(opens_at), reg, auto)
            self.instances[iid] = inst
            self._open_instances.add(iid)
            if self.wal is not None:
                self.wal.save_decision(inst)
        return iid

    def _auto_open(self, atom: EvidenceAtom) -> None:
        if not self.cfg.auto_open:
            return
        for c in self.contracts.values():
            role = c.roles.get(atom.role_id)
            if role is None or role.kind != "evidence" or role.scope_class != c.scope_class:
                continue
            proj = scope_projection(dict(atom.scope), c.scope_class)
            if proj is not None:
                self.open_decision(c.contract_id, proj, atom.observed_at, auto=True)

    def _matching_sealed_instances(self, role_id: str, scope: Dict[str, str], cid: Optional[str] = None) -> List[str]:
        matched: List[str] = []
        sc_items = tuple(scope.items())
        for iid in self._sealed:
            inst = self.instances[iid]
            c = self.contracts[inst.contract_id]
            if cid and c.contract_id != cid:
                continue
            r = c.roles.get(role_id)
            if r is not None and scope_in(sc_items, inst.scope_dict, r.scope_class):
                matched.append(iid)
        return matched

    def _has_open_target_for_atom(self, atom: EvidenceAtom) -> bool:
        sc = dict(atom.scope)
        sc_items = tuple(sc.items())
        for iid in self._open_instances:
            inst = self.instances[iid]
            c = self.contracts[inst.contract_id]
            r = c.roles.get(atom.role_id)
            if r is not None and scope_in(sc_items, inst.scope_dict, r.scope_class):
                return True
        if self.cfg.auto_open:
            for c in self.contracts.values():
                role = c.roles.get(atom.role_id)
                if role is None or role.kind != "evidence" or role.scope_class != c.scope_class:
                    continue
                proj = scope_projection(sc, c.scope_class)
                if proj is not None:
                    cand_iid = f"{c.contract_id}@" + "|".join(proj[f] for f in SCOPE_FIELDS[c.scope_class])
                    if cand_iid not in self._sealed:
                        return True
        return False

    def _has_open_target_for_fact(self, fact: ReferenceFact) -> bool:
        sc_items = tuple(dict(fact.scope).items())
        for iid in self._open_instances:
            inst = self.instances[iid]
            c = self.contracts[inst.contract_id]
            for r in c.roles.values():
                if r.kind == "reference" and r.fact_type == fact.fact_type:
                    return True
        # Global SESSION facts may also apply to future auto-opened decisions
        if self.cfg.auto_open and dict(fact.scope):
            for c in self.contracts.values():
                for r in c.roles.values():
                    if r.kind == "reference" and r.fact_type == fact.fact_type and r.scope_class == ScopeClass.SESSION:
                        return True
        return len(self._sealed) == 0 and any(True for _ in sc_items)

    # ------------------------------------------------------------------ admission
    def admit_atom(self, atom: EvidenceAtom, knowledge_time) -> Admission:
        # Pre-admission finality quarantine check BEFORE ledger mutation
        try:
            kt = parse_instant(knowledge_time)
        except (ValueError, TypeError):
            return self.ledger.admit_atom(atom, knowledge_time)
        sealed_hits = self._matching_sealed_instances(atom.role_id, dict(atom.scope))
        if sealed_hits and kt >= self.ledger.clock and atom.recompute_id() == atom.atom_id and not self._has_open_target_for_atom(atom):
            self.ledger.advance_clock(kt)
            for iid in sealed_hits:
                rec = {
                    "decision_instance_id": iid,
                    "kind": "atom",
                    "item_id": atom.atom_id,
                    "knowledge_time": fmt_instant(kt),
                    "code": "POST_FINALITY_QUARANTINED",
                }
                self.finality_violations.append(rec)
                self.quarantined_items.append({**rec, "payload": atom.to_dict()})
                if self.wal is not None:
                    self.wal.save_quarantine("atom", atom.atom_id, iid, kt, "POST_FINALITY_QUARANTINED", {**atom.to_dict(), "knowledge_time": fmt_instant(kt)})
            return Admission("QUARANTINED", "POST_FINALITY_QUARANTINED", atom.atom_id)

        adm = self.ledger.admit_atom(atom, knowledge_time)
        if adm.accepted:
            if self.wal is not None:
                self.wal.save_atom(atom, kt, self.ledger._seq)
            self._auto_open(atom)
            atom_drv = dict(atom.scope).get("driver_id")
            for iid in self._open_instances:
                inst = self.instances[iid]
                if atom.role_id not in self.contracts[inst.contract_id].roles:
                    continue
                inst_drv = inst.scope_dict.get("driver_id")
                if inst_drv is not None and atom_drv is not None and inst_drv != atom_drv:
                    continue
                self._dirty.add(iid)
            self._check_finality(atom.role_id, dict(atom.scope), "atom", atom.atom_id, kt, payload=atom.to_dict())
        return adm

    def admit_fact(self, fact: ReferenceFact, knowledge_time) -> Admission:
        try:
            kt = parse_instant(knowledge_time)
        except (ValueError, TypeError):
            return self.ledger.admit_fact(fact, knowledge_time)
        sealed_hits: List[str] = []
        for c in self.contracts.values():
            for rn, r in c.roles.items():
                if r.kind == "reference" and r.fact_type == fact.fact_type:
                    sealed_hits.extend(self._matching_sealed_instances(rn, dict(fact.scope), cid=c.contract_id))
        if sealed_hits and kt >= self.ledger.clock and fact.recompute_id() == fact.fact_id and not self._has_open_target_for_fact(fact):
            self.ledger.advance_clock(kt)
            for iid in dict.fromkeys(sealed_hits):
                rec = {
                    "decision_instance_id": iid,
                    "kind": "fact",
                    "item_id": fact.fact_id,
                    "knowledge_time": fmt_instant(kt),
                    "code": "POST_FINALITY_QUARANTINED",
                }
                self.finality_violations.append(rec)
                self.quarantined_items.append({**rec, "payload": fact.to_dict()})
                if self.wal is not None:
                    self.wal.save_quarantine("fact", fact.fact_id, iid, kt, "POST_FINALITY_QUARANTINED", {**fact.to_dict(), "knowledge_time": fmt_instant(kt)})
            return Admission("QUARANTINED", "POST_FINALITY_QUARANTINED", fact.fact_id)

        adm = self.ledger.admit_fact(fact, knowledge_time)
        if adm.accepted:
            if self.wal is not None:
                self.wal.save_fact(fact, kt, self.ledger._seq)
            for iid in self._open_instances:
                self._dirty.add(iid)
            for c in self.contracts.values():
                for rn, r in c.roles.items():
                    if r.kind == "reference" and r.fact_type == fact.fact_type:
                        self._check_finality(rn, dict(fact.scope), "fact", fact.fact_id, kt, cid=c.contract_id, payload=fact.to_dict())
        return adm

    def admit_guard(self, guard: GuardFact, knowledge_time) -> Admission:
        adm = self.ledger.admit_guard(guard, knowledge_time)
        if adm.accepted:
            kt = parse_instant(knowledge_time)
            if self.wal is not None:
                self.wal.save_guard(guard, kt, self.ledger._seq)
            for iid in self._open_instances:
                self._dirty.add(iid)
        return adm

    def _check_finality(self, role_id: str, scope: Dict[str, str], kind: str, item_id: str, kt: int, cid: Optional[str] = None, payload: Optional[dict] = None) -> None:
        """Post-finality evidence for sealed decisions is logged as a violation and quarantined."""
        for iid in self._matching_sealed_instances(role_id, scope, cid=cid):
            rec = {"decision_instance_id": iid, "kind": kind, "item_id": item_id,
                   "knowledge_time": fmt_instant(kt), "code": "POST_FINALITY_QUARANTINED"}
            self.finality_violations.append(rec)
            self.quarantined_items.append({**rec, "payload": payload or {}})
            if self.wal is not None:
                self.wal.save_quarantine(kind, item_id, iid, kt, "POST_FINALITY_QUARANTINED", {**(payload or {}), "knowledge_time": fmt_instant(kt)})

    # ------------------------------------------------------------------ evaluation
    def void_decision(self, instance_id: str, K, *, reason: str = "SESSION_EVENT", witness_code: str = "VOIDED", detail: str = "") -> Assessment:
        """Legitimately voids a scheduled decision instance (CR-1) using standard SIA v3 schema."""
        K = parse_instant(K)
        if instance_id not in self.instances:
            raise KeyError(f"unknown decision instance: {instance_id}")
        if instance_id in self._sealed:
            return self._sealed[instance_id]
        inst = self.instances[instance_id]
        self.ledger.advance_clock(K)
        head = self.index.head(instance_id)
        rev = 1 if head is None else head.revision_number + 1
        prev = GENESIS if head is None else head.record_hash
        kt = max(K, head.knowledge_time) if head is not None else K

        c = self.contracts[inst.contract_id]
        from .algebra import Timeline
        void_timeline = Timeline([(inst.opens_at, S.UNKNOWN)])
        witness_entry = {
            "code": witness_code,
            "role": "decision",
            "detail": detail or f"Legitimately voided due to {reason}",
        }
        content = {
            "schema": "calibre.sia.assessment/3.0",
            "decision_instance_id": instance_id,
            "contract": c.ref,
            "scope": dict(inst.scope_dict),
            "opens_at": fmt_instant(inst.opens_at),
            "validity_timeline": void_timeline.to_list(),
            "resolution_maturity": "TUPLE_RESOLVED",
            "finality_status": "FINAL",
            "envelope": {"lower": S.UNKNOWN.name, "upper": S.UNKNOWN.name, "alternatives": [S.UNKNOWN.name]},
            "roles": {},
            "constraints": {},
            "diagnosis": {"result": "NONE", "excluded_items": [], "excluded_origins": [], "minimal_diagnoses": []},
            "resilience": {"required_k": 0, "profile": {}, "critical_origins": []},
            "witnesses": [witness_entry],
            "limitations": ["DECISION_VOIDED"],
            "evidence_frontier": fmt_instant(kt),
        }
        ch, rh = make_record(content, rev, prev, kt, "VOIDED")
        rec = Assessment(content, ch, rev, prev, kt, "VOIDED", rh, K, void_timeline)
        self.index.append(rec)
        self._sealed[instance_id] = rec
        self._open_instances.discard(instance_id)
        if self.wal is not None:
            self.wal.save_assessment(rec)
        return rec

    def evaluate(self, instance_id: str, K) -> Assessment:
        K = parse_instant(K)
        inst = self.instances[instance_id]
        if instance_id in self._sealed:
            return replace(self._sealed[instance_id], evaluated_at=max(K, self._sealed[instance_id].evaluated_at))
        if K < self._last_eval.get(instance_id, NEG_INF):
            raise ValueError("evaluation instant regressed; use as_of() for historical queries")
        self._last_eval[instance_id] = K
        self.ledger.advance_clock(K)
        c = self.contracts[inst.contract_id]
        out = evaluate_decision(c, inst, self.ledger, self.registry, self.cfg, K)
        head = self.index.head(instance_id)
        if head is not None and head.content_hash == _hash(out.content):
            rec = replace(head, evaluated_at=K)             # same conclusion: no new revision
        else:
            rev = 1 if head is None else head.revision_number + 1
            prev = GENESIS if head is None else head.record_hash
            reason = "INITIAL" if head is None else _reason(head.content, out.content)
            kt = out.knowledge_time if head is None else max(out.knowledge_time, head.knowledge_time)
            ch, rh = make_record(out.content, rev, prev, kt, reason)
            rec = Assessment(out.content, ch, rev, prev, kt, reason, rh, K, out.timeline)
            self.index.append(rec)
            if self.wal is not None:
                self.wal.save_assessment(rec)
        self._dirty.discard(instance_id)
        wake_candidates = [rec.timeline.next_change_after(K), inst.opens_at + c.cutoff_us]
        for r in c.roles.values():
            wake_candidates.append(inst.opens_at + r.slot.deadline_us)
            wake_candidates.append(inst.opens_at + r.slot.deadline_us + r.slot.lateness_us)
        self._next_wake[instance_id] = min((t for t in wake_candidates if t is not None and t > K), default=POS_INF)
        if out.final:
            self._sealed[instance_id] = rec
            self._open_instances.discard(instance_id)
        return rec

    def tick(self, K) -> List[Assessment]:
        """Advance the run clock and evaluate open decisions that are dirty or crossed a transition boundary."""
        K = parse_instant(K)
        self.ledger.advance_clock(K)
        prev_k = self._last_tick_K
        if self._guard_scan_idx < len(self.ledger.guards):
            unseen = self.ledger.guards[self._guard_scan_idx :]
            if any(prev_k < g.kt <= K for g in unseen):
                for iid in self._open_instances:
                    self._dirty.add(iid)
            if all(g.kt <= K for g in unseen):
                self._guard_scan_idx = len(self.ledger.guards)
        self._last_tick_K = max(prev_k, K)
        res: List[Assessment] = []
        for i in sorted(self._open_instances):
            head = self.index.head(i)
            if head is not None and i not in self._dirty and K < self._next_wake.get(i, NEG_INF):
                if K < self._last_eval.get(i, NEG_INF):
                    raise ValueError("evaluation instant regressed; use as_of() for historical queries")
                self._last_eval[i] = K
                res.append(replace(head, evaluated_at=K))
            else:
                res.append(self.evaluate(i, K))
        return res

    # ------------------------------------------------------------------ queries
    def history(self, instance_id: str) -> List[Assessment]:
        return self.index.chain(instance_id)

    def as_of(self, instance_id: str, knowledge_time) -> Optional[Assessment]:
        return self.index.as_of(instance_id, knowledge_time)

    def verify(self) -> Dict[str, str]:
        return {i: verify_chain(self.index.chain(i))[1] for i in self.index.decisions()}

    def verify_incremental(self, cached_lengths: Dict[str, int]) -> bool:
        """Verify only decision chains whose length changed since cached_lengths."""
        for iid in self.index.decisions():
            chain = self.index.chain(iid)
            n = len(chain)
            if cached_lengths.get(iid) == n:
                continue
            if verify_chain(chain)[1] != "OK":
                return False
            cached_lengths[iid] = n
        return True

    def explain(self, a: Assessment) -> str:
        return explain(a)

    def diff(self, a: Assessment, b: Assessment) -> List[str]:
        return revision_diff(a, b)


def _hash(content: dict) -> str:
    from .canon import sha256_hex
    return sha256_hex(content)


def _reason(prev: dict, new: dict) -> str:
    if prev["contract"] != new["contract"]:
        return "CONTRACT_CHANGE"
    if prev["finality_status"] != new["finality_status"]:
        return "FINALIZED"
    if any(w["code"] == "LATE_EVIDENCE_ADMITTED" for w in new["witnesses"]) and not any(w["code"] == "LATE_EVIDENCE_ADMITTED" for w in prev["witnesses"]):
        return "LATE_EVIDENCE"
    ev_keys = lambda c: {n: (r["support_atom_ids"], r["reference_fact_ids"]) for n, r in c["roles"].items()}
    return "EVIDENCE_CHANGE" if ev_keys(prev) != ev_keys(new) else "CLOCK_EVENT"
