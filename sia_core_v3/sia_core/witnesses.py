"""Standard Witness Registry for Scoped Integrity Algebra (CR-6).

Centralizes the classification, severity, and normative descriptions of all witness codes
emitted by SIA Core evaluators, specialist agents, and contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Optional


class WitnessSeverity(str, Enum):
    INFO = "INFO"          # Informational context (e.g. legitimate absence, healthy margin)
    WARNING = "WARNING"    # Caveat or weakened confidence (e.g. within uncertainty, single origin)
    DEFECT = "DEFECT"      # Structural failure (e.g. missing mandatory slot, constraint breach)


@dataclass(frozen=True)
class WitnessDefinition:
    code: str
    severity: WitnessSeverity
    category: str
    description: str
    remedial_action: Optional[str] = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "category": self.category,
            "description": self.description,
            "remedial_action": self.remedial_action,
        }


# Canonical Witness Definitions
_REGISTRY: Dict[str, WitnessDefinition] = {
    "HEALTHY_EVIDENCE": WitnessDefinition(
        "HEALTHY_EVIDENCE",
        WitnessSeverity.INFO,
        "HEALTH",
        "All required evidence slots are populated with valid, unexpired, and corroborated observations.",
    ),
    "VOIDED": WitnessDefinition(
        "VOIDED",
        WitnessSeverity.INFO,
        "LIFECYCLE",
        "Decision instance legitimately voided due to session event (retirement, red flag, or lap cancellation).",
        "No remedial action needed; decision excluded from failure metrics.",
    ),
    "MISSING_EVIDENCE": WitnessDefinition(
        "MISSING_EVIDENCE",
        WitnessSeverity.DEFECT,
        "COMPLETENESS",
        "Mandatory evidence slot has passed its deadline without receiving valid observations.",
        "Check feed liveness, adapter connectivity, or participant session status.",
    ),
    "MISSING_REFERENCE_FACT": WitnessDefinition(
        "MISSING_REFERENCE_FACT",
        WitnessSeverity.DEFECT,
        "REFERENCE",
        "Required reference fact (session T0, lap start, surveyed geometry) is unresolved in scope.",
        "Ensure upstream session context or spatial survey registry is populated.",
    ),
    "LATE_REFERENCE_FACT": WitnessDefinition(
        "LATE_REFERENCE_FACT",
        WitnessSeverity.WARNING,
        "TIMING",
        "Reference fact arrived after the contract's soft deadline, delaying verdict finalization.",
    ),
    "STALE_EVIDENCE": WitnessDefinition(
        "STALE_EVIDENCE",
        WitnessSeverity.WARNING,
        "FRESHNESS",
        "Evidence observation exceeds soft age tolerance, indicating a potentially lagging feed.",
    ),
    "EXPIRED_EVIDENCE": WitnessDefinition(
        "EXPIRED_EVIDENCE",
        WitnessSeverity.DEFECT,
        "FRESHNESS",
        "Evidence observation exceeds hard age cutoff; slot is considered dead/expired.",
    ),
    "DISAGREEMENT": WitnessDefinition(
        "DISAGREEMENT",
        WitnessSeverity.WARNING,
        "CORROBORATION",
        "Independent observations for the same evidence role disagree beyond declared tolerance.",
        "Inspect sensor accuracy, calibration drift, or environmental anomalies.",
    ),
    "CONSTRAINT_VIOLATION": WitnessDefinition(
        "CONSTRAINT_VIOLATION",
        WitnessSeverity.DEFECT,
        "INTEGRITY",
        "Cross-role physical or logical constraint failed (bounds, ratio, diff, or interval).",
    ),
    "INSUFFICIENT_CORROBORATION": WitnessDefinition(
        "INSUFFICIENT_CORROBORATION",
        WitnessSeverity.WARNING,
        "INDEPENDENCE",
        "Role requires multiple independent source or processing origins, but fewer disjoint origins were observed.",
    ),
    "COMMON_CAUSE_EXPOSURE": WitnessDefinition(
        "COMMON_CAUSE_EXPOSURE",
        WitnessSeverity.WARNING,
        "LINEAGE",
        "Multiple observing providers share a common upstream dependency token, precluding fault isolation.",
    ),
    "CRITICAL_ORIGIN": WitnessDefinition(
        "CRITICAL_ORIGIN",
        WitnessSeverity.WARNING,
        "RESILIENCE",
        "A single source origin is a single point of failure for this decision instance.",
    ),
    "AMBIGUOUS_DIAGNOSIS": WitnessDefinition(
        "AMBIGUOUS_DIAGNOSIS",
        WitnessSeverity.WARNING,
        "DIAGNOSIS",
        "Multiple competing minimal fault hypotheses exist; no single observation can be safely excluded.",
    ),
    "LATE_EVIDENCE_ADMITTED": WitnessDefinition(
        "LATE_EVIDENCE_ADMITTED",
        WitnessSeverity.WARNING,
        "TIMING",
        "Evidence admitted after decision slot deadline but before finality cutoff.",
    ),
    "POST_FINALITY_QUARANTINED": WitnessDefinition(
        "POST_FINALITY_QUARANTINED",
        WitnessSeverity.WARNING,
        "FINALITY",
        "Evidence arrived after the decision was finalized; quarantined without modifying sealed verdict.",
    ),
    "WITHIN_UNCERTAINTY": WitnessDefinition(
        "WITHIN_UNCERTAINTY",
        WitnessSeverity.WARNING,
        "METROLOGY",
        "Measured quantity is closer to a rule threshold than the combined measurement uncertainty (Pattern P3).",
        "Defer automated sporting enforcement; require human steward review under guard-band policy.",
    ),
    "KINEMATIC_ANOMALY": WitnessDefinition(
        "KINEMATIC_ANOMALY",
        WitnessSeverity.DEFECT,
        "PHYSICS",
        "Vehicle acceleration, brake/throttle exclusivity, or speed delta violates physical plausibility bounds.",
    ),
    "SCHEMA_DRIFT": WitnessDefinition(
        "SCHEMA_DRIFT",
        WitnessSeverity.DEFECT,
        "INGESTION",
        "Feed provider schema hash altered or required fields missing relative to baseline contract.",
    ),
    "FEED_STALLED": WitnessDefinition(
        "FEED_STALLED",
        WitnessSeverity.DEFECT,
        "LIVENESS",
        "Supervisor detected stream cadence drop below minimum expected threshold.",
    ),
    "REFERENCE_LAYOUT_EXPIRED": WitnessDefinition(
        "REFERENCE_LAYOUT_EXPIRED",
        WitnessSeverity.DEFECT,
        "GEOMETRY",
        "Circuit geometry or loop distance reference has expired for the current event layout version.",
        "Re-homologate circuit survey references before relying on timing-derived speeds.",
    ),
}


def get_witness_definition(code: str) -> WitnessDefinition:
    return _REGISTRY.get(code, WitnessDefinition(code, WitnessSeverity.WARNING, "GENERAL", f"Custom witness: {code}"))


def list_witness_definitions() -> Mapping[str, WitnessDefinition]:
    return dict(_REGISTRY)

