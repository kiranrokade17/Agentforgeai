import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.architecture_plan import ArchitecturePlan


class ArchitecturePlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, plan_id: uuid.UUID) -> ArchitecturePlan | None:
        result = await self.session.execute(
            select(ArchitecturePlan).where(ArchitecturePlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(
        self, project_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[ArchitecturePlan]:
        result = await self.session.execute(
            select(ArchitecturePlan)
            .where(ArchitecturePlan.project_id == project_id)
            .order_by(ArchitecturePlan.version.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_latest_by_project(self, project_id: uuid.UUID) -> ArchitecturePlan | None:
        result = await self.session.execute(
            select(ArchitecturePlan)
            .where(ArchitecturePlan.project_id == project_id)
            .order_by(ArchitecturePlan.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        project_id: uuid.UUID,
        specification_id: uuid.UUID,
        title: str,
        content_json: dict,
        version: int = 1,
    ) -> ArchitecturePlan:
        plan = ArchitecturePlan(
            project_id=project_id,
            specification_id=specification_id,
            title=title,
            content_json=content_json,
            version=version,
            status="draft",
        )
        self.session.add(plan)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def update(self, plan: ArchitecturePlan, **kwargs) -> ArchitecturePlan:
        for key, value in kwargs.items():
            if value is not None and hasattr(plan, key):
                setattr(plan, key, value)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan
