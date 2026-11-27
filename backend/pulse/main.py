from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pulse.agents.event_control import EventControlAgent
from pulse.agents.fusion import ConsequenceFusionEngine
from pulse.agents.track_state import TrackStateAgent
from pulse.agents.tyre_strategy import TyreStrategyAgent
from pulse.agents.vehicle_response import VehicleResponseAgent
from pulse.integrity.agent import IntegrityAgent
from pulse.api.router import api_router
from pulse.integrity.router import integrity_router
from pulse.config import get_settings
from pulse.contracts import Assessment, EventEnvelope, Finding, RunStatus
from pulse.replay.processor import ReplayEventProcessor
from pulse.simulator.runner import get_scenario_runner
from pulse.state.store import get_state_store
from pulse.stream.bus import get_event_bus
from pulse.stream.kafka_client import get_kafka_broker
from pulse.stream.normalizer import StreamNormalizer
from pulse.topics import (
    AGENT_TOPICS,
    INTELLIGENCE_TOPICS,
    NORMALISED_TOPICS,
    RAW_TOPICS,
    raw_topic_for_event,
    routing_key,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pulse.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: manages Kafka broker, stream normalizer, 5 specialist agents, and scenario runner."""
    settings = get_settings()
    settings.validate_security_posture()
    bus = get_event_bus()
    broker = get_kafka_broker()
    normalizer = StreamNormalizer()
    store = get_state_store()
    runner = get_scenario_runner()

    logger.info("Initializing PULSE Race Intelligence Engine...")

    # 1. Connect Kafka broker according to transport_mode
    mode = settings.transport_mode.upper()
    flink_online = False
    if mode == "KAFKA":
        try:
            await broker.start()
            logger.info("Kafka cluster online at %s", broker.bootstrap_servers)
        except Exception as e:
            logger.error("FATAL: KAFKA transport mode required but connection failed at %s: %s", broker.bootstrap_servers, e)
            raise RuntimeError(f"KAFKA transport mode required but connection failed at {broker.bootstrap_servers}: {e}") from e

        from pulse.stream.flink.manager import get_flink_manager
        flink_mgr = get_flink_manager()
        flink_online = flink_mgr.client.is_cluster_online()
        if not flink_online:
            if settings.flink_required:
                logger.error("FATAL: KAFKA transport mode requires Flink stream normalizer, but Flink cluster is offline at %s", flink_mgr.client.rest_url)
                raise RuntimeError(f"KAFKA transport mode requires Flink stream normalizer, but Flink cluster is offline at {flink_mgr.client.rest_url}")
            else:
                logger.warning("Flink cluster is offline at %s. Operating in KAFKA mode with Python in-process stream normalizer fallback.", flink_mgr.client.rest_url)
        else:
            try:
                job_id = flink_mgr.ensure_normalizer_job_running()
                logger.info("Flink cluster online at %s. Flink streaming normalizer active (job: %s).", flink_mgr.client.rest_url, job_id)
            except Exception as e:
                if settings.flink_required:
                    logger.error("FATAL: Failed to ensure Flink normalizer job running: %s", e)
                    raise RuntimeError(f"Failed to ensure Flink normalizer job running: {e}") from e
                flink_online = False
                logger.warning("Flink normalizer deployment unavailable (%s). Using Python stream normalizer fallback.", e)
    elif mode == "MEMORY":
        logger.info("Operating in MEMORY transport mode (unit tests). In-memory event bus active.")
    elif mode == "SIMULATOR":
        logger.info("Operating in SIMULATOR transport mode. Local deterministic bus active.")
    else:
        raise ValueError(f"Unsupported transport_mode: {settings.transport_mode}")

    from pulse.replay.controller import get_replay_controller
    replay_controller = get_replay_controller()
    wal_path = (settings.sia_wal_path or "").strip() or None

    # 2. Instantiate all 6 agents and register for execution transparency
    agent_ec = EventControlAgent(bus=bus)
    agent_ts = TrackStateAgent(bus=bus)
    agent_vr = VehicleResponseAgent(bus=bus)
    agent_ty = TyreStrategyAgent(bus=bus)
    agent_fu = ConsequenceFusionEngine(bus=bus)
    agent_ia = IntegrityAgent(bus=bus, wal_path=wal_path, session_id=replay_controller.session_id)

    store.register_agent(agent_ec)
    store.register_agent(agent_ts)
    store.register_agent(agent_vr)
    store.register_agent(agent_ty)
    store.register_agent(agent_fu)
    store.register_agent(agent_ia)

    # 3. Normalizer subscriber: routes raw telemetry/events to canonical streams
    async def raw_event_handler(topic: str, key: str, value: Any) -> None:
        canonical_env, target_topic = normalizer.process(value)
        if canonical_env and target_topic:
            await bus.publish(target_topic, key, canonical_env)

    if mode != "KAFKA" or not flink_online:
        for raw_topic in RAW_TOPICS.values():
            bus.subscribe(raw_topic, raw_event_handler)

    # 4. Normalized topic subscribers: route canonical events to agents and StateStore
    async def normalized_race_events_handler(topic: str, key: str, value: Any) -> None:
        try:
            env = value if isinstance(value, EventEnvelope) else EventEnvelope.model_validate(value)
            store.record_canonical_event(env)
            await agent_ec.on_event(topic, key, env)
            await agent_ts.on_event(topic, key, env)
            await agent_ty.on_event(topic, key, env)
            await agent_ia.on_event(topic, key, env)
        except Exception as e:
            logger.error("Error in normalized race events pipeline: %s", e)

    async def normalized_driver_laps_handler(topic: str, key: str, value: Any) -> None:
        try:
            env = value if isinstance(value, EventEnvelope) else EventEnvelope.model_validate(value)
            store.record_canonical_event(env)
            await agent_vr.on_event(topic, key, env)
            await agent_ia.on_event(topic, key, env)
        except Exception as e:
            logger.error("Error in normalized driver laps pipeline: %s", e)

    async def normalized_driver_state_handler(topic: str, key: str, value: Any) -> None:
        try:
            env = value if isinstance(value, EventEnvelope) else EventEnvelope.model_validate(value)
            store.record_canonical_event(env)
            await agent_vr.on_event(topic, key, env)
            await agent_ty.on_event(topic, key, env)
            await agent_ia.on_event(topic, key, env)
        except Exception as e:
            logger.error("Error in normalized driver state pipeline: %s", e)

    async def normalized_track_handler(topic: str, key: str, value: Any) -> None:
        try:
            env = value if isinstance(value, EventEnvelope) else EventEnvelope.model_validate(value)
            store.record_canonical_event(env)
            await agent_ts.on_event(topic, key, env)
            await agent_ia.on_event(topic, key, env)
        except Exception as e:
            logger.error("Error in normalized track pipeline: %s", e)

    async def normalized_tyre_stints_handler(topic: str, key: str, value: Any) -> None:
        try:
            env = value if isinstance(value, EventEnvelope) else EventEnvelope.model_validate(value)
            store.record_canonical_event(env)
            await agent_ty.on_event(topic, key, env)
            await agent_ia.on_event(topic, key, env)
        except Exception as e:
            logger.error("Error in normalized tyre stints pipeline: %s", e)

    async def dispatch_normalized(topic: str, key: str, envelope: EventEnvelope) -> None:
        """Send a canonical envelope through the same handlers used at runtime."""
        handlers = {
            NORMALISED_TOPICS["race_events"]: normalized_race_events_handler,
            NORMALISED_TOPICS["driver_laps"]: normalized_driver_laps_handler,
            NORMALISED_TOPICS["driver_state"]: normalized_driver_state_handler,
            NORMALISED_TOPICS["track_segments"]: normalized_track_handler,
            NORMALISED_TOPICS["tyre_stints"]: normalized_tyre_stints_handler,
        }
        handler = handlers.get(topic)
        if handler is None:
            raise ValueError(f"No normalized handler registered for topic {topic}")
        await handler(topic, key, envelope)

    if mode != "KAFKA":
        bus.subscribe(NORMALISED_TOPICS["race_events"], normalized_race_events_handler)
        bus.subscribe(NORMALISED_TOPICS["driver_laps"], normalized_driver_laps_handler)
        bus.subscribe(NORMALISED_TOPICS["driver_state"], normalized_driver_state_handler)
        bus.subscribe(NORMALISED_TOPICS["track_segments"], normalized_track_handler)
        bus.subscribe(NORMALISED_TOPICS["tyre_stints"], normalized_tyre_stints_handler)

    # 5. Agent findings subscribers: route findings to Fusion Engine (Agent 5) and StateStore
    async def agent_finding_handler(topic: str, key: str, value: Any) -> None:
        try:
            finding = value if isinstance(value, Finding) else Finding.model_validate(value)
            store.record_finding(finding)
            await agent_fu.on_finding(topic, key, finding)
        except Exception as e:
            logger.error("Error processing agent finding: %s", e)

    for agent_topic in AGENT_TOPICS.values():
        bus.subscribe(agent_topic, agent_finding_handler)

    # 6. Intelligence subscribers: route fused assessments to StateStore
    async def intelligence_handler(topic: str, key: str, value: Any) -> None:
        try:
            assessment = value if isinstance(value, Assessment) else Assessment.model_validate(value)
            store.record_assessment(assessment)
        except Exception as e:
            logger.error("Error recording intelligence assessment: %s", e)

    bus.subscribe(INTELLIGENCE_TOPICS["driver_impact"], intelligence_handler)

    async def publish_raw(topic: str, key: str, envelope: EventEnvelope) -> None:
        await bus.publish(topic, key, envelope)

    processor = ReplayEventProcessor(normalizer, dispatch_normalized, publish_raw if mode == "KAFKA" else None)

    async def process_replay_event(envelope: EventEnvelope, *, publish: bool) -> None:
        # KAFKA playback is normalized by its dedicated external Flink job.
        # A seek rebuild is local-only so agent/fusion state is reconstructed
        # without producing duplicate raw or finding records.
        if mode == "KAFKA" and publish:
            await publish_raw(
                raw_topic_for_event(envelope.event_type),
                routing_key(
                    envelope.run.session_instance_id,
                    envelope.subject.driver_number,
                    envelope.subject.segment_id,
                ),
                envelope,
            )
            return
        if not publish:
            async with bus.local_only():
                await processor.process(envelope, publish=False)
            return
        await processor.process(envelope, publish=True)

    # 7. In KAFKA transport mode, consume all normalized streams from Kafka with idempotent WAL sink
    kafka_consumer_task: asyncio.Task | None = None
    verdict_sink: Any = None
    if mode == "KAFKA":
        from collections import deque
        from pathlib import Path
        from pulse.replay.controller import ReplayStatus, get_replay_controller
        from pulse.stream.kafka_io import IdempotentVerdictSink

        from aiokafka import TopicPartition
        verdict_db_path = Path("data/pulse_verdicts.sqlite")
        verdict_db_path.parent.mkdir(parents=True, exist_ok=True)
        verdict_sink = IdempotentVerdictSink(verdict_db_path)
        consumer_ready = asyncio.Event()
        paused_replay_buffer: deque[tuple[str, int, int, str, EventEnvelope]] = deque(maxlen=5000)

        async def _route_normalized(topic: str, key_str: str, env: EventEnvelope) -> None:
            if topic == NORMALISED_TOPICS["race_events"]:
                await normalized_race_events_handler(topic, key_str, env)
            elif topic == NORMALISED_TOPICS["driver_laps"]:
                await normalized_driver_laps_handler(topic, key_str, env)
            elif topic == NORMALISED_TOPICS["driver_state"]:
                await normalized_driver_state_handler(topic, key_str, env)
            elif topic == NORMALISED_TOPICS["track_segments"]:
                await normalized_track_handler(topic, key_str, env)
            elif topic == NORMALISED_TOPICS["tyre_stints"]:
                await normalized_tyre_stints_handler(topic, key_str, env)

        async def kafka_consumer_loop() -> None:
            try:
                consumer = await broker.create_consumer(
                    topics=list(NORMALISED_TOPICS.values()),
                    group_id="pulse-backend-normalised-consumer-v2",
                    auto_offset_reset="latest",
                    enable_auto_commit=False,
                )
                consumer_ready.set()
                logger.info("Kafka consumer loop assigned & ready for normalized topics: %s", list(NORMALISED_TOPICS.values()))
                while True:
                    batches = await consumer.getmany(timeout_ms=100, max_records=250)
                    if not batches:
                        continue
                    rc = get_replay_controller()
                    pending_offsets: dict[TopicPartition, int] = {}
                    for _tp, records in batches.items():
                        for msg in records:
                            tp = TopicPartition(msg.topic, msg.partition)
                            try:
                                val = msg.value
                                if val is None:
                                    # Tombstone from upsert-kafka compaction: advance offset cleanly
                                    pending_offsets[tp] = msg.offset + 1
                                    continue
                                if isinstance(val, (str, bytes)):
                                    import json
                                    val = json.loads(val)
                                if isinstance(val, dict):
                                    rblk = val.get("run")
                                    if isinstance(rblk, dict):
                                        rid = str(rblk.get("run_id") or "")
                                        sid = str(rblk.get("session_instance_id") or "")
                                        if (
                                            store.is_run_retired(rid)
                                            or rid.startswith(("bench-", "diag-"))
                                            or sid.startswith(("e2e-session-", "sess-ph-"))
                                            or (rc.session_id and sid and sid != rc.session_id)
                                        ):
                                            pending_offsets[tp] = msg.offset + 1
                                            continue
                                env = EventEnvelope.model_validate(val)
                                key_str = msg.key.decode("utf-8") if isinstance(msg.key, bytes) else str(msg.key or "")
                                if verdict_sink.has_verdict(msg.topic, msg.partition, msg.offset):
                                    pending_offsets[tp] = msg.offset + 1
                                    continue
                                if (
                                    store.is_run_retired(env.run.run_id)
                                    or (rc.session_id and env.run.session_instance_id != rc.session_id)
                                ):
                                    pending_offsets[tp] = msg.offset + 1
                                    continue
                                if rc.status == ReplayStatus.PAUSED and env.run.run_id == rc.run_id:
                                    paused_replay_buffer.append((msg.topic, msg.partition, msg.offset, key_str, env))
                                    continue
                                while paused_replay_buffer:
                                    b_topic, b_part, b_off, b_key, b_env = paused_replay_buffer.popleft()
                                    if not store.is_run_retired(b_env.run.run_id) and not verdict_sink.has_verdict(b_topic, b_part, b_off):
                                        await _route_normalized(b_topic, b_key, b_env)
                                        verdict_sink.insert_verdict(b_topic, b_part, b_off, b_key, b_env.event_id)
                                    pending_offsets[TopicPartition(b_topic, b_part)] = max(
                                        pending_offsets.get(TopicPartition(b_topic, b_part), 0), b_off + 1
                                    )
                                await _route_normalized(msg.topic, key_str, env)
                                verdict_sink.insert_verdict(msg.topic, msg.partition, msg.offset, key_str, env.event_id)
                                pending_offsets[tp] = msg.offset + 1
                            except Exception as err:
                                logger.error("Poison/unhandled Kafka normalized message from %s[%s]@%s: %s", msg.topic, msg.partition, msg.offset, err)
                                raw_bytes = msg.value if isinstance(msg.value, (bytes, bytearray)) else str(msg.value or "").encode("utf-8")
                                broker.publish_dlq(msg.topic, msg.partition, msg.offset, msg.key, bytes(raw_bytes), err)
                                pending_offsets[tp] = msg.offset + 1
                    if pending_offsets:
                        await consumer.commit(pending_offsets)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                consumer_ready.set()
                logger.error("Kafka consumer loop exited with error: %s", e)

        kafka_consumer_task = asyncio.create_task(kafka_consumer_loop())
        try:
            await asyncio.wait_for(consumer_ready.wait(), timeout=8.0)
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for Kafka normalized consumer partition assignment")

    # 8. Initialize backend ReplayController (preserve WAL on startup crash recovery)
    replay_controller.set_event_processor(process_replay_event)
    replay_controller.set_reset_hook(normalizer.reset)
    store.switch_session(replay_controller.session_id, preserve_wal=bool(wal_path))
    logger.info("Backend ReplayController initialized in READY state (session: %s).", replay_controller.session_id)

    yield

    # Teardown
    logger.info("Shutting down PULSE Race Intelligence Engine...")
    replay_controller.set_event_processor(None)
    replay_controller.set_reset_hook(None)
    if kafka_consumer_task:
        kafka_consumer_task.cancel()
        try:
            await kafka_consumer_task
        except asyncio.CancelledError:
            pass
    if replay_controller.status == "RUNNING":
        replay_controller.pause()
    if runner.status == RunStatus.RUNNING:
        runner.pause()
    agent_ia.close()
    if verdict_sink is not None:
        verdict_sink.close()
    await broker.stop()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_security_posture()
    app = FastAPI(
        title="PULSE Race Intelligence API",
        description="F1 Event Consequence Engine with Specialist Agents, Flink Stream Normalization & SIA Integrity Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-PULSE-API-Key", "Last-Event-ID"],
    )

    app.include_router(api_router)
    app.include_router(integrity_router)

    @app.get("/")
    async def root():
        return {
            "name": "PULSE Race Intelligence API",
            "version": "0.1.0",
            "status": "ONLINE",
            "docs_url": "/docs",
            "sse_stream_url": "/api/stream",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    s = get_settings()
    s.validate_security_posture()
    uvicorn.run(
        "pulse.main:app",
        host=s.host,
        port=s.port,
        reload=(s.is_local_dev_env and not s.is_non_loopback_host),
    )
