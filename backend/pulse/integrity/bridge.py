"""Bridge between PULSE's Pydantic event model and SIA Core v3's content-addressed domain model.

Translates EventEnvelopes / Findings into SIA atoms / facts, and converts
SIA Assessment results back into JSON-serialisable dicts for the API layer.

All conversions are fail-safe: missing fields log warnings and return None
rather than crashing the pipeline.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

# Ensure sia_core_v3 is importable
_SIA_ROOT = str(Path(__file__).resolve().parents[3] / "sia_core_v3")
if _SIA_ROOT not in sys.path:
    sys.path.insert(0, _SIA_ROOT)

from sia_core import (  # noqa: E402
    IntegrityState,
    OriginRegistry,
    TimeClass,
    TypedTime,
    make_atom,
    make_fact,
    make_guard,
    fmt_instant,
    parse_instant,
    sec_to_us,
    ScopeClass,
)
from sia_core.verdict import Assessment as SIAAssessment  # noqa: E402

from pulse.contracts import EventEnvelope, Finding, Interpretation, Completeness  # noqa: E402

logger = logging.getLogger("pulse.integrity.bridge")

# ---------------------------------------------------------------------------
# Origin configuration
# ---------------------------------------------------------------------------

DEFAULT_ORIGINS: dict[str, list[str]] = {
    "PITWALL": ["F1_FOM_TIMING"],
    "TRACINGINSIGHTS": ["F1_FOM_TIMING"],
    "CAR_SENSOR": [],
    "GPS": [],
    "TIMING_CONFIG": ["F1_FOM_TIMING"],
    "POP_MONITOR": [],
    "SURVEY": [],
    "FIA_OFFICIAL": ["FIA_RACE_CONTROL"],
    "WEATHER_SERVICE": [],
    "FASTF1_RESEARCH": ["F1_TIMING_ARCHIVE", "F1_FOM_TIMING"],
    "JOLPICA_OPEN": ["ERGAST_JOLPICA_ARCHIVE"],
    "SYNTHETIC_SIM": ["PULSE_SYNTHETIC_GENERATOR"],
    "LAB_ARCHIVE": ["PULSE_LAB_COMPOSED_STREAM"],
    "PULSE_PIPELINE": [],
}


def build_origin_registry(origins: dict[str, list[str]] | None = None) -> OriginRegistry:
    """Create an OriginRegistry from a provider-upstream mapping."""
    return OriginRegistry(origins or DEFAULT_ORIGINS)


# ---------------------------------------------------------------------------
# PULSE event type → SIA role mapping
# ---------------------------------------------------------------------------

_EVENT_ROLE_MAP: dict[str, list[str]] = {
    # Lap timing
    "LAP_COMPLETED": ["lap_record"],
    "DRIVER_LAP_DATA": ["lap_record"],
    # Sector timing
    "SECTOR_COMPLETED": ["sector_record"],
    "SECTOR_TIME": ["sector_record"],
    # Speed
    "SPEED_TRAP": ["timing_speed"],
    "PIT_SPEED": ["timing_speed"],
    # Telemetry → vehicle speed
    "CAR_TELEMETRY": ["vehicle_speed"],
    "CAR_TELEMETRY_SAMPLE": ["vehicle_speed"],
    "DRIVER_TELEMETRY": ["vehicle_speed", "position_report"],
    # Position
    "POSITION_UPDATE": ["position_report"],
    "INTERVAL_UPDATE": ["position_report"],
    # Weather
    "WEATHER_OBSERVATION": ["weather_reading"],
}

# Payload key → value extraction for each role
_VALUE_KEYS: dict[str, list[str]] = {
    "lap_record": ["lap_time_seconds", "last_lap_seconds", "lap_time", "duration_s", "value"],
    "sector_record": ["sector_time_seconds", "sector_time", "duration_s", "value"],
    "timing_speed": ["speed_kph", "speed", "pit_speed_kph", "value"],
    "vehicle_speed": ["speed_kph", "speed", "car_speed", "value"],
    "position_report": ["position", "driver_position", "value"],
    "weather_reading": ["air_temp_c", "air_temp", "air_temperature", "track_temp_c", "track_temp", "temperature", "value"],
    "configured_distance": ["distance_cm", "loop_distance_cm", "value"],
}

# Role → unit mapping
_ROLE_UNITS: dict[str, str] = {
    "lap_record": "s",
    "sector_record": "s",
    "timing_speed": "kph",
    "vehicle_speed": "kph",
    "position_report": "enum",
    "weather_reading": "celsius",
    "configured_distance": "cm",
}

# Role → which contract(s) it belongs to
_ROLE_TO_CONTRACT: dict[str, str] = {
    "lap_record": "lap_time",
    "sector_record": "sector_time",
    "timing_speed": "pit_speed",
    "vehicle_speed": "pit_speed",
    "position_report": "driver_position",
    "weather_reading": "weather_observation",
    "configured_distance": "pit_speed",
}


def map_event_to_roles(event_type: str) -> list[str]:
    """Map a PULSE event_type to the SIA role_ids it can populate."""
    return _EVENT_ROLE_MAP.get(event_type.upper(), [])


def role_to_contract(role_id: str) -> str | None:
    """Given a role_id, return the contract_id it belongs to."""
    return _ROLE_TO_CONTRACT.get(role_id)


# ---------------------------------------------------------------------------
# Quality mapping
# ---------------------------------------------------------------------------

def _interpretation_to_grade(interp: str | Interpretation) -> IntegrityState:
    """Map PULSE interpretation to SIA quality grade."""
    s = str(interp).upper()
    if s in ("OBSERVED", "DERIVED"):
        return IntegrityState.HEALTHY
    if s in ("INFERRED", "PREDICTED"):
        return IntegrityState.SUSPECT
    return IntegrityState.UNKNOWN


def _completeness_to_grade(comp: str | Completeness) -> IntegrityState:
    """Map PULSE completeness to SIA quality grade."""
    s = str(comp).upper()
    if s in ("COMPLETE",):
        return IntegrityState.HEALTHY
    if s in ("PARTIAL", "UNKNOWN"):
        return IntegrityState.SUSPECT
    return IntegrityState.DEGRADED


def _quality_grade(envelope: EventEnvelope) -> IntegrityState:
    """Compute the overall SIA quality grade from a PULSE envelope."""
    g1 = _interpretation_to_grade(envelope.quality.interpretation)
    g2 = _completeness_to_grade(envelope.quality.completeness)
    return min(g1, g2)  # pessimistic: take the worst


quality_grade = _quality_grade


# ---------------------------------------------------------------------------
# Scope extraction
# ---------------------------------------------------------------------------

def extract_scope(envelope: EventEnvelope) -> dict[str, str]:
    """Build a scope dict from envelope fields + payload."""
    scope: dict[str, str] = {}

    # Session
    sid = envelope.session.session_id or envelope.run.session_instance_id
    if sid:
        scope["session_id"] = sid

    # Driver
    dn = envelope.subject.driver_number
    if dn is not None:
        scope["driver_id"] = str(dn)

    # Lap from payload
    p = envelope.payload
    for key in ("lap_number", "lap", "current_lap"):
        if key in p and p[key] is not None:
            scope["lap_number"] = str(p[key])
            break

    # Sector from payload
    for key in ("sector_number", "sector", "sector_id"):
        if key in p and p[key] is not None:
            scope["sector_number"] = str(p[key])
            break

    return scope


def build_scope_for_contract(envelope: EventEnvelope, scope_class: str) -> dict[str, str] | None:
    """Build a scope dict with exactly the fields needed for scope_class. None if insufficient."""
    raw = extract_scope(envelope)
    needed = {
        "SESSION": ["session_id"],
        "DRIVER_SESSION": ["session_id", "driver_id"],
        "DRIVER_LAP": ["session_id", "driver_id", "lap_number"],
        "SECTOR": ["session_id", "driver_id", "lap_number", "sector_number"],
    }
    fields = needed.get(scope_class, [])
    if not all(f in raw for f in fields):
        return None
    return {f: raw[f] for f in fields}


# ---------------------------------------------------------------------------
# PULSE → SIA conversion
# ---------------------------------------------------------------------------

def _parse_time_str(val: Any) -> Any:
    """Parse lap time string like '1:17.000' or '77.0' into float seconds."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        v = val.strip()
        if ":" in v:
            try:
                parts = v.split(":")
                if len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
            except (ValueError, TypeError):
                pass
        try:
            return float(v)
        except (ValueError, TypeError):
            pass
    return val


