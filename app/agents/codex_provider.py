import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.agents.base import BaseCodingAgentProvider
from app.schemas.agent_run import AgentRunStatus, AgentRunSummary


class CodexProvider(BaseCodingAgentProvider):
    provider_name = "codex"

    def __init__(self, provider_name: str = "codex"):
        self.provider_name = provider_name

    async def execute(
        self,
        task_id: uuid.UUID,
        task_title: str,
        repo_path: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentRunSummary:
        now = datetime.now(UTC)
        return AgentRunSummary(
            id=uuid.uuid4(),
            task_id=task_id,
            task_title=task_title,
            provider=self.provider_name,
            status=AgentRunStatus.QUEUED,
            summary=(
                "Codex provider accepted the task and queued it for execution. "
                "The placeholder implementation is intentionally isolated from the host runtime."
            ),
            created_at=now,
            started_at=now,
            finished_at=None,
            exit_code=None,
        )


class MockCodingAgentProvider(BaseCodingAgentProvider):
    provider_name = "mock"

    async def execute(
        self,
        task_id: uuid.UUID,
        task_title: str,
        repo_path: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentRunSummary:
        now = datetime.now(UTC)
        return AgentRunSummary(
            id=uuid.uuid4(),
            task_id=task_id,
            task_title=task_title,
            provider=self.provider_name,
            status=AgentRunStatus.SUCCEEDED,
            summary="Mock coding-agent execution completed successfully in the restricted test sandbox.",
            created_at=now,
            started_at=now,
            finished_at=now,
            exit_code=0,
        )


def get_provider(provider_name: str | None = None) -> BaseCodingAgentProvider:
    name = (provider_name or "codex").strip().lower()
    if name in {"codex", "claude_code"}:
        return CodexProvider(name)
    if name == "mock":
        return MockCodingAgentProvider()
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unsupported coding-agent provider '{name}'. Supported providers are 'codex', 'claude_code', and 'mock'.",
    )
