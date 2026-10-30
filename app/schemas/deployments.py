from pydantic import BaseModel, ConfigDict


class DeploymentCreate(BaseModel):
    environment: str
    status: str = "queued"
    version: str
    notes: str | None = None


class DeploymentApprovalRequest(BaseModel):
    approved: bool = True
    approver: str | None = None


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    environment: str
    status: str
    version: str
    notes: str | None = None
    created_at: str | None = None


class CIStatusCreate(BaseModel):
    deployment_id: str
    workflow: str
    status: str
    conclusion: str | None = None
    branch: str | None = None
    run_url: str | None = None


class CIStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    deployment_id: str
    workflow: str
    status: str
    conclusion: str | None = None
    branch: str | None = None
    run_url: str | None = None
    created_at: str | None = None
