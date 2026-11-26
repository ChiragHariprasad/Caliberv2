import os
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Kafka is the default operational transport."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_prefix="PULSE_",
        extra="ignore"
    )

    env: str = "development"
    log_level: str = "INFO"
    transport_mode: str = Field(
        default="KAFKA",
        description="Transport mode: KAFKA (fail-fast if broker unavailable), MEMORY (unit tests), SIMULATOR",
        validation_alias=AliasChoices("PULSE_TRANSPORT_MODE", "TRANSPORT_MODE"),
    )
    kafka_bootstrap_servers: str = Field(
        default="localhost:19092,localhost:19093,localhost:19094",
        validation_alias=AliasChoices("CALIBRE_KAFKA_BOOTSTRAP", "PULSE_KAFKA_BOOTSTRAP_SERVERS", "KAFKA_BOOTSTRAP_SERVERS")
    )
    kafka_group_id: str = "pulse-api-v1"
    kafka_required: bool = True
    kafka_auto_create_topics: bool = False
    driver_partitions: int = Field(
        default=11,
        validation_alias=AliasChoices("CALIBRE_DRIVER_PARTITIONS", "DRIVER_PARTITIONS")
    )
    kafka_eos: int = Field(
        default=1,
        validation_alias=AliasChoices("CALIBRE_KAFKA_EOS", "KAFKA_EOS")
    )
    instance_id: str = Field(
        default="calibre-core-1",
        validation_alias=AliasChoices("CALIBRE_INSTANCE_ID", "INSTANCE_ID")
    )
    flink_rest_url: str = Field(
        default="http://127.0.0.1:8081",
        validation_alias=AliasChoices("PULSE_FLINK_REST_URL", "FLINK_REST_URL"),
    )
    flink_required: bool = Field(
        default=False,
        description="Whether a running Flink cluster is strictly required in KAFKA mode",
        validation_alias=AliasChoices("PULSE_FLINK_REQUIRED", "FLINK_REQUIRED"),
    )
    sia_wal_path: str | None = Field(
        default="data/sia_ledger.sqlite",
        description="SQLite WAL persistence path for SIA Core v3 ledger & hash chains (None disables disk WAL)",
        validation_alias=AliasChoices("PULSE_SIA_WAL_PATH", "SIA_WAL_PATH"),
    )
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    control_api_key: str = Field(
        default="",
        description="Optional API key required for mutating control routes when non-empty",
        validation_alias=AliasChoices("PULSE_API_KEY", "PULSE_CONTROL_API_KEY"),
    )
    max_sse_listeners: int = Field(default=64, ge=1, le=500)
    default_replay_speed: float = Field(default=1.0, gt=0, le=32)
    groq_enabled: bool = True
    groq_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("PULSE_GROQ_API_KEY", "GROQ_API_KEY")
    )
    groq_model: str = "openai/gpt-oss-120b"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
