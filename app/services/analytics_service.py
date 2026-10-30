from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.deployments import Deployment, UsageRecord
from app.schemas.analytics import AnalyticsSummary


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_deployments(self) -> list[Deployment]:
        result = await self.session.execute(select(Deployment).order_by(Deployment.created_at.desc()))
        return list(result.scalars().all())

    async def get_summary(self) -> AnalyticsSummary:
        deployment_rows = (await self.session.execute(select(Deployment))).scalars().all()
        usage_rows = (await self.session.execute(select(UsageRecord))).scalars().all()

        status_breakdown: dict[str, int] = defaultdict(int)
        for item in deployment_rows:
            status_breakdown[item.status] += 1

        resource_breakdown: dict[str, int] = defaultdict(int)
        total_cost_estimate = 0.0
        for usage in usage_rows:
            resource_breakdown[usage.resource_type] += usage.quantity
            if usage.cost_estimate is not None:
                total_cost_estimate += float(usage.cost_estimate)

        return AnalyticsSummary(
            deployments_total=len(deployment_rows),
            successful_deployments=sum(1 for item in deployment_rows if item.status == "succeeded"),
            failed_deployments=sum(1 for item in deployment_rows if item.status == "failed"),
            queued_deployments=sum(1 for item in deployment_rows if item.status == "queued"),
            status_breakdown=dict(status_breakdown),
            usage_records_total=len(usage_rows),
            total_cost_estimate=round(total_cost_estimate, 4),
            resource_breakdown=dict(resource_breakdown),
        )
