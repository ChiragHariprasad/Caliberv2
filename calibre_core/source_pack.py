"""Source lineage and claim limits owned by a domain pack, not the kernel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .durable import DataRegime, DomainPack


@dataclass(frozen=True)
class SourceOrigin:
    origin_id: str
    upstreams: tuple[str, ...] = ()
    approved_regimes: tuple[DataRegime, ...] = ()
    licence_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.origin_id:
            raise ValueError("source origin id is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "origin_id": self.origin_id,
            "upstreams": list(self.upstreams),
            "approved_regimes": [item.value for item in self.approved_regimes],
            "licence_reference": self.licence_reference,
        }


class SourcePack:
    """A pack-specific, inspectable source lineage graph.

    The graph is intentionally conservative: missing origin data means that
    independence is not demonstrated. A caller cannot infer independence from
    two different provider display names.
    """

    def __init__(self, pack: DomainPack, origins: Iterable[SourceOrigin]) -> None:
        self.pack = pack
        origin_items = tuple(origins)
        self._origins = {item.origin_id: item for item in origin_items}
        if not self._origins:
            raise ValueError("a source pack requires at least one origin")
        if len(self._origins) != len(origin_items):
            raise ValueError("source origin ids must be unique")
        unknown = {upstream for item in self._origins.values() for upstream in item.upstreams if upstream not in self._origins}
        if unknown:
            raise ValueError(f"source pack has unknown upstream origins: {sorted(unknown)}")
        for origin in self._origins:
            self._closure(origin)

    def _closure(self, origin_id: str, seen: set[str] | None = None) -> frozenset[str]:
        if origin_id not in self._origins:
            raise ValueError(f"unknown source origin: {origin_id}")
        seen = set() if seen is None else seen
        if origin_id in seen:
            raise ValueError(f"source lineage contains a cycle at {origin_id}")
        seen.add(origin_id)
        result = {origin_id}
        for upstream in self._origins[origin_id].upstreams:
            result.update(self._closure(upstream, seen.copy()))
        return frozenset(result)

    def is_approved(self, origin_id: str, regime: DataRegime) -> bool:
        return regime in self._origins[origin_id].approved_regimes

    def independent(self, left: str, right: str, regime: DataRegime) -> bool:
        """Return true only for approved origins with disjoint lineage."""
        return (
            regime is DataRegime.INSTITUTIONAL
            and self.is_approved(left, regime)
            and self.is_approved(right, regime)
            and self._closure(left).isdisjoint(self._closure(right))
        )

    def allowed_claims(self, regime: DataRegime) -> frozenset[str]:
        claims = {"FEED_HEALTH_MONITORING", "FORENSIC_SUPPORT"}
        if regime is DataRegime.LAB:
            return frozenset({"DEMONSTRATION", "METHOD_DEVELOPMENT"})
        if regime is DataRegime.INSTITUTIONAL:
            claims.add("INDEPENDENT_CORROBORATION_WHEN_PROVEN")
        return frozenset(claims)

    def to_dict(self) -> dict[str, object]:
        return {
            "pack": self.pack.to_dict(),
            "origins": [self._origins[key].to_dict() for key in sorted(self._origins)],
        }


def f1_reference_source_pack() -> SourcePack:
    """The reference pack makes public shared-upstream limits explicit."""
    pack = DomainPack(
        "f1-reference",
        "1.0.0",
        ("event", "session", "asset", "lap", "segment"),
        (DataRegime.PUBLIC, DataRegime.LICENSED, DataRegime.INSTITUTIONAL, DataRegime.LAB),
    )
    return SourcePack(pack, (
        SourceOrigin("F1_FOM_TIMING"),
        SourceOrigin("PITWALL", ("F1_FOM_TIMING",), (DataRegime.PUBLIC, DataRegime.LICENSED)),
        SourceOrigin("TRACINGINSIGHTS", ("F1_FOM_TIMING",), (DataRegime.PUBLIC, DataRegime.LICENSED)),
        SourceOrigin("INSTITUTIONAL_LOOP_A", (), (DataRegime.INSTITUTIONAL,), "institutional-agreement-required"),
        SourceOrigin("INSTITUTIONAL_LOOP_B", (), (DataRegime.INSTITUTIONAL,), "institutional-agreement-required"),
    ))
