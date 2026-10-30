import uuid

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.github import PullRequestRecord, RepositoryRecord
from app.schemas.github import (
    PullRequestCreate,
    PullRequestResponse,
    RepositoryCreate,
    RepositoryResponse,
)


class GitHubService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_repositories(self) -> list[RepositoryResponse]:
        result = await self.session.execute(select(RepositoryRecord).order_by(RepositoryRecord.created_at.desc()))
        repos = result.scalars().all()
        return [
            RepositoryResponse(
                id=str(repo.id),
                name=repo.name,
                owner=repo.owner,
                default_branch=repo.default_branch,
                provider=repo.provider,
                status=repo.status,
                created_at=repo.created_at.isoformat() if repo.created_at else None,
            )
            for repo in repos
        ]

    async def create_repository(self, data: RepositoryCreate) -> RepositoryResponse:
        repo = RepositoryRecord(
            owner=data.owner,
            name=data.name,
            default_branch=data.default_branch,
            provider=data.provider,
            status="connected",
        )
        self.session.add(repo)
        await self.session.commit()
        await self.session.refresh(repo)
        return RepositoryResponse(
            id=str(repo.id),
            name=repo.name,
            owner=repo.owner,
            default_branch=repo.default_branch,
            provider=repo.provider,
            status=repo.status,
            created_at=repo.created_at.isoformat() if repo.created_at else None,
        )

    async def list_pull_requests(self) -> list[PullRequestResponse]:
        result = await self.session.execute(
            select(PullRequestRecord).order_by(PullRequestRecord.created_at.desc())
        )
        prs = result.scalars().all()
        return [
            PullRequestResponse(
                id=str(pr.id),
                repository_id=str(pr.repository_id),
                title=pr.title,
                head_branch=pr.head_branch,
                base_branch=pr.base_branch,
                status=pr.status,
                created_at=pr.created_at.isoformat() if pr.created_at else None,
            )
            for pr in prs
        ]

    async def create_pull_request(self, data: PullRequestCreate) -> PullRequestResponse:
        repo_id = uuid.UUID(data.repository_id)
        pr = PullRequestRecord(
            repository_id=repo_id,
            title=data.title,
            head_branch=data.head_branch,
            base_branch=data.base_branch,
            status=data.status,
        )
        self.session.add(pr)
        await self.session.commit()
        await self.session.refresh(pr)
        return PullRequestResponse(
            id=str(pr.id),
            repository_id=str(pr.repository_id),
            title=pr.title,
            head_branch=pr.head_branch,
            base_branch=pr.base_branch,
            status=pr.status,
            created_at=pr.created_at.isoformat() if pr.created_at else None,
        )

    async def approve_pull_request(self, pull_request_id: uuid.UUID) -> PullRequestResponse:
        result = await self.session.execute(
            select(PullRequestRecord).where(PullRequestRecord.id == pull_request_id)
        )
        pr = result.scalar_one_or_none()
        if pr is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Pull request not found",
            )

        pr.status = "approved"
        await self.session.commit()
        await self.session.refresh(pr)
        return PullRequestResponse(
            id=str(pr.id),
            repository_id=str(pr.repository_id),
            title=pr.title,
            head_branch=pr.head_branch,
            base_branch=pr.base_branch,
            status=pr.status,
            created_at=pr.created_at.isoformat() if pr.created_at else None,
        )
