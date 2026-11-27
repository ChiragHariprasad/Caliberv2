"""Decision Evidence Contracts (DEC): what evidence a decision needs, and how it is judged.

New vs the old engine: (1) cross-role ``constraints`` (the old code could only compare atoms
*within* one role, so the headline ``|T_lap-(T_end-T_start)| <= eta`` check never existed);
(2) every declared knob is honoured by the evaluator (no inert fields); (3) independence is
derived from an ``OriginRegistry`` instead of hard-coded provider prefixes.
"""
from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .canon import US_PER_S, sec_to_us, sha256_hex
from .model import SCOPE_RANK, OriginRegistry, ScopeClass
from .timeclass import SEMANTIC, TimeClass


class ContractError(ValueError):
    pass


METRICS = ("abs_diff", "relative_diff", "discrete_equality")
DISCRETE_UNITS = {"enum", "boolean", "bool", "string", "flags"}
CONSTRAINT_KINDS = ("bounds", "abs_diff", "ratio", "equals", "linear", "interval")


@dataclass(frozen=True)
class AgreementSpec:
    metric: str = "discrete_equality"
    unit: str = "s"
    tolerance: Decimal = Decimal(0)


@dataclass(frozen=True)
class FreshnessSpec:
    soft_us: Optional[int] = None
    hard_us: Optional[int] = None


@dataclass(frozen=True)
class SlotSpec:
    deadline_us: int = 30 * US_PER_S
    lateness_us: int = 60 * US_PER_S


@dataclass(frozen=True)
class CorroborationSpec:
    mode: str = "INFORMATIONAL"           # INFORMATIONAL | MANDATORY
    min_source_depth: int = 0
    min_processing_depth: int = 0


@dataclass(frozen=True)
class RoleSpec:
    name: str
    kind: str                             # evidence | reference
    scope_class: ScopeClass
    time_class_required: TimeClass
    fact_type: str
    admissible_source_origins: Tuple[str, ...]
    agreement: AgreementSpec
    freshness: FreshnessSpec
    slot: SlotSpec
    corroboration: CorroborationSpec
    value_time_class: Optional[TimeClass] = None      # set when the *value* is itself a time
    time_check_tolerance_us: Optional[int] = None     # cross-check resolved time vs observed_at


@dataclass(frozen=True)
class ConstraintSpec:
    id: str
    kind: str
    operands: Tuple[str, ...]
    params: Mapping[str, Any]


@dataclass(frozen=True)
class FaultModel:
    diagnosis_budget: int = 0             # f: max simultaneously faulty origins a conflict may be blamed on
    resilience_requirement: int = 0       # k: decision must stay HEALTHY after losing ANY k origins
    report_k: int = 1                     # depth of the resilience profile that is always reported


# ------------------------------------------------------------------ formula AST
@dataclass(frozen=True)
class Leaf:
    role: str


@dataclass(frozen=True)
class Op:
    op: str                               # AND | OR | K_OF_N
    k: int
    children: Tuple[Any, ...]


def fold(node, leaf: Callable, comb: Callable):
    if isinstance(node, Leaf):
        return leaf(node.role)
    return comb(node.op, node.k, [fold(c, leaf, comb) for c in node.children])


def roles_of(node) -> set:
    return {node.role} if isinstance(node, Leaf) else set().union(*[roles_of(c) for c in node.children])


_TOK = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*|\d+|[(),])")


def parse_formula(text: str):
    toks, pos = [], 0
    text = text.strip()
    if not text:
        raise ContractError("empty formula")
    while pos < len(text):
        m = _TOK.match(text, pos)
        if not m:
            raise ContractError(f"unexpected character at {pos} in formula {text!r}")
        toks.append(m.group(1))
        pos = m.end()
    i = 0

    def peek():
        return toks[i] if i < len(toks) else None

    def eat(expect=None):
        nonlocal i
        t = peek()
        if t is None or (expect and t != expect):
            raise ContractError(f"expected {expect!r} but found {t!r} in {text!r}")
        i += 1
        return t

    def expr(depth=0):
        if depth > 50:
            raise ContractError("formula nesting too deep")
        name = eat()
        if not re.match(r"[A-Za-z_]", name):
            raise ContractError(f"expected role/operator, found {name!r}")
        up = name.upper()
        if up in ("AND", "OR") and peek() == "(":
            eat("(")
            kids = args(depth)
            eat(")")
            return Op(up, 0, tuple(kids))
        if up == "K_OF_N" and peek() == "(":
            eat("(")
            k = int(eat())
            eat(",")
            kids = args(depth)
            eat(")")
            return Op("K_OF_N", k, tuple(kids))
        return Leaf(name)

    def args(depth):
        out = [expr(depth + 1)]
        while peek() == ",":
            eat(",")
            out.append(expr(depth + 1))
        return out

    ast = expr()
    if i != len(toks):
        raise ContractError(f"trailing tokens after formula: {toks[i:]}")
    return ast


