# First implementation slice: deterministic VSC demonstration

This is the smallest end-to-end slice that proves the architecture before infrastructure scale or external data access complicates it.

## Goal

Implement a fully deterministic `vsc_pit_window` scenario which produces:

1. source events with preserved simulated event time;
2. canonical event/state projections;
3. Agent 1 race-event lifecycle/exposure findings;
4. Agent 4 pit-window finding deliberately delayed relative to Agent 1;
5. Agent 5 provisional impact assessment v1 followed by superseding v2;
6. FastAPI reads for timeline, drivers, findings, and assessment revisions;
7. a minimal dashboard showing the progression and its evidence.

The first slice can use the in-memory event-bus abstraction. Kafka/Flink integration comes after the behaviour is validated with the same contracts.

## Recommended initial implementation files

### Backend

```text
backend/
├── pyproject.toml
├── pulse/
│   ├── __init__.py
│   ├── main.py
│   ├── contracts/
│   │   ├── enums.py
│   │   ├── events.py
│   │   ├── findings.py
│   │   └── health.py
│   ├── simulator/
│   │   ├── scenarios.py
│   │   └── replay.py
│   ├── stream/
│   │   ├── bus.py
│   │   ├── normalizer.py
│   │   └── projections.py
│   ├── agents/
│   │   ├── base.py
│   │   ├── event_control.py
│   │   ├── strategy.py
│   │   └── fusion.py
│   ├── state/
│   │   └── store.py
│   └── api/
│       ├── router.py
│       └── schemas.py
└── tests/
    ├── test_contracts.py
    ├── test_vsc_scenario.py
    ├── test_event_agent.py
    ├── test_strategy_agent.py
    ├── test_fusion_revisions.py
    └── test_api.py
```

The first slice intentionally omits real adapters, telemetry modelling, Flink, database migrations, and agents 2/3 so it can reach behavioural proof quickly. Their contracts should still be represented by explicit `UNAVAILABLE`/coverage semantics in fusion.

### Frontend

```text
frontend/
├── package.json
├── src/
│   ├── main.tsx
│   ├── app.tsx
│   ├── api/client.ts
│   ├── fixtures/vscPitWindow.ts
│   ├── features/race-state/RaceStateView.tsx
│   ├── features/consequences/ConsequencesView.tsx
│   ├── components/ModeBadge.tsx
│   ├── components/Timeline.tsx
│   ├── components/EvidenceDrawer.tsx
│   └── styles.css
└── tests/
```

Start with fixtures matching API contracts. Add live API/SSE polling only after the UI correctly renders each specified state.

## VSC scenario event script

All times below are session elapsed coordinates. The generated envelope also includes deterministic UTC timestamps and `mode=SIMULATED`.

| Offset | Event | Subject | Purpose |
| --- | --- | --- | --- |
| 0:00 | `SESSION_STARTED` | session | Establish session. |
| 0:01–0:10 | position/lap/tyre state events | drivers 16, 44, 1, 4 | Build baseline race/stint state. |
| 0:11 | `VSC_DEPLOYED` | session | Agent 1 emits active lifecycle finding. |
| 0:11.1 | position/interval update | drivers 16, 44 | Establish relative exposure. |
| 0:11.2 | Agent 1 finding | driver 16 | `DRIVER_EVENT_EXPOSURE`; trigger correlation group. |
| 0:11.5 | fusion deadline | driver 16 | Publish provisional v1 with strategy pending. |
| 0:12 | `PIT_ENTRY` / strategy features | driver 16 | Supplies pit-window context. |
| 0:12.5 | Agent 4 finding | driver 16 | `PIT_WINDOW_OPPORTUNITY`, evidence and assumptions. |
| 0:12.6 | fusion revision | driver 16 | Publish v2 superseding v1. |
| 0:14 | `VSC_ENDING` | session | Lifecycle update. |
| 0:15 | `VSC_ENDED` | session | Final lifecycle state. |

Expected assessment v1:

- status: `PROVISIONAL`;
- trigger: active VSC;
- coverage: event complete, strategy pending/unavailable, track/vehicle unavailable;
- explanation: neutralisation affects pit-loss context but no strategy model result is yet available.

Expected assessment v2:

- status: `PROVISIONAL` or `CONFIRMED` based on configured finality;
- predecessor references v1;
- strategy coverage is complete for this modelled scenario;
- summary describes a potential pit-window advantage, not a pit instruction;
- evidence includes source race-control and pit/stint references plus both agent findings.

## Minimal model interfaces

The first code pass should expose interfaces with the following responsibility boundaries:

| Type | Core methods | Constraints |
| --- | --- | --- |
| `EventBus` | `publish(topic, key, value)`, `subscribe(topic, handler)`, `drain()` | Deterministic delivery ordering in test mode. |
| `ScenarioRunner` | `start()`, `advance_to(offset)`, `pause()`, `resume()`, `restart()` | Does not mutate original event time. |
| `Normalizer` | `validate(event)`, `normalise(event)`, `deduplicate(event)` | Emits terminal input outcome. |
| `RaceStateProjector` | `apply(event)`, `get_driver(driver)`, `get_event(event_id)` | Produces current state and immutable change log. |
| `EventControlAgent` | `on_event(event) -> list[Finding]` | Rule-based lifecycle only. |
| `StrategyAgent` | `on_state(state, context) -> list[Finding]` | Emits only when input threshold is met. |
| `FusionEngine` | `on_finding(finding) -> list[Assessment]`, `on_timeout(time)` | Revisioned and arrival-order independent final state. |
| `RunStore` | `append_*`, `latest_*`, `history_*` | Idempotent by ID + revision. |

## First-slice tests

- [ ] Contract parsing rejects event with missing source/capture/run/time/quality fields.
- [ ] Contract serialization retains all three time coordinates.
- [ ] Duplicate VSC event creates one canonical lifecycle, not two.
- [ ] `VSC_DEPLOYED → VSC_ENDING → VSC_ENDED` is valid; invalid transition is visible.
- [ ] Strategy agent does not emit before the configured minimum state is present.
- [ ] Fusion publishes v1 when deadline fires with Agent 1 evidence.
- [ ] Fusion publishes v2 when Agent 4 later provides a compatible finding.
- [ ] v2 correctly references v1 and preserves v1 historical record.
- [ ] Agent 4 input before Agent 1 input creates the same final v2 content after correlation.
- [ ] API latest endpoint returns v2; history endpoint returns v1 and v2 in order.
- [ ] Dashboard fixture renders the mode badge, lifecycle event, provisional state, superseding state, and evidence refs.

## First-slice done condition

The implementation is ready for Phase 2 only when a new developer can run the same seeded scenario twice and obtain byte-equivalent ordered canonical/finding/assessment payloads apart from explicitly allowed process metadata. The dashboard must visibly explain why the final assessment changed.

