import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.planning import (
    TaskGenerateRequest,
    TaskPlanResponse,
    TaskResponse,
    TaskStatus,
    TaskType,
    TaskUpdateRequest,
)
from app.services.task_service import TaskService

router = APIRouter(tags=["Tasks"])


@router.post(
    "/projects/{project_id}/tasks/generate",
    response_model=TaskPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a dependency-aware task plan from an approved specification",
)
async def generate_tasks(
    project_id: uuid.UUID,
    request: TaskGenerateRequest,
    provider: Literal["gemini", "mock", "openrouter"] | None = Query(
        None,
        description="LLM provider to use: 'gemini', 'openrouter', or 'mock' (development/test only)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    return await service.generate(
        current_user.id,
        project_id,
        request,
        provider_name=provider,
    )


@router.get(
    "/projects/{project_id}/tasks",
    response_model=list[TaskResponse],
    summary="List tasks for a project",
)
async def list_tasks(
    project_id: uuid.UUID,
    task_status: TaskStatus | None = Query(None, alias="status"),
    task_type: TaskType | None = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    return await service.list_by_project(
        current_user.id,
        project_id,
        task_status=task_status,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get a specific task",
)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    return await service.get(current_user.id, task_id)


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Edit a task",
)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    return await service.update(current_user.id, task_id, data)


@router.post(
    "/tasks/{task_id}/approve",
    response_model=TaskResponse,
    summary="Human approval gate: approve a task for execution",
)
async def approve_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    return await service.approve(current_user.id, task_id)
