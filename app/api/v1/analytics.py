from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.analytics import AnalyticsSummary
from app.schemas.deployments import DeploymentResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["Analytics"])


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummary,
    summary="Summarize deployments and usage telemetry",
)
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = AnalyticsService(db)
    return await service.get_summary()
