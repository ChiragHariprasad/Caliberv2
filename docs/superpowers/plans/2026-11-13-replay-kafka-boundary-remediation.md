# Replay and Kafka Boundary Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the live replay execution path and make the Kafka boundary's real reliability level explicit and testable.

**Architecture:** A reusable in-process replay processor will normalize and dispatch each event through the same agents for normal playback and reconstruction. Kafka remains a transport adapter pending its complete migration; publication failures cannot be swallowed. Historical generated records are constrained to LAB claims.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, aiokafka, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-replay-kafka-boundary-design.md`

## Global Constraints

- Preserve existing PULSE API/topic compatibility.
- Do not claim Flink/Kafka end-to-end validation without a running broker and normalizer.
- Replay reconstruction must not republish source records.
- Legacy/generated evidence defaults to LAB.

## Review Focus

- A seek must exercise specialist agents, not just `StateStore` projection.
- Repeated seek/reset sessions must not retain prior findings or assessments.
- A handler failure must leave replay status `FAILED` and expose the cause.
- Broker publication failure must reach the replay controller rather than silently succeeding.
- A missing Kafka normalizer must be observable as an unhealthy pipeline condition.

---

### Task 1: Canonical replay processor

**Files:**
- Create: `backend/pulse/replay/processor.py`
- Modify: `backend/pulse/replay/controller.py`
- Test: `backend/tests/test_replay_processing.py`

**Interfaces:**
- Produces: `ReplayEventProcessor.process(envelope: EventEnvelope, *, publish: bool) -> None`.
- Consumes: `ReplayController.set_event_processor(processor)`.

- [ ] **Step 1: Write failing tests** for processor dispatch during regular playback, reconstruction during seek, and no external republish during reconstruction.
- [ ] **Step 2: Run the targeted pytest tests and confirm they fail before the new processor exists.**
- [ ] **Step 3: Implement the processor callback and route normal playback and seek through it.**
- [ ] **Step 4: Run targeted replay tests and confirm they pass.**

### Task 2: Application lifecycle integration and failure visibility

**Files:**
- Modify: `backend/pulse/main.py`
- Modify: `backend/pulse/stream/bus.py`
- Modify: `backend/pulse/state/store.py`
- Test: `backend/tests/test_replay_processing.py`

**Interfaces:**
- Consumes: `ReplayEventProcessor` and existing agent handlers.
- Produces: application-owned processor registered with the singleton replay controller.

- [ ] **Step 1: Write failing tests** that a replay callback failure becomes visible and a broker publish exception is propagated.
- [ ] **Step 2: Run targeted tests and confirm expected failures.**
- [ ] **Step 3: Register the shared processor in app lifespan, reset run state correctly, and stop swallowing publication failures.**
- [ ] **Step 4: Run targeted tests and the affected existing replay tests.**

### Task 3: Provenance and dependency remediation

**Files:**
- Modify: `scripts/acquire_historical_race.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_acquisition_provenance.py`

**Interfaces:**
- Produces: generated capture metadata that declares `LAB` when composed records lack primary source artifacts.

- [ ] **Step 1: Write failing tests** for conservative provenance metadata and declared runtime Kafka dependencies.
- [ ] **Step 2: Run targeted tests and confirm failure.**
- [ ] **Step 3: Mark the generated capture regime explicitly and make the installed Confluent dependency reproducible.**
- [ ] **Step 4: Run provenance/dependency and full deterministic test suites.**
