import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ArchitecturePlanStatus = Literal["draft", "approved", "rejected"]
ComponentLayer = Literal["frontend", "backend", "database", "infra", "external"]
ChangeType = Literal["create", "modify", "delete", "no-change"]
TaskType = Literal["frontend", "backend", "database", "testing", "documentation", "devops"]
TaskPriority = Literal["critical", "high", "medium", "low"]
TaskStatus = Literal["backlog", "in_progress", "done", "blocked", "cancelled"]


class AffectedComponent(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    layer: ComponentLayer
    change_type: ChangeType
    description: str = Field(..., min_length=1, max_length=2_000)


class ArchitecturePlanContent(BaseModel):
    overview: str = Field(..., min_length=10, max_length=5_000)
    affected_components: list[AffectedComponent] = Field(default_factory=list, max_length=50)
    new_api_endpoints: list[str] = Field(default_factory=list, max_length=50)
    database_changes: list[str] = Field(default_factory=list, max_length=50)
    external_dependencies: list[str] = Field(default_factory=list, max_length=50)
    security_considerations: list[str] = Field(default_factory=list, max_length=50)
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    open_questions: list[str] = Field(default_factory=list, max_length=50)

    model_config = ConfigDict(from_attributes=True)


class ArchitecturePlanGenerateRequest(BaseModel):
    specification_id: uuid.UUID = Field(
        ..., description="ID of the approved specification to plan for"
    )
    repo_context: str | None = Field(
        None, max_length=20_000, description="Brief description of the existing codebase"
    )

    @field_validator("repo_context")
    @classmethod
    def normalize_repo_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ArchitecturePlanUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    content_json: ArchitecturePlanContent | None = None


class ArchitecturePlanResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    specification_id: uuid.UUID
    version: int
    title: str
    content_json: ArchitecturePlanContent
    status: ArchitecturePlanStatus
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskItem(BaseModel):
    order: int = Field(..., ge=1, description="Execution order within the plan (1-based)")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5_000)
    task_type: TaskType = "backend"
    priority: TaskPriority = "medium"
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)
    required_tests: list[str] = Field(default_factory=list, max_length=20)
    depends_on_orders: list[int] = Field(default_factory=list, max_length=20)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("depends_on_orders")
    @classmethod
    def dependency_orders_must_be_unique(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("depends_on_orders must not contain duplicates")
        return value


class TaskPlanContent(BaseModel):
    planning_summary: str = Field(
        ..., min_length=10, max_length=5_000, description="Brief rationale for the breakdown"
    )
    tasks: list[TaskItem] = Field(..., min_length=1, max_length=20)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def orders_must_be_unique(self) -> "TaskPlanContent":
        orders = [task.order for task in self.tasks]
        if len(orders) != len(set(orders)):
            raise ValueError("task order values must be unique")
        return self


class TaskGenerateRequest(BaseModel):
    specification_id: uuid.UUID = Field(..., description="ID of the approved specification")
    architecture_plan_id: uuid.UUID | None = Field(
        None, description="Optional approved architecture plan to incorporate"
    )
    additional_context: str | None = Field(None, max_length=20_000)

    @field_validator("additional_context")
    @classmethod
    def normalize_additional_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, min_length=10, max_length=5_000)
    task_type: TaskType | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    acceptance_criteria: list[str] | None = Field(None, max_length=20)
    required_tests: list[str] | None = Field(None, max_length=20)


class TaskDependencyResponse(BaseModel):
    id: uuid.UUID
    order: int
    title: str


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    specification_id: uuid.UUID
    order: int
    title: str
    description: str
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    acceptance_criteria: list[str]
    required_tests: list[str]
    metadata_json: dict
    depends_on: list[TaskDependencyResponse] = Field(default_factory=list)
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskPlanResponse(BaseModel):
    planning_summary: str
    tasks: list[TaskResponse]
