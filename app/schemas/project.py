import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    stack_json: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    stack_json: dict[str, Any] | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None = None
    stack_json: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