# ------------------------------------------------------------------ contract
@dataclass(frozen=True)
class Contract:
    contract_id: str
    version: str
    epoch: int
    decision_type: str
    scope_class: ScopeClass
    formula_str: str
    formula: Any
    roles: Mapping[str, RoleSpec]
    constraints: Tuple[ConstraintSpec, ...]
    window_us: int
    fault_model: FaultModel
    limitations: Tuple[str, ...]
    definition_hash: str

    @property
    def role_names(self) -> Tuple[str, ...]:
        return tuple(sorted(self.roles))

    @property
    def cutoff_us(self) -> int:
        return max(r.slot.deadline_us + r.slot.lateness_us for r in self.roles.values())

    @property
    def ref(self) -> dict:
        return {"id": self.contract_id, "version": self.version, "epoch": self.epoch, "definition_hash": self.definition_hash}


def _dec(x, default=None) -> Optional[Decimal]:
    if x is None:
        return default
    try:
        return Decimal(str(x))
    except InvalidOperation as e:
        raise ContractError(f"not a number: {x!r}") from e


def _opt_us(x) -> Optional[int]:
    return None if x is None else sec_to_us(x)


def parse_contract(data: Mapping[str, Any]) -> Contract:
    for req in ("contract_id", "version", "epoch", "decision_type", "decision_scope", "formula", "roles"):
        if req not in data:
            raise ContractError(f"missing required contract field: {req!r}")
    raw = json.loads(json.dumps(data, default=str))
    try:
        scope_class = ScopeClass(data["decision_scope"]["scope_class"])
    except (KeyError, ValueError) as e:
        raise ContractError("invalid decision_scope.scope_class") from e
    formula = parse_formula(str(data["formula"]))
    if not isinstance(data["roles"], Mapping):
        raise ContractError("'roles' must be a mapping")

    roles: Dict[str, RoleSpec] = {}
    for name, r in data["roles"].items():
        try:
            kind = r.get("kind", "evidence")
            agr = r.get("agreement") or {}
            fr = r.get("freshness") or {}
            sl = r.get("slot") or {}
            co = r.get("corroboration") or {}
            vtc = r.get("value_time_class")
            roles[name] = RoleSpec(
                name=name, kind=kind,
                scope_class=ScopeClass(r.get("scope_class", scope_class.value)),
                time_class_required=TimeClass(r.get("time_class_required", "ABSOLUTE_UTC")),
                fact_type=r.get("fact_type", name),
                admissible_source_origins=tuple(r.get("admissible_source_origins", ())),
                agreement=AgreementSpec(agr.get("metric", "discrete_equality"), agr.get("unit", "s"), _dec(agr.get("tolerance"), Decimal(0))),
                freshness=FreshnessSpec(_opt_us(fr.get("soft_age_s")), _opt_us(fr.get("hard_age_s"))),
                slot=SlotSpec(sec_to_us(sl.get("deadline_s", 30)), sec_to_us(sl.get("allowed_lateness_s", 60))),
                corroboration=CorroborationSpec(co.get("mode", "INFORMATIONAL"), int(co.get("min_source_depth", 0)), int(co.get("min_processing_depth", 0))),
                value_time_class=None if vtc is None else TimeClass(vtc),
                time_check_tolerance_us=_opt_us(r.get("time_check_tolerance_s")),
            )
        except (ValueError, AttributeError) as e:
            raise ContractError(f"invalid role {name!r}: {e}") from e

    cons: List[ConstraintSpec] = []
    for c in data.get("constraints", []) or []:
        p = {k: v for k, v in c.items() if k not in ("id", "kind", "operands")}
        for key in ("tolerance", "lo", "hi"):
            if key in p:
                p[key] = _dec(p[key])
        if "coeffs" in p:
            p["coeffs"] = [_dec(x) for x in p["coeffs"]]
        if "time_class" in p:
            p["time_class"] = TimeClass(p["time_class"])
        ops = tuple(c.get("operands", ()))
        if c.get("kind") == "interval":
            ops = (p.get("duration"), p.get("start"), p.get("end"))
        cons.append(ConstraintSpec(str(c.get("id", "")), str(c.get("kind", "")), ops, p))

    fm = data.get("fault_model") or {}
    return Contract(
        contract_id=str(data["contract_id"]), version=str(data["version"]), epoch=int(data["epoch"]),
        decision_type=str(data["decision_type"]), scope_class=scope_class, formula_str=str(data["formula"]),
        formula=formula, roles=roles, constraints=tuple(cons),
        window_us=sec_to_us(data.get("simultaneity_window_s", 1.0)),
        fault_model=FaultModel(int(fm.get("diagnosis_budget", 0)), int(fm.get("resilience_requirement", 0)), int(fm.get("report_k", 1))),
        limitations=tuple(data.get("limitations", ()) or ()), definition_hash=sha256_hex(raw))


