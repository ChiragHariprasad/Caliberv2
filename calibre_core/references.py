"""Effective-dated references for rule regimes, layouts, and calibrations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .durable import DomainPack


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("effective dates must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class EffectiveReference:
    reference_id: str
    kind: str
    scope: Mapping[str, str]
    value: Any
    unit: str
    valid_from: datetime
    valid_to: datetime | None = None
    uncertainty: float | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        start = _utc(self.valid_from)
        end = _utc(self.valid_to) if self.valid_to else None
        if end is not None and end <= start:
            raise ValueError("valid_to must be after valid_from")
        if self.uncertainty is not None and self.uncertainty < 0:
            raise ValueError("reference uncertainty cannot be negative")

    def applies_at(self, at: datetime) -> bool:
        at = _utc(at)
        return at >= _utc(self.valid_from) and (self.valid_to is None or at < _utc(self.valid_to))


class ReferenceRegistry:
    def __init__(self, pack: DomainPack, records: Iterable[EffectiveReference] = ()) -> None:
        self.pack = pack
        self._records: list[EffectiveReference] = []
        for record in records:
            self.add(record)

    def add(self, record: EffectiveReference) -> None:
        normalized = self.pack.validate_scope(record.scope)
        if dict(record.scope) != normalized:
            raise ValueError("reference scope must use the pack's canonical field names")
        if any(item.reference_id == record.reference_id for item in self._records):
            raise ValueError(f"duplicate reference id: {record.reference_id}")
        self._records.append(record)

    def resolve(self, kind: str, scope: Mapping[str, str], at: datetime) -> EffectiveReference | None:
        normalized = self.pack.validate_scope(scope)
        matches = [
            item for item in self._records
            if item.kind == kind and item.applies_at(at)
            and all(normalized.get(k) == v for k, v in item.scope.items())
        ]
        if len(matches) > 1:
            raise ValueError(f"ambiguous effective reference for {kind} at {at.isoformat()}")
        return matches[0] if matches else None
