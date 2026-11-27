import os
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_LOCAL_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
_LOCAL_DEV_ENVS = frozenset({"development", "dev", "local", "test"})
_EXTERNAL_ENVS = frozenset({"production", "prod", "staging", "external"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_WEAK_API_KEYS = frozenset({"changeme", "default", "secret", "password", "test", "pulse", "demo", "dev-key"})


class Settings(BaseSettings):
    """Runtime configuration. Kafka is the default operational transport."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_prefix="PULSE_",
        extra="ignore"
    )

    env: str = "development"
    host: str = Field(
        default="127.0.0.1",
        description="Bind host for HTTP server (non-loopback requires API key & explicit CORS)",
        validation_alias=AliasChoices("PULSE_HOST", "HOST"),
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("PULSE_PORT", "PORT"),
    )
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
    cors_origins: str = DEFAULT_LOCAL_CORS_ORIGINS
    control_api_key: str = Field(
        default="",
        description="API key required for mutating control routes when non-empty or required by posture",
        validation_alias=AliasChoices("PULSE_API_KEY", "PULSE_CONTROL_API_KEY"),
    )
    require_control_auth: bool = Field(
        default=False,
        description="Fail closed on startup and control mutations unless a strong control API key is configured",
        validation_alias=AliasChoices("PULSE_REQUIRE_CONTROL_AUTH", "PULSE_REQUIRE_AUTH"),
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

    @property
    def is_local_dev_env(self) -> bool:
        return self.env.strip().lower() in _LOCAL_DEV_ENVS

    @property
    def is_external_env(self) -> bool:
        return self.env.strip().lower() in _EXTERNAL_ENVS

    @property
    def is_non_loopback_host(self) -> bool:
        return self.host.strip().lower() not in _LOOPBACK_HOSTS

    @property
    def requires_control_auth(self) -> bool:
        return bool(self.require_control_auth or not self.is_local_dev_env or self.is_non_loopback_host)

    def validate_security_posture(self) -> None:
        """Fail closed when auth is required or when exposed externally with local dev defaults."""
        origins = self.cors_origin_list
        if "*" in origins:
            raise ValueError("Security configuration error: wildcard CORS origin '*' is forbidden with credentialed endpoints")
        if not origins:
            raise ValueError("Security configuration error: PULSE_CORS_ORIGINS cannot be empty")

        key = (self.control_api_key or "").strip()
        if self.requires_control_auth:
            if not key:
                raise ValueError(
                    "Security configuration error: PULSE_API_KEY / PULSE_CONTROL_API_KEY must be configured "
                    f"when authentication is required (env={self.env!r}, host={self.host!r}, "
                    f"require_control_auth={self.require_control_auth})"
                )
            if len(key) < 16 or key.lower() in _WEAK_API_KEYS:
                raise ValueError(
                    "Security configuration error: PULSE_API_KEY / PULSE_CONTROL_API_KEY must be at least "
                    "16 non-placeholder characters when authentication is required"
                )

        if self.is_external_env or self.is_non_loopback_host:
            if self.cors_origins.strip() == DEFAULT_LOCAL_CORS_ORIGINS:
                raise ValueError(
                    "Security configuration error: externally exposed or non-loopback configuration cannot "
                    "run with default permissive local-development CORS origins; set explicit PULSE_CORS_ORIGINS"
                )
        if self.is_external_env:
            if any("localhost" in o.lower() or "127.0.0.1" in o or "[::1]" in o for o in origins):
                raise ValueError(
                    "Security configuration error: localhost CORS origins are forbidden in production/staging/external env"
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()
