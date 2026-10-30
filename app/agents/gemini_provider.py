import asyncio
import json
import logging
from typing import Any, TypeVar

from fastapi import HTTPException, status
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.agents.base import BaseLLMProvider
from app.core.config import settings
from app.schemas.planning import ArchitecturePlanContent, TaskPlanContent
from app.schemas.specification import SRSContent

logger = logging.getLogger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)

SRS_SYSTEM_INSTRUCTION = """
You are the AgentForge AI Lead Software Architect and Requirements Engineering Agent.
Your responsibility is to analyze natural-language software requirements and compile an authoritative, production-grade Software Requirements Specification (SRS).

Guidelines:
1. Formulate a comprehensive, architectural project summary.
2. Break down the system into atomic, numbered functional requirements (e.g. FR-01, FR-02) with priority (critical, high, medium, low) and explicit, verifiable acceptance criteria.
3. Define non-functional requirements (e.g. Security, Performance, Fault Tolerance, Isolation) with concrete metrics/SLAs where applicable.
4. Generate Agile user stories (US-01, US-02) specifying 'as_a', 'i_want', 'so_that', and acceptance criteria.
5. Identify technical assumptions, risks with mitigations, and any open questions or ambiguities that need developer or user clarification.
6. Adhere strictly to the requested JSON output schema.
"""

ARCHITECTURE_SYSTEM_INSTRUCTION = """
You are the AgentForge AI Senior Software Architect.
Given an approved Software Requirements Specification (SRS), produce a technical architecture plan.

Guidelines:
1. Write a concise but thorough technical overview covering layers, patterns, and key design decisions.
2. List every component, service, or module that will be created or modified with its layer (frontend, backend, database, infra, external) and change type (create, modify, delete, no-change).
3. List new REST or WebSocket API endpoints to be designed (e.g. POST /api/v1/tasks).
4. List any database schema changes (new tables, columns, indexes, migrations).
5. List external dependencies (libraries, third-party services, cloud resources).
6. Identify security considerations, architectural assumptions, and open questions.
7. Respond only with valid JSON matching the schema exactly.
"""

TASK_PLANNING_SYSTEM_INSTRUCTION = """
You are the AgentForge AI Engineering Lead and Sprint Planner.
Given an approved SRS and optional architecture plan, break the work into a precise, dependency-aware, ordered task plan.

Guidelines:
1. Write a brief planning_summary explaining your breakdown rationale.
2. Each task must have: order (1-based integer), title, description, task_type, priority, acceptance_criteria, required_tests.
3. task_type must be one of: frontend, backend, database, testing, documentation, devops.
4. priority must be one of: critical, high, medium, low.
5. depends_on_orders must list the order numbers of tasks that must complete before this one (no circular dependencies).
6. required_tests must list specific test types needed to accept the task as done (e.g. "unit test for TaskRepository.create").
7. Order tasks so that foundational work (database, models) precedes dependent work (services, routes, frontend).
8. Produce at least 3 tasks and at most 20.
9. Respond only with valid JSON matching the schema exactly.
"""


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = (api_key or settings.GEMINI_API_KEY or "").strip()
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini API key is not configured. Please set GEMINI_API_KEY in .env.",
            )
        self.model = model or settings.GEMINI_MODEL
        self._client: Any | None = None

    @property
    def client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def _call(self, system_instruction: str, prompt: str, schema):
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        )
        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model, contents=prompt, config=config
                ),
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.error(
                "Gemini request timed out after %s seconds", settings.LLM_REQUEST_TIMEOUT_SECONDS
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The LLM provider timed out while generating the response. Please retry.",
            )
        except Exception as exc:
            logger.error("Gemini request failed with %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The LLM provider failed to generate a response. Please retry.",
            )

        if not response.text:
            logger.error("Gemini returned an empty response")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The LLM provider returned an empty response. Please retry.",
            )
        return response.text

    def _parse_response(self, text: str, schema: type[SchemaT], label: str) -> SchemaT:
        try:
            return schema.model_validate_json(text)
        except ValidationError:
            logger.error("Gemini returned an invalid %s payload", label)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The LLM provider returned a response that did not match the required schema.",
            )

    async def generate_srs(
        self, user_requirement: str, project_context: dict[str, Any] | None = None
    ) -> SRSContent:
        prompt_parts = [f"### User Requirements:\n{user_requirement.strip()}\n"]
        if project_context:
            prompt_parts.append(f"### Project Context:\n{json.dumps(project_context, indent=2)}\n")
        prompt_parts.append(
            "Compile the complete, schema-valid Software Requirements Specification (SRS)."
        )
        text = await self._call(SRS_SYSTEM_INSTRUCTION, "\n".join(prompt_parts), SRSContent)
        return self._parse_response(text, SRSContent, "SRS")

    async def generate_architecture_plan(
        self,
        srs: SRSContent,
        project_context: dict[str, Any] | None = None,
        repo_context: str | None = None,
    ) -> ArchitecturePlanContent:
        prompt_parts = [f"### Approved SRS:\n{srs.model_dump_json(indent=2)}\n"]
        if project_context:
            prompt_parts.append(f"### Project Context:\n{json.dumps(project_context, indent=2)}\n")
        if repo_context:
            prompt_parts.append(f"### Existing Repository Context:\n{repo_context}\n")
        prompt_parts.append("Produce the complete technical architecture plan.")
        text = await self._call(
            ARCHITECTURE_SYSTEM_INSTRUCTION, "\n".join(prompt_parts), ArchitecturePlanContent
        )
        return self._parse_response(text, ArchitecturePlanContent, "architecture plan")

    async def generate_tasks(
        self,
        srs: SRSContent,
        architecture: ArchitecturePlanContent | None = None,
        project_context: dict[str, Any] | None = None,
        additional_context: str | None = None,
    ) -> TaskPlanContent:
        prompt_parts = [f"### Approved SRS:\n{srs.model_dump_json(indent=2)}\n"]
        if architecture:
            prompt_parts.append(
                f"### Architecture Plan:\n{architecture.model_dump_json(indent=2)}\n"
            )
        if project_context:
            prompt_parts.append(f"### Project Context:\n{json.dumps(project_context, indent=2)}\n")
        if additional_context:
            prompt_parts.append(f"### Additional Context:\n{additional_context}\n")
        prompt_parts.append("Produce the complete, ordered, dependency-aware task plan.")
        text = await self._call(
            TASK_PLANNING_SYSTEM_INSTRUCTION, "\n".join(prompt_parts), TaskPlanContent
        )
        return self._parse_response(text, TaskPlanContent, "task plan")
