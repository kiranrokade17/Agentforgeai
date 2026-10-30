import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.deployments import (
    CIStatusCreate,
    CIStatusResponse,
    DeploymentApprovalRequest,
    DeploymentCreate,
    DeploymentResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.deployment_service import DeploymentService

router = APIRouter(tags=["Deployments"])


@router.get(
    "/deployments",
    response_model=list[DeploymentResponse],
    summary="List deployment records",
)
async def list_deployments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = AnalyticsService(db)
    deployments = await service.get_deployments()
    return [
        DeploymentResponse(
            id=str(item.id),
            environment=item.environment,
            status=item.status,
            version=item.version,
            notes=item.notes,
            created_at=item.created_at.isoformat() if item.created_at else None,
        )
        for item in deployments
    ]


@router.post(
    "/deployments",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    payload: DeploymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = DeploymentService(db)
    return await service.create_deployment(payload)


@router.post(
    "/ci/status",
    response_model=CIStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist CI status for a deployment",
)
async def record_ci_status(
    payload: CIStatusCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = DeploymentService(db)
    return await service.record_ci_status(payload)


@router.post(
    "/deployments/{deployment_id}/approve",
    response_model=DeploymentResponse,
    summary="Approve or reject a deployment after CI verification",
)
async def approve_deployment(
    deployment_id: uuid.UUID,
    payload: DeploymentApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = DeploymentService(db)
    return await service.approve_deployment(deployment_id, approved=payload.approved)
