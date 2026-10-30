import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.planning import (
    ArchitecturePlanGenerateRequest,
    ArchitecturePlanResponse,
    ArchitecturePlanUpdateRequest,
)
from app.services.architecture_plan_service import ArchitecturePlanService

router = APIRouter(tags=["Architecture Plans"])


@router.post(
    "/projects/{project_id}/architecture/generate",
    response_model=ArchitecturePlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an architecture plan from an approved specification",
)
async def generate_architecture_plan(
    project_id: uuid.UUID,
    request: ArchitecturePlanGenerateRequest,
    provider: Literal["gemini", "mock", "openrouter"] | None = Query(
        None,
        description="LLM provider to use: 'gemini', 'openrouter', or 'mock' (development/test only)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ArchitecturePlanService(db)
    return await service.generate(
        current_user.id,
        project_id,
        request,
        provider_name=provider,
    )


@router.get(
    "/projects/{project_id}/architecture",
    response_model=list[ArchitecturePlanResponse],
    summary="List architecture plan versions for a project",
)
async def list_architecture_plans(
    project_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ArchitecturePlanService(db)
    return await service.list_by_project(current_user.id, project_id, limit=limit, offset=offset)


@router.get(
    "/architecture/{plan_id}",
    response_model=ArchitecturePlanResponse,
    summary="Get a specific architecture plan",
)
async def get_architecture_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ArchitecturePlanService(db)
    return await service.get(current_user.id, plan_id)


@router.patch(
    "/architecture/{plan_id}",
    response_model=ArchitecturePlanResponse,
    summary="Edit a draft architecture plan",
)
async def update_architecture_plan(
    plan_id: uuid.UUID,
    data: ArchitecturePlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ArchitecturePlanService(db)
    return await service.update(current_user.id, plan_id, data)


@router.post(
    "/architecture/{plan_id}/approve",
    response_model=ArchitecturePlanResponse,
    summary="Human approval gate: approve an architecture plan",
)
async def approve_architecture_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ArchitecturePlanService(db)
    return await service.approve(current_user.id, plan_id)


@router.post(
    "/architecture/{plan_id}/reject",
    response_model=ArchitecturePlanResponse,
    summary="Reject an architecture plan",
)
async def reject_architecture_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ArchitecturePlanService(db)
    return await service.reject(current_user.id, plan_id)
