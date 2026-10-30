import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.project_repo import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.workspace_service import WorkspaceService


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.workspace_service = WorkspaceService(session)

    async def create_project(self, user_id: uuid.UUID, data: ProjectCreate) -> ProjectResponse:
        # Enforce that user has developer, admin, or owner role in the workspace
        await self.workspace_service.check_access(
            workspace_id=data.workspace_id,
            user_id=user_id,
            required_roles=["owner", "admin", "developer"],
        )

        project = await self.project_repo.create(
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description,
            stack_json=data.stack_json,
        )
        return ProjectResponse.model_validate(project)

    async def get_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        # Enforce that user belongs to the project's workspace
        await self.workspace_service.check_access(
            workspace_id=project.workspace_id, user_id=user_id
        )
        return ProjectResponse.model_validate(project)

    async def list_projects(
        self, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[ProjectResponse]:
        await self.workspace_service.check_access(workspace_id=workspace_id, user_id=user_id)
        projects = await self.project_repo.list_by_workspace_id(workspace_id)
        return [ProjectResponse.model_validate(p) for p in projects]

    async def update_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID, data: ProjectUpdate
    ) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        await self.workspace_service.check_access(
            workspace_id=project.workspace_id,
            user_id=user_id,
            required_roles=["owner", "admin", "developer"],
        )

        update_dict = data.model_dump(exclude_unset=True)
        updated = await self.project_repo.update(project, **update_dict)
        return ProjectResponse.model_validate(updated)
