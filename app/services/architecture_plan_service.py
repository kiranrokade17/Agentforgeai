import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import get_llm_provider
from app.db.models.architecture_plan import ArchitecturePlan
from app.repositories.architecture_plan_repo import ArchitecturePlanRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.specification_repo import SpecificationRepository
from app.schemas.planning import (
    ArchitecturePlanContent,
    ArchitecturePlanGenerateRequest,
    ArchitecturePlanResponse,
    ArchitecturePlanUpdateRequest,
)
from app.schemas.specification import SRSContent
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)

GENERATE_ROLES = ["owner", "admin", "developer"]
APPROVE_ROLES = ["owner", "admin"]


class ArchitecturePlanService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plan_repo = ArchitecturePlanRepository(session)
        self.project_repo = ProjectRepository(session)
        self.spec_repo = SpecificationRepository(session)
        self.workspace_service = WorkspaceService(session)

    async def _assert_project_access(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        required_roles: list[str] | None = None,
    ):
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        await self.workspace_service.check_access(
            workspace_id=project.workspace_id,
            user_id=user_id,
            required_roles=required_roles,
        )
        return project

    @staticmethod
    def _to_response(plan: ArchitecturePlan) -> ArchitecturePlanResponse:
        return ArchitecturePlanResponse(
            id=plan.id,
            project_id=plan.project_id,
            specification_id=plan.specification_id,
            version=plan.version,
            title=plan.title,
            content_json=ArchitecturePlanContent.model_validate(plan.content_json),
            status=plan.status,
            approved_by=plan.approved_by,
            approved_at=plan.approved_at,
            created_at=plan.created_at,
        )

    async def generate(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        request: ArchitecturePlanGenerateRequest,
        provider_name: str | None = None,
    ) -> ArchitecturePlanResponse:
        project = await self._assert_project_access(
            user_id, project_id, required_roles=GENERATE_ROLES
        )
        if project.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Architecture plans can only be generated for active projects.",
            )

        specification = await self.spec_repo.get_by_id(request.specification_id)
        if not specification or specification.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specification not found for this project",
            )
        if specification.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Architecture planning requires an approved specification.",
            )

        try:
            srs = SRSContent.model_validate(specification.content_json)
        except Exception:
            logger.error("Stored specification %s has an invalid payload", specification.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The stored specification is invalid.",
            )

        project_context: dict[str, Any] = {
            "project_name": project.name,
            "project_description": project.description or "",
            "stack": project.stack_json,
        }

        try:
            provider = get_llm_provider(provider_name)
            generated = await provider.generate_architecture_plan(
                srs=srs,
                project_context=project_context,
                repo_context=request.repo_context,
            )
            content = (
                generated
                if isinstance(generated, ArchitecturePlanContent)
                else ArchitecturePlanContent.model_validate(generated)
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Architecture generation failed for project %s (provider=%s, error=%s)",
                project_id,
                provider_name or "default",
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "The LLM provider failed to generate a valid architecture plan. Please retry."
                ),
            )

        base_title = f"Architecture Plan - {specification.title}"
        title = base_title[:200]

        for attempt in range(3):
            latest = await self.plan_repo.get_latest_by_project(project_id)
            new_version = (latest.version + 1) if latest else 1
            try:
                async with self.session.begin_nested():
                    plan = await self.plan_repo.create(
                        project_id=project_id,
                        specification_id=specification.id,
                        title=title,
                        content_json=content.model_dump(),
                        version=new_version,
                    )
                return self._to_response(plan)
            except IntegrityError:
                logger.warning(
                    "Architecture version conflict for project %s (attempt %s)",
                    project_id,
                    attempt + 1,
                )
                if attempt == 2:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=("A concurrent architecture generation conflicted. Please retry."),
                    )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to allocate an architecture plan version. Please retry.",
        )

    async def get(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> ArchitecturePlanResponse:
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Architecture plan not found",
            )
        await self._assert_project_access(user_id, plan.project_id)
        return self._to_response(plan)

    async def list_by_project(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ArchitecturePlanResponse]:
        await self._assert_project_access(user_id, project_id)
        plans = await self.plan_repo.list_by_project(project_id, limit=limit, offset=offset)
        return [self._to_response(plan) for plan in plans]

    async def update(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        data: ArchitecturePlanUpdateRequest,
    ) -> ArchitecturePlanResponse:
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Architecture plan not found",
            )
        await self._assert_project_access(user_id, plan.project_id, required_roles=GENERATE_ROLES)
        if plan.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot edit an architecture plan with status '{plan.status}'. "
                    "Generate a new version instead."
                ),
            )

        updates: dict[str, Any] = {}
        if data.title is not None:
            updates["title"] = data.title
        if data.content_json is not None:
            updates["content_json"] = data.content_json.model_dump()

        updated = await self.plan_repo.update(plan, **updates)
        return self._to_response(updated)

    async def approve(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> ArchitecturePlanResponse:
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Architecture plan not found",
            )
        await self._assert_project_access(user_id, plan.project_id, required_roles=APPROVE_ROLES)
        if plan.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Architecture plan is already approved.",
            )
        if plan.status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A rejected architecture plan cannot be approved. "
                    "Generate a new version instead."
                ),
            )
        updated = await self.plan_repo.update(
            plan,
            status="approved",
            approved_by=user_id,
            approved_at=datetime.now(UTC),
        )
        return self._to_response(updated)

    async def reject(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> ArchitecturePlanResponse:
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Architecture plan not found",
            )
        await self._assert_project_access(user_id, plan.project_id, required_roles=APPROVE_ROLES)
        if plan.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An approved architecture plan cannot be rejected.",
            )
        if plan.status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Architecture plan is already rejected.",
            )
        updated = await self.plan_repo.update(plan, status="rejected")
        return self._to_response(updated)
