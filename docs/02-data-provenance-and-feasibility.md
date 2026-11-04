# Data provenance and feasibility gate

## Why this gate comes before real replay

PULSE needs more than finishing positions. Its central claim relies on temporal relationships among race-control events, driver state, sector/lap timing, pits, tyres, weather, and track status. A source that supplies only results cannot validate the main product hypothesis.

The project may build its simulator and interfaces before this gate passes. It must not label a real-data replay as an evaluated MVP until at least one historical capture is approved through this process.

## Source policy

| Source class | Allowed use | Conditions |
| --- | --- | --- |
| PULSE deterministic simulator | Development, demos, resilience tests, contract tests. | Mark `mode=SIMULATED`; include scenario version and generator seed. |
| Jolpica | Calendar, circuit, team, driver, result, lap, and pit reference data. | Record API version/query and acquisition time. Do not treat it as high-frequency telemetry or live race control. |
| FastF1 historical archive | Optional detailed replay adapter. | Only with valid authorised access and recorded capture provenance. Verify current access requirements before implementation. |
| FIA publications | Rules, classifications, reference validation. | Cite document version and publication date. |
| Independently sourced historical capture | Replay/evaluation data. | Confirm licence, origin, completeness, hash, and retention permission. |
| Licensed team/circuit/provider feed | Future live operation. | Contract, entitlement, rate limits, and operational source agreement required. |
| OpenF1-derived data | Isolated legacy material only. | Must not become a PULSE adapter, fallback, or evaluation input. |

## Required source manifest

Every capture needs a machine-readable and human-reviewed manifest before admission. Store it under `data/manifests/<capture_id>.yaml` once implementation starts.

```yaml
capture_id: example-2024-race-capture-001
content_hash: sha256:<immutable-content-hash>
acquired_at_utc: 2026-11-04T00:00:00Z
source:
  provider: AUTHORISED_PROVIDER
  adapter: historical_capture_adapter
  source_url_or_reference: internal-or-public-reference
  source_terms_reference: licence-or-contract-reference
  permitted_uses: [development, evaluation]
session:
  season: 2024
  meeting_id: provider-specific-id
  session_id: provider-specific-id
  session_type: RACE
coverage:
  race_control: complete
  positions_and_intervals: complete
  laps_and_sectors: complete
  pits: complete
  tyres: partial
  weather: complete
  track_status: complete
  telemetry: unavailable
  circuit_geometry: verified
gaps:
  - Telemetry is absent; vehicle-response work is timing-only and cannot make telemetry claims.
approval:
  reviewed_by: required
  reviewed_at_utc: required
  approved_for: [simulation_baseline, replay]
```

## Coverage definitions

| Status | Meaning | Allowed analytical use |
| --- | --- | --- |
| `complete` | Known complete for the stated session scope and a representative sample was verified. | Feature/model evaluation allowed within declared measurement limits. |
| `partial` | Known gaps, lower cadence, or incomplete fields. | Use only where the specific output explicitly reflects incomplete coverage. |
| `unavailable` | Cannot be sourced with valid provenance. | Must remain unavailable; no silent imputation. |
| `unknown` | Not audited. | Cannot be admitted to a benchmark/replay run. |

Completeness means the source can support a defined question, not that every physical variable is measured. For example, lap timing can support a pace deviation but cannot directly establish tyre surface temperature or mechanical condition.

## Three-race coverage audit

Select sessions only after inspecting available data. The desired set contains:

| Dataset role | Required characteristic | Primary evaluation purpose |
| --- | --- | --- |
| A | Predominantly dry race with conventional pit strategy. | Baselines for state reconstruction, pace, and stint modelling. |
| B | Safety Car/VSC and multiple race interruptions. | Event lifecycle and consequence analysis. |
| C | Wet or materially changing weather/track condition. | Track-state transitions and supported vehicle/strategy response. |

### Audit matrix template

Replace `TBD` only after evidence is captured in the source manifest. Do not choose a race based solely on public results availability.

| Field | Dataset A | Dataset B | Dataset C |
| --- | --- | --- | --- |
| Candidate session | TBD | TBD | TBD |
| Capture ID | TBD | TBD | TBD |
| Provenance approved? | ☐ | ☐ | ☐ |
| Licence permits development/evaluation? | ☐ | ☐ | ☐ |
| Race-control messages / flags | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Position and interval events | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Lap and sector times | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Pit events | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Compound and stint data | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Weather observations | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Track status / segment scope | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Telemetry (optional) | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable | ☐ complete / ☐ partial / ☐ unavailable |
| Ground-truth timeline prepared? | ☐ | ☐ | ☐ |
| Held-out interval identified? | ☐ | ☐ | ☐ |
| Intended use | baseline | event impact | changing-condition |
| Gaps and caveats | TBD | TBD | TBD |

## Admission checklist

### Capture admission

- [ ] Source name, legal/contractual basis, acquisition date, and original identifier are recorded.
- [ ] The raw capture is immutable and has a content hash.
- [ ] The source manifest has a named reviewer.
- [ ] Session/meeting/session-type identifiers map without ambiguity.
- [ ] All timestamp semantics are documented, including time zone and session elapsed time.
- [ ] Schema samples validate against the PULSE envelope or a documented adapter mapping.
- [ ] Duplicates, clock resets, gaps, and out-of-order patterns have been profiled.
- [ ] Missing or unsupported fields remain explicit rather than imputed.
- [ ] The capture is labelled `SIMULATED`, `REPLAY`, or `LIVE` correctly.

### Historical replay admission

- [ ] All mandatory MVP streams are complete, or the declared replay scope excludes unsupported features.
- [ ] Event and pit timelines have been manually sampled against an independent reference.
- [ ] A reproducible replay configuration references only capture IDs and content hashes.
- [ ] A held-out time interval or session is reserved before model tuning.
- [ ] The dashboard data-mode badge and provenance panel show the actual run mode.

## Data-quality controls

The initial ingestion job records one of four terminal outcomes for every admitted record: `ACCEPTED`, `DUPLICATE`, `DEAD_LETTER`, or `PENDING_LATE_WINDOW`. Later processing may revise derived state, but must never modify original source time or source payload.

Validation includes:

- schema version and required envelope fields;
- provider-to-canonical identifier mapping;
- unit plausibility and explicit unit conversion history;
- timestamp parseability and source clock semantics;
- stable source-record identifier or documented generated deduplication fingerprint;
- mode/source/capture provenance;
- payload-specific checks such as non-negative stint age and valid driver number.

## Data limitations and claim language

Use the wording below in APIs and UI copy:

| Evidence available | Permitted wording | Forbidden leap |
| --- | --- | --- |
| Lap/sector timing | “Observed pace deviation relative to this driver’s contextual baseline.” | “The car has a mechanical fault.” |
| Weather + track status | “Observed wet/drying track-status transition.” | “Measured grip fell by X” without direct grip measurement. |
| Race-control message | “VSC lifecycle is active based on source message.” | A fictional sporting classification or unrecorded control instruction. |
| Tyre stint + pace | “Modelled degradation/pit-window estimate.” | A claim that actual tyre temperature/wear was measured when it was not. |
| Simulator | “Deterministic simulated scenario outcome.” | A historical or live competitive prediction. |

## Exit decision

Phase 0 passes when at least one non-OpenF1 historical capture supports a clearly bounded replay evaluation with a complete provenance manifest. It is acceptable for the full three-race study to remain incomplete at this point, provided the project states the limited scope. If no such capture is secured, the simulator/demo MVP remains viable; real-data validation is blocked and must be described as such.

