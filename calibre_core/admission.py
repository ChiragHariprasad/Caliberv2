"""CALIBRE Admission Log Engine conforming to LOG v1.0 specification.

Implements deterministic ordered log writing, verification, hash-chaining,
and replaying into the Scoped Integrity Algebra (SIA) IntegrityEngine.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from calibre_core.durable import canonical_json, digest_bytes, validate_digest
from sia_core_v3.sia_core.engine import IntegrityEngine, parse_contract
from sia_core_v3.sia_core.model import EvidenceAtom, GuardFact, ReferenceFact

GENESIS_DIGEST = "sha256:" + "0" * 64
VALID_ENTRY_TYPES = frozenset({"ATOM", "FACT", "GUARD", "TICK", "CONFIG", "SCHEDULE", "VOID"})


@dataclass(frozen=True)
class AdmissionEntry:
    """A single deterministic admission log entry conforming to LOG v1.0."""

    seq: int
    knowledge_time: int
    entry_type: str
    payload: dict[str, Any]
    entry_digest: str
    previous_digest: str = GENESIS_DIGEST

    def __post_init__(self) -> None:
        if self.seq < 0:
            raise ValueError(f"Sequence number must be non-negative, got {self.seq}")
        if self.entry_type not in VALID_ENTRY_TYPES:
            raise ValueError(f"Invalid entry_type '{self.entry_type}'; must be one of {sorted(VALID_ENTRY_TYPES)}")
        validate_digest(self.entry_digest)
        validate_digest(self.previous_digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "knowledge_time": self.knowledge_time,
            "entry_type": self.entry_type,
            "payload": self.payload,
            "entry_digest": self.entry_digest,
            "previous_digest": self.previous_digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdmissionEntry:
        return cls(
            seq=int(data["seq"]),
            knowledge_time=int(data["knowledge_time"]),
            entry_type=str(data["entry_type"]),
            payload=dict(data["payload"]),
            entry_digest=str(data["entry_digest"]),
            previous_digest=str(data.get("previous_digest", GENESIS_DIGEST)),
        )


def compute_entry_digest(seq: int, knowledge_time: int, entry_type: str, payload: dict[str, Any], previous_digest: str) -> str:
    """Calculates canonical SHA-256 digest over entry fields."""
    canonical_body = {
        "seq": seq,
        "knowledge_time": knowledge_time,
        "entry_type": entry_type,
        "payload": payload,
        "previous_digest": previous_digest,
    }
    return digest_bytes(canonical_json(canonical_body))


class AdmissionLogWriter:
    """Appends sequenced, hash-chained admission entries conforming to LOG v1.0."""

    def __init__(self, output_path: str | Path | None = None, initial_seq: int = 0, initial_digest: str = GENESIS_DIGEST) -> None:
        self.output_path = Path(output_path) if output_path else None
        self._next_seq = initial_seq
        self._last_kt = 0
        self._last_digest = initial_digest
        self._entries: list[AdmissionEntry] = []

        if self.output_path:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def entries(self) -> list[AdmissionEntry]:
        return list(self._entries)

    @property
    def latest_digest(self) -> str:
        return self._last_digest

    @property
    def next_seq(self) -> int:
        return self._next_seq

    def admit(self, entry_type: str, payload: dict[str, Any], knowledge_time: int) -> AdmissionEntry:
        """Admit a raw entry ensuring strict monotonicity and hash chaining."""
        kt = int(knowledge_time)
        if kt < self._last_kt:
            raise ValueError(f"Knowledge time regression: {kt} < {self._last_kt}")

        seq = self._next_seq
        entry_digest = compute_entry_digest(seq, kt, entry_type, payload, self._last_digest)

        entry = AdmissionEntry(
            seq=seq,
            knowledge_time=kt,
            entry_type=entry_type,
            payload=payload,
            entry_digest=entry_digest,
            previous_digest=self._last_digest,
        )

        self._entries.append(entry)
        self._next_seq += 1
        self._last_kt = kt
        self._last_digest = entry_digest

        if self.output_path:
            with self.output_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        return entry

    def admit_atom(self, atom: EvidenceAtom | dict[str, Any], knowledge_time: int) -> AdmissionEntry:
        payload = atom if isinstance(atom, dict) else asdict(atom)
        return self.admit("ATOM", payload, knowledge_time)

    def admit_fact(self, fact: ReferenceFact | dict[str, Any], knowledge_time: int) -> AdmissionEntry:
        payload = fact if isinstance(fact, dict) else asdict(fact)
        return self.admit("FACT", payload, knowledge_time)

    def admit_guard(self, guard: GuardFact | dict[str, Any], knowledge_time: int) -> AdmissionEntry:
        payload = guard if isinstance(guard, dict) else asdict(guard)
        return self.admit("GUARD", payload, knowledge_time)

    def admit_tick(self, knowledge_time: int) -> AdmissionEntry:
        return self.admit("TICK", {"tick_kt": int(knowledge_time)}, knowledge_time)

    def admit_config(self, contract_dict: dict[str, Any], knowledge_time: int) -> AdmissionEntry:
        return self.admit("CONFIG", contract_dict, knowledge_time)

    def admit_schedule(self, contract_id: str, scope: Mapping[str, Any], opens_at: int, knowledge_time: int) -> AdmissionEntry:
        payload = {
            "contract_id": contract_id,
            "scope": dict(scope),
            "opens_at": opens_at,
        }
        return self.admit("SCHEDULE", payload, knowledge_time)

    def admit_void(self, instance_id: str, reason: str, knowledge_time: int, witness_code: str = "VOIDED", detail: str = "") -> AdmissionEntry:
        payload = {
            "instance_id": instance_id,
            "reason": reason,
            "witness_code": witness_code,
            "detail": detail,
        }
        return self.admit("VOID", payload, knowledge_time)


class AdmissionLogReader:
    """Reads, verifies, and replays admission log entries into SIA IntegrityEngine."""

    def __init__(self, entries_or_path: Sequence[AdmissionEntry | dict[str, Any]] | Path | str) -> None:
        if isinstance(entries_or_path, (str, Path)):
            path = Path(entries_or_path)
            if not path.exists():
                raise FileNotFoundError(f"Admission log file not found: {path}")
            raw_entries = []
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        raw_entries.append(json.loads(line))
            self._raw = raw_entries
        else:
            self._raw = list(entries_or_path)

    def verify(self) -> list[AdmissionEntry]:
        """Validates sequence continuity, monotonic knowledge time, digests, and hash chaining."""
        verified: list[AdmissionEntry] = []
        expected_seq = 0
        last_kt = 0
        expected_prev_digest = GENESIS_DIGEST

        for item in self._raw:
            entry = item if isinstance(item, AdmissionEntry) else AdmissionEntry.from_dict(item)

            if entry.seq != expected_seq:
                raise ValueError(f"Sequence gap or regression: expected {expected_seq}, got {entry.seq}")
            if entry.knowledge_time < last_kt:
                raise ValueError(f"Knowledge time regression at seq {entry.seq}: {entry.knowledge_time} < {last_kt}")
            if entry.previous_digest != expected_prev_digest:
                raise ValueError(f"Hash chain broken at seq {entry.seq}: expected {expected_prev_digest}, got {entry.previous_digest}")

            recomputed_digest = compute_entry_digest(
                entry.seq, entry.knowledge_time, entry.entry_type, entry.payload, entry.previous_digest
            )
            if entry.entry_digest != recomputed_digest:
                raise ValueError(f"Corrupt digest at seq {entry.seq}: {entry.entry_digest} != {recomputed_digest}")

            verified.append(entry)
            expected_seq += 1
            last_kt = entry.knowledge_time
            expected_prev_digest = entry.entry_digest

        return verified

    def replay(self, engine: IntegrityEngine) -> list[Any]:
        """Deterministically replays the log entries through the given SIA IntegrityEngine.

        Returns all assessments generated during replay.
        """
        entries = self.verify()
        assessments: list[Any] = []

        for entry in entries:
            t = entry.entry_type
            p = entry.payload
            kt = entry.knowledge_time

            if t == "CONFIG":
                contract = parse_contract(p)
                engine.register_contract(contract)

            elif t == "SCHEDULE":
                engine.open_decision(
                    contract_id=p["contract_id"],
                    scope=p["scope"],
                    opens_at=p["opens_at"],
                    known_at=kt,
                )

            elif t == "ATOM":
                # Convert dict back to EvidenceAtom if needed
                atom = p if isinstance(p, EvidenceAtom) else EvidenceAtom(**p)
                engine.admit_atom(atom, knowledge_time=kt)

            elif t == "FACT":
                fact = p if isinstance(p, ReferenceFact) else ReferenceFact(**p)
                engine.admit_fact(fact, knowledge_time=kt)

            elif t == "GUARD":
                guard = p if isinstance(p, GuardFact) else GuardFact(**p)
                engine.admit_guard(guard, knowledge_time=kt)

            elif t == "VOID":
                assm = engine.void_decision(
                    instance_id=p["instance_id"],
                    K=kt,
                    reason=p.get("reason", "SESSION_EVENT"),
                    witness_code=p.get("witness_code", "VOIDED"),
                    detail=p.get("detail", ""),
                )
                assessments.append(assm)

            elif t == "TICK":
                res = engine.tick(kt)
                if res:
                    assessments.extend(res)

        return assessments
