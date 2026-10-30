from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]

INSECURE_DEFAULT_SECRET = "insecure_dev_secret_key_please_change_in_production_min_32_chars"
SUPPORTED_LLM_PROVIDERS = {"gemini", "mock", "openrouter"}
SUPPORTED_CODING_AGENT_PROVIDERS = {"codex", "claude_code", "mock"}


class Settings(BaseSettings):
    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_NAME: str = "AgentForge AI"
    APP_SECRET_KEY: str = INSECURE_DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_ENABLED: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/agentforge"
    DATABASE_URL_SYNC: str = "postgresql+psycopg://postgres:postgrespassword@localhost:5432/agentforge"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # LLM Providers (Gemini Primary, OpenAI & Anthropic Optional)
    DEFAULT_LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    LLM_REQUEST_TIMEOUT_SECONDS: int = 120
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # Coding Agent Adapter
    CODING_AGENT_PROVIDER: str = "codex"
    CODING_AGENT_TIMEOUT_SECONDS: int = 600
    MAX_AGENT_REPAIR_ATTEMPTS: int = 2

    # GitHub Integration
    GITHUB_WEBHOOK_SECRET: str = "dev_github_webhook_secret_32_chars"
    GITHUB_API_TOKEN: str = ""

    # Storage
    ARTIFACT_STORAGE: str = "local"
    ARTIFACT_STORAGE_PATH: str = "./.artifacts"

    model_config = SettingsConfigDict(
        env_file=[PROJECT_ROOT / ".env", ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DEFAULT_LLM_PROVIDER")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LLM_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{normalized}'. "
                f"Expected one of: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}"
            )
        return normalized

    @field_validator("GITHUB_WEBHOOK_SECRET", mode="before")
    @classmethod
    def normalize_github_webhook_secret(cls, value: str | None) -> str:
        if value is None:
            return "dev_github_webhook_secret_32_chars"
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or "dev_github_webhook_secret_32_chars"
        return str(value)

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Self:
        if len(self.APP_SECRET_KEY.encode("utf-8")) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 bytes")

        if self.APP_ENV != "production":
            return self

        if self.APP_SECRET_KEY == INSECURE_DEFAULT_SECRET:
            raise ValueError("APP_SECRET_KEY must be explicitly configured in production")
        if self.DEFAULT_LLM_PROVIDER == "mock":
            raise ValueError("The mock LLM provider is not permitted in production")
        if self.DEFAULT_LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY.strip():
            raise ValueError("GEMINI_API_KEY is required for the Gemini provider in production")
        if self.DEFAULT_LLM_PROVIDER == "openrouter" and not self.OPENROUTER_API_KEY.strip():
            raise ValueError("OPENROUTER_API_KEY is required for the OpenRouter provider in production")
        if "*" in self.CORS_ORIGINS:
            raise ValueError("Wildcard CORS origins are not permitted in production")
        if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver in production")
        if not self.DATABASE_URL_SYNC.startswith("postgresql+psycopg://"):
            raise ValueError(
                "DATABASE_URL_SYNC must use the postgresql+psycopg driver in production"
            )

        return self


settings = Settings()
