"""SQLite WAL persistence layer for SIA Core v3.

Persists contracts, admitted atoms/facts/guards, decision instances,
append-only hash-chained assessments, and pre-admission quarantined records
under SQLite WAL mode so restarts recover ledger state and verify hash chains
with bit-for-bit fidelity.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from .algebra import IntegrityState as S, Timeline
from .canon import NEG_INF, parse_instant
from .model import (
    DecisionInstance,
    EvidenceAtom,
    GuardFact,
    OriginRegistry,
    ReferenceFact,
    TimeClass,
    TypedTime,
    norm_scope,
)
from .verdict import Assessment

if TYPE_CHECKING:
    from .contract import EngineConfig
    from .engine import IntegrityEngine


class SIAWALStore:
    """Durable SQLite WAL backend for SIA IntegrityEngine."""

    def __init__(self, db_path: str | Path, session_id: str = "default") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self._closed: bool = False
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sia_contracts (
                    session_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    contract_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, contract_id, version, epoch)
                );
                CREATE TABLE IF NOT EXISTS sia_atoms (
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    atom_id TEXT NOT NULL,
                    kt INTEGER NOT NULL,
                    atom_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, atom_id)
                );
                CREATE TABLE IF NOT EXISTS sia_facts (
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    fact_id TEXT NOT NULL,
                    kt INTEGER NOT NULL,
                    fact_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, fact_id)
                );
                CREATE TABLE IF NOT EXISTS sia_guards (
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    guard_id TEXT NOT NULL,
                    kt INTEGER NOT NULL,
                    guard_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, guard_id)
                );
                CREATE TABLE IF NOT EXISTS sia_decisions (
                    session_id TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    scope_json TEXT NOT NULL,
                    opens_at INTEGER NOT NULL,
                    registered_at INTEGER NOT NULL,
                    auto INTEGER NOT NULL,
                    PRIMARY KEY (session_id, instance_id)
                );
                CREATE TABLE IF NOT EXISTS sia_assessments (
                    session_id TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    revision_number INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    previous_record_hash TEXT NOT NULL,
                    knowledge_time INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    evaluated_at INTEGER NOT NULL,
                    PRIMARY KEY (session_id, instance_id, revision_number)
                );
                CREATE TABLE IF NOT EXISTS sia_quarantine (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    item_kind TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    decision_instance_id TEXT NOT NULL,
                    kt INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def clear_session(self, session_id: Optional[str] = None) -> None:
        sid = session_id or self.session_id
        with self._conn:
            for tbl in (
                "sia_contracts",
                "sia_atoms",
                "sia_facts",
                "sia_guards",
                "sia_decisions",
                "sia_assessments",
                "sia_quarantine",
            ):
                self._conn.execute(f"DELETE FROM {tbl} WHERE session_id = ?", (sid,))

    def save_contract(self, contract_dict: dict[str, Any]) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO sia_contracts (session_id, contract_id, version, epoch, contract_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.session_id,
                    contract_dict["contract_id"],
                    str(contract_dict["version"]),
                    int(contract_dict.get("epoch", 1)),
                    json.dumps(contract_dict),
                ),
            )

    def save_atom(self, atom: EvidenceAtom, kt: int, seq: int) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO sia_atoms (session_id, seq, atom_id, kt, atom_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.session_id, seq, atom.atom_id, kt, json.dumps(atom.to_dict())),
            )

    def save_fact(self, fact: ReferenceFact, kt: int, seq: int) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO sia_facts (session_id, seq, fact_id, kt, fact_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.session_id, seq, fact.fact_id, kt, json.dumps(fact.to_dict())),
            )

    def save_guard(self, guard: GuardFact, kt: int, seq: int) -> None:
        d = {**guard.canonical(), "guard_id": guard.guard_id}
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO sia_guards (session_id, seq, guard_id, kt, guard_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.session_id, seq, guard.guard_id, kt, json.dumps(d)),
            )

    def save_decision(self, inst: DecisionInstance) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO sia_decisions
                (session_id, instance_id, contract_id, scope_json, opens_at, registered_at, auto)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.session_id,
                    inst.instance_id,
                    inst.contract_id,
                    json.dumps(inst.scope_dict),
                    inst.opens_at,
                    inst.registered_at,
                    1 if inst.auto else 0,
                ),
            )

    def save_assessment(self, a: Assessment) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO sia_assessments
                (session_id, instance_id, revision_number, content_json, content_hash,
                 previous_record_hash, knowledge_time, reason, record_hash, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.session_id,
                    a.decision_instance_id,
                    a.revision_number,
                    json.dumps(a.content),
                    a.content_hash,
                    a.previous_record_hash,
                    a.knowledge_time,
                    a.reason,
                    a.record_hash,
                    a.evaluated_at,
                ),
            )

    def save_quarantine(
        self,
        item_kind: str,
        item_id: str,
        decision_instance_id: str,
        kt: int,
        code: str,
        payload: dict[str, Any],
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sia_quarantine
                (session_id, item_kind, item_id, decision_instance_id, kt, code, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (self.session_id, item_kind, item_id, decision_instance_id, kt, code, json.dumps(payload)),
            )

    def load_quarantine(self) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """
            SELECT item_kind, item_id, decision_instance_id, kt, code, payload_json
            FROM sia_quarantine WHERE session_id = ? ORDER BY id ASC
            """,
            (self.session_id,),
        )
        out = []
        for kind, iid, did, kt, code, pjson in cur.fetchall():
            out.append({
                "kind": kind,
                "item_id": iid,
                "decision_instance_id": did,
                "kt": kt,
                "code": code,
                "payload": json.loads(pjson),
            })
        return out

    def load_engine(
        self,
        registry: Optional[OriginRegistry] = None,
        config: Optional[EngineConfig] = None,
    ) -> "IntegrityEngine":
        """Reconstruct a complete IntegrityEngine state & hash-chains from SQLite WAL."""
        from .engine import IntegrityEngine

        eng = IntegrityEngine(registry=registry, config=config, wal=None)

        # 1. Contracts
        cur = self._conn.execute(
            "SELECT contract_json FROM sia_contracts WHERE session_id = ? ORDER BY contract_id, epoch, version",
            (self.session_id,),
        )
        for (cjson,) in cur.fetchall():
            eng.register_contract(json.loads(cjson))

        # 2. Decisions
        cur = self._conn.execute(
            "SELECT instance_id, contract_id, scope_json, opens_at, registered_at, auto FROM sia_decisions WHERE session_id = ?",
            (self.session_id,),
        )
        for iid, cid, sjson, opens_at, reg_at, auto in cur.fetchall():
            sc = norm_scope(json.loads(sjson))
            eng.instances[iid] = DecisionInstance(iid, cid, sc, opens_at, reg_at, bool(auto))
            eng._open_instances.add(iid)

        # 3. Atoms, facts, guards ordered by seq
        max_kt = NEG_INF
        events: list[tuple[int, str, int, dict[str, Any]]] = []
        for tbl, kind, col in (
            ("sia_atoms", "atom", "atom_json"),
            ("sia_facts", "fact", "fact_json"),
            ("sia_guards", "guard", "guard_json"),
        ):
            c2 = self._conn.execute(
                f"SELECT seq, kt, {col} FROM {tbl} WHERE session_id = ?",
                (self.session_id,),
            )
            for seq, kt, raw_json in c2.fetchall():
                events.append((seq, kind, kt, json.loads(raw_json)))
        events.sort(key=lambda x: x[0])

        for _seq, kind, kt, d in events:
            max_kt = max(max_kt, kt)
            if kind == "atom":
                tinfo = d["time"]
                tt = TypedTime(int(tinfo["value"]), TimeClass(tinfo["class"]), int(tinfo.get("unc", 0)))
                atom = EvidenceAtom(
                    atom_id=d["atom_id"],
                    role_id=d["role_id"],
                    value=d["value"],
                    unit=d["unit"],
                    observed_at=parse_instant(d["observed_at"]),
                    time=tt,
                    scope=norm_scope(d["scope"]),
                    source_origins=tuple(d["source_origins"]),
                    processing_origins=tuple(d["processing_origins"]),
                    processor_family_id=d["processor_family_id"],
                    transform_version=d["transform_version"],
                    raw_event_ids=tuple(d["raw_event_ids"]),
                    quality_grade=S.parse(d["quality_grade"]),
                    supersedes=d.get("supersedes"),
                    reference_atom_ids=tuple(d.get("reference_atom_ids") or ()),
                )
                eng.ledger.admit_atom(atom, kt)
            elif kind == "fact":
                fact = ReferenceFact(
                    fact_id=d["fact_id"],
                    fact_type=d["fact_type"],
                    scope=norm_scope(d["scope"]),
                    value=d["value"],
                    unit=d["unit"],
                    grade=S.parse(d["grade"]),
                    origins=tuple(d["origins"]),
                    valid_from=None if d.get("valid_from") is None else parse_instant(d["valid_from"]),
                    valid_to=None if d.get("valid_to") is None else parse_instant(d["valid_to"]),
                    uncertainty_us=int(d.get("uncertainty_us", 0)),
                    rejection_reason=d.get("rejection_reason"),
                    supersedes=d.get("supersedes"),
                    note=d.get("note", ""),
                )
                eng.ledger.admit_fact(fact, kt)
            elif kind == "guard":
                guard = GuardFact(
                    guard_id=d["guard_id"],
                    origin=d["origin"],
                    status=d["status"],
                    detected_at=parse_instant(d["detected_at"]),
                    epoch=int(d.get("epoch", 1)),
                )
                eng.ledger.admit_guard(guard, kt)

        # 4. Assessments
        cur = self._conn.execute(
            """
            SELECT instance_id, revision_number, content_json, content_hash,
                   previous_record_hash, knowledge_time, reason, record_hash, evaluated_at
            FROM sia_assessments WHERE session_id = ?
            ORDER BY instance_id, revision_number ASC
            """,
            (self.session_id,),
        )
        for iid, rev, cjson, ch, prev, kt, reason, rh, eval_at in cur.fetchall():
            content = json.loads(cjson)
            tl = Timeline.from_list(content["validity_timeline"])
            a = Assessment(content, ch, rev, prev, kt, reason, rh, eval_at, tl)
            eng.index.append(a)
            eng._last_eval[iid] = max(eng._last_eval.get(iid, NEG_INF), eval_at)
            if content.get("finality_status") == "FINAL":
                eng._sealed[iid] = a
                eng._open_instances.discard(iid)

        # 5. Quarantine log
        for q in self.load_quarantine():
            eng.finality_violations.append({
                "decision_instance_id": q["decision_instance_id"],
                "kind": q["kind"],
                "item_id": q["item_id"],
                "knowledge_time": q["payload"].get("knowledge_time"),
                "code": q["code"],
            })
            eng.quarantined_items.append(q)

        if max_kt > NEG_INF:
            eng.ledger.advance_clock(max_kt)
        eng.wal = self
        return eng

    def sync_engine(self, eng: "IntegrityEngine") -> None:
        """Replace stored session WAL state with a full consistent snapshot of `eng` in one SQLite tx."""
        with self._conn:
            for tbl in (
                "sia_contracts",
                "sia_atoms",
                "sia_facts",
                "sia_guards",
                "sia_decisions",
                "sia_assessments",
                "sia_quarantine",
            ):
                self._conn.execute(f"DELETE FROM {tbl} WHERE session_id = ?", (self.session_id,))

            for cid, cdict in getattr(eng, "_contract_raw", {}).items():
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO sia_contracts (session_id, contract_id, version, epoch, contract_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.session_id,
                        cdict["contract_id"],
                        str(cdict["version"]),
                        int(cdict.get("epoch", 1)),
                        json.dumps(cdict),
                    ),
                )

            for inst in eng.instances.values():
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO sia_decisions
                    (session_id, instance_id, contract_id, scope_json, opens_at, registered_at, auto)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.session_id,
                        inst.instance_id,
                        inst.contract_id,
                        json.dumps(inst.scope_dict),
                        inst.opens_at,
                        inst.registered_at,
                        1 if inst.auto else 0,
                    ),
                )

            for recs in eng.ledger._atoms.values():
                for rec in recs:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO sia_atoms (session_id, seq, atom_id, kt, atom_json) VALUES (?, ?, ?, ?, ?)",
                        (self.session_id, rec.seq, rec.atom.atom_id, rec.kt, json.dumps(rec.atom.to_dict())),
                    )

            for recs in eng.ledger._facts.values():
                for rec in recs:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO sia_facts (session_id, seq, fact_id, kt, fact_json) VALUES (?, ?, ?, ?, ?)",
                        (self.session_id, rec.seq, rec.fact.fact_id, rec.kt, json.dumps(rec.fact.to_dict())),
                    )

            for rec in eng.ledger.guards:
                d = {**rec.guard.canonical(), "guard_id": rec.guard.guard_id}
                self._conn.execute(
                    "INSERT OR IGNORE INTO sia_guards (session_id, seq, guard_id, kt, guard_json) VALUES (?, ?, ?, ?, ?)",
                    (self.session_id, rec.seq, rec.guard.guard_id, rec.kt, json.dumps(d)),
                )

            for did in eng.index.decisions():
                for a in eng.index.chain(did):
                    self._conn.execute(
                        """
                        INSERT OR IGNORE INTO sia_assessments
                        (session_id, instance_id, revision_number, content_json, content_hash,
                         previous_record_hash, knowledge_time, reason, record_hash, evaluated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            self.session_id,
                            a.decision_instance_id,
                            a.revision_number,
                            json.dumps(a.content),
                            a.content_hash,
                            a.previous_record_hash,
                            a.knowledge_time,
                            a.reason,
                            a.record_hash,
                            a.evaluated_at,
                        ),
                    )

            for q in eng.quarantined_items:
                q_kt = q.get("kt")
                if q_kt is None and q.get("knowledge_time") is not None:
                    q_kt = parse_instant(q["knowledge_time"])
                self._conn.execute(
                    """
                    INSERT INTO sia_quarantine
                    (session_id, item_kind, item_id, decision_instance_id, kt, code, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.session_id,
                        q["kind"],
                        q["item_id"],
                        q["decision_instance_id"],
                        int(q_kt or 0),
                        q["code"],
                        json.dumps(q["payload"]),
                    ),
                )

    @property
    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if not self._closed:
            self._conn.close()
            self._closed = True