def load_contract_yaml(text: str) -> Contract:
    import yaml
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ContractError("YAML root must be a mapping")
    return parse_contract(raw)


def load_contract_file(path: Union[str, Path]) -> Contract:
    p = Path(path)
    txt = p.read_text(encoding="utf-8")
    return parse_contract(json.loads(txt)) if p.suffix == ".json" else load_contract_yaml(txt)


# ------------------------------------------------------------------ validation
@dataclass
class Validation:
    errors: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> List[str]:
        return [c for c, _ in self.errors]


def _check_ops(node, errs):
    if isinstance(node, Op):
        n = len(node.children)
        if node.op in ("AND", "OR") and n < 2:
            errs.append(("E_V02_INVALID_ARITY", f"{node.op} needs >= 2 children, got {n}"))
        if node.op == "K_OF_N":
            if n < 2:
                errs.append(("E_V02_INVALID_ARITY", f"K_OF_N needs n >= 2, got {n}"))
            if not (1 <= node.k <= max(n, 1)):
                errs.append(("E_V02_INVALID_K_THRESHOLD", f"K_OF_N k={node.k} invalid for n={n}"))
        for c in node.children:
            _check_ops(c, errs)


def validate_contract(c: Contract, registry: Optional[OriginRegistry] = None) -> Validation:
    v = Validation()
    e = v.errors
    froles, droles = roles_of(c.formula), set(c.roles)
    for r in sorted(droles - froles):
        e.append(("E_V01_ORPHAN_ROLE", f"role {r!r} declared but not used in formula"))
    for r in sorted(froles - droles):
        e.append(("E_V01_UNDEFINED_ROLE", f"role {r!r} used in formula but not declared"))
    _check_ops(c.formula, e)
    if c.window_us < 0:
        e.append(("E_V06_INVALID_SLOT_BOUNDS", "negative simultaneity window"))
    if c.fault_model.diagnosis_budget < 0 or c.fault_model.resilience_requirement < 0 or not (0 <= c.fault_model.report_k <= 3):
        e.append(("E_V12_INVALID_FAULT_MODEL", "fault model out of range (budget,k >= 0; report_k <= 3)"))

    for n, r in c.roles.items():
        a = r.agreement
        if r.kind not in ("evidence", "reference"):
            e.append(("E_V11_INVALID_ROLE_KIND", f"{n}: kind must be evidence|reference"))
        if a.metric not in METRICS:
            e.append(("E_V03_UNKNOWN_METRIC", f"{n}: unknown agreement metric {a.metric!r}"))
        if a.metric in ("abs_diff", "relative_diff") and a.unit.lower() in DISCRETE_UNITS:
            e.append(("E_V03_INCOMPATIBLE_UNIT", f"{n}: continuous metric with discrete unit {a.unit!r}"))
        if a.tolerance < 0 or (a.metric == "discrete_equality" and a.tolerance != 0):
            e.append(("E_V03_INVALID_TOLERANCE", f"{n}: tolerance invalid for metric {a.metric}"))
        if r.time_class_required not in SEMANTIC:
            e.append(("E_V04_ILLEGAL_TIME_CLASS", f"{n}: time_class_required {r.time_class_required.value} is not a semantic timestamp class"))
        if r.value_time_class is not None and r.value_time_class not in SEMANTIC | {TimeClass.LAP_DURATION}:
            e.append(("E_V04_ILLEGAL_TIME_CLASS", f"{n}: value_time_class {r.value_time_class.value} not allowed"))
        f = r.freshness
        for nm, val in (("soft", f.soft_us), ("hard", f.hard_us)):
            if val is not None and val <= 0:
                e.append(("E_V05_INVALID_FRESHNESS", f"{n}: {nm}_age_s must be > 0"))
        if f.soft_us is not None and f.hard_us is not None and f.soft_us > f.hard_us:
            e.append(("E_V05_INVALID_FRESHNESS", f"{n}: soft_age_s > hard_age_s"))
        if r.slot.deadline_us <= 0 or r.slot.lateness_us < 0:
            e.append(("E_V06_INVALID_SLOT_BOUNDS", f"{n}: need deadline_s > 0 and allowed_lateness_s >= 0"))
        if SCOPE_RANK[r.scope_class] > SCOPE_RANK[c.scope_class]:
            e.append(("E_V07_SCOPE_FINER_THAN_DECISION", f"{n}: role scope {r.scope_class.value} is finer than decision scope {c.scope_class.value}"))
        if r.kind == "reference" and not r.fact_type:
            e.append(("E_V11_INVALID_ROLE_KIND", f"{n}: reference role needs fact_type"))
        co = r.corroboration
        if co.mode not in ("INFORMATIONAL", "MANDATORY"):
            e.append(("E_V09_INVALID_CORROBORATION", f"{n}: mode must be INFORMATIONAL|MANDATORY"))
        if co.mode == "MANDATORY" and co.min_source_depth > 0:
            adm = r.admissible_source_origins
            if adm and len(adm) < co.min_source_depth + 1:
                e.append(("E_V09_IMPOSSIBLE_SOURCE_DEPTH", f"{n}: depth {co.min_source_depth} needs >= {co.min_source_depth + 1} admissible origins, got {len(adm)}"))
            elif adm and registry is not None and registry.max_independent(adm) < co.min_source_depth + 1:
                e.append(("E_V10_COMMON_UPSTREAM_INDEPENDENCE_OVERCLAIM",
                          f"{n}: origins {list(adm)} share upstream lineage; at most {registry.max_independent(adm)} are independent"))

    ids = set()
    for cs in c.constraints:
        if cs.id in ids or not cs.id:
            e.append(("E_V08_BAD_CONSTRAINT", f"constraint id missing/duplicate: {cs.id!r}"))
        ids.add(cs.id)
        if cs.kind not in CONSTRAINT_KINDS:
            e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: unknown kind {cs.kind!r}"))
            continue
        bad = [o for o in cs.operands if o not in c.roles or o not in froles]
        if bad:
            e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: operands {bad} are not roles used in the formula"))
            continue
        p, k = cs.params, cs.kind
        need = {"bounds": 1, "abs_diff": 2, "ratio": 2, "equals": 2}.get(k)
        if need and len(cs.operands) != need:
            e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: {k} needs {need} operand(s)"))
        if k in ("abs_diff", "ratio", "linear", "interval") and p.get("tolerance") is None:
            e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: {k} needs a tolerance"))
        if k == "bounds" and p.get("lo") is None and p.get("hi") is None:
            e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: bounds needs lo and/or hi"))
        if k == "linear":
            if len(p.get("coeffs", [])) != len(cs.operands):
                e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: linear needs one coeff per operand"))
            if any(c.roles[o].value_time_class is not None for o in cs.operands):
                e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: linear constraints may not mix time-valued operands (use 'interval')"))
        if k == "interval":
            d, s, en = (c.roles[o] for o in cs.operands)
            tc = p.get("time_class")
            if tc is None or tc not in SEMANTIC:
                e.append(("E_V08_BAD_CONSTRAINT", f"{cs.id}: interval needs a semantic time_class"))
            for nm, role in (("start", s), ("end", en)):
                if role.value_time_class not in SEMANTIC:
                    e.append(("E_V04_ILLEGAL_TIME_CLASS", f"{cs.id}: {nm} role {role.name!r} must declare a semantic value_time_class (LAP_DURATION/RECEIPT/PROCESSING are not timestamps)"))
            if d.value_time_class not in (None, TimeClass.LAP_DURATION):
                e.append(("E_V04_ILLEGAL_TIME_CLASS", f"{cs.id}: duration role must be a quantity or LAP_DURATION"))
    return v
