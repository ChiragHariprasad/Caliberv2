"""Integrity Assessments: hash-chained revisions, bitemporal index, verification, explanation.

Two hashes, deliberately separate:

* ``content_hash`` (a.k.a. verdict hash) - identity of *what was concluded*. Depends only on
  contract + admitted evidence (+ slot-closure status). It does NOT contain the evaluation
  instant, so re-evaluating the same knowledge never mints a new verdict (fixes the old
  "every tick is a new revision" churn).
* ``record_hash`` - the hash-chain link: H(content_hash, previous_record_hash, revision_number,
  knowledge_time, reason). Tampering with any past revision breaks every later link.

Bitemporal axes: *valid time* (what the timeline says about the world) and *knowledge time*
(when the engine could have known it). ``as_of(K)`` answers "what did we conclude, as known at K?".
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from .algebra import IntegrityState as S, Timeline
from .canon import fmt_instant, parse_instant, sha256_hex

GENESIS = "0" * 64


@dataclass(frozen=True)
class Assessment:
    content: dict
    content_hash: str
    revision_number: int
    previous_record_hash: str
    knowledge_time: int
    reason: str
    record_hash: str
    evaluated_at: int = 0
    timeline: Timeline = field(default=None, compare=False, repr=False)   # parsed view of content["validity_timeline"]

    # ---- projections (not hashed)
    @property
    def decision_instance_id(self) -> str:
        return self.content["decision_instance_id"]

    @property
    def integrity_state(self) -> S:
        return self.timeline.state_at(self.evaluated_at)

    def state_at(self, valid_time) -> S:
        return self.timeline.state_at(parse_instant(valid_time))

    @property
    def finality_status(self) -> str:
        return self.content["finality_status"]

    @property
    def resolution_maturity(self) -> str:
        return self.content["resolution_maturity"]

    @property
    def decision_maturity(self) -> str:
        if self.finality_status == "FINAL":
            return "FINAL"
        return "REVISED" if self.revision_number > 1 else "PROVISIONAL"

    @property
    def witnesses(self) -> List[dict]:
        return self.content["witnesses"]

    @property
    def next_transition_at(self) -> Optional[int]:
        return self.timeline.next_change_after(self.evaluated_at)

    def lease_until(self, max_lease_us: int = 30_000_000) -> Optional[int]:
        if self.finality_status == "FINAL":
            return None
        nxt = self.next_transition_at
        cap = self.evaluated_at + max_lease_us
        return cap if nxt is None else min(nxt, cap)

    def to_dict(self) -> dict:
        st = self.integrity_state
        nxt, lease = self.next_transition_at, self.lease_until()
        limiting = [n for n, r in self.content["roles"].items() if Timeline.from_list(r["timeline"]).state_at(self.evaluated_at) == st and st < S.HEALTHY]
        return {
            **self.content,
            "integrity_state": st.name,
            "evaluated_at": fmt_instant(self.evaluated_at),
            "next_transition_at": None if nxt is None else fmt_instant(nxt),
            "lease_until": None if lease is None else fmt_instant(lease),
            "primary_binding_witness": binding_witness(self.content, st),
            "witness_set": [f"{w['code']}: {w['detail']}" if not w["role"] else f"{w['code']}[{w['role']}]: {w['detail']}" for w in self.witnesses],
            "limiting_children": limiting,
            "decision_maturity": self.decision_maturity,
            "revision_number": self.revision_number,
            "revision_reason": self.reason,
            "knowledge_time": fmt_instant(self.knowledge_time),
            "previous_record_hash": self.previous_record_hash,
            "verdict_hash": self.content_hash,
            "record_hash": self.record_hash,
        }


PRECEDENCE = ["CONSTRAINT_VIOLATION", "UNRESOLVED_CONFLICT", "DIAGNOSIS_AMBIGUOUS", "FAULT_BUDGET_EXCEEDED", "INSUFFICIENT_CORROBORATION",
              "INSUFFICIENT_RESILIENCE", "COMMON_CAUSE_EXPOSURE", "AMBIGUOUS_REFERENCE_FACT", "REFERENCE_FACT_GRADE", "MISSING_REFERENCE_FACT",
              "ILLEGAL_TIME_CLASS", "TIME_BASIS_MISMATCH", "CONSTRAINT_UNEVALUABLE", "LOW_QUALITY_EVIDENCE", "INADMISSIBLE_ORIGIN",
              "SEARCH_BUDGET_EXCEEDED", "FUTURE_DATED_OBSERVATION", "INVALID_REFERENCE_FACT", "EXCLUDED_FAULTY_ORIGIN", "LATE_EVIDENCE_ADMITTED"]


def binding_witness(content: dict, state: S) -> str:
    ws = content["witnesses"]
    if state == S.HEALTHY or not ws:
        if state == S.HEALTHY:
            roles = ", ".join(sorted(content["roles"]))
            return f"MUTUAL_AGREEMENT_VALIDATED: roles=[{roles}]"
    for code in PRECEDENCE:
        for w in ws:
            if w["code"] == code:
                return f"{code}: {w['detail']}"
    return ws[0]["code"] + ": " + ws[0]["detail"] if ws else "NO_WITNESS"


# --------------------------------------------------------------------------- chain
def make_record(content: dict, revision: int, prev_record_hash: str, knowledge_time: int, reason: str) -> Tuple[str, str]:
    ch = sha256_hex(content)
    rh = sha256_hex({"content_hash": ch, "previous_record_hash": prev_record_hash, "revision_number": revision,
                     "knowledge_time": fmt_instant(knowledge_time), "reason": reason})
    return ch, rh


def verify_chain(chain: Sequence[Assessment]) -> Tuple[bool, str]:
    prev, last_kt = GENESIS, None
    for i, a in enumerate(chain, start=1):
        if a.revision_number != i:
            return False, f"revision numbering broken at position {i}"
        if a.previous_record_hash != prev:
            return False, f"previous_record_hash link broken at revision {i}"
        ch, rh = make_record(a.content, a.revision_number, a.previous_record_hash, a.knowledge_time, a.reason)
        if ch != a.content_hash:
            return False, f"content tampered at revision {i}"
        if rh != a.record_hash:
            return False, f"record hash mismatch at revision {i}"
        if last_kt is not None and a.knowledge_time < last_kt:
            return False, f"knowledge_time regressed at revision {i}"
        prev, last_kt = a.record_hash, a.knowledge_time
    return True, "OK"


class BitemporalIndex:
    """Append-only index: (decision, knowledge_time) -> revision; valid-time lookups via the revision's timeline."""

    def __init__(self) -> None:
        self._chains: Dict[str, List[Assessment]] = {}

    def append(self, a: Assessment) -> None:
        self._chains.setdefault(a.decision_instance_id, []).append(a)

    def chain(self, decision_id: str) -> List[Assessment]:
        return list(self._chains.get(decision_id, []))

    def head(self, decision_id: str) -> Optional[Assessment]:
        c = self._chains.get(decision_id)
        return c[-1] if c else None

    def as_of(self, decision_id: str, knowledge_time) -> Optional[Assessment]:
        """What did we conclude about D, as known at K? (latest revision with knowledge_time <= K)"""
        k = parse_instant(knowledge_time)
        cands = [a for a in self._chains.get(decision_id, []) if a.knowledge_time <= k]
        return cands[-1] if cands else None

    def state_as_of(self, decision_id: str, valid_time, knowledge_time) -> Optional[S]:
        a = self.as_of(decision_id, knowledge_time)
        return None if a is None else a.state_at(valid_time)

    def decisions(self) -> List[str]:
        return sorted(self._chains)


