import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SpecificationStatus = Literal["draft", "in_review", "approved", "rejected"]


class FunctionalRequirement(BaseModel):
    id: str = Field(..., description="Unique ID, e.g. FR-01")
    title: str = Field(..., description="Brief title of the requirement")
    description: str = Field(..., description="Detailed description")
    priority: str = Field("high", description="Priority level: critical, high, medium, low")
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Verifiable test criteria"
    )


class NonFunctionalRequirement(BaseModel):
    category: str = Field(..., description="Category, e.g. Security, Performance, Scalability")
    requirement: str = Field(..., description="Target requirement description")
    metric: str | None = Field(None, description="Measurable SLA or metric")


class UserStory(BaseModel):
    id: str = Field(..., description="Unique ID, e.g. US-01")
    as_a: str = Field(..., description="User role or persona")
    i_want: str = Field(..., description="Desired capability")
    so_that: str = Field(..., description="Business benefit or goal")
    acceptance_criteria: list[str] = Field(default_factory=list, description="Pass/fail criteria")


class SRSContent(BaseModel):
    project_summary: str = Field(..., description="Executive architecture and functional summary")
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    assumptions: list[str] = Field(
        default_factory=list, description="Key architectural assumptions"
    )
    risks: list[str] = Field(
        default_factory=list, description="Identified technical/delivery risks"
    )
    open_questions: list[str] = Field(
        default_factory=list, description="Ambiguities or open questions"
    )

    model_config = ConfigDict(from_attributes=True)


class SpecificationGenerateRequest(BaseModel):
    user_requirement: str = Field(
        ..., min_length=10, max_length=10_000, description="Natural language software requirement"
    )
    additional_context: str | None = Field(
        None,
        max_length=20_000,
        description="Existing repo context, stack preferences, or guidelines",
    )

    @field_validator("user_requirement")
    @classmethod
    def requirement_must_have_content(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 10:
            raise ValueError("user_requirement must contain at least 10 non-whitespace characters")
        return stripped

    @field_validator("additional_context")
    @classmethod
    def normalize_additional_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SpecificationUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    content_json: SRSContent | None = None


class SpecificationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    title: str
    content_json: SRSContent
    status: SpecificationStatus
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
