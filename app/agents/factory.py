from fastapi import HTTPException, status

from app.agents.base import BaseCodingAgentProvider, BaseLLMProvider
from app.core.config import settings

SUPPORTED_LLM_PROVIDERS = {"gemini", "mock"}
SUPPORTED_CODING_AGENT_PROVIDERS = {"codex", "claude_code", "mock"}


def get_llm_provider(provider_name: str | None = None, api_key: str | None = None) -> BaseLLMProvider:
    """
    Factory that returns the configured LLM provider adapter.

    Phase 2 intentionally supports Gemini for real generation and a
    deterministic mock provider for local development and tests. Additional
    provider adapters must be added before their names are advertised.
    """
    name = (provider_name or settings.DEFAULT_LLM_PROVIDER).strip().lower()

    if name == "gemini":
        from app.agents.gemini_provider import GeminiProvider

        return GeminiProvider(api_key=(api_key or settings.GEMINI_API_KEY).strip() or None)

    if name == "openrouter":
        from app.agents.openrouter_provider import OpenRouterProvider

        return OpenRouterProvider(
            api_key=(api_key or settings.OPENROUTER_API_KEY).strip() or None,
        )

    if name == "mock":
        if settings.APP_ENV not in {"development", "test"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The mock LLM provider is only available in development or test environments.",
            )
        from app.agents.mock_provider import MockLLMProvider

        return MockLLMProvider()

    raise HTTPException(
        status_code=422,
        detail=(
            f"Unsupported LLM provider '{name}'. "
            "Phase 2 supports 'gemini' for real generation and 'mock' for development and tests."
        ),
    )


def get_coding_agent_provider(provider_name: str | None = None) -> BaseCodingAgentProvider:
    """Return the selected coding-agent provider, defaulting to the configured provider."""
    name = (provider_name or settings.CODING_AGENT_PROVIDER).strip().lower()

    if name in {"codex", "claude_code"}:
        from app.agents.codex_provider import CodexProvider

        return CodexProvider(name)

    if name == "mock":
        from app.agents.codex_provider import MockCodingAgentProvider

        return MockCodingAgentProvider()

    raise HTTPException(
        status_code=422,
        detail=(
            f"Unsupported coding-agent provider '{name}'. "
            "Supported providers are 'codex', 'claude_code', and 'mock'."
        ),
    )
