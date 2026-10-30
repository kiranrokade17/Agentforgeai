import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.specification import (
    SpecificationGenerateRequest,
    SpecificationResponse,
    SpecificationUpdateRequest,
)
from app.services.specification_service import SpecificationService

router = APIRouter(prefix="/specifications", tags=["Specifications"])


@router.post(
    "/projects/{project_id}/generate",
    response_model=SpecificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate SRS from natural language requirement",
    description=(
        "Analyzes the provided natural-language requirement using the configured LLM provider "
        "(default: Gemini 2.5 Flash) and returns a structured, schema-validated "
        "Software Requirements Specification (SRS) as a versioned draft."
    ),
)
async def generate_specification(
    project_id: uuid.UUID,
    request: SpecificationGenerateRequest,
    provider: Literal["gemini", "mock", "openrouter"] | None = Query(
        None,
        description="LLM provider to use: 'gemini', 'openrouter', or 'mock' (development/test only)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SpecificationService(db)
    return await service.generate(
        current_user.id,
        project_id,
        request,
        provider_name=provider,
    )


@router.get(
    "/projects/{project_id}",
    response_model=list[SpecificationResponse],
    summary="List all specifications for a project",
)
async def list_specifications(
    project_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200, description="Maximum specifications to return"),
    offset: int = Query(0, ge=0, description="Number of specifications to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SpecificationService(db)
    return await service.list_by_project(current_user.id, project_id, limit=limit, offset=offset)


@router.get(
    "/{spec_id}", response_model=SpecificationResponse, summary="Get a specific specification by ID"
)
async def get_specification(
    spec_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SpecificationService(db)
    return await service.get(current_user.id, spec_id)


@router.patch(
    "/{spec_id}", response_model=SpecificationResponse, summary="Edit a draft specification"
)
async def update_specification(
    spec_id: uuid.UUID,
    data: SpecificationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SpecificationService(db)
    return await service.update(current_user.id, spec_id, data)


@router.post(
    "/{spec_id}/approve",
    response_model=SpecificationResponse,
    summary="Human approval gate: approve a specification for task planning",
    description=(
        "Marks the specification as approved. Only workspace owners and admins may approve. "
        "Approved specifications are locked from further editing and unlock task planning."
    ),
)
async def approve_specification(
    spec_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SpecificationService(db)
    return await service.approve(current_user.id, spec_id)


@router.post(
    "/{spec_id}/reject",
    response_model=SpecificationResponse,
    summary="Reject a specification",
    description=(
        "Marks a draft or in-review specification as rejected. "
        "Only workspace owners and admins may reject."
    ),
)
async def reject_specification(
    spec_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SpecificationService(db)
    return await service.reject(current_user.id, spec_id)
