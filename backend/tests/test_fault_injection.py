from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer

from pulse.agents.event_control import EventControlAgent
from pulse.config import get_settings
from pulse.contracts import (
    Completeness,
    EventEnvelope,
    EventTime,
    Finding,
    Interpretation,
    Quality,
    RunContext,
    RunMode,
    SessionRef,
    SourceRef,
    Subject,
    UnitValidation,
    utc_now,
)
from pulse.stream.bus import PulseEventBus
from pulse.stream.flink.manager import get_flink_manager
from pulse.stream.kafka_client import KafkaBroker
from pulse.topics import AGENT_TOPICS, NORMALISED_TOPICS, RAW_TOPICS


def create_test_envelope(event_id: str, event_type: str = "VSC_DEPLOYED", session_id: str = "fault-test-session") -> EventEnvelope:
    now = utc_now()
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        source=SourceRef(
            provider="PULSE_FAULT_INJECTION_TEST",
            adapter="fault_runner_v1",
            source_record_id=f"src-{event_id}",
            capture_id=f"capture-{session_id}",
        ),
        run=RunContext(
            run_id=f"run-{event_id}",
            session_instance_id=session_id,
            mode=RunMode.REPLAY,
        ),
        session=SessionRef(
            season=2026,
            meeting_id="monaco-2026",
            session_id=session_id,
            session_type="RACE",
        ),
        time=EventTime(
            event_time_utc=now,
            session_elapsed_ms=18000,
            ingest_time_utc=now,
        ),
        subject=Subject(segment_id="sector-2", driver_number=16),
        payload={
            "reason": "Fault injection debris test",
            "affected_drivers": [16],
        },
        quality=Quality(
            interpretation=Interpretation.OBSERVED,
            completeness=Completeness.COMPLETE,
            unit_validation=UnitValidation.PASSED,
        ),
    )


@pytest.mark.asyncio
async def test_duplicate_race_control_event():
    """Fault Injection 1: Ingests duplicate raw events and verifies Flink deduplication.
    
    Ensures that downstream EventControlAgent counts do not inflate.
    """
    settings = get_settings()
    broker = KafkaBroker(bootstrap_servers=settings.kafka_bootstrap_servers)
    flink_mgr = get_flink_manager()

    await broker.start()
    try:
        # 1. Verify Flink is healthy and normalizer is running
        assert flink_mgr.client.is_cluster_online(), "Flink cluster must be online"
        job_id = flink_mgr.ensure_normalizer_job_running()
        assert job_id is not None

        # 2. Prepare duplicate event payload
        duplicate_event_id = f"evt-dup-{uuid4().hex[:8]}"
        session_id = f"session-dup-{uuid4().hex[:6]}"
        test_event = create_test_envelope(duplicate_event_id, session_id=session_id)

        # 3. Start consumer on normalized topic to observe outputs
        norm_consumer = await broker.create_consumer(
            topics=[NORMALISED_TOPICS["race_events"]],
            group_id=f"pulse-dup-verifier-{uuid4().hex[:6]}",
            auto_offset_reset="latest",
        )

        try:
            # 4. Inject duplicate events into RAW topic
            # First publication
            await broker.publish(RAW_TOPICS["race_control"], session_id, test_event)
            # Duplicate publication of identical event_id
            await broker.publish(RAW_TOPICS["race_control"], session_id, test_event)

            # 5. Capture records for duplicate_event_id over 4 seconds
            received_matching_records = []
            deadline = asyncio.get_event_loop().time() + 4.0
            while asyncio.get_event_loop().time() < deadline:
                try:
                    msg = await asyncio.wait_for(norm_consumer.getone(), timeout=1.0)
                    val = msg.value
                    if isinstance(val, (str, bytes)):
                        val = json.loads(val)
                    if isinstance(val, dict) and val.get("event_id") == duplicate_event_id:
                        received_matching_records.append(val)
                except asyncio.TimeoutError:
                    continue

            # Flink ROW_NUMBER() OVER (PARTITION BY event_id ...) MUST emit exactly 1 record!
            assert len(received_matching_records) == 1, (
                f"Expected exactly 1 deduplicated record from Flink, got {len(received_matching_records)}"
            )

            # 6. Verify Agent 1 only processes 1 event and does not inflate findings
            bus = PulseEventBus(broker=broker)
            agent = EventControlAgent(bus=bus)
            canonical = EventEnvelope.model_validate(received_matching_records[0])

            initial_emitted = agent.emitted_findings
            await agent.on_event(NORMALISED_TOPICS["race_events"], session_id, canonical)

            # Exactly 2 findings for this 1 event (1 lifecycle + 1 driver exposure for driver 16)
            assert agent.emitted_findings - initial_emitted == 2
            assert agent.processed_events == 1
            assert agent.outcomes_count["FINDING_EMITTED"] == 1

        finally:
            await norm_consumer.stop()

    finally:
        await broker.stop()


@pytest.mark.asyncio
async def test_kafka_consumer_restart():
    """Fault Injection 2: Consumer crash and restart during active stream.
    
    Verifies that Kafka offset commits ensure zero message loss and no skipped messages.
    """
    settings = get_settings()
    broker = KafkaBroker(bootstrap_servers=settings.kafka_bootstrap_servers)
    await broker.start()

    test_group_id = f"pulse-crash-restart-group-{uuid4().hex[:6]}"
    topic = RAW_TOPICS["race_control"]
    session_id = f"session-restart-{uuid4().hex[:6]}"

    event_1 = create_test_envelope(f"evt-restart-1-{uuid4().hex[:6]}", session_id=session_id)
    event_2 = create_test_envelope(f"evt-restart-2-{uuid4().hex[:6]}", session_id=session_id)

    try:
        # Phase 1: Start Initial Consumer
        consumer_1 = AIOKafkaConsumer(
            topic,
            bootstrap_servers=broker.bootstrap_servers,
            group_id=test_group_id,
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
        )
        await consumer_1.start()

        # Publish Event 1
        await broker.publish(topic, session_id, event_1)

        # Receive Event 1 on consumer 1
        msg1 = await asyncio.wait_for(consumer_1.getone(), timeout=4.0)
        assert msg1.value["event_id"] == event_1.event_id

        # Commit offset for Event 1
        await consumer_1.commit()

        # Phase 2: Simulate Consumer Crash / Restart
        # Stop Consumer 1 cleanly simulating process shutdown
        await consumer_1.stop()

        # While consumer is offline, publish Event 2 to Kafka
        await broker.publish(topic, session_id, event_2)

        # Phase 3: Resume New Consumer on the same consumer group
        consumer_2 = AIOKafkaConsumer(
            topic,
            bootstrap_servers=broker.bootstrap_servers,
            group_id=test_group_id,
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
        )
        await consumer_2.start()

        try:
            # Consumer 2 must resume from committed offset and receive Event 2 without message loss
            msg2 = await asyncio.wait_for(consumer_2.getone(), timeout=4.0)
            assert msg2.value["event_id"] == event_2.event_id, (
                f"Expected event {event_2.event_id}, received {msg2.value['event_id']}"
            )
            await consumer_2.commit()
        finally:
            await consumer_2.stop()

    finally:
        await broker.stop()

