import uuid
from abc import ABC, abstractmethod
from typing import Any

from app.schemas.agent_run import AgentRunSummary
from app.schemas.planning import ArchitecturePlanContent, TaskPlanContent
from app.schemas.specification import SRSContent


class BaseCodingAgentProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def execute(
        self,
        task_id: uuid.UUID,
        task_title: str,
        repo_path: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentRunSummary:
        """Execute a coding task in an isolated workspace and return a status summary."""


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_srs(
        self, user_requirement: str, project_context: dict[str, Any] | None = None
    ) -> SRSContent:
        """Analyze natural language requirement and return a structured SRS."""
        pass

    @abstractmethod
    async def generate_architecture_plan(
        self,
        srs: SRSContent,
        project_context: dict[str, Any] | None = None,
        repo_context: str | None = None,
    ) -> ArchitecturePlanContent:
        """Produce a technical architecture plan from an approved SRS."""
        pass

    @abstractmethod
    async def generate_tasks(
        self,
        srs: SRSContent,
        architecture: ArchitecturePlanContent | None = None,
        project_context: dict[str, Any] | None = None,
        additional_context: str | None = None,
    ) -> TaskPlanContent:
        """Break an approved SRS into a dependency-aware, ordered task plan."""
        pass
