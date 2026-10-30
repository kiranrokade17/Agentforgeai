import pytest
from fastapi import HTTPException

from app.agents.factory import get_llm_provider
from app.agents.mock_provider import MockLLMProvider
from app.core.config import settings
from app.schemas.planning import ArchitecturePlanContent


def test_mock_provider_is_available_in_development(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    assert isinstance(get_llm_provider("mock"), MockLLMProvider)


def test_mock_provider_is_blocked_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(HTTPException) as exc_info:
        get_llm_provider("mock")
    assert exc_info.value.status_code == 403


def test_gemini_provider_is_supported(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    provider = get_llm_provider("gemini")
    assert provider.__class__.__name__ == "GeminiProvider"


def test_gemini_provider_uses_server_configured_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "server-key")
    provider = get_llm_provider("gemini")
    assert provider.__class__.__name__ == "GeminiProvider"
    assert provider.api_key == "server-key"


def test_openrouter_provider_is_supported(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-v1-router-key")
    provider = get_llm_provider("openrouter")
    assert provider.__class__.__name__ == "OpenRouterProvider"
    assert provider.api_key == "sk-or-v1-router-key"


def test_openrouter_provider_normalizes_pasted_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", '  Bearer "sk-or-v1-user-key"  ')
    provider = get_llm_provider("openrouter")
    assert provider.api_key == "sk-or-v1-user-key"


def test_openrouter_provider_rejects_non_openrouter_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "AQ.gemini-style-key")
    with pytest.raises(HTTPException) as exc_info:
        get_llm_provider("openrouter")
    assert exc_info.value.status_code == 400
    assert "sk-or-v1-" in exc_info.value.detail


def test_openrouter_parser_accepts_markdown_json_block(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-v1-router-key")
    provider = get_llm_provider("openrouter")
    raw = '''```json
    {
      "overview": "This application provides a robust platform for project planning and execution.",
      "affected_components": [],
      "new_api_endpoints": [],
      "database_changes": [],
      "external_dependencies": [],
      "security_considerations": [],
      "assumptions": [],
      "open_questions": []
    }
    ```'''

    plan = provider._parse_response(raw, ArchitecturePlanContent, "architecture plan")
    assert plan.overview.startswith("This application")


def test_openrouter_parser_repairs_trailing_commas(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-v1-router-key")
    provider = get_llm_provider("openrouter")
    raw = (
        '{"overview": "A sufficiently long architecture overview for validation.",'
        ' "affected_components": [], "new_api_endpoints": [],'
        ' "database_changes": [], "external_dependencies": [],'
        ' "security_considerations": [], "assumptions": [], "open_questions": [],}'
    )

    plan = provider._parse_response(raw, ArchitecturePlanContent, "architecture plan")
    assert plan.overview.startswith("A sufficiently long")


@pytest.mark.asyncio
async def test_openrouter_retries_with_repair_prompt_on_schema_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-v1-router-key")
    provider = get_llm_provider("openrouter")

    valid = (
        '{"overview": "A sufficiently long architecture overview for validation.",'
        ' "affected_components": [], "new_api_endpoints": [],'
        ' "database_changes": [], "external_dependencies": [],'
        ' "security_considerations": [], "assumptions": [], "open_questions": []}'
    )
    responses = ["not json at all", valid]
    calls: list[str] = []

    async def fake_call(system_instruction, prompt, schema):
        calls.append(prompt)
        return responses[len(calls) - 1]

    monkeypatch.setattr(provider, "_call", fake_call)

    plan = await provider._generate_structured(
        "system", "prompt", ArchitecturePlanContent, "architecture plan"
    )
    assert plan.overview.startswith("A sufficiently long")
    assert len(calls) == 2
    assert "Previous Invalid Output" in calls[1]


@pytest.mark.parametrize("provider_name", ["openai", "anthropic", "unknown"])
def test_unsupported_provider_returns_controlled_error(provider_name):
    with pytest.raises(HTTPException) as exc_info:
        get_llm_provider(provider_name)
    assert exc_info.value.status_code == 422
    assert "Unsupported LLM provider" in exc_info.value.detail
