"""Population-level calibration monitor (systemic-fault detector).

Decision-scope locality (one decision's fault must not poison unrelated decisions) has a blind
spot: a *systematic* calibration error - e.g. a wrongly configured loop distance inflating every
pit-lane speed by ~2.9% - is visible only ACROSS many decisions. This monitor turns a population
of (reference, measured) pairs into a session-scoped ``calibration_bias`` ReferenceFact. Contracts
that care list it as a reference role; contracts that do not, are untouched (locality preserved).

Deterministic: robust median of measured/reference ratios in exact Decimal arithmetic.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence, Tuple

from .algebra import IntegrityState as S
from .model import ReferenceFact, make_fact


def estimate_bias(pairs: Sequence[Tuple[Any, Any]], tolerance: Any, min_samples: int, scope: Mapping[str, Any],
                  origins: Sequence[str], fact_type: str = "calibration_bias") -> ReferenceFact:
    tol = Decimal(str(tolerance))
    ratios = sorted(Decimal(str(m)) / Decimal(str(r)) for r, m in pairs if Decimal(str(r)) != 0)
    n = len(ratios)
    if n < min_samples:
        return make_fact(fact_type, scope, 0.0, origins, unit="ratio", grade=S.UNKNOWN,
                         note=f"insufficient samples n={n} < {min_samples}")
    med = ratios[n // 2] if n % 2 else (ratios[n // 2 - 1] + ratios[n // 2]) / 2
    bias = med - 1
    flagged = sum(1 for r in ratios if abs(r - 1) > tol)
    ok = abs(bias) <= tol
    note = f"median measured/reference={med:.6f} bias={bias:+.4%} n={n} flagged={flagged}"
    return make_fact(fact_type, scope, float(round(bias, 6)), origins, unit="ratio",
                     grade=S.HEALTHY if ok else S.SUSPECT, note=note)
