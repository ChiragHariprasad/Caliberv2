# PULSE project charter

## Mission

PULSE converts a race's fragmented event streams into a continuously revised answer to four operational questions:

1. What happened and what is currently active?
2. Which drivers and circuit segments are affected?
3. What observed changes and supported inferences explain the impact?
4. What competitive effects are likely over the next one to three laps?

The product is aimed at race strategists, performance engineers, vehicle-dynamics analysts, and motorsport data analysts. It provides analytical evidence; it does not make authoritative sporting decisions.

## Problem statement

Formula 1 sessions emit heterogeneous signals at different rates: race-control updates, positions and intervals, sector and lap timing, tyre stints, pit events, weather, track status, and sometimes telemetry. A VSC, Safety Car, rainfall onset, pit cycle, or pace change can alter the competitive context for several drivers at once. A dashboard that merely lists inputs fails to explain these consequences.

PULSE uses specialised services to independently establish event state, track conditions, vehicle response, and strategy implications. A deterministic fusion service relates their findings and exposes an explainable driver-level assessment.

## Product scope

### v0.1 supported inputs and intelligence

| Area | v0.1 responsibility |
| --- | --- |
| Race events | Safety Car, VSC, yellow flag, red flag, session status, and lifecycle updates where supported by the source. |
| Race state | Positions, intervals, gaps, laps, sectors, pit entry/stop/exit, tyre compound, and stint age. |
| Track context | Weather, track status, circuit segments, direct observations, and explicit data-quality gaps. |
| Vehicle response | Driver-relative speed and sector deviations only when measurements support them. |
| Strategy | Contextual tyre degradation, pit-window estimates, and alternative pit scenarios. |
| Consequences | Affected drivers, evidence, uncertainty, partial assessments, revisions, and short-horizon forecasts. |

### Explicitly out of scope for v0.1

- Video crash recognition, radio sentiment, and driver emotion analysis.
- Mechanical failure diagnosis or driver-error attribution.
- Battery, state-of-charge, or MGU-K predictions without authorised energy telemetry.
- Automatic pit instructions, FIA penalties, and race-control automation.
- Any claim that a synthetic or replayed session is a live Grand Prix feed.

## Operating modes

| Mode | Purpose | Data rule |
| --- | --- | --- |
| `SIMULATED` | Development, deterministic demonstrations, and fault injection. | Every output must identify its synthetic provenance. |
| `REPLAY` | Historical events published at real-time or accelerated speed. | Preserve original event time and keep replay clock separate. |
| `LIVE` | Future ingestion from a licensed or authorised provider. | Use the same contracts, but only after source access is approved and documented. |

Modes cannot be mixed without an explicit run boundary and provenance label. Synthetic observations must never be silently substituted for missing observed telemetry.

## Frozen architectural decisions

1. **Kafka-mediated agents.** Agents exchange structured messages through versioned Kafka topics rather than direct agent-to-agent calls.
2. **Five independently meaningful agents.** Each owns a distinct analytical question and measurable contribution.
3. **Deterministic fusion.** Agent 5 uses structured correlation, bounded waiting, and explicit revision rules. It is not an unconstrained language-model decision maker.
4. **Event-time correctness.** Original source time, ingest time, and replay clock are separate fields with distinct meanings.
5. **Evidence and provenance first.** An intelligence output contains evidence references, data coverage, interpretation class, uncertainty, and revision linkage.
6. **No OpenF1 dependency.** OpenF1 is excluded as a primary, fallback, or required adapter. Existing OpenF1-derived records remain isolated legacy material.
7. **Data feasibility before real replay.** The real-data MVP needs a provenance-approved coverage audit. The simulator may proceed in parallel.

## Definition of useful v0.1

v0.1 is useful when a deterministic simulation or an approved historical replay can:

- reconstruct session, driver, stint, event, and track-segment state from out-of-order input;
- publish individual specialist findings and a traceable fused assessment;
- show partial assessment followed by a revision when later evidence arrives;
- distinguish observed, derived, inferred, and predicted information;
- provide a dashboard with race, track, strategy, impact, and operations views;
- recover from duplicate/late events and replay interruption without duplicate final findings.

## Success measures

These are engineering acceptance targets, not claims about Formula 1 operational performance:

| Measure | Initial target |
| --- | --- |
| Input accounting | Every admitted record has a pending, accepted, discarded, or dead-letter outcome. |
| Event detection | F1 >= 0.90 against defined held-out labels for supported event types. |
| Normalised event to first finding | p95 < 2 seconds at 1x replay after infrastructure tuning. |
| Finding to fused update | p95 < 3 seconds after required inputs arrive. |
| Recovery | Replay restart does not persist duplicate final findings. |
| Provenance | 100% of intelligence output links to evidence or explicitly says its input is unavailable. |
| Multi-agent value | Complete fusion outperforms a chosen simple baseline on at least one held-out primary task without material degradation elsewhere. |

