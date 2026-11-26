# CALIBRE — Historical Engineering Decision Log

> **Supersession notice (22 November 2026):** This record is retained for design traceability. It contains implementation-status claims that conflict with the current static code audit, including claims about end-to-end archetype wiring and digest unification. Do not use it as a current architecture or completion record; see [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md), [AUDIT.md](AUDIT.md), and [ROADMAP.md](ROADMAP.md).

| Field | Value |
|---|---|
| Platform | CALIBRE Evidence Integrity Platform |
| Engine | Scoped Integrity Algebra (SIA) Core v3 |
| Date | 14 November 2026 |
| Status | Canonical Living Document |

This log records major architectural decisions, trade-offs, rationale, alternatives considered, and invariants enforced across the CALIBRE platform.

---

## ADR-01: Zero Kernel Dependencies Preservation

- **Status:** Enforced
- **Context:** The reasoning kernel (`sia_core_v3`) must outlive current streaming frameworks, database engines, and language packaging ecosystems over a 5–10 year horizon.
- **Decision:** `sia_core_v3` and `standalone_verifier.py` strictly depend on the Python Standard Library only (`hashlib`, `json`, `math`, `datetime`, `dataclasses`, `enum`, `typing`, `bisect`, `decimal`). No external packages (`numpy`, `pandas`, `requests`, `fastapi`, `pydantic`) may be imported into the reasoning kernel.
- **Alternatives Considered:** Using `pydantic` for schema validation or `numpy` for vector calculations. Rejected because third-party dependencies introduce breaking API churn, security vulnerabilities, and packaging lock-in.
- **Consequence:** SIA Core runs identically on any Python 3.10+ runtime, embedded appliances, serverless workers, and offline audit environments.

---

## ADR-02: RFC 8785 Canonical JSON & Algorithm-Tagged Digests (CR-L2)

- **Status:** Enforced
- **Context:** Cryptographic digests must be reproducible bit-for-bit across different platforms, languages, and future kernel implementations. Bare 64-character hashes lack cryptographic agility.
- **Decision:**
  - All JSON hashing utilizes strict RFC 8785 subset: UTF-8 encoding, no whitespace separators (`','`, `':'`), alphabetical key sorting, `allow_nan=False`.
  - All content-addressed digests use the lowercase algorithm prefix: `sha256:<64-hex>`.
  - Legacy bare hashes are accepted only with explicit backward-compatibility validation flags.
- **Alternatives Considered:** Standard `json.dumps()` with arbitrary spacing or unpinned Python dictionary iteration order. Rejected due to hash instability across Python versions and runtimes.

---

## ADR-03: Legitimate Absence Decision Voiding (CR-1)

- **Status:** Enforced
- **Context:** Scheduled decision instances expect observations to arrive before slot deadlines. In dynamic motorsport sessions, cars retire (e.g. Latifi Abu Dhabi 2021 Lap 53) or sessions are suspended under red flag (e.g. Belgium 2021). Without a formal voiding mechanism, silence turns `UNKNOWN` into `DEGRADED`, generating hundreds of false alarms for missing telemetry.
- **Decision:**
  - Implemented `IntegrityEngine.void_decision(instance_id, K, reason, witness_code, detail)`.
  - The decision instance is finalized with `state = UNKNOWN`, `finality_status = FINAL`, `maturity_status = TUPLE_RESOLVED`, `revision_reason = VOIDED`, and a named `VOIDED` witness.
  - Voided decisions are excluded from failure rates while remaining fully auditable.
- **Alternatives Considered:** Cancelling or deleting decision instances. Rejected because deletion destroys audit trails and leaves unexplained sequence gaps.

---

## ADR-04: Lateness Witness for Late Reference Facts (CR-2)

