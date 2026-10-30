from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.github import RepositoryCreate, RepositoryResponse
from app.services.github_service import GitHubService

router = APIRouter(tags=["GitHub"])


@router.get(
    "/repositories",
    response_model=list[RepositoryResponse],
    summary="List connected repositories",
)
async def list_repositories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = GitHubService(db)
    return await service.list_repositories()


@router.post(
    "/repositories",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_repository(
    payload: RepositoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = GitHubService(db)
    return await service.create_repository(payload)
