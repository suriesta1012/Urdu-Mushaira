import os
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"


class BaseConfigSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(ENV_FILE_PATH), ".env"],
        extra="ignore",
        frozen=True,
        env_nested_delimiter="__",
        case_sensitive=False,
    )


class AnthropicSettings(BaseConfigSettings):
    """Anthropic API configuration."""
    model_config = SettingsConfigDict(
        env_prefix="ANTHROPIC_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    api_key: str = Field(..., description="Anthropic API key")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Model name")
    max_tokens: int = Field(default=1200, ge=1, le=4096)
    timeout: int = Field(default=30, ge=1)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or not v.startswith("sk-"):
            raise ValueError("ANTHROPIC_API_KEY must be a valid Anthropic API key starting with 'sk-'")
        return v


class PostgresSettings(BaseConfigSettings):
    """PostgreSQL configuration for checkpointing and session persistence."""
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    user: str = Field(default="postgres")
    password: str = Field(default="")
    database: str = Field(default="mushaira")
    enabled: bool = Field(default=True, description="Enable Postgres persistence")

    @property
    def connection_string(self) -> str:
        """Build psycopg3 connection string."""
        if self.password:
            auth = f"{self.user}:{self.password}"
        else:
            auth = self.user
        return f"postgresql://{auth}@{self.host}:{self.port}/{self.database}"

    @field_validator("database")
    @classmethod
    def validate_database_name(cls, v: str) -> str:
        if not v or len(v) < 1:
            raise ValueError("Database name cannot be empty")
        return v


class LangfuseSettings(BaseConfigSettings):
    """Langfuse observability configuration."""
    model_config = SettingsConfigDict(
        env_file=[str(ENV_FILE_PATH), ".env"],
        env_prefix="LANGFUSE_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    public_key: str = Field(default="", description="Langfuse public key")
    secret_key: str = Field(default="", description="Langfuse secret key")
    host: str = Field(default="https://cloud.langfuse.com", description="Langfuse host URL")
    enabled: bool = Field(default=True, description="Enable Langfuse tracing")
    flush_at: int = Field(default=15, ge=1, description="Batch size before flush")
    flush_interval: float = Field(default=1.0, ge=0.1, description="Flush interval in seconds")
    max_retries: int = Field(default=3, ge=1)
    timeout: int = Field(default=30, ge=1)
    debug: bool = Field(default=False)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Langfuse host must be a valid URL")
        return v


class Settings(BaseConfigSettings):
    """Main application settings."""
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)

    debug: bool = Field(default=False)
    workers: int = Field(default=4, ge=1)


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (lazy-loaded singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
