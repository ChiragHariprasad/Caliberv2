"""Domain model: scopes, origin lineage, evidence atoms, reference facts, guard facts.

Identity is content-addressed (SHA-256 over RFC 8785 canonical JSON), so replaying or reprocessing
the same observation can never look like a new independent source.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Sequence, Tuple

from .algebra import IntegrityState as S
from .canon import fmt_instant, parse_instant, quantize_value, sha256_hex
from .timeclass import TimeClass, TypedTime


# --------------------------------------------------------------------------- scopes
class ScopeClass(str, Enum):
    SESSION = "SESSION"
    DRIVER_SESSION = "DRIVER_SESSION"
    DRIVER_LAP = "DRIVER_LAP"
    SECTOR = "SECTOR"
    ZONE = "ZONE"


SCOPE_FIELDS: Dict[ScopeClass, Tuple[str, ...]] = {
    ScopeClass.SESSION: ("session_id",),
    ScopeClass.DRIVER_SESSION: ("session_id", "driver_id"),
    ScopeClass.DRIVER_LAP: ("session_id", "driver_id", "lap_number"),
    ScopeClass.SECTOR: ("session_id", "driver_id", "lap_number", "sector_number"),
    ScopeClass.ZONE: ("session_id", "driver_id", "lap_number", "sector_number", "zone_id"),
}
SCOPE_RANK = {ScopeClass.SESSION: 0, ScopeClass.DRIVER_SESSION: 1, ScopeClass.DRIVER_LAP: 2, ScopeClass.SECTOR: 3, ScopeClass.ZONE: 4}
_ALIAS = {"session": "session_id", "driver": "driver_id", "driver_number": "driver_id",
          "lap": "lap_number", "sector": "sector_number", "zone": "zone_id", "loop": "zone_id"}

ScopeT = Tuple[Tuple[str, str], ...]


def norm_scope(scope: Mapping[str, Any]) -> ScopeT:
    out = {}
    for k, v in scope.items():
        if v is None or str(v) == "":
            continue
        out[_ALIAS.get(k, k)] = str(v)
    return tuple(sorted(out.items()))


def scope_in(item_scope: ScopeT, inst_scope: Mapping[str, str], cls: ScopeClass) -> bool:
    """Item carries every field of ``cls`` and agrees with the decision on each (scope locality)."""
    d = dict(item_scope)
    return all(f in d and f in inst_scope and d[f] == inst_scope[f] for f in SCOPE_FIELDS[cls])


def scope_covers(item_scope: ScopeT, scope: Mapping[str, str]) -> bool:
    """A (possibly broader) fact applies to a decision iff all its scope fields match."""
    return all(scope.get(k) == v for k, v in item_scope)


def scope_projection(scope: Mapping[str, Any], cls: ScopeClass) -> Optional[Dict[str, str]]:
    d = dict(norm_scope(scope))
    if not all(f in d for f in SCOPE_FIELDS[cls]):
        return None
    return {f: d[f] for f in SCOPE_FIELDS[cls]}


# --------------------------------------------------------------------------- origins
class OriginRegistry:
    """Origin lineage: ``{"PITWALL": ["F1_FOM_TIMING"], "TRACINGINSIGHTS": ["F1_FOM_TIMING"]}``.

    The *closure* of an origin contains everything it depends on. Two atoms are independent on
    the source axis iff their closures are disjoint - this derives the "shared F1 upstream"
    limitation mechanically instead of hard-coding provider-name prefixes.
    """

    def __init__(self, upstream: Optional[Mapping[str, Iterable[str]]] = None):
        self._up = {k: tuple(v) for k, v in (upstream or {}).items()}

    def closure(self, origin: str) -> FrozenSet[str]:
        seen, stack = set(), [origin]
        while stack:
            o = stack.pop()
            if o in seen:
                continue
            seen.add(o)
            stack.extend(self._up.get(o, ()))
        return frozenset(seen)

    def deps(self, source_origins: Iterable[str], processing_origins: Iterable[str]) -> FrozenSet[str]:
        d = set()
        for o in source_origins:
            d |= {"S:" + x for x in self.closure(o)}
        d |= {"P:" + p for p in processing_origins}
        return frozenset(d)

    def max_independent(self, origins: Sequence[str]) -> int:
        """Largest subset of ``origins`` with pairwise-disjoint closures."""
        cl = [self.closure(o) for o in origins]
        best = 0
        for r in range(1, len(cl) + 1):
            for combo in itertools.combinations(range(len(cl)), r):
                if all(cl[i].isdisjoint(cl[j]) for i, j in itertools.combinations(combo, 2)):
                    best = max(best, r)
                    break
        return best


# --------------------------------------------------------------------------- atoms
def _canon_value(v: Any, unit: str) -> Any:
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    if isinstance(v, (float, Decimal)):
        if not _finite(v):
            return str(v)               # hashable; admission rejects non-finite values (MALFORMED_VALUE)
        return quantize_value(v, unit)
    return str(v)


def _finite(v: Any) -> bool:
    if isinstance(v, Decimal):
        return v.is_finite()
    return not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


@dataclass(frozen=True)
class EvidenceAtom:
    atom_id: str
    role_id: str
    value: Any
    unit: str
    observed_at: int                      # absolute instant the observation refers to (freshness basis)
    time: TypedTime                       # typed semantic timestamp (alignment basis)
    scope: ScopeT
    source_origins: Tuple[str, ...]
    processing_origins: Tuple[str, ...]
    processor_family_id: str
    transform_version: str
    raw_event_ids: Tuple[str, ...]
    quality_grade: S = S.HEALTHY
    supersedes: Optional[str] = None
    reference_atom_ids: Tuple[str, ...] = ()

    def canonical(self) -> dict:
        return {
            "role_id": self.role_id,
            "value": _canon_value(self.value, self.unit),
            "unit": self.unit,
            "observed_at": fmt_instant(self.observed_at),
            "time": {"class": self.time.time_class.value, "value": self.time.value, "unc": self.time.uncertainty_us},
            "scope": dict(self.scope),
            "source_origins": sorted(self.source_origins),
            "processing_origins": sorted(self.processing_origins),
            "processor_family_id": self.processor_family_id,
            "transform_version": self.transform_version,
            "raw_event_ids": sorted(self.raw_event_ids),
            "quality_grade": self.quality_grade.name,
            "supersedes": self.supersedes,
            "reference_atom_ids": sorted(self.reference_atom_ids),
        }

    def recompute_id(self) -> str:
        return sha256_hex(self.canonical())

    def to_dict(self) -> dict:
        d = self.canonical()
        d["atom_id"] = self.atom_id
        return d


def make_atom(role_id: str, value: Any, observed_at: Any, scope: Mapping[str, Any],
              source_origins: Sequence[str], *, time: Optional[TypedTime] = None, unit: str = "s",
              processing_origins: Optional[Sequence[str]] = None, processor_family_id: str = "generic_parser_family",
              transform_version: str = "1.0.0", raw_event_ids: Sequence[str] = (),
              quality_grade: S = S.HEALTHY, supersedes: Optional[str] = None,
              reference_atom_ids: Sequence[str] = ()) -> EvidenceAtom:
    obs = parse_instant(observed_at)
    if processing_origins is None:      # default: one adapter per source (shared processors must be declared explicitly)
        processing_origins = tuple("adapter:" + o for o in source_origins)
    tt = time or TypedTime(obs, TimeClass.ABSOLUTE_UTC)
    sc = norm_scope(scope)
    raws = tuple(raw_event_ids) or ("raw:" + sha256_hex({"r": role_id, "o": obs, "s": sc, "v": _canon_value(value, unit),
                                                          "src": sorted(source_origins)})[:24],)
    a = EvidenceAtom("", role_id, value, unit, obs, tt, sc, tuple(sorted(source_origins)), tuple(sorted(processing_origins)),
                     processor_family_id, transform_version, tuple(sorted(raws)), S.parse(quality_grade), supersedes,
                     tuple(sorted(reference_atom_ids)))
    return EvidenceAtom(**{**a.__dict__, "atom_id": a.recompute_id()})


# --------------------------------------------------------------------------- reference facts
@dataclass(frozen=True)
class ReferenceFact:
    fact_id: str
    fact_type: str                        # lap_start | session_t0 | calibration_bias | track_geometry | ...
    scope: ScopeT
    value: Any                            # int microseconds for time facts, numeric/str otherwise
    unit: str
    grade: S
    origins: Tuple[str, ...]
    valid_from: Optional[int] = None
    valid_to: Optional[int] = None
    uncertainty_us: int = 0
    rejection_reason: Optional[str] = None
    supersedes: Optional[str] = None
    note: str = ""

    def canonical(self) -> dict:
        return {
            "fact_type": self.fact_type, "scope": dict(self.scope), "value": _canon_value(self.value, self.unit),
            "unit": self.unit, "grade": self.grade.name, "origins": sorted(self.origins),
            "valid_from": None if self.valid_from is None else fmt_instant(self.valid_from),
            "valid_to": None if self.valid_to is None else fmt_instant(self.valid_to),
            "uncertainty_us": self.uncertainty_us, "rejection_reason": self.rejection_reason,
            "supersedes": self.supersedes, "note": self.note,
        }

    def recompute_id(self) -> str:
        return sha256_hex(self.canonical())

    def to_dict(self) -> dict:
        return {**self.canonical(), "fact_id": self.fact_id}


def make_fact(fact_type: str, scope: Mapping[str, Any], value: Any, origins: Sequence[str], *, unit: str = "us",
              grade: S = S.HEALTHY, valid_from: Any = None, valid_to: Any = None, uncertainty_us: int = 0,
              rejection_reason: Optional[str] = None, supersedes: Optional[str] = None, note: str = "") -> ReferenceFact:
    f = ReferenceFact("", fact_type, norm_scope(scope), value, unit, S.parse(grade), tuple(sorted(origins)),
                      None if valid_from is None else parse_instant(valid_from),
                      None if valid_to is None else parse_instant(valid_to),
                      int(uncertainty_us), rejection_reason, supersedes, note)
    return ReferenceFact(**{**f.__dict__, "fact_id": f.recompute_id()})


# --------------------------------------------------------------------------- guard facts
@dataclass(frozen=True)
class GuardFact:
    guard_id: str
    origin: str
    status: str                           # STALLED | RESUMED
    detected_at: int
    epoch: int = 1

    def canonical(self) -> dict:
        return {"origin": self.origin, "status": self.status, "detected_at": fmt_instant(self.detected_at), "epoch": self.epoch}

    def recompute_id(self) -> str:
        return sha256_hex(self.canonical())


def make_guard(origin: str, status: str, detected_at: Any, epoch: int = 1) -> GuardFact:
    if status not in ("STALLED", "RESUMED"):
        raise ValueError("guard status must be STALLED or RESUMED")
    g = GuardFact("", origin, status, parse_instant(detected_at), epoch)
    return GuardFact(**{**g.__dict__, "guard_id": g.recompute_id()})


# --------------------------------------------------------------------------- decision instance
@dataclass(frozen=True)
class DecisionInstance:
    instance_id: str
    contract_id: str
    scope: ScopeT
    opens_at: int                         # valid-time slot opening (scheduled; NOT arrival time)
    registered_at: int                    # knowledge time at which the engine learned of the slot
    auto: bool = False

    @property
    def scope_dict(self) -> Dict[str, str]:
        return dict(self.scope)
