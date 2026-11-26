"""Append-only evidence ledger with fail-closed admission.

Admission only rejects *structurally broken* items (bad content hash, no provenance, non-finite
value, naive/regressing knowledge time). Items that are well-formed but unusable for a decision
(illegal time class, low quality grade, ...) ARE admitted and judged per contract, so the verdict
can name the precise reason instead of silently seeing "no evidence".

Bitemporal guarantee: ``knowledge_time`` may never regress below the ledger clock, so a verdict
issued "as of K" can never be changed retroactively by a later admission.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .canon import NEG_INF, fmt_instant, parse_instant
from .model import SCOPE_FIELDS, EvidenceAtom, GuardFact, ReferenceFact, ScopeClass, _finite


@dataclass(frozen=True)
class AtomRec:
    atom: EvidenceAtom
    kt: int
    seq: int


@dataclass(frozen=True)
class FactRec:
    fact: ReferenceFact
    kt: int
    seq: int


@dataclass(frozen=True)
class GuardRec:
    guard: GuardFact
    kt: int
    seq: int


@dataclass(frozen=True)
class Admission:
    status: str      # ACCEPTED | DUPLICATE | REJECTED
    code: str
    item_id: str

    @property
    def accepted(self) -> bool:
        return self.status == "ACCEPTED"


class Ledger:
    def __init__(self) -> None:
        self.clock: int = NEG_INF
        self._seq = 0
        self._atoms: Dict[str, List[AtomRec]] = {}
        self._atoms_by_drv: Dict[tuple, List[AtomRec]] = {}
        self._atoms_by_drv_lap: Dict[tuple, List[AtomRec]] = {}
        self._facts: Dict[str, List[FactRec]] = {}
        self.guards: List[GuardRec] = []
        self._ids: Dict[str, object] = {}
        self.rejections: List[dict] = []

    # ---- queries
    def atoms(self, role_id: str) -> List[AtomRec]:
        return self._atoms.get(role_id, [])

    def atoms_for(self, role_id: str, scope: dict, scope_class: ScopeClass) -> List[AtomRec]:
        if scope_class == ScopeClass.DRIVER_LAP and "driver_id" in scope and "lap_number" in scope:
            exact = self._atoms_by_drv_lap.get((role_id, scope["driver_id"], scope["lap_number"]))
            # Driver-wide atoms (no lap_number) must still be considered if present
            wild = self._atoms_by_drv_lap.get((role_id, scope["driver_id"], None))
            if wild:
                return (exact or []) + wild
            return exact or []
        if "driver_id" in SCOPE_FIELDS[scope_class] and "driver_id" in scope:
            return self._atoms_by_drv.get((role_id, scope["driver_id"]), [])
        return self._atoms.get(role_id, [])

    def get_atom(self, atom_id: str) -> EvidenceAtom | None:
        rec = self._ids.get(atom_id)
        return getattr(rec, "atom", None)

    def get_fact(self, fact_id: str) -> ReferenceFact | None:
        rec = self._ids.get(fact_id)
        return getattr(rec, "fact", None)

    def facts(self, fact_type: str) -> List[FactRec]:
        return self._facts.get(fact_type, [])

    def counts(self) -> dict:
        return {"atoms": sum(len(v) for v in self._atoms.values()), "facts": sum(len(v) for v in self._facts.values()),
                "guards": len(self.guards), "rejections": len(self.rejections)}

    # ---- admission
    def _reject(self, kind: str, item_id: str, code: str, kt) -> Admission:
        self.rejections.append({"kind": kind, "id": item_id, "code": code, "knowledge_time": None if kt is None else fmt_instant(kt)})
        return Admission("REJECTED", code, item_id)

    def _common(self, kind: str, item, item_id: str, kt, expected_id: str):
        try:
            kt = parse_instant(kt)
        except (ValueError, TypeError):
            return None, self._reject(kind, item_id, "MALFORMED_KNOWLEDGE_TIME", None)
        if kt < self.clock:
            return None, self._reject(kind, item_id, "KNOWLEDGE_TIME_REGRESSION", kt)
        if expected_id != item_id:
            return None, self._reject(kind, item_id, "ID_CONTENT_MISMATCH", kt)
        return kt, None

    def _next(self, kt: int) -> int:
        self.clock = max(self.clock, kt)
        self._seq += 1
        return self._seq

    def admit_atom(self, atom: EvidenceAtom, knowledge_time) -> Admission:
        kt, bad = self._common("atom", atom, atom.atom_id, knowledge_time, atom.recompute_id())
        if bad:
            return bad
        if atom.atom_id in self._ids:
            self.clock = max(self.clock, kt)
            return Admission("DUPLICATE", "DUPLICATE_ATOM", atom.atom_id)
        if not atom.role_id:
            return self._reject("atom", atom.atom_id, "MISSING_ROLE", kt)
        if not atom.source_origins:
            return self._reject("atom", atom.atom_id, "MISSING_PROVENANCE", kt)
        if not _finite(atom.value):
            return self._reject("atom", atom.atom_id, "MALFORMED_VALUE", kt)
        rec = AtomRec(atom, kt, self._next(kt))
        self._atoms.setdefault(atom.role_id, []).append(rec)
        sc_dict = dict(atom.scope)
        drv = sc_dict.get("driver_id")
        lap = sc_dict.get("lap_number")
        self._atoms_by_drv.setdefault((atom.role_id, drv), []).append(rec)
        self._atoms_by_drv_lap.setdefault((atom.role_id, drv, lap), []).append(rec)
        self._ids[atom.atom_id] = rec
        return Admission("ACCEPTED", "OK", atom.atom_id)

    def admit_fact(self, fact: ReferenceFact, knowledge_time) -> Admission:
        kt, bad = self._common("fact", fact, fact.fact_id, knowledge_time, fact.recompute_id())
        if bad:
            return bad
        if fact.fact_id in self._ids:
            self.clock = max(self.clock, kt)
            return Admission("DUPLICATE", "DUPLICATE_FACT", fact.fact_id)
        if not fact.origins:
            return self._reject("fact", fact.fact_id, "MISSING_PROVENANCE", kt)
        if not _finite(fact.value):
            return self._reject("fact", fact.fact_id, "MALFORMED_VALUE", kt)
        rec = FactRec(fact, kt, self._next(kt))
        self._facts.setdefault(fact.fact_type, []).append(rec)
        self._ids[fact.fact_id] = rec
        return Admission("ACCEPTED", "OK", fact.fact_id)

    def admit_guard(self, guard: GuardFact, knowledge_time) -> Admission:
        kt, bad = self._common("guard", guard, guard.guard_id, knowledge_time, guard.recompute_id())
        if bad:
            return bad
        if guard.guard_id in self._ids:
            return Admission("DUPLICATE", "DUPLICATE_GUARD", guard.guard_id)
        rec = GuardRec(guard, kt, self._next(kt))
        self.guards.append(rec)
        self._ids[guard.guard_id] = rec
        return Admission("ACCEPTED", "OK", guard.guard_id)

    def advance_clock(self, kt: int) -> None:
        self.clock = max(self.clock, kt)
