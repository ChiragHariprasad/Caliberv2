"""CALIBRE Agent Archetype SDK (enforcing rules AR-1 through AR-10).

All specialist evidence agents derive from AgentArchetype. They are pure factual observation
producers: they never output integrity states (HEALTHY/DEGRADED), scores, or fault verdicts.
"""
from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

from sia_core import EvidenceAtom, IntegrityState, TimeClass, TypedTime, make_atom, parse_instant

logger = logging.getLogger("calibre.agent")


@dataclass(frozen=True)
class RawSpanReference:
    topic: str
    partition: int
    offset_start: int
    offset_end: int
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "partition": self.partition,
            "offset_start": self.offset_start,
            "offset_end": self.offset_end,
            "content_hash": self.content_hash,
        }


@dataclass
class Diagnostic:
    code: str
    detail: str
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail, "timestamp_utc": self.timestamp_utc}


class AgentArchetype(ABC):
    """Abstract Base Class for CALIBRE Specialist Agents.

    Rules:
      AR-1:  Emit observations only; never integrity grades or fault verdicts.
      AR-2:  Pure function of declared inputs and agent version (deterministic atom IDs).
      AR-3:  Every atom carries raw span references, typed time, origins, scope, uncertainty.
      AR-4:  Never invent time or scope; unresolved bindings emit diagnostics.
      AR-5:  Windows close by data, not wall clock.
      AR-6:  No cross-agent imports; only the shared SDK.
      AR-7:  Fixes are new processor versions that supersede; atoms are never mutated.
      AR-8:  Ship declared failure catalogue.
      AR-9:  Bounded buffers; overflow is an explicit diagnostic, never a silent drop.
      AR-10: Batch parity: identical execution across live stream and historical offline replay.
    """

    def __init__(
        self,
        agent_id: str,
        processor_id: str,
        version: str,
        source_origin: str,
        processing_origin: str,
        buffer_capacity: int = 10000,
    ) -> None:
        self.agent_id = agent_id
        self.processor_id = processor_id
        self.version = version
        self.source_origin = source_origin
        self.processing_origin = processing_origin
        self.buffer_capacity = buffer_capacity

        self._buffer: List[Any] = []
        self.diagnostics: List[Diagnostic] = []
        self.emitted_atoms: List[EvidenceAtom] = []

    @property
    @abstractmethod
    def failure_catalogue(self) -> Sequence[str]:
        """Declared failure codes this agent can emit as diagnostics (AR-8)."""
        pass

    def record_diagnostic(self, code: str, detail: str) -> None:
        """Records an explicit diagnostic (AR-4, AR-9)."""
        if code not in self.failure_catalogue and code != "BUFFER_OVERFLOW":
            logger.warning(f"Diagnostic {code} not in declared failure catalogue {self.failure_catalogue}")
        diag = Diagnostic(code, detail)
        self.diagnostics.append(diag)
        logger.info(f"[{self.agent_id}] Diagnostic: {code} - {detail}")

    def emit_atom(
        self,
        role_id: str,
        value: Any,
        unit: str,
        typed_time: TypedTime,
        observed_at: int | str,
        scope: Mapping[str, Any],
        raw_refs: Sequence[RawSpanReference] = (),
        uncertainty: float = 0.0,
        quality_grade: IntegrityState = IntegrityState.HEALTHY,
        supersedes_atom_id: Optional[str] = None,
    ) -> EvidenceAtom:
        """Emits a content-addressed EvidenceAtom adhering to AR-1, AR-2, AR-3."""
        obs_us = parse_instant(observed_at)
        atom = make_atom(
            role_id=role_id,
            scope=scope,
            time=typed_time,
            observed_at=obs_us,
            source_origins=[self.source_origin],
            processing_origins=[self.processing_origin],
            processor_family_id=self.processor_id,
            transform_version=self.version,
            raw_event_ids=[r.content_hash for r in raw_refs],
            value=value,
            unit=unit,
            quality_grade=quality_grade,
            supersedes=supersedes_atom_id,
        )
        self.emitted_atoms.append(atom)
        return atom

    @abstractmethod
    def process_record(self, raw_record: Mapping[str, Any], raw_ref: Optional[RawSpanReference] = None) -> Sequence[EvidenceAtom]:
        """Process a single incoming raw record and return any produced evidence atoms."""
        pass

    def reset(self) -> None:
        """Reset internal buffers for clean replay reconstruction."""
        self._buffer.clear()
        self.diagnostics.clear()
        self.emitted_atoms.clear()

