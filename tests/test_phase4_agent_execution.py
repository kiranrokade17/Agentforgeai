import uuid

import pytest
from fastapi import HTTPException

from app.agents.codex_provider import CodexProvider
from app.agents.factory import get_coding_agent_provider
from app.execution.sandbox import SandboxPolicy


def test_codex_provider_is_available():
    provider = get_coding_agent_provider("codex")
    assert isinstance(provider, CodexProvider)


def test_mock_provider_is_available_in_test_environment(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "test")
    provider = get_coding_agent_provider("mock")
    assert provider.__class__.__name__ == "MockCodingAgentProvider"


def test_unsupported_coding_agent_provider_returns_422():
    with pytest.raises(HTTPException) as exc_info:
        get_coding_agent_provider("unknown")
    assert exc_info.value.status_code == 422


def test_sandbox_policy_has_safe_defaults():
    policy = SandboxPolicy()
    assert policy.network_mode == "none"
    assert policy.max_cpu_cores >= 1
    assert policy.max_memory_mb >= 512
    assert policy.user == "nonroot"
    assert policy.allow_docker_socket is False


def test_agent_run_status_can_be_created():
    from app.schemas.agent_run import AgentRunCreate, AgentRunStatus, AgentRunSummary

    payload = AgentRunCreate(task_id=uuid.uuid4(), task_title="Add login route")
    summary = AgentRunSummary(
        id=uuid.uuid4(),
        task_id=payload.task_id,
        status=AgentRunStatus.QUEUED,
        provider="codex",
        exit_code=None,
    )
    assert summary.task_id == payload.task_id
    assert summary.status == AgentRunStatus.QUEUED
