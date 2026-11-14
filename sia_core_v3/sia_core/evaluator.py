"""Pure, deterministic decision evaluator.

``evaluate_decision(contract, instance, ledger, registry, cfg, K)`` is a function of
(contract, admitted evidence with knowledge_time <= K, K) only. It reads no clock, does no I/O.

Pipeline (all inside one decision scope):
  1. role leaves     - scope select, supersession, typed-time resolution, freshness/slot timelines,
                       agreement + origin-disjoint corroboration (two axes)
  2. constraints     - cross-role relations (bounds / abs_diff / ratio / linear / interval)
  3. diagnosis       - conflicts from roles AND constraints -> admissible fault hypotheses over
                       origin tokens; exclude only what is in EVERY minimal diagnosis
  4. resilience      - "possible worlds" in which origins are lost: critical origins, common-cause
                       exposure, fault tolerance k  (the entanglement layer)
  5. envelope        - superposition of what open slots may still collapse to; maturity/finality
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from .algebra import (FULL, IntegrityState as S, Timeline, envelope, set_and, set_comb, tl_comb)
from .canon import NEG_INF, fmt_instant, sec_to_us, us_to_sec
from .contract import ConstraintSpec, Contract, RoleSpec, fold
from .ledger import AtomRec, FactRec, Ledger
from .model import DecisionInstance, OriginRegistry, scope_covers, scope_in
from .timeclass import TimeClass, TypedTime, resolve_time

Witness = Tuple[str, str, str]  # (code, role, detail)


@dataclass(frozen=True)
class EngineConfig:
    M_max: int = 12                       # support-search budget per role (distinct origin groups)
    max_lease_us: int = 30_000_000
    clock_skew_us: int = 5_000_000
    resilience_cap_k: int = 2
    universe_cap: int = 14                # max dependency tokens enumerated for k>=2 / diagnosis
    diagnosis_enum_cap: int = 20000
    envelope_cap: int = 20000
    auto_open: bool = True


# =========================================================================== helpers
@dataclass
class _Obs:
    oid: str
    value: Any
    deps: FrozenSet[str]
    src: FrozenSet[str]
    proc: FrozenSet[str]
    obs_at: int
    grade: S
    kt: int
    refs: Tuple[str, ...] = ()


@dataclass
class Edge:
    deps: FrozenSet[str]
    detail: str
    ids: Tuple[str, ...]


@dataclass
class RoleResult:
    name: str
    kind: str
    timeline: Timeline
    state_k: S
    closed: bool
    deadline: int
    cutoff: int
    start: int
    possible: FrozenSet[S]
    has_evidence: bool = False
    support_ids: Tuple[str, ...] = ()
    ref_ids: Tuple[str, ...] = ()
    deps: FrozenSet[str] = frozenset()
    source_depth: int = 0
    processing_depth: int = 0
    witnesses: List[Witness] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    rep: Optional[_Obs] = None
    rep_time_us: Optional[int] = None
    latest_obs: Optional[int] = None
    obs: List[_Obs] = field(default_factory=list)


@dataclass
class ConstraintResult:
    id: str
    timeline: Timeline
    state_k: S
    closed: bool
    possible: FrozenSet[S]
    start: int
    witnesses: List[Witness] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)


def _vkey(v: str):
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in str(v).split("."))


def _num(v) -> Optional[Decimal]:
    if isinstance(v, bool):
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def _agree(a, b, metric: str, tol: Decimal) -> bool:
    if metric == "discrete_equality":
        return str(a) == str(b)
    da, db = _num(a), _num(b)
    if da is None or db is None:
        return str(a) == str(b)
    diff = abs(da - db)
    if metric == "abs_diff":
        return diff <= tol
    denom = max(abs(da), abs(db))
    return True if denom == 0 else diff / denom <= tol


def _cliques(adj: List[FrozenSet[int]], n: int) -> List[FrozenSet[int]]:
    out: List[FrozenSet[int]] = []

    def bk(r, p, x):
        if not p and not x:
            out.append(r)
            return
        piv = max(p | x, key=lambda u: (len(adj[u] & p), -u))
        for v in sorted(p - adj[piv]):
            bk(r | {v}, p & adj[v], x & adj[v])
            p = p - {v}
            x = x | {v}

    bk(frozenset(), frozenset(range(n)), frozenset())
    return out


def _depth(obs: List[_Obs], agree: List[List[bool]], axis: str) -> int:
    n = len(obs)
    if n == 0:
        return 0
    sets = [(o.src if axis == "src" else o.proc) or frozenset({"?"}) for o in obs]   # unknown lineage is NOT independent
    adj = [frozenset(j for j in range(n) if j != i and agree[i][j] and sets[i].isdisjoint(sets[j])) for i in range(n)]
    return max(len(c) for c in _cliques(adj, n)) - 1


def _supersede_atoms(recs: List[AtomRec]) -> List[AtomRec]:
    sup = {r.atom.supersedes for r in recs if r.atom.supersedes}
    best: Dict[tuple, AtomRec] = {}
    for r in recs:
        if r.atom.atom_id in sup:
            continue
        a = r.atom
        key = (a.raw_event_ids, a.role_id, a.processor_family_id)
        cur = best.get(key)
        if cur is None or (_vkey(a.transform_version), a.atom_id) > (_vkey(cur.atom.transform_version), cur.atom.atom_id):
            best[key] = r
    return list(best.values())


def _supersede_facts(recs: List[FactRec]) -> List[FactRec]:
    sup = {r.fact.supersedes for r in recs if r.fact.supersedes}
    return [r for r in recs if r.fact.fact_id not in sup]


# =========================================================================== context
class _Ctx:
    def __init__(self, c: Contract, inst: DecisionInstance, ledger: Ledger, reg: OriginRegistry,
                 cfg: EngineConfig, K: int, removed: FrozenSet[str], collect: bool, excl_ids: FrozenSet[str] = frozenset()):
        self.c, self.inst, self.ledger, self.reg, self.cfg, self.K = c, inst, ledger, reg, cfg, K
        self.removed, self.collect, self.excl_ids = removed, collect, excl_ids
        self.scope = inst.scope_dict
        self.frontier = inst.registered_at
        self._stalled: Optional[Dict[str, int]] = None

    def note_kt(self, kt: int) -> None:
        if self.collect and kt > self.frontier:
            self.frontier = kt

    def stalled(self) -> Dict[str, int]:
        if self._stalled is None:
            latest: Dict[str, tuple] = {}
            for g in self.ledger.guards:
                if g.kt <= self.K:
                    key = (g.guard.epoch, g.guard.detected_at, g.guard.guard_id)
                    if g.guard.origin not in latest or key > latest[g.guard.origin][0]:
                        latest[g.guard.origin] = (key, g.guard)
            self._stalled = {o: gd.detected_at for o, (_k, gd) in latest.items() if gd.status == "STALLED"}
        return self._stalled

    def stall_time(self, origins: Sequence[str]) -> Optional[int]:
        """Instant by which ALL given origins are known stalled (None if any is live/unknown)."""
        if not origins:
            return None
        st, times = self.stalled(), []
        for o in origins:
            ts = [st[t] for t in self.reg.closure(o) if t in st]
            if not ts:
                return None
            times.append(min(ts))
        return max(times)

    def lookup_fact(self, ftype: str, scope: Dict[str, str], horizon: int):
        keep = []
        recs = [r for r in self.ledger.facts(ftype) if r.kt <= horizon and scope_covers(r.fact.scope, scope) and not r.fact.rejection_reason]
        for r in _supersede_facts(recs):
            d = self.reg.deps(r.fact.origins, ())
            if not (d & self.removed) and r.fact.fact_id not in self.excl_ids:
                keep.append((r, d))
        if not keep:
            return None
        keep.sort(key=lambda x: (x[0].kt, x[0].fact.fact_id))
        r, d = keep[-1]
        self.note_kt(r.kt)
        return r.fact, len({str(x[0].fact.value) for x in keep}) > 1, d


def _possible(state: S, closed: bool, has_evidence: bool = True) -> FrozenSet[S]:
    if closed:
        return frozenset({state})
    if has_evidence and state in (S.HEALTHY, S.SUSPECT):
        return frozenset({S.SUSPECT, S.HEALTHY})
    return FULL


def _absent_timeline(opens: int, deadline: int, stall_t: Optional[int]) -> Timeline:
    t_deg = deadline if stall_t is None else min(deadline, max(opens, stall_t))
    return Timeline([(opens, S.UNKNOWN), (t_deg, S.DEGRADED)])


def _leaf_timeline(opens, deadline, start, state, latest_obs, role: RoleSpec, stall_t, valid_to=None) -> Timeline:
    base = [(opens, S.UNKNOWN)]
    if start > deadline:
        base.append((deadline, S.DEGRADED))
    base.append((max(start, opens), state))
    tls = [Timeline(base)]
    fr = role.freshness
    if latest_obs is not None:
        if fr.soft_us is not None:
            tls.append(Timeline([(NEG_INF, S.HEALTHY), (latest_obs + fr.soft_us, S.SUSPECT)]))
        if fr.hard_us is not None:
            tls.append(Timeline([(NEG_INF, S.HEALTHY), (latest_obs + fr.hard_us, S.DEGRADED)]))
        if stall_t is not None and (fr.soft_us is not None or fr.hard_us is not None):
            tls.append(Timeline([(NEG_INF, S.HEALTHY), (max(stall_t, opens), S.SUSPECT)]))
    if valid_to is not None:
        tls.append(Timeline([(NEG_INF, S.HEALTHY), (valid_to, S.DEGRADED)]))
    return Timeline.combine(tls, min, extra_times=[opens]).clip(opens)


# =========================================================================== evidence role
def _eval_evidence(ctx: _Ctx, role: RoleSpec) -> RoleResult:
    inst, c, K = ctx.inst, ctx.c, ctx.K
    deadline = inst.opens_at + role.slot.deadline_us
    cutoff = deadline + role.slot.lateness_us
    horizon, closed = min(K, cutoff), K >= cutoff
    wit: List[Witness] = []
    usable: List[_Obs] = []
    unresolved: List[tuple] = []
    scope = ctx.scope

    recs = [r for r in ctx.ledger.atoms(role.name) if r.kt <= horizon and scope_in(r.atom.scope, scope, role.scope_class)]
    for r in sorted(_supersede_atoms(recs), key=lambda r: (r.atom.observed_at, r.atom.atom_id)):
        a = r.atom
        ctx.note_kt(r.kt)
        deps = ctx.reg.deps(a.source_origins, a.processing_origins)
        if deps & ctx.removed or a.atom_id in ctx.excl_ids:
            continue
        tag = a.atom_id[:10]
        if a.quality_grade < S.SUSPECT:
            wit.append(("LOW_QUALITY_EVIDENCE", role.name, f"atom={tag} grade={a.quality_grade.name} (not admissible as evidence)"))
            continue
        if role.admissible_source_origins and not (set(a.source_origins) & set(role.admissible_source_origins)):
            wit.append(("INADMISSIBLE_ORIGIN", role.name, f"atom={tag} origins={list(a.source_origins)}"))
            continue
        adict = dict(a.scope)
        rr = resolve_time(a.time, role.time_class_required, lambda ft: ctx.lookup_fact(ft, adict, horizon))
        if rr.illegal:
            wit.append(("ILLEGAL_TIME_CLASS", role.name, f"atom={tag} {a.time.time_class.value}->{role.time_class_required.value} is not a legal conversion"))
            continue
        if rr.missing:
            unresolved.append((a, rr.missing))
            continue
        grade = min(a.quality_grade, rr.grade)
        if rr.ambiguous:
            grade = min(grade, S.SUSPECT)
            wit.append(("AMBIGUOUS_REFERENCE_FACT", role.name, f"atom={tag} conflicting reference facts {list(rr.fact_ids)}"))
        if a.observed_at > r.kt + ctx.cfg.clock_skew_us:
            grade = min(grade, S.SUSPECT)
            wit.append(("FUTURE_DATED_OBSERVATION", role.name, f"atom={tag} observed_at is after its arrival"))
        if role.time_check_tolerance_us is not None:
            ab = resolve_time(a.time, TimeClass.ABSOLUTE_UTC, lambda ft: ctx.lookup_fact(ft, adict, horizon))
            if ab.time is not None and abs(ab.time.value - a.observed_at) > role.time_check_tolerance_us + ab.time.uncertainty_us:
                grade = min(grade, S.SUSPECT)
                wit.append(("TIME_BASIS_MISMATCH", role.name,
                            f"atom={tag} resolved time differs from observed_at by {abs(ab.time.value - a.observed_at) / 1e6:.3f}s"))
        usable.append(_Obs(a.atom_id, a.value, deps | rr.fact_deps,
                           frozenset(d for d in deps if d.startswith("S:")), frozenset(d for d in deps if d.startswith("P:")),
                           a.observed_at, grade, r.kt, rr.fact_ids))

    # ---- no usable evidence: pending (UNKNOWN) until the slot deadline, then DEGRADED
    if not usable:
        stall_t = ctx.stall_time(role.admissible_source_origins)
        tl = _absent_timeline(inst.opens_at, deadline, stall_t)
        if unresolved:
            types = sorted({t for _a, ms in unresolved for t in ms})
            wit.append(("MISSING_REFERENCE_FACT", role.name, f"cannot align time: missing {types} for scope {sorted(scope.items())}"))
        st = tl.state_at(K)
        return RoleResult(role.name, "evidence", tl, st, closed, deadline, cutoff, deadline, _possible(st, closed, False),
                          False, witnesses=wit)

    latest = max(o.obs_at for o in usable)
    window = [o for o in usable if latest - o.obs_at <= c.window_us]
    groups: Dict[frozenset, _Obs] = {}
    for o in sorted(window, key=lambda o: (o.obs_at, o.oid)):
        groups[o.deps] = o                                 # latest observation per dependency-set wins
    obs = sorted(groups.values(), key=lambda o: (o.obs_at, o.oid))
    overflow = len(obs) > ctx.cfg.M_max
    if overflow:
        obs = obs[-ctx.cfg.M_max:]
        wit.append(("SEARCH_BUDGET_EXCEEDED", role.name, f"origin groups={len(groups)} > M_max={ctx.cfg.M_max}"))

    n = len(obs)
    agree = [[True] * n for _ in range(n)]
    edges: List[Edge] = []
    for i in range(n):
        for j in range(i + 1, n):
            if not _agree(obs[i].value, obs[j].value, role.agreement.metric, role.agreement.tolerance):
                agree[i][j] = agree[j][i] = False
                edges.append(Edge(obs[i].deps | obs[j].deps, f"{role.name}: {obs[i].value} vs {obs[j].value}", (obs[i].oid, obs[j].oid)))
    sd, pdp = _depth(obs, agree, "src"), _depth(obs, agree, "proc")

    state = S.HEALTHY
    if overflow:
        state = min(state, S.UNKNOWN)
    if edges:
        state = min(state, S.SUSPECT)
        for e in edges[:6]:
            wit.append(("UNRESOLVED_CONFLICT", role.name, f"pair=({e.ids[0][:10]},{e.ids[1][:10]}) {e.detail}"))
        if len(edges) > 6:
            wit.append(("UNRESOLVED_CONFLICT", role.name, f"... {len(edges) - 6} more conflicting pairs"))
    gmin = min(o.grade for o in obs)
    if gmin < S.HEALTHY:
        state = min(state, gmin)
        wit.append(("LOW_QUALITY_EVIDENCE", role.name, f"support contains {gmin.name}-grade evidence"))
    if unresolved:
        state = min(state, S.SUSPECT)
        types = sorted({t for _a, ms in unresolved for t in ms})
        wit.append(("MISSING_REFERENCE_FACT", role.name, f"{len(unresolved)} atom(s) could not be time-aligned (missing {types})"))
    co = role.corroboration
    if co.mode == "MANDATORY" and (sd < co.min_source_depth or pdp < co.min_processing_depth):
        state = min(state, S.SUSPECT)
        wit.append(("INSUFFICIENT_CORROBORATION", role.name,
                    f"source_depth={sd} (need {co.min_source_depth}), processing_depth={pdp} (need {co.min_processing_depth})"))
    late = max((o.kt - deadline for o in obs if o.kt > deadline), default=0)
    if late > 0:
        wit.append(("LATE_EVIDENCE_ADMITTED", role.name, f"max delay past slot deadline={late / 1e6:.3f}s"))

    all_src = sorted({x[2:] for o in obs for x in o.src})
    stall_t = ctx.stall_time(all_src) if all_src else None
    tl = _leaf_timeline(inst.opens_at, deadline, latest, state, latest, role, stall_t)
    rep = obs[-1]
    rep_t = sec_to_us(rep.value) if role.value_time_class is not None and _num(rep.value) is not None else None
    deps = frozenset().union(*[o.deps for o in obs])
    st = tl.state_at(K)
    return RoleResult(role.name, "evidence", tl, st, closed, deadline, cutoff, latest, _possible(st, closed), True,
                      tuple(sorted(o.oid for o in obs)), tuple(sorted({r for o in obs for r in o.refs})), deps, sd, pdp,
                      wit, edges, rep, rep_t, latest, list(obs))


# =========================================================================== reference role
def _eval_reference(ctx: _Ctx, role: RoleSpec) -> RoleResult:
    inst, K = ctx.inst, ctx.K
    deadline = inst.opens_at + role.slot.deadline_us
    cutoff = deadline + role.slot.lateness_us
    horizon, closed = min(K, cutoff), K >= cutoff
    wit: List[Witness] = []
    recs = [r for r in ctx.ledger.facts(role.fact_type) if r.kt <= horizon and scope_in(r.fact.scope, ctx.scope, role.scope_class)]
    valid: List[Tuple[FactRec, FrozenSet[str]]] = []
    for r in _supersede_facts(recs):
        ctx.note_kt(r.kt)
        d = ctx.reg.deps(r.fact.origins, ())
        if d & ctx.removed or r.fact.fact_id in ctx.excl_ids:
            continue
        if r.fact.rejection_reason:
            wit.append(("INVALID_REFERENCE_FACT", role.name, f"fact={r.fact.fact_id[:10]} reason={r.fact.rejection_reason}"))
            continue
        valid.append((r, d))
    if not valid:
        tl = _absent_timeline(inst.opens_at, deadline, ctx.stall_time(role.admissible_source_origins))
        if not wit:
            pass
        st = tl.state_at(K)
        return RoleResult(role.name, "reference", tl, st, closed, deadline, cutoff, deadline, _possible(st, closed, False), False, witnesses=wit)

    valid.sort(key=lambda x: (x[0].kt, x[0].fact.fact_id))
    obs = [_Obs(r.fact.fact_id, r.fact.value, d, frozenset(x for x in d if x.startswith("S:")), frozenset(), r.kt, r.fact.grade, r.kt) for r, d in valid]
    n = len(obs)
    agree = [[True] * n for _ in range(n)]
    edges: List[Edge] = []
    for i in range(n):
        for j in range(i + 1, n):
            if not _agree(obs[i].value, obs[j].value, role.agreement.metric, role.agreement.tolerance):
                agree[i][j] = agree[j][i] = False
                edges.append(Edge(obs[i].deps | obs[j].deps, f"{role.name}: {obs[i].value} vs {obs[j].value}", (obs[i].oid, obs[j].oid)))
    state = min(o.grade for o in obs)
    if edges:
        state = min(state, S.SUSPECT)
        wit.append(("AMBIGUOUS_REFERENCE_FACT", role.name, f"{len(edges)} conflicting reference fact pair(s)"))
    if state < S.HEALTHY and not edges:
        notes = "; ".join(sorted({r.fact.note for r, _ in valid if r.fact.note}))
        wit.append(("REFERENCE_FACT_GRADE", role.name, f"reference graded {state.name}" + (f": {notes}" if notes else "")))
    if any(r.kt > deadline for r, _ in valid):
        wit.append(("LATE_REFERENCE_FACT", role.name, "Reference fact arrived after slot deadline"))
    f0 = valid[-1][0].fact
    start = max(inst.opens_at, f0.valid_from if f0.valid_from is not None else inst.opens_at)
    tl = _leaf_timeline(inst.opens_at, deadline, start, state, None, role, None, valid_to=f0.valid_to)
    rep = obs[-1]
    rep_t = int(rep.value) if role.value_time_class is not None and _num(rep.value) is not None else None
    deps = frozenset().union(*[o.deps for o in obs])
    st = tl.state_at(K)
    return RoleResult(role.name, "reference", tl, st, closed, deadline, cutoff, start, _possible(st, closed), True,
                      tuple(sorted(o.oid for o in obs)), (), deps, _depth(obs, agree, "src"), 0, wit, edges, rep, rep_t, None, list(obs))


# =========================================================================== constraints
def _eval_constraint(ctx: _Ctx, cs: ConstraintSpec, roles: Dict[str, RoleResult]) -> ConstraintResult:
    ops = [roles[o] for o in cs.operands]
    opens = ctx.inst.opens_at
    closed = all(r.closed for r in ops)
    cutoff = max(r.cutoff for r in ops)
    start = max(r.start for r in ops)
    wit: List[Witness] = []

    def unevaluable(reason: str) -> ConstraintResult:
        tl = Timeline([(opens, S.UNKNOWN), (cutoff, S.DEGRADED)])
        wit.append(("CONSTRAINT_UNEVALUABLE", cs.id, reason))
        st = tl.state_at(ctx.K)
        return ConstraintResult(cs.id, tl, st, closed, _possible(st, closed, False), cutoff, wit, [])

    if any(r.rep is None for r in ops):
        return unevaluable("operand evidence not available: " + ",".join(r.name for r in ops if r.rep is None))
    p, k = cs.params, cs.kind
    horizon = min(ctx.K, ctx.inst.opens_at + ctx.c.cutoff_us)
    ok, detail = True, ""
    if k == "interval":
        dur, st_r, en_r = ops
        target: TimeClass = p["time_class"]
        conv = []
        for r in (st_r, en_r):
            spec = ctx.c.roles[r.name]
            rr = resolve_time(TypedTime(r.rep_time_us, spec.value_time_class), target, lambda ft: ctx.lookup_fact(ft, ctx.scope, horizon))
            if rr.time is None:
                return unevaluable(f"cannot convert {r.name} ({spec.value_time_class.value}->{target.value}): missing {list(rr.missing) or 'legal path'}")
            conv.append(rr.time.value)
        dv = _num(dur.rep.value)
        if dv is None:
            ok, detail = False, "duration is not numeric"
        else:
            diff = abs(dv - us_to_sec(conv[1] - conv[0]))
            ok = diff <= p["tolerance"]
            detail = f"|duration {dv} - (end-start) {us_to_sec(conv[1] - conv[0])}| = {diff} (tol {p['tolerance']})"
    else:
        vals = [_num(r.rep.value) for r in ops]
        if k == "equals":
            ok = str(ops[0].rep.value) == str(ops[1].rep.value)
            detail = f"{ops[0].rep.value!r} vs {ops[1].rep.value!r}"
        elif any(v is None for v in vals):
            ok, detail = False, "non-numeric operand"
        elif k == "bounds":
            v, lo, hi = vals[0], p.get("lo"), p.get("hi")
            ok = (lo is None or v >= lo) and (hi is None or v <= hi)
            detail = f"value {v} outside [{lo}, {hi}]" if not ok else f"value {v} within [{lo}, {hi}]"
            unc = p.get("uncertainty")
            if unc is not None and unc > 0:
                if (lo is not None and abs(v - lo) <= unc) or (hi is not None and abs(v - hi) <= unc):
                    thresh = lo if (lo is not None and abs(v - lo) <= unc) else hi
                    wit.append(("WITHIN_UNCERTAINTY", cs.id, f"value {v} is within uncertainty ±{unc} of threshold {thresh}"))
        elif k == "abs_diff":
            d = abs(vals[0] - vals[1])
            ok, detail = d <= p["tolerance"], f"|{vals[0]} - {vals[1]}| = {d} (tol {p['tolerance']})"
        elif k == "ratio":
            if vals[1] == 0:
                ok, detail = False, "division by zero"
            else:
                r_ = vals[0] / vals[1]
                dev = abs(r_ - 1)
                ok, detail = dev <= p["tolerance"], f"{vals[0]}/{vals[1]} = {r_:.6f}, |ratio-1| = {dev:.6f} (tol {p['tolerance']})"
        else:  # linear
            tot = sum(cf * v for cf, v in zip(p["coeffs"], vals))
            ok, detail = abs(tot) <= p["tolerance"], f"sum(coeff*value) = {tot} (tol {p['tolerance']})"
    state = S.HEALTHY if ok else S.SUSPECT
    edges: List[Edge] = []
    if not ok:
        wit.append(("CONSTRAINT_VIOLATION", cs.id, f"{k}: {detail}"))
        edges.append(Edge(frozenset().union(*[r.rep.deps for r in ops]), f"{cs.id}: {detail}", tuple(r.rep.oid for r in ops)))
    tl = Timeline([(opens, S.UNKNOWN), (max(opens, start), state)])
    st = tl.state_at(ctx.K)
    return ConstraintResult(cs.id, tl, st, closed, _possible(st, closed), start, wit, edges)


# =========================================================================== core
@dataclass
class Core:
    roles: Dict[str, RoleResult]
    cons: Dict[str, ConstraintResult]
    timeline: Timeline
    state_k: S
    edges: List[Edge]
    deps: FrozenSet[str]


def evaluate_core(ctx: _Ctx) -> Core:
    roles: Dict[str, RoleResult] = {}
    for name in ctx.c.role_names:
        spec = ctx.c.roles[name]
        roles[name] = _eval_reference(ctx, spec) if spec.kind == "reference" else _eval_evidence(ctx, spec)
    cons = {cs.id: _eval_constraint(ctx, cs, roles) for cs in ctx.c.constraints}
    tl = fold(ctx.c.formula, lambda r: roles[r].timeline, tl_comb)
    for cr in cons.values():
        tl = Timeline.combine([tl, cr.timeline], min)
    edges = [e for r in roles.values() for e in r.edges] + [e for cr in cons.values() for e in cr.edges]
    deps = frozenset().union(*[r.deps for r in roles.values()]) if roles else frozenset()
    return Core(roles, cons, tl, tl.state_at(ctx.K), edges, deps)


# =========================================================================== diagnosis
@dataclass
class Diagnosis:
    result: str                           # NONE | EXCLUDED_FAULTS | DIAGNOSIS_AMBIGUOUS | FAULT_BUDGET_EXCEEDED
    excluded_ids: FrozenSet[str]          # observations removed under EVERY minimal diagnosis
    excluded_origins: FrozenSet[str]      # dependency tokens common to every minimal diagnosis (may be empty)
    minimal: List[FrozenSet[str]]
    witnesses: List[Witness]


def diagnose(edges: List[Edge], items: Dict[str, FrozenSet[str]], f: int, cfg: EngineConfig) -> Diagnosis:
    """Theorem G4-I (conservative). Hypotheses are sets of faulty dependency tokens (<= f); an observation is
    excluded only if EVERY inclusion-minimal admissible hypothesis removes it. Otherwise the verdict is ambiguous."""
    E = frozenset()
    if not edges:
        return Diagnosis("NONE", E, E, [], [])
    uni = sorted({d for e in edges for d in e.deps})
    if f <= 0:
        return Diagnosis("FAULT_BUDGET_EXCEEDED", E, E, [], [("FAULT_BUDGET_EXCEEDED", "", f"conflicts={len(edges)}, diagnosis_budget={f}")])
    work = sum(1 for r in range(1, f + 1) for _ in itertools.islice(itertools.combinations(uni, r), cfg.diagnosis_enum_cap + 1))
    if work > cfg.diagnosis_enum_cap:
        return Diagnosis("DIAGNOSIS_AMBIGUOUS", E, E, [], [("DIAGNOSIS_AMBIGUOUS", "", "enumeration capped; excluding nothing")])
    adm = [frozenset(c) for r in range(1, f + 1) for c in itertools.combinations(uni, r) if all(set(c) & e.deps for e in edges)]
    if not adm:
        return Diagnosis("FAULT_BUDGET_EXCEEDED", E, E, [], [("FAULT_BUDGET_EXCEEDED", "", f"no admissible diagnosis within f={f} for {len(edges)} conflicts")])
    dmin = sorted({d for d in adm if not any(o < d for o in adm)}, key=lambda s: (len(s), sorted(s)))
    removed_sets = [frozenset(i for i, deps in items.items() if deps & d) for d in dmin]
    ex_ids = frozenset.intersection(*removed_sets)
    inter = frozenset.intersection(*dmin)
    fmt = "[" + ", ".join("{" + ", ".join(sorted(d)) + "}" for d in dmin) + "]"
    if not ex_ids:
        return Diagnosis("DIAGNOSIS_AMBIGUOUS", E, E, dmin, [("DIAGNOSIS_AMBIGUOUS", "", f"minimal_diagnoses={fmt}, common_exclusion=EMPTY")])
    return Diagnosis("EXCLUDED_FAULTS", ex_ids, inter, dmin,
                     [("EXCLUDED_FAULTY_ORIGIN", "", f"observations={sorted(x[:10] for x in ex_ids)} minimal_diagnoses={fmt}")])


# =========================================================================== decision output
@dataclass
class EvalOutput:
    content: dict
    timeline: Timeline
    state_k: S
    knowledge_time: int
    final: bool
    cutoff: int
    witnesses: List[Witness]
    roles: Dict[str, RoleResult]


def evaluate_decision(c: Contract, inst: DecisionInstance, ledger: Ledger, reg: OriginRegistry, cfg: EngineConfig, K: int) -> EvalOutput:
    ctx0 = _Ctx(c, inst, ledger, reg, cfg, K, frozenset(), True)
    core0 = evaluate_core(ctx0)
    items = {o.oid: o.deps for r in core0.roles.values() for o in r.obs}
    diag = diagnose(core0.edges, items, c.fault_model.diagnosis_budget, cfg)
    excl = diag.excluded_ids
    core = core0 if not excl else evaluate_core(_Ctx(c, inst, ledger, reg, cfg, K, frozenset(), False, excl))
    witnesses: List[Witness] = [w for r in core.roles.values() for w in r.witnesses] + [w for x in core.cons.values() for w in x.witnesses] + list(diag.witnesses)

    # ---- resilience ("possible worlds": which origin losses would break this decision?)
    # Evaluated at a K-independent reference instant (tuple completion), so the profile is a property of the
    # evidence structure, not of the evaluation clock.
    profile: Dict[str, str] = {}
    critical: List[str] = []
    req = c.fault_model.resilience_requirement
    kmax = min(max(c.fault_model.report_k, req), cfg.resilience_cap_k)
    cap_tl: Optional[Timeline] = None
    starts = [r.start for r in core.roles.values() if r.has_evidence]
    t_ref = max(starts) if starts else None
    if t_ref is not None and core.timeline.state_at(t_ref) == S.HEALTHY:
        uni = sorted(d for d in core.deps if d.startswith("S:"))     # resilience = loss of SOURCE origins
        for k in range(1, kmax + 1):
            if k >= 2 and len(uni) > cfg.universe_cap:
                profile[str(k)] = "NOT_EVALUATED"
                continue
            worst = S.HEALTHY
            for F in itertools.combinations(uni, k):
                st = evaluate_core(_Ctx(c, inst, ledger, reg, cfg, K, frozenset(F), False, excl)).timeline.state_at(t_ref)
                worst = min(worst, st)
                if k == 1 and st < S.HEALTHY:
                    critical.append(F[0])
            profile[str(k)] = worst.name
        if critical:
            witnesses.append(("COMMON_CAUSE_EXPOSURE", "", f"single points of failure: {sorted(critical)}"))
        if req > 0 and profile.get(str(req)) not in (None, "HEALTHY", "NOT_EVALUATED"):
            lim = max(S.parse(profile[str(req)]), S.SUSPECT)          # resilience shortfall is "questionable", not "unavailable"
            witnesses.append(("INSUFFICIENT_RESILIENCE", "", f"requires HEALTHY after loss of any {req} origin(s); worst case is {profile[str(req)]}"))
            cap_tl = Timeline([(inst.opens_at, S.UNKNOWN), (max(t_ref, inst.opens_at), lim)])
    timeline = core.timeline if cap_tl is None else Timeline.combine([core.timeline, cap_tl], min)
    state_k = timeline.state_at(K)

    # ---- envelope / maturity / finality
    rsets = {n: r.possible for n, r in core.roles.items()}
    fset = fold(c.formula, lambda r: rsets[r], lambda op, k, it: set_comb(op, k, it, cfg.envelope_cap))
    for cr in core.cons.values():
        fset = set_and(fset, cr.possible)
    all_closed = all(r.closed for r in core.roles.values())
    if cap_tl is not None:
        capv = cap_tl.state_at(K) if cap_tl.state_at(K) != S.UNKNOWN else S.SUSPECT
        capped = frozenset(min(x, capv) for x in fset)
        fset = capped if all_closed else (fset | capped)     # while slots are open a late independent source may cure the shortfall
    lo, hi = envelope(fset)
    maturity = "TUPLE_RESOLVED" if all_closed else ("STATE_RESOLVED" if lo == hi else "OPEN")
    final = all_closed
    cutoff_inst = inst.opens_at + c.cutoff_us

    # ---- limitations (derived, not hard-coded)
    lims = list(c.limitations)
    for n, r in core.roles.items():
        spec = c.roles[n]
        if r.kind == "evidence" and r.has_evidence and r.source_depth == 0 and spec.corroboration.mode != "MANDATORY":
            lims.append(f"INFORMATIONAL_CORROBORATION_ONLY: role={n} has no independent source corroboration")
    if critical:
        lims.append(f"UNMODELLED_COMMON_CAUSE: shared dependency {sorted(critical)}")
    lims = sorted(set(lims))

    # ---- assemble hashed content (no K-dependent prose: deadlines/expiry are derived at explain-time from timelines)
    roles_c = {}
    for n, r in core.roles.items():
        roles_c[n] = {"kind": r.kind, "timeline": r.timeline.to_list(), "closed": r.closed, "deadline": fmt_instant(r.deadline),
                      "cutoff": fmt_instant(r.cutoff), "has_evidence": r.has_evidence, "source_depth": r.source_depth,
                      "processing_depth": r.processing_depth, "support_atom_ids": list(r.support_ids),
                      "reference_fact_ids": list(r.ref_ids), "dependencies": sorted(r.deps),
                      "latest_observed_at": None if r.latest_obs is None else fmt_instant(r.latest_obs)}
    cons_c = {i: {"timeline": x.timeline.to_list(), "closed": x.closed} for i, x in core.cons.items()}
    wl = sorted({(code, role, detail) for code, role, detail in witnesses})
    frontier = max([ctx0.frontier] + [r.cutoff for r in core.roles.values() if r.closed])
    content = {
        "schema": "calibre.sia.assessment/3.0",
        "decision_instance_id": inst.instance_id,
        "contract": c.ref,
        "scope": dict(inst.scope),
        "opens_at": fmt_instant(inst.opens_at),
        "validity_timeline": timeline.to_list(),
        "resolution_maturity": maturity,
        "finality_status": "FINAL" if final else "OPEN",
        "envelope": {"lower": lo.name, "upper": hi.name, "alternatives": sorted(s.name for s in fset)},
        "roles": roles_c,
        "constraints": cons_c,
        "diagnosis": {"result": diag.result, "excluded_items": sorted(diag.excluded_ids), "excluded_origins": sorted(diag.excluded_origins),
                      "minimal_diagnoses": [sorted(d) for d in diag.minimal]},
        "resilience": {"required_k": req, "profile": profile, "critical_origins": sorted(critical)},
        "witnesses": [{"code": a, "role": b, "detail": d} for a, b, d in wl],
        "limitations": lims,
        "evidence_frontier": fmt_instant(frontier),
    }
    return EvalOutput(content, timeline, state_k, frontier, final, cutoff_inst, wl, core.roles)
