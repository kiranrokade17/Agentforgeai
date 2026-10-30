import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workspace import Workspace
from app.db.models.workspace_member import WorkspaceMember


class WorkspaceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, workspace_id: uuid.UUID) -> Workspace | None:
        result = await self.session.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def create(self, name: str, owner_id: uuid.UUID) -> Workspace:
        workspace = Workspace(name=name, owner_id=owner_id)
        self.session.add(workspace)
        await self.session.flush()

        # Add owner as workspace member with role 'owner'
        membership = WorkspaceMember(workspace_id=workspace.id, user_id=owner_id, role="owner")
        self.session.add(membership)
        await self.session.flush()
        await self.session.refresh(workspace)
        return workspace

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: str = "developer"
    ) -> WorkspaceMember:
        member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.session.flush()
        return member
