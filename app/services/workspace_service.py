import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.workspace_repo import WorkspaceRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse


class WorkspaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)

    async def create_workspace(
        self, user_id: uuid.UUID, data: WorkspaceCreate
    ) -> WorkspaceResponse:
        workspace = await self.workspace_repo.create(name=data.name, owner_id=user_id)
        return WorkspaceResponse.model_validate(workspace)

    async def list_user_workspaces(self, user_id: uuid.UUID) -> list[WorkspaceResponse]:
        workspaces = await self.workspace_repo.list_by_user_id(user_id)
        return [WorkspaceResponse.model_validate(w) for w in workspaces]

    async def check_access(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, required_roles: list[str] | None = None
    ):
        membership = await self.workspace_repo.get_member(
            workspace_id=workspace_id, user_id=user_id
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace",
            )
        if required_roles and membership.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of roles: {', '.join(required_roles)}",
            )
        return membership
