from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from pydantic import BaseModel

from pulse.config import get_settings
from pulse.topics import ALL_TOPICS

logger = logging.getLogger("pulse.kafka")


def json_serializer(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    raise TypeError(f"Type {type(obj)} not serializable")


class KafkaBroker:
    """Production Kafka broker transport using aiokafka."""

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        settings = get_settings()
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer: AIOKafkaProducer | None = None
        self._admin: AIOKafkaAdminClient | None = None
        self._is_connected = False
        self._consumers: list[AIOKafkaConsumer] = []

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def start(self) -> None:
        try:
            logger.info("Connecting to Kafka cluster at %s...", self.bootstrap_servers)
            self._admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
            await self._admin.start()

            # Ensure all required topics exist
            await self.ensure_topics()

            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=json_serializer).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
                acks="all",
            )
            await self._producer.start()
            self._is_connected = True
            logger.info("Kafka producer connected and ready.")
        except Exception as e:
            logger.error("Failed to start Kafka transport: %s", e)
            self._is_connected = False
            raise

    async def ensure_topics(self) -> None:
        if not self._admin:
            return
        try:
            existing = await self._admin.list_topics()
            missing = [t for t in ALL_TOPICS if t not in existing]
            if missing:
                logger.info("Creating %d missing Kafka topics...", len(missing))
                new_topics = [NewTopic(name=t, num_partitions=1, replication_factor=1) for t in missing]
                await self._admin.create_topics(new_topics)
                logger.info("Kafka topics created successfully.")
        except Exception as e:
            logger.warning("Error checking or creating Kafka topics: %s", e)

    async def publish(self, topic: str, key: str, value: Any) -> None:
        if not self._producer:
            raise RuntimeError("Kafka producer is not running")

        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        elif isinstance(value, dict):
            payload = value
        else:
            payload = {"data": value}

        await self._producer.send_and_wait(topic, value=payload, key=key)

    async def create_consumer(
        self,
        topics: list[str],
        group_id: str,
        auto_offset_reset: str = "latest",
    ) -> AIOKafkaConsumer:
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=True,
        )
        await consumer.start()
        self._consumers.append(consumer)
        return consumer

    async def stop(self) -> None:
        logger.info("Stopping Kafka broker transport...")
        for c in self._consumers:
            try:
                await c.stop()
            except Exception as e:
                logger.debug("Error stopping consumer: %s", e)
        self._consumers.clear()

        if self._producer:
            try:
                await self._producer.stop()
            except Exception as e:
                logger.debug("Error stopping producer: %s", e)
            self._producer = None

        if self._admin:
            try:
                await self._admin.close()
            except Exception as e:
                logger.debug("Error closing admin: %s", e)
            self._admin = None

        self._is_connected = False
        logger.info("Kafka broker transport stopped.")


_broker: KafkaBroker | None = None


def get_kafka_broker() -> KafkaBroker:
    global _broker
    if _broker is None:
        _broker = KafkaBroker()
    return _broker

