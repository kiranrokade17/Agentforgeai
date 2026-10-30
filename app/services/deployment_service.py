import uuid

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.deployments import Deployment, DeploymentStatusRecord, UsageRecord
from app.schemas.deployments import (
    CIStatusCreate,
    CIStatusResponse,
    DeploymentCreate,
    DeploymentResponse,
)


class DeploymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_deployment_or_404(self, deployment_id: uuid.UUID) -> Deployment:
        result = await self.session.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        if deployment is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Deployment not found",
            )
        return deployment

    async def create_deployment(self, data: DeploymentCreate) -> DeploymentResponse:
        deployment = Deployment(
            environment=data.environment,
            status=data.status,
            version=data.version,
            notes=data.notes,
        )
        self.session.add(deployment)
        await self.session.commit()
        await self.session.refresh(deployment)
        return DeploymentResponse(
            id=str(deployment.id),
            environment=deployment.environment,
            status=deployment.status,
            version=deployment.version,
            notes=deployment.notes,
            created_at=deployment.created_at.isoformat() if deployment.created_at else None,
        )

    async def record_ci_status(self, data: CIStatusCreate) -> CIStatusResponse:
        deployment_id = uuid.UUID(data.deployment_id)
        deployment = await self._get_deployment_or_404(deployment_id)
        status_record = DeploymentStatusRecord(
            deployment_id=deployment.id,
            workflow=data.workflow,
            status=data.status,
            conclusion=data.conclusion,
            branch=data.branch,
            run_url=data.run_url,
        )
        deployment.status = data.status if data.status in {"queued", "in_progress", "success", "failure", "cancelled"} else deployment.status
        self.session.add(status_record)
        await self.session.commit()
        await self.session.refresh(status_record)
        return CIStatusResponse(
            id=str(status_record.id),
            deployment_id=str(status_record.deployment_id),
            workflow=status_record.workflow,
            status=status_record.status,
            conclusion=status_record.conclusion,
            branch=status_record.branch,
            run_url=status_record.run_url,
            created_at=status_record.created_at.isoformat() if status_record.created_at else None,
        )

    async def approve_deployment(self, deployment_id: uuid.UUID, approved: bool = True) -> DeploymentResponse:
        deployment = await self._get_deployment_or_404(deployment_id)
        deployment.status = "approved" if approved else "rejected"
        await self.session.commit()
        await self.session.refresh(deployment)
        return DeploymentResponse(
            id=str(deployment.id),
            environment=deployment.environment,
            status=deployment.status,
            version=deployment.version,
            notes=deployment.notes,
            created_at=deployment.created_at.isoformat() if deployment.created_at else None,
        )

    async def record_usage(self, *, resource_type: str, quantity: int, cost_estimate: float | None = None, metadata_json: dict | None = None, user_id=None) -> UsageRecord:
        usage = UsageRecord(
            user_id=user_id,
            resource_type=resource_type,
            quantity=quantity,
            cost_estimate=cost_estimate,
            metadata_json=metadata_json or {},
        )
        self.session.add(usage)
        await self.session.commit()
        await self.session.refresh(usage)
        return usage
