"""IntegrityEngine: stateful facade over the pure evaluator.

Owns the ledger, the scheduled decision instances, the append-only revision chains and the
bitemporal index. All time is passed in explicitly (no wall-clock reads), so live and replay
runs are bit-for-bit comparable.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional

from .algebra import IntegrityState as S
from .canon import NEG_INF, fmt_instant, parse_instant
from .contract import Contract, Validation, parse_contract, validate_contract
from .evaluator import EngineConfig, evaluate_decision
from .ledger import Admission, Ledger
from .model import (DecisionInstance, EvidenceAtom, GuardFact, OriginRegistry, ReferenceFact, SCOPE_FIELDS,
                    norm_scope, scope_in, scope_projection)
from .verdict import GENESIS, Assessment, BitemporalIndex, explain, make_record, revision_diff, verify_chain


class ContractRejected(ValueError):
    def __init__(self, validation: Validation):
        self.validation = validation
        super().__init__("; ".join(f"[{c}] {m}" for c, m in validation.errors))


class IntegrityEngine:
    def __init__(self, registry: Optional[OriginRegistry] = None, config: Optional[EngineConfig] = None):
        self.registry = registry or OriginRegistry()
        self.cfg = config or EngineConfig()
        self.ledger = Ledger()
        self.contracts: Dict[str, Contract] = {}
        self.instances: Dict[str, DecisionInstance] = {}
        self.index = BitemporalIndex()
        self._sealed: Dict[str, Assessment] = {}
        self._last_eval: Dict[str, int] = {}
        self.finality_violations: List[dict] = []
        self.contract_history: List[dict] = []

    # ------------------------------------------------------------------ contracts
    def register_contract(self, contract: Contract | Mapping[str, Any]) -> Contract:
        c = parse_contract(contract) if isinstance(contract, Mapping) else contract
        v = validate_contract(c, self.registry)
        if not v.ok:
            raise ContractRejected(v)
        self.contracts[c.contract_id] = c
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
            self.instances[iid] = DecisionInstance(iid, contract_id, norm_scope(proj), parse_instant(opens_at), reg, auto)
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

    # ------------------------------------------------------------------ admission
    def admit_atom(self, atom: EvidenceAtom, knowledge_time) -> Admission:
        adm = self.ledger.admit_atom(atom, knowledge_time)
        if adm.accepted:
            self._auto_open(atom)
            self._check_finality(atom.role_id, dict(atom.scope), "atom", atom.atom_id, parse_instant(knowledge_time))
        return adm

    def admit_fact(self, fact: ReferenceFact, knowledge_time) -> Admission:
        adm = self.ledger.admit_fact(fact, knowledge_time)
        if adm.accepted:
            for c in self.contracts.values():
                for rn, r in c.roles.items():
                    if r.kind == "reference" and r.fact_type == fact.fact_type:
                        self._check_finality(rn, dict(fact.scope), "fact", fact.fact_id, parse_instant(knowledge_time), cid=c.contract_id)
        return adm

    def admit_guard(self, guard: GuardFact, knowledge_time) -> Admission:
        return self.ledger.admit_guard(guard, knowledge_time)

    def _check_finality(self, role_id: str, scope: Dict[str, str], kind: str, item_id: str, kt: int, cid: Optional[str] = None) -> None:
        """Post-finality evidence is quarantined (never changes a FINAL verdict) and logged as a violation."""
        for iid, sealed in self._sealed.items():
            inst = self.instances[iid]
            c = self.contracts[inst.contract_id]
            if cid and c.contract_id != cid:
                continue
            r = c.roles.get(role_id)
            if r is not None and scope_in(tuple(scope.items()), inst.scope_dict, r.scope_class):
                self.finality_violations.append({"decision_instance_id": iid, "kind": kind, "item_id": item_id,
                                                 "knowledge_time": fmt_instant(kt), "code": "POST_FINALITY_QUARANTINED"})

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, instance_id: str, K) -> Assessment:
        K = parse_instant(K)
        inst = self.instances[instance_id]
        if instance_id in self._sealed:
            return replace(self._sealed[instance_id], evaluated_at=max(K, self._sealed[instance_id].evaluated_at))
        if K < self._last_eval.get(instance_id, NEG_INF):
            raise ValueError("evaluation instant regressed; use as_of() for historical queries")
        self._last_eval[instance_id] = K
        self.ledger.advance_clock(K)
        out = evaluate_decision(self.contracts[inst.contract_id], inst, self.ledger, self.registry, self.cfg, K)
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
        if out.final:
            self._sealed[instance_id] = rec
        return rec

    def tick(self, K) -> List[Assessment]:
        """Advance the run clock and re-evaluate every open decision (works with a stationary watermark)."""
        K = parse_instant(K)
        self.ledger.advance_clock(K)
        return [self.evaluate(i, K) for i in sorted(self.instances) if i not in self._sealed]

    # ------------------------------------------------------------------ queries
    def history(self, instance_id: str) -> List[Assessment]:
        return self.index.chain(instance_id)

    def as_of(self, instance_id: str, knowledge_time) -> Optional[Assessment]:
        return self.index.as_of(instance_id, knowledge_time)

    def verify(self) -> Dict[str, str]:
        return {i: verify_chain(self.index.chain(i))[1] for i in self.index.decisions()}

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