- **Status:** Enforced
- **Context:** When reference facts (such as updated session start times, amended track layouts, or late-entered speed limits) arrive after observations have already been evaluated, the bitemporal index must track the discrepancy.
- **Decision:** Added `LATE_REFERENCE_FACT` witness code to the evaluator. When a reference fact is admitted with an effective time earlier than the latest admitted evidence, the assessment logs a warning witness highlighting the retrofitted reference.
- **Alternatives Considered:** Silently applying the reference fact or rejecting late reference facts outright. Rejected because motorsport telemetry frequently requires post-session baseline alignment.

---

## ADR-05: Formal Witness Code Registry with Tri-Level Severity (CR-6)

- **Status:** Enforced
- **Context:** In early prototypes, witnesses were unstructured string descriptions, making it difficult for downstream consumer systems, dashboards, and automated benchmark scoring to filter signal from noise.
- **Decision:**
  - Created `sia_core_v3/sia_core/witnesses.py` defining standard witness codes with strict tri-level severity:
    - `INFO`: Informational context (e.g. `VOIDED`, `DESCRIPTIVE_CONCENTRATION`).
    - `WARNING`: Sub-optimal evidence conditions (e.g. `WITHIN_UNCERTAINTY`, `COMMON_CAUSE_EXPOSURE`, `LATE_REFERENCE_FACT`, `STALE_REFERENCE`).
    - `DEFECT`: Structural integrity failures (e.g. `MISSING_MANDATORY_ROLE`, `OUT_OF_ORDER_TIMESTAMP`, `KINEMATIC_INCONSISTENCY`, `TIME_CONVERSION_FAILED`).
  - Added programmatic lookup `lookup_witness_severity(code)`.

---

## ADR-06: Zone Sub-Scope Support (CR-10)

- **Status:** Enforced
- **Context:** Decision instances in pit-lane speed enforcement and track limit monitoring operate on micro-sectors or timing loop zones (e.g. the first 26.92 m pit entry zone at Monaco).
- **Decision:** Added `ScopeClass.ZONE = "ZONE"` to `sia_core_v3/sia_core/model.py` with scope field bindings `("session_id", "driver_id", "lap_number", "zone_id")`, allowing high-resolution local integrity decisions without polluting driver-lap scopes.

---

## ADR-07: Pattern P3 Guard-Banded Threshold Uncertainty (CR-L6)

- **Status:** Enforced
- **Context:** In strict threshold enforcement (e.g. 0.1 km/h pit speeding in Monaco 2026), standard measurement uncertainty ($\pm 5$ cm over 26.92 m $\approx \pm 0.11$ km/h) often exceeds the alleged violation margin. Naive systems treat 60.08 km/h as an absolute violation of a 60.0 km/h limit.
- **Decision:**
  - Evaluates margin $m = v_{obs} - v_{limit}$ against combined standard uncertainty $u_c = \sqrt{u_{obs}^2 + u_{limit}^2}$.
  - When $|m| \le u_c$, emits `ThresholdWitness(classification="INDETERMINATE")` and registers witness `WITHIN_UNCERTAINTY`.
  - Crucially, CALIBRE never decides sporting penalties or declares whether a rule was broken; it informs human stewards that the alleged exceedance lies within the noise band of the measurement instrument.

---

## ADR-08: Five Specialist Agent Archetypes (A1–A5) & AR-1..AR-10 Enforcement

- **Status:** Enforced
- **Context:** Translating raw heterogeneous data streams into evidence must be decoupled from the reasoning kernel to allow replacing data sources without architectural rewrites.
- **Decision:**
  - Implemented 5 specialist archetypes in `calibre_core/agents/`:
    - **A1 Timing Agent:** Official loop durations, speed traps, sector times; numbering regression detection.
    - **A2 Vehicle Telemetry Agent:** ECU speed, throttle/brake exclusivity, kinematic plausibility ($>2.0$g anomaly detection).
    - **A3 Spatial Agent:** Gate crossing interpolation, path length integration, effective-dated geometry reference generation.
    - **A4 Session Context Agent:** Flag lifecycles (SC/VSC/Yellow/Red), driver retirement tracking, rule limits.
    - **A5 Feed Supervisor Agent:** Independent tap, monotonic clock ticks, `STALLED`/`RESUMED` guards.
  - Strict compliance with Agent Rules:
    - **AR-1:** Emit observations only; never integrity grades or fault verdicts.
    - **AR-2:** Deterministic atom IDs derived from canonical JSON hashes.
    - **AR-3:** Explicit two-axis origin lineage (`source_origins`, `processing_origins`).
    - **AR-4:** Diagnostics recorded for all unparseable, anomalous, or regressive input.

