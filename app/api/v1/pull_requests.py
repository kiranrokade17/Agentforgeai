import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.github import PullRequestCreate, PullRequestResponse
from app.services.github_service import GitHubService

router = APIRouter(tags=["GitHub"])


@router.get(
    "/pull-requests",
    response_model=list[PullRequestResponse],
    summary="List pull requests",
)
async def list_pull_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = GitHubService(db)
    return await service.list_pull_requests()


@router.post(
    "/pull-requests",
    response_model=PullRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pull_request(
    payload: PullRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = GitHubService(db)
    return await service.create_pull_request(payload)


@router.post(
    "/pull-requests/{pull_request_id}/approve",
    response_model=PullRequestResponse,
    summary="Approve a pull request",
)
async def approve_pull_request(
    pull_request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = GitHubService(db)
    return await service.approve_pull_request(pull_request_id)
