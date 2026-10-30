import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class WorkspaceMemberResponse(BaseModel):
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
