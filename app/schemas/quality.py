from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QualityFindingItem(BaseModel):
    severity: str = "medium"
    title: str
    file: str | None = None
    line: int | None = None
    description: str | None = None


class TestRunCreate(BaseModel):
    task_id: str | None = None
    command: str
    status: str = "queued"
    exit_code: int = 0
    summary: str | None = None
    duration_ms: int | None = None


class TestRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str | None = None
    command: str
    status: str
    exit_code: int = 0
    summary: str | None = None
    duration_ms: int | None = None
    created_at: str | None = None


class ReviewCreate(BaseModel):
    task_id: str | None = None
    summary: str
    status: str = "pending"
    findings: list[QualityFindingItem] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str | None = None
    summary: str
    status: str
    findings: list[QualityFindingItem] = Field(default_factory=list)
    created_at: str | None = None
