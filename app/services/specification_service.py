import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import get_llm_provider
from app.db.models.specification import Specification
from app.repositories.project_repo import ProjectRepository
from app.repositories.specification_repo import SpecificationRepository
from app.schemas.specification import (
    SpecificationGenerateRequest,
    SpecificationResponse,
    SpecificationUpdateRequest,
    SRSContent,
)
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)


class SpecificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.spec_repo = SpecificationRepository(session)
        self.project_repo = ProjectRepository(session)
        self.workspace_service = WorkspaceService(session)

    async def _assert_project_access(
        self, user_id: uuid.UUID, project_id: uuid.UUID, required_roles: list[str] | None = None
    ):
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        await self.workspace_service.check_access(
            workspace_id=project.workspace_id, user_id=user_id, required_roles=required_roles
        )
        return project

    @staticmethod
    def _to_response(spec: Specification) -> SpecificationResponse:
        return SpecificationResponse(
            id=spec.id,
            project_id=spec.project_id,
            version=spec.version,
            title=spec.title,
            content_json=SRSContent.model_validate(spec.content_json),
            status=spec.status,
            approved_by=spec.approved_by,
            approved_at=spec.approved_at,
            created_at=spec.created_at,
        )

    async def generate(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        request: SpecificationGenerateRequest,
        provider_name: str | None = None,
    ) -> SpecificationResponse:
        project = await self._assert_project_access(
            user_id, project_id, required_roles=["owner", "admin", "developer"]
        )
        if project.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Specifications can only be generated for active projects.",
            )

        project_context: dict[str, Any] = {
            "project_name": project.name,
            "project_description": project.description or "",
            "stack": project.stack_json,
        }
        if request.additional_context:
            project_context["additional_context"] = request.additional_context

        try:
            provider = get_llm_provider(provider_name)
            generated = await provider.generate_srs(
                user_requirement=request.user_requirement,
                project_context=project_context,
            )
            srs = generated if isinstance(generated, SRSContent) else SRSContent.model_validate(generated)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Specification generation failed for project %s (provider=%s, error=%s)",
                project_id,
                provider_name or "default",
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The LLM provider failed to generate a valid specification. Please retry.",
            )

        title = (
            srs.project_summary[:80].strip().rstrip(".")
            if srs.project_summary and srs.project_summary.strip()
            else None
        )

        for attempt in range(3):
            latest = await self.spec_repo.get_latest_by_project_id(project_id)
            new_version = (latest.version + 1) if latest else 1
            try:
                async with self.session.begin_nested():
                    spec = await self.spec_repo.create(
                        project_id=project_id,
                        title=title or f"Specification v{new_version}",
                        content_json=srs.model_dump(),
                        version=new_version,
                    )
                return self._to_response(spec)
            except IntegrityError:
                logger.warning(
                    "Specification version conflict for project %s (attempt %s)",
                    project_id,
                    attempt + 1,
                )
                if attempt == 2:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A concurrent specification generation conflicted. Please retry.",
                    )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to allocate a specification version. Please retry.",
        )

    async def get(self, user_id: uuid.UUID, spec_id: uuid.UUID) -> SpecificationResponse:
        spec = await self.spec_repo.get_by_id(spec_id)
        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found"
            )
        await self._assert_project_access(user_id, spec.project_id)
        return self._to_response(spec)

    async def list_by_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[SpecificationResponse]:
        await self._assert_project_access(user_id, project_id)
        specs = await self.spec_repo.list_by_project_id(project_id, limit=limit, offset=offset)
        return [self._to_response(spec) for spec in specs]

    async def update(
        self, user_id: uuid.UUID, spec_id: uuid.UUID, data: SpecificationUpdateRequest
    ) -> SpecificationResponse:
        spec = await self.spec_repo.get_by_id(spec_id)
        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found"
            )
        await self._assert_project_access(
            user_id, spec.project_id, required_roles=["owner", "admin", "developer"]
        )
        if spec.status in {"approved", "rejected"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot edit a specification with status '{spec.status}'. Generate a new version instead.",
            )

        update_kwargs: dict[str, Any] = {}
        if data.title is not None:
            update_kwargs["title"] = data.title
        if data.content_json is not None:
            update_kwargs["content_json"] = data.content_json.model_dump()

        updated = await self.spec_repo.update(spec, **update_kwargs)
        return self._to_response(updated)

    async def approve(self, user_id: uuid.UUID, spec_id: uuid.UUID) -> SpecificationResponse:
        spec = await self.spec_repo.get_by_id(spec_id)
        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found"
            )
        await self._assert_project_access(
            user_id, spec.project_id, required_roles=["owner", "admin"]
        )
        if spec.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Specification is already approved."
            )
        if spec.status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A rejected specification cannot be approved. Generate a new version instead.",
            )
        updated = await self.spec_repo.update(
            spec, status="approved", approved_by=user_id, approved_at=datetime.now(UTC)
        )
        return self._to_response(updated)

    async def reject(self, user_id: uuid.UUID, spec_id: uuid.UUID) -> SpecificationResponse:
        spec = await self.spec_repo.get_by_id(spec_id)
        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found"
            )
        await self._assert_project_access(
            user_id, spec.project_id, required_roles=["owner", "admin"]
        )
        if spec.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An approved specification cannot be rejected.",
            )
        if spec.status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Specification is already rejected."
            )
        updated = await self.spec_repo.update(spec, status="rejected")
        return self._to_response(updated)
