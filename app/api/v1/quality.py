from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.quality import ReviewCreate, ReviewResponse, TestRunCreate, TestRunResponse
from app.services.quality_service import QualityService

router = APIRouter(tags=["Quality"])


@router.post(
    "/quality/test-runs",
    response_model=TestRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_run(
    payload: TestRunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = QualityService(db)
    return await service.create_test_run(payload)


@router.post(
    "/quality/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review(
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = QualityService(db)
    return await service.create_review(payload)
