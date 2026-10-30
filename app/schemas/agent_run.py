import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AgentRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRunCreate(BaseModel):
    task_id: uuid.UUID
    task_title: str = Field(..., min_length=1)
    provider: str = "codex"
    repo_path: str | None = None
    context: dict[str, str | int | bool | None] | None = None


class AgentRunSummary(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    task_title: str | None = None
    provider: str
    status: AgentRunStatus
    exit_code: int | None = None
    summary: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