# --------------------------------------------------------------------------- explanation
def revision_diff(prev: Assessment, new: Assessment) -> List[str]:
    out = []
    for key in ("validity_timeline", "resolution_maturity", "finality_status", "diagnosis", "resilience", "limitations", "witnesses", "constraints"):
        if prev.content.get(key) != new.content.get(key):
            out.append(key)
    for n in new.content["roles"]:
        if prev.content["roles"].get(n) != new.content["roles"][n]:
            out.append(f"roles.{n}")
    return out


def explain(a: Assessment) -> str:
    """Deterministic, template-based explanation (no LLM)."""
    d, K = a.to_dict(), a.evaluated_at
    st = a.integrity_state
    lines = [f"DECISION {d['decision_instance_id']}  ->  {st.name}   (as of {fmt_instant(K)})",
             f"  contract {d['contract']['id']} v{d['contract']['version']} epoch {d['contract']['epoch']}  |  maturity={d['resolution_maturity']}  finality={d['finality_status']}  revision={a.revision_number} ({a.reason})",
             f"  why: {d['primary_binding_witness']}"]
    lines.append("  roles:")
    for n, r in sorted(d["roles"].items()):
        rs = Timeline.from_list(r["timeline"]).state_at(K)
        note = ""
        if not r["has_evidence"]:
            dl = parse_instant(r["deadline"])
            note = " - slot deadline passed with no usable evidence" if K >= dl else " - waiting for evidence"
        elif r["latest_observed_at"] and rs < S.HEALTHY and not any(w["role"] == n for w in d["witnesses"]):
            note = f" - freshness horizon passed (last observation {r['latest_observed_at']})"
        lines.append(f"    - {n} [{r['kind']}]: {rs.name}  source_depth={r['source_depth']} processing_depth={r['processing_depth']}{note}")
    if d["constraints"]:
        lines.append("  constraints:")
        for i, c in sorted(d["constraints"].items()):
            lines.append(f"    - {i}: {Timeline.from_list(c['timeline']).state_at(K).name}")
    dg = d["diagnosis"]
    if dg["result"] != "NONE":
        lines.append(f"  diagnosis: {dg['result']} excluded_items={[x[:10] for x in dg['excluded_items']]} minimal={dg['minimal_diagnoses']}")
    rs = d["resilience"]
    if rs["profile"]:
        lines.append(f"  resilience: profile={rs['profile']} critical_origins={rs['critical_origins']} (required k={rs['required_k']})")
    if d["witnesses"]:
        lines.append("  witnesses:")
        for w in d["witnesses"]:
            lines.append(f"    * {w['code']}" + (f" [{w['role']}]" if w["role"] else "") + f": {w['detail']}")
    if d["limitations"]:
        lines.append("  limitations:")
        lines += [f"    ! {x}" for x in d["limitations"]]
    lines.append(f"  envelope: lower={d['envelope']['lower']} upper={d['envelope']['upper']} alternatives={d['envelope']['alternatives']}")
    if d["next_transition_at"]:
        lines.append(f"  next state change: {d['next_transition_at']}   lease_until: {d['lease_until']}")
    return "\n".join(lines)
