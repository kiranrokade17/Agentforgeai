import pytest
from pydantic import ValidationError

from app.core.celery_app import celery_app
from app.core.config import INSECURE_DEFAULT_SECRET, Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "production",
        "APP_SECRET_KEY": "a" * 32,
        "DEFAULT_LLM_PROVIDER": "gemini",
        "GEMINI_API_KEY": "configured-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_settings_accept_explicit_secrets() -> None:
    settings = production_settings()

    assert settings.APP_ENV == "production"
    assert settings.APP_SECRET_KEY == "a" * 32


def test_non_production_allows_mock_provider() -> None:
    settings = Settings(_env_file=None, APP_ENV="test", DEFAULT_LLM_PROVIDER="mock")

    assert settings.DEFAULT_LLM_PROVIDER == "mock"


def test_local_dev_defaults_match_docker_postgres_password() -> None:
    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL == "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/agentforge"
    assert settings.DATABASE_URL_SYNC == "postgresql+psycopg://postgres:postgrespassword@localhost:5432/agentforge"


def test_settings_reads_repo_root_env_file() -> None:
    settings = Settings()

    # The repo-root .env is loaded (it sets a non-default app name).
    assert settings.APP_NAME == "AgentForge AI"
    assert settings.DEFAULT_LLM_PROVIDER in {"gemini", "openrouter", "mock"}


def test_short_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(_env_file=None, APP_SECRET_KEY="short")


def test_production_rejects_default_secret() -> None:
    with pytest.raises(ValidationError, match="explicitly configured"):
        production_settings(APP_SECRET_KEY=INSECURE_DEFAULT_SECRET)


def test_production_rejects_mock_provider() -> None:
    with pytest.raises(ValidationError, match="not permitted"):
        production_settings(DEFAULT_LLM_PROVIDER="mock")


def test_production_requires_gemini_key() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        production_settings(GEMINI_API_KEY="")


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        production_settings(CORS_ORIGINS=["*"])


def test_unsupported_provider_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Unsupported provider"):
        Settings(_env_file=None, DEFAULT_LLM_PROVIDER="unknown")


def test_production_rejects_non_postgresql_database() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        production_settings(DATABASE_URL="sqlite+aiosqlite:///:memory:")


def test_celery_uses_configured_broker() -> None:
    assert celery_app.conf.broker_url
    assert celery_app.conf.result_backend