def _extract_value(payload: dict[str, Any], role_id: str) -> Any:
    """Extract the numeric/categorical value from a payload for a given role."""
    keys = _VALUE_KEYS.get(role_id, ["value"])
    for k in keys:
        if k in payload and payload[k] is not None:
            raw = payload[k]
            if role_id in ("lap_record", "sector_record") and isinstance(raw, str):
                return _parse_time_str(raw)
            return raw
    return None


def _provider_to_origin(provider: str) -> str:
    """Normalise a PULSE provider name into an honest SIA source origin without laundering synthetic feeds."""
    p = provider.upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "PULSE_SYNTHETIC_SIM": "SYNTHETIC_SIM",
        "PULSE_SYNTHETIC_SIMULATOR": "SYNTHETIC_SIM",
        "SIMULATOR": "SYNTHETIC_SIM",
        "TEST_HARNESS": "SYNTHETIC_SIM",
        "PULSE_VERIFICATION_HARNESS": "SYNTHETIC_SIM",
        "LAB_COMPOSED_ARCHIVE": "LAB_ARCHIVE",
        "JOLPICA_F1_AND_FIA_OFFICIAL": "JOLPICA_OPEN",
        "JOLPICA": "JOLPICA_OPEN",
        "JOLPICA_OPEN": "JOLPICA_OPEN",
        "FASTF1": "FASTF1_RESEARCH",
        "FASTF1_RESEARCH": "FASTF1_RESEARCH",
        "OPENF1": "TRACINGINSIGHTS",
        "F1_TIMING": "PITWALL",
        "FOM": "PITWALL",
        "LIVE_TIMING": "PITWALL",
        "FIA_OFFICIAL_TIMING": "PITWALL",
        "FIA_OFFICIAL_TIMING_AND_TELEMETRY": "PITWALL",
        "FIA_OFFICIAL": "FIA_OFFICIAL",
        "CAR_ECU": "CAR_SENSOR",
        "CAR_SENSOR": "CAR_SENSOR",
        "WEATHER_SERVICE": "WEATHER_SERVICE",
    }
    return aliases.get(p, p)


