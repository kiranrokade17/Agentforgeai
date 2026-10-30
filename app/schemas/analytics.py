from pydantic import BaseModel, ConfigDict


class AnalyticsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deployments_total: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    queued_deployments: int = 0
    status_breakdown: dict[str, int] = {}
    usage_records_total: int = 0
    total_cost_estimate: float = 0.0
    resource_breakdown: dict[str, int] = {}
