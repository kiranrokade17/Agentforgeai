import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.specification import Specification


class SpecificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, spec_id: uuid.UUID) -> Specification | None:
        result = await self.session.execute(
            select(Specification).where(Specification.id == spec_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project_id(
        self, project_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Specification]:
        result = await self.session.execute(
            select(Specification)
            .where(Specification.project_id == project_id)
            .order_by(Specification.version.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_latest_by_project_id(self, project_id: uuid.UUID) -> Specification | None:
        result = await self.session.execute(
            select(Specification)
            .where(Specification.project_id == project_id)
            .order_by(Specification.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self, project_id: uuid.UUID, title: str, content_json: dict, version: int = 1
    ) -> Specification:
        spec = Specification(
            project_id=project_id,
            title=title,
            content_json=content_json,
            version=version,
            status="draft",
        )
        self.session.add(spec)
        await self.session.flush()
        await self.session.refresh(spec)
        return spec

    async def update(self, spec: Specification, **kwargs) -> Specification:
        for key, value in kwargs.items():
            if value is not None and hasattr(spec, key):
                setattr(spec, key, value)
        await self.session.flush()
        await self.session.refresh(spec)
        return spec