def envelope_to_atom(envelope: EventEnvelope, role_id: str):
    """Convert a PULSE EventEnvelope into a SIA EvidenceAtom for the given role.

    Returns the atom, or None if the value cannot be extracted.
    """
    value = _extract_value(envelope.payload, role_id)
    if value is None:
        logger.debug("Cannot extract value for role '%s' from event %s", role_id, envelope.event_id)
        return None

    scope = extract_scope(envelope)
    origin = _provider_to_origin(envelope.source.provider)
    unit = _ROLE_UNITS.get(role_id, "s")
    grade = _quality_grade(envelope)

    # Build observed_at from event_time_utc
    observed_at = envelope.time.event_time_utc.isoformat()

    # Build typed time
    if envelope.time.session_elapsed_ms is not None:
        tt = TypedTime(envelope.time.session_elapsed_ms * 1000, TimeClass.SESSION_ELAPSED)
    else:
        tt = None  # make_atom defaults to ABSOLUTE_UTC from observed_at

    run_suffix = f"-{envelope.run.run_id}" if envelope.run and envelope.run.run_id else ""
    canonical_event_id = (
        envelope.event_id[: -len(run_suffix)]
        if run_suffix and envelope.event_id.endswith(run_suffix)
        else envelope.event_id
    )

    try:
        atom = make_atom(
            role_id=role_id,
            value=value,
            observed_at=observed_at,
            scope=scope,
            source_origins=[origin],
            time=tt,
            unit=unit,
            processing_origins=[f"adapter:{envelope.source.adapter}"],
            processor_family_id=envelope.source.adapter or "pulse_normalizer",
            transform_version="1.0.0",
            raw_event_ids=(canonical_event_id,),
            quality_grade=grade,
        )
        return atom
    except Exception as exc:
        logger.warning("Failed to create atom from event %s for role %s: %s", envelope.event_id, role_id, exc)
        return None


def finding_to_atom(finding: Finding, role_id: str):
    """Convert a PULSE Finding into a SIA EvidenceAtom.

    Returns the atom, or None if conversion fails.
    """
    value = _extract_value(finding.result, role_id)
    if value is None:
        # Try the top-level result dict values
        for v in finding.result.values():
            if isinstance(v, (int, float)):
                value = v
                break
    if value is None:
        return None

    scope: dict[str, str] = {}
    if finding.session_id:
        scope["session_id"] = finding.session_id
    if finding.subject.driver_number is not None:
        scope["driver_id"] = str(finding.subject.driver_number)

    unit = _ROLE_UNITS.get(role_id, "s")
    grade = _interpretation_to_grade(finding.interpretation)

    try:
        atom = make_atom(
            role_id=role_id,
            value=value,
            observed_at=finding.as_of_event_time.isoformat(),
            scope=scope,
            source_origins=[finding.agent_id],
            unit=unit,
            processing_origins=[f"agent:{finding.agent_id}"],
            processor_family_id=finding.agent_id,
            transform_version=finding.model_version,
            raw_event_ids=(finding.finding_id,),
            quality_grade=grade,
        )
        return atom
    except Exception as exc:
        logger.warning("Failed to create atom from finding %s for role %s: %s", finding.finding_id, role_id, exc)
        return None


# ---------------------------------------------------------------------------
# SIA → PULSE conversion
# ---------------------------------------------------------------------------

