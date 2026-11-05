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
    kafka_bootstrap_servers: str = "127.0.0.1:9092"
    kafka_group_id: str = "pulse-api-v1"
    kafka_required: bool = True
    kafka_auto_create_topics: bool = True
    flink_rest_url: str = Field(
        default="http://127.0.0.1:8081",
        validation_alias=AliasChoices("PULSE_FLINK_REST_URL", "FLINK_REST_URL"),
    )
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
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
