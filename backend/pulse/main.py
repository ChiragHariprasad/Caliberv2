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
            logger.info("Flink cluster online at %s. Flink streaming normalizer active.", flink_mgr.client.rest_url)
    elif mode == "MEMORY":
        logger.info("Operating in MEMORY transport mode (unit tests). In-memory event bus active.")
    elif mode == "SIMULATOR":
        logger.info("Operating in SIMULATOR transport mode. Local deterministic bus active.")
    else:
        raise ValueError(f"Unsupported transport_mode: {settings.transport_mode}")

    # 2. Instantiate all 6 agents and register for execution transparency
    agent_ec = EventControlAgent(bus=bus)
    agent_ts = TrackStateAgent(bus=bus)
    agent_vr = VehicleResponseAgent(bus=bus)
    agent_ty = TyreStrategyAgent(bus=bus)
    agent_fu = ConsequenceFusionEngine(bus=bus)
    agent_ia = IntegrityAgent(bus=bus)

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

    # 7. In KAFKA transport mode, consume all Flink-normalized streams from Kafka
    kafka_consumer_task: asyncio.Task | None = None
    if mode == "KAFKA":
        async def kafka_consumer_loop() -> None:
            try:
                consumer = await broker.create_consumer(
                    topics=list(NORMALISED_TOPICS.values()),
                    group_id="pulse-backend-normalised-consumer-v2",
                    auto_offset_reset="latest",
                )
                logger.info("Kafka consumer loop started for normalized topics: %s", list(NORMALISED_TOPICS.values()))
                async for msg in consumer:
                    try:
                        val = msg.value
                        if isinstance(val, (str, bytes)):
                            import json
                            val = json.loads(val)
                        env = EventEnvelope.model_validate(val)
                        key_str = msg.key.decode("utf-8") if isinstance(msg.key, bytes) else str(msg.key or "")
                        if msg.topic == NORMALISED_TOPICS["race_events"]:
                            await normalized_race_events_handler(msg.topic, key_str, env)
                        elif msg.topic == NORMALISED_TOPICS["driver_laps"]:
                            await normalized_driver_laps_handler(msg.topic, key_str, env)
                        elif msg.topic == NORMALISED_TOPICS["driver_state"]:
                            await normalized_driver_state_handler(msg.topic, key_str, env)
                        elif msg.topic == NORMALISED_TOPICS["track_segments"]:
                            await normalized_track_handler(msg.topic, key_str, env)
                        elif msg.topic == NORMALISED_TOPICS["tyre_stints"]:
                            await normalized_tyre_stints_handler(msg.topic, key_str, env)
                    except Exception as err:
                        logger.error("Error handling Kafka normalized message from %s: %s", msg.topic, err)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("Kafka consumer loop exited with error: %s", e)

        kafka_consumer_task = asyncio.create_task(kafka_consumer_loop())

    # 8. Initialize backend ReplayController
    from pulse.replay.controller import get_replay_controller
    replay_controller = get_replay_controller()
    replay_controller.set_event_processor(process_replay_event)
    replay_controller.set_reset_hook(normalizer.reset)
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
    await broker.stop()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PULSE Race Intelligence API",
        description="F1 Event Consequence Engine with Specialist Agents, SIA Integrity Engine & Groq Tactical Synthesis",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    uvicorn.run("pulse.main:app", host="0.0.0.0", port=8000, reload=True)
