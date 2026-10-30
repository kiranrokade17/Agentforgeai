from pydantic import BaseModel, ConfigDict


class RepositoryCreate(BaseModel):
    name: str
    owner: str
    default_branch: str = "main"
    provider: str = "github"


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner: str
    default_branch: str
    provider: str
    status: str = "connected"
    created_at: str | None = None


class PullRequestCreate(BaseModel):
    repository_id: str
    title: str
    head_branch: str
    base_branch: str = "main"
    status: str = "draft"


class PullRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    title: str
    head_branch: str
    base_branch: str
    status: str = "draft"
    created_at: str | None = None


class PullRequestApproval(BaseModel):
    status: str = "approved"
    note: str | None = None
