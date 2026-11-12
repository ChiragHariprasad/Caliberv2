"""State algebra.

* ``IntegrityState``  - total order  DEGRADED < UNKNOWN < SUSPECT < HEALTHY.
* ``StateSet``        - a *superposition*: the set of states a quantity may still collapse to.
* ``Timeline``        - a step function  valid-time -> state  (before its first breakpoint the
                        state is UNKNOWN, never retro-extended: fixes the old ``state_at`` bug).

The "quantum-logic" flavour here is purely classical and deterministic: a pending quantity is a
set of admissible outcomes, composition is lifted pointwise, and *collapse* happens when the set
becomes a singleton. No amplitudes, no randomness, no order dependence.
"""
from __future__ import annotations

import itertools
from bisect import bisect_right
from enum import IntEnum
from functools import reduce
from typing import Callable, FrozenSet, Iterable, List, Sequence, Tuple

from .canon import NEG_INF, fmt_instant


class IntegrityState(IntEnum):
    DEGRADED = 0
    UNKNOWN = 1
    SUSPECT = 2
    HEALTHY = 3

    @classmethod
    def parse(cls, v) -> "IntegrityState":
        return v if isinstance(v, cls) else cls[str(v).upper()]


S = IntegrityState
FULL: FrozenSet[S] = frozenset(S)


def and_state(*s: S) -> S:
    return min(s) if s else S.HEALTHY


def or_state(*s: S) -> S:
    return max(s) if s else S.DEGRADED


def k_of_n_state(k: int, *s: S) -> S:
    if not s or not (1 <= k <= len(s)):
        raise ValueError(f"k_of_n requires 1 <= k <= n; got k={k}, n={len(s)}")
    return sorted(s, reverse=True)[k - 1]


def state_comb(op: str, k: int, items: Sequence[S]) -> S:
    if op == "AND":
        return and_state(*items)
    if op == "OR":
        return or_state(*items)
    return k_of_n_state(k, *items)


# --------------------------------------------------------------------------- superposition sets
def sset(*x) -> FrozenSet[S]:
    return frozenset(S.parse(i) for i in x)


def set_and(a: FrozenSet[S], b: FrozenSet[S]) -> FrozenSet[S]:
    return frozenset(min(x, y) for x in a for y in b)


def set_or(a: FrozenSet[S], b: FrozenSet[S]) -> FrozenSet[S]:
    return frozenset(max(x, y) for x in a for y in b)


def set_comb(op: str, k: int, items: Sequence[FrozenSet[S]], cap: int = 20000) -> FrozenSet[S]:
    """Lift AND/OR/k-of-n to superposition sets (exact; sound interval fallback above ``cap``)."""
    if op == "AND":
        return reduce(set_and, items)
    if op == "OR":
        return reduce(set_or, items)
    size = 1
    for i in items:
        size *= len(i)
    if size <= cap:
        return frozenset(k_of_n_state(k, *c) for c in itertools.product(*items))
    lo = k_of_n_state(k, *[min(i) for i in items])
    hi = k_of_n_state(k, *[max(i) for i in items])
    return frozenset(s for s in S if lo <= s <= hi)


def envelope(a: FrozenSet[S]) -> Tuple[S, S]:
    return min(a), max(a)


# --------------------------------------------------------------------------- timelines
class Timeline:
    """Immutable step function over valid time (int microseconds)."""

    __slots__ = ("bps", "_ts")

    def __init__(self, bps: Iterable[Tuple[int, S]] = ()):
        pts = sorted(((int(t), S.parse(s)) for t, s in bps), key=lambda p: p[0])  # stable
        dedup: List[Tuple[int, S]] = []
        for t, s in pts:
            if dedup and dedup[-1][0] == t:
                dedup[-1] = (t, s)  # later insertion at the same instant wins
            else:
                dedup.append((t, s))
        merged: List[Tuple[int, S]] = []
        for t, s in dedup:
            if not merged or merged[-1][1] != s:
                merged.append((t, s))
        self.bps: Tuple[Tuple[int, S], ...] = tuple(merged)
        self._ts = [t for t, _ in self.bps]

    def state_at(self, t: int) -> S:
        i = bisect_right(self._ts, t) - 1
        return self.bps[i][1] if i >= 0 else S.UNKNOWN

    def next_change_after(self, t: int):
        i = bisect_right(self._ts, t)
        return self.bps[i][0] if i < len(self.bps) else None

    def clip(self, t0: int) -> "Timeline":
        return Timeline([(t0, self.state_at(t0))] + [(t, s) for t, s in self.bps if t > t0])

    def to_list(self) -> List[dict]:
        return [{"from": fmt_instant(t), "state": s.name} for t, s in self.bps]

    @staticmethod
    def from_list(rows: Sequence[dict]) -> "Timeline":
        from .canon import parse_instant
        return Timeline([(parse_instant(r["from"]), S.parse(r["state"])) for r in rows])

    @staticmethod
    def combine(tls: Sequence["Timeline"], fn: Callable[[List[S]], S], extra_times: Iterable[int] = ()) -> "Timeline":
        times = sorted({t for tl in tls for t in tl._ts} | set(extra_times))
        return Timeline([(t, fn([tl.state_at(t) for tl in tls])) for t in times])

    def __eq__(self, other) -> bool:
        return isinstance(other, Timeline) and self.bps == other.bps

    def __repr__(self) -> str:
        return f"Timeline({[(fmt_instant(t), s.name) for t, s in self.bps]})"


def cap_timeline(points: Sequence[Tuple[int, S]]) -> Timeline:
    """Cap that is HEALTHY (no restriction) until each ``(t, state)`` takes effect."""
    return Timeline([(NEG_INF, S.HEALTHY)] + list(points))


def tl_comb(op: str, k: int, items: Sequence[Timeline]) -> Timeline:
    return Timeline.combine(items, lambda st: state_comb(op, k, st))