---

## ADR-09: Complete F1 Contract Catalogue (C01–C13)

- **Status:** Enforced
- **Context:** The platform requires standardized, mathematically rigorous specifications of evidence requirements covering the full spectrum of motorsport decisions.
- **Decision:**
  - Implemented all 13 contracts in `calibre_core/contracts/catalogue.py`:
    - `C01`: Lap-time consistency
    - `C02`: Sector-sum consistency
    - `C03`: Pit-lane speed enforcement (flagship P1, P2, P3, P4, P8)
    - `C04`: Vehicle kinematic plausibility
    - `C05`: Telemetry time alignment
    - `C06`: Position and track consistency
    - `C07`: Session-status integrity
    - `C08`: Incident timing
    - `C09`: Weather reporting
    - `C10`: Weather-dependent advisory (scope locality)
    - `C11`: Feed-source integrity
    - `C12`: Population monitor health
    - `C13`: Rule-regime consistency
  - All contracts pass kernel structural validation (`validate_contract().ok == True`).

---

## ADR-10: Multi-Race Acquisition Pipeline & Jolpica-F1 Ergast Fallback

- **Status:** Enforced
- **Context:** Public telemetry mirrors (such as FastF1 static mirror) experience rate-limiting, incomplete sessions, or missing extended live timing for certain historical rounds (e.g. Austria 2023, Australia 2023, COTA 2024, Las Vegas 2023).
- **Decision:**
  - Built an automated dual-engine acquisition pipeline in `scripts/acquire_f1_corpus.py`.
  - When FastF1 raises `SessionNotAvailableError` or unpopulated laps, the pipeline automatically fails over to the open Jolpica-F1 Ergast API (`http://api.jolpi.ca/ergast/f1/`), retrieving 100% complete entry lists, classification, lap-by-lap records, and pit stops.
  - All payloads are sanitized with `clean_for_json()` to replace non-compliant IEEE 754 `NaN`/`Infinity` floats with canonical `None` values before RFC 8785 hashing.

---

## ADR-11: Content-Addressed Admission Log Engine (`LOG v1.0`)

- **Status:** Enforced
- **Context:** The reasoning kernel must be a pure, deterministic function of an ordered log. Replay must reproduce identical verdicts and record hashes bit for bit.
- **Decision:**
  - Created `calibre_core/admission.py` implementing `AdmissionLogWriter` and `AdmissionLogReader`.
  - Sequential integer microsecond timestamps, strictly monotonic sequence IDs, and SHA-256 hash chaining (`previous_digest`).
  - Seamless replay bridge dispatching `ATOM`, `FACT`, `GUARD`, `CONFIG`, `SCHEDULE`, `VOID`, and `TICK` directly into `IntegrityEngine`.

---

## ADR-12: Radical Provenance Honesty Across Four Data Regimes

- **Status:** Enforced
- **Context:** Downstream sports telemetry consumers often conflate multiple commercial APIs as "independent sources" when they all rely on the same FOM live timing feed.
- **Decision:**
  - Four explicit data governance regimes:
    - `PUBLIC`: Unofficial or public feeds. Two-axis origin lineage reports source depth 1 across all public feeds; `COMMON_CAUSE_EXPOSURE` is reported on every verdict. No isolation claims.
    - `LICENSED`: Commercial contracted feeds with verified upstream lineage.
    - `INSTITUTIONAL`: Dedicated timing loop transponders, FIA race control networks, surveyed loop registers. Genuine independent measurement paths.
    - `LAB`: Synthetic twins and fault-injected benchmarks for mechanism proofs.