def _role_evidence_details(
    role_dict: dict[str, Any],
    ledger: Any = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve concrete admitted Atom and ReferenceFact metadata for API/UI inspection."""
    atoms_detail: list[dict[str, Any]] = []
    facts_detail: list[dict[str, Any]] = []
    if ledger is None:
        return atoms_detail, facts_detail

    for aid in role_dict.get("support_atom_ids") or []:
        atom = ledger.get_atom(aid) if hasattr(ledger, "get_atom") else None
        if atom is None:
            rec = (getattr(ledger, "_ids", None) or {}).get(aid)
            atom = getattr(rec, "atom", None)
        if atom is None:
            continue
        atoms_detail.append({
            "atom_id": atom.atom_id,
            "role_id": atom.role_id,
            "value": atom.value,
            "unit": atom.unit,
            "observed_at": fmt_instant(atom.observed_at),
            "source_origins": list(atom.source_origins),
            "processing_origins": list(atom.processing_origins),
            "quality_grade": atom.quality_grade.name if hasattr(atom.quality_grade, "name") else str(atom.quality_grade),
            "raw_event_ids": list(atom.raw_event_ids),
        })
    for fid in role_dict.get("reference_fact_ids") or []:
        fact = ledger.get_fact(fid) if hasattr(ledger, "get_fact") else None
        if fact is None:
            rec = (getattr(ledger, "_ids", None) or {}).get(fid)
            fact = getattr(rec, "fact", None)
        if fact is None:
            continue
        facts_detail.append({
            "fact_id": fact.fact_id,
            "fact_type": fact.fact_type,
            "value": fact.value,
            "unit": fact.unit,
            "valid_from": fmt_instant(fact.valid_from) if fact.valid_from is not None else None,
            "source_origins": list(getattr(fact, "origins", ()) or ()),
        })
    return atoms_detail, facts_detail


def sia_assessment_to_dict(
    assessment: SIAAssessment,
    ledger: Any = None,
    contract: Any = None,
) -> dict[str, Any]:
    """Convert a SIA Assessment into a JSON-serialisable dict enriched with witness details."""
    d = assessment.to_dict()
    roles_out: dict[str, Any] = {}
    distinct_sources: set[str] = set()
    distinct_processors: set[str] = set()
    max_source_depth = 0
    for rname, rinfo in (d.get("roles") or {}).items():
        rcopy = dict(rinfo)
        max_source_depth = max(max_source_depth, int(rcopy.get("source_depth") or 0))
        for dep in rcopy.get("dependencies") or []:
            if isinstance(dep, str) and dep.startswith("S:"):
                distinct_sources.add(dep[2:])
            elif isinstance(dep, str) and dep.startswith("P:"):
                distinct_processors.add(dep[2:])
        atoms_detail, facts_detail = _role_evidence_details(rcopy, ledger=ledger)
        rcopy["atoms_detail"] = atoms_detail
        rcopy["reference_facts_detail"] = facts_detail
        roles_out[rname] = rcopy

    resilience = d.get("resilience") or {}
    crit = resilience.get("critical_origins") or []
    denom = max(1, len(distinct_sources))
    crit_sources = [c for c in crit if isinstance(c, str) and c.startswith("S:")]
    common_cause_exposure = round(min(1.0, len(crit_sources) / denom), 2) if distinct_sources else 1.0

    contract_constraints = []
    if contract is not None and getattr(contract, "constraints", None):
        for cs in contract.constraints:
            params = dict(getattr(cs, "params", {}) or {})
            contract_constraints.append({
                "id": getattr(cs, "id", None),
                "kind": getattr(cs, "kind", None),
                "operands": list(getattr(cs, "operands", ()) or ()),
                "lo": params.get("lo"),
                "hi": params.get("hi"),
                "tolerance": params.get("tolerance", params.get("tol")),
                "uncertainty": params.get("uncertainty"),
            })

    return {
        "decision_instance_id": d.get("decision_instance_id"),
        "contract": d.get("contract"),
        "scope": d.get("scope"),
        "integrity_state": d.get("integrity_state"),
        "validity_timeline": d.get("validity_timeline"),
        "resolution_maturity": d.get("resolution_maturity"),
        "finality_status": d.get("finality_status"),
        "decision_maturity": d.get("decision_maturity"),
        "envelope": d.get("envelope"),
        "roles": roles_out,
        "constraints": d.get("constraints"),
        "contract_constraints": contract_constraints,
        "diagnosis": d.get("diagnosis"),
        "resilience": resilience,
        "witnesses": d.get("witnesses"),
        "witness_set": d.get("witness_set"),
        "primary_binding_witness": d.get("primary_binding_witness"),
        "limitations": d.get("limitations"),
        "source_origins": sorted(distinct_sources),
        "processing_origins": sorted(distinct_processors),
        "corroboration_depth": max_source_depth,
        "common_cause_exposure": common_cause_exposure,
        "evaluated_at": d.get("evaluated_at"),
        "next_transition_at": d.get("next_transition_at"),
        "lease_until": d.get("lease_until"),
        "limiting_children": d.get("limiting_children"),
        "revision_number": d.get("revision_number"),
        "revision_reason": d.get("revision_reason"),
        "knowledge_time": d.get("knowledge_time"),
        "verdict_hash": d.get("verdict_hash"),
        "record_hash": d.get("record_hash"),
        "previous_record_hash": d.get("previous_record_hash"),
        "evidence_frontier": d.get("evidence_frontier"),
    }


def sia_explain(assessment: SIAAssessment) -> str:
    """Produce a template-based explanation of a SIA Assessment."""
    from sia_core import explain
    return explain(assessment)

