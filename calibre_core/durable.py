"""Stable, dependency-free primitives for CALIBRE v4 archives and packs.

These types deliberately live outside the PULSE and SIA implementations.  They
form the small compatibility boundary that must survive runtime replacements.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from math import sqrt
from typing import Any, Mapping


CANONICALIZATION_VERSION = "jcs-rfc8785-subset/1"
_DIGEST = re.compile(r"^(sha256):([0-9a-f]{64})$")


class DataRegime(str, Enum):
    PUBLIC = "PUBLIC"
    LICENSED = "LICENSED"
    INSTITUTIONAL = "INSTITUTIONAL"
    LAB = "LAB"


class TimeScale(str, Enum):
    UTC = "UTC"
    TAI = "TAI"
    GPS = "GPS"


def canonical_json(value: Any) -> bytes:
    """Return stable JSON bytes for manifest content.

    Archive schemas reject values that cannot be represented as canonical JSON;
    callers therefore cannot accidentally hash a Python repr or a NaN.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest_bytes(content: bytes, algorithm: str = "sha256") -> str:
    if algorithm != "sha256":
        raise ValueError(f"unsupported digest algorithm: {algorithm}")
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_json(value))


def validate_digest(value: str, *, allow_legacy_bare_sha256: bool = False) -> str:
    """Validate a tagged durable digest, optionally recognizing v3 bare hashes."""
    if _DIGEST.fullmatch(value):
        return value
    if allow_legacy_bare_sha256 and re.fullmatch(r"[0-9a-f]{64}", value):
        return f"sha256:{value}"
    raise ValueError("digest must be a lowercase algorithm-tagged sha256 digest")


@dataclass(frozen=True)
class TimeScaleReference:
    scale: TimeScale
    leap_second_table_id: str
    leap_second_table_version: str

    def __post_init__(self) -> None:
        if not self.leap_second_table_id or not self.leap_second_table_version:
            raise ValueError("time scale references require a leap-second table id and version")

    def to_dict(self) -> dict[str, str]:
        return {
            "scale": self.scale.value,
            "leap_second_table_id": self.leap_second_table_id,
            "leap_second_table_version": self.leap_second_table_version,
        }


@dataclass(frozen=True)
class ThresholdWitness:
    """A policy-neutral statement of a measurement's distance from a threshold."""

    observed: float
    threshold: float
    margin: float
    combined_uncertainty: float
    classification: str

    def to_dict(self) -> dict[str, float | str]:
        return {
            "observed": self.observed,
            "threshold": self.threshold,
            "margin": self.margin,
            "combined_uncertainty": self.combined_uncertainty,
            "classification": self.classification,
        }


def threshold_witness(
    observed: float,
    threshold: float,
    *,
    observed_uncertainty: float = 0.0,
    threshold_uncertainty: float = 0.0,
) -> ThresholdWitness:
    """Report a guard-band witness without deciding any enforcement outcome.

    ``INDETERMINATE`` means the signed margin lies inside the combined
    uncertainty.  The function intentionally does not return pass/fail.
    """
    if observed_uncertainty < 0 or threshold_uncertainty < 0:
        raise ValueError("uncertainty cannot be negative")
    margin = float(observed) - float(threshold)
    uncertainty = sqrt(observed_uncertainty ** 2 + threshold_uncertainty ** 2)
    if abs(margin) <= uncertainty:
        state = "INDETERMINATE"
    elif margin > 0:
        state = "ABOVE_THRESHOLD"
    else:
        state = "BELOW_THRESHOLD"
    return ThresholdWitness(float(observed), float(threshold), margin, uncertainty, state)


@dataclass(frozen=True)
class DomainPack:
    """Versioned domain vocabulary; it prevents F1 names entering the kernel."""

    pack_id: str
    version: str
    scope_levels: tuple[str, ...]
    supported_regimes: tuple[DataRegime, ...]

    def __post_init__(self) -> None:
        if not self.pack_id or not self.version:
            raise ValueError("a domain pack requires an id and immutable version")
        if not self.scope_levels or len(set(self.scope_levels)) != len(self.scope_levels):
            raise ValueError("scope levels must be a non-empty unique hierarchy")

    def validate_scope(self, scope: Mapping[str, str]) -> dict[str, str]:
        unknown = set(scope) - set(self.scope_levels)
        if unknown:
            raise ValueError(f"scope contains fields not defined by pack {self.pack_id}: {sorted(unknown)}")
        return {level: str(scope[level]) for level in self.scope_levels if level in scope and str(scope[level])}

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "version": self.version,
            "scope_levels": list(self.scope_levels),
            "supported_regimes": [regime.value for regime in self.supported_regimes],
        }
