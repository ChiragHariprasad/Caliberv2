"""Typed time (CAL-DOC-007 §2.2) with reference-gated conversions.

    LAP_RELATIVE --(lap_start)--> SESSION_ELAPSED --(session_t0)--> ABSOLUTE_UTC     (and back)

LAP_DURATION, RECEIPT_TIME_ONLY, PROCESSING_TIME and UNKNOWN are *never* timestamps: any attempt
to use them as semantic time is an ILLEGAL conversion. A conversion also inherits the reference
fact's uncertainty and provenance; it is never invented when the reference is absent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from .algebra import IntegrityState as S


class TimeClass(str, Enum):
    ABSOLUTE_UTC = "ABSOLUTE_UTC"
    SESSION_ELAPSED = "SESSION_ELAPSED"
    LAP_RELATIVE = "LAP_RELATIVE"
    LAP_DURATION = "LAP_DURATION"
    RECEIPT_TIME_ONLY = "RECEIPT_TIME_ONLY"
    PROCESSING_TIME = "PROCESSING_TIME"
    UNKNOWN = "UNKNOWN"


SEMANTIC = frozenset({TimeClass.ABSOLUTE_UTC, TimeClass.SESSION_ELAPSED, TimeClass.LAP_RELATIVE})


@dataclass(frozen=True)
class TypedTime:
    value: int                      # microseconds (instant for ABSOLUTE_UTC, offset otherwise)
    time_class: TimeClass
    uncertainty_us: int = 0


_EDGES: Dict[Tuple[TimeClass, TimeClass], Tuple[str, int]] = {
    (TimeClass.LAP_RELATIVE, TimeClass.SESSION_ELAPSED): ("lap_start", +1),
    (TimeClass.SESSION_ELAPSED, TimeClass.LAP_RELATIVE): ("lap_start", -1),
    (TimeClass.SESSION_ELAPSED, TimeClass.ABSOLUTE_UTC): ("session_t0", +1),
    (TimeClass.ABSOLUTE_UTC, TimeClass.SESSION_ELAPSED): ("session_t0", -1),
}


def conversion_path(src: TimeClass, dst: TimeClass) -> Optional[List[Tuple[TimeClass, TimeClass, str, int]]]:
    if src == dst:
        return []
    if src not in SEMANTIC or dst not in SEMANTIC:
        return None
    queue: List[Tuple[TimeClass, list]] = [(src, [])]
    seen = {src}
    while queue:
        cur, path = queue.pop(0)
        for (a, b), (ft, sign) in _EDGES.items():
            if a == cur and b not in seen:
                np = path + [(a, b, ft, sign)]
                if b == dst:
                    return np
                seen.add(b)
                queue.append((b, np))
    return None


@dataclass
class Resolution:
    time: Optional[TypedTime]
    fact_ids: tuple = ()
    fact_deps: frozenset = frozenset()
    grade: S = S.HEALTHY
    missing: tuple = ()
    illegal: bool = False
    ambiguous: bool = False


Lookup = Callable[[str], Optional[tuple]]   # fact_type -> (fact, ambiguous, deps) | None


def resolve_time(t: TypedTime, target: TimeClass, lookup: Lookup) -> Resolution:
    path = conversion_path(t.time_class, target)
    if path is None:
        return Resolution(None, illegal=True, grade=S.DEGRADED)
    val, unc = t.value, t.uncertainty_us
    ids, deps, missing = [], set(), []
    grade, amb = S.HEALTHY, False
    for _a, _b, ftype, sign in path:
        hit = lookup(ftype)
        if hit is None:
            missing.append(ftype)
            continue
        fact, ambiguous, fdeps = hit
        val += sign * int(fact.value)
        unc += int(fact.uncertainty_us)
        ids.append(fact.fact_id)
        deps |= set(fdeps)
        grade = min(grade, fact.grade)
        amb = amb or ambiguous
    if missing:
        return Resolution(None, tuple(ids), frozenset(deps), grade, tuple(missing), False, amb)
    return Resolution(TypedTime(val, target, unc), tuple(ids), frozenset(deps), grade, (), False, amb)
