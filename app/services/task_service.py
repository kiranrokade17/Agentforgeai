import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import get_llm_provider
from app.db.models.task import Task
from app.repositories.architecture_plan_repo import ArchitecturePlanRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.specification_repo import SpecificationRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.planning import (
    ArchitecturePlanContent,
    TaskDependencyResponse,
    TaskGenerateRequest,
    TaskPlanContent,
    TaskPlanResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from app.schemas.specification import SRSContent
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)

GENERATE_ROLES = ["owner", "admin", "developer"]
APPROVE_ROLES = ["owner", "admin"]
CONTENT_FIELDS = {
    "title",
    "description",
    "task_type",
    "priority",
    "acceptance_criteria",
    "required_tests",
}


class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = TaskRepository(session)
        self.project_repo = ProjectRepository(session)
        self.spec_repo = SpecificationRepository(session)
        self.plan_repo = ArchitecturePlanRepository(session)
        self.workspace_service = WorkspaceService(session)

    async def _assert_project_access(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        required_roles: list[str] | None = None,
    ):
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        await self.workspace_service.check_access(
            workspace_id=project.workspace_id,
            user_id=user_id,
            required_roles=required_roles,
        )
        return project

    @staticmethod
    def _to_response(task: Task) -> TaskResponse:
        dependencies = sorted(
            (edge.depends_on_task for edge in task.dependencies),
            key=lambda dependency: dependency.order,
        )
        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            specification_id=task.specification_id,
            order=task.order,
            title=task.title,
            description=task.description,
            task_type=task.task_type,
            priority=task.priority,
            status=task.status,
            acceptance_criteria=task.acceptance_criteria,
            required_tests=task.required_tests,
            metadata_json=task.metadata_json,
            depends_on=[
                TaskDependencyResponse(
                    id=dependency.id,
                    order=dependency.order,
                    title=dependency.title,
                )
                for dependency in dependencies
            ],
            approved_by=task.approved_by,
            approved_at=task.approved_at,
            created_at=task.created_at,
        )

    @staticmethod
    def _validate_dependencies(plan: TaskPlanContent) -> None:
        items = [task.model_dump() for task in plan.tasks]
        orders = [item["order"] for item in items]
        order_set: set[int] = set(orders)

        if len(orders) != len(order_set):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The task plan contains duplicate order values.",
            )

        for item in items:
            for dependency_order in item["depends_on_orders"]:
                if dependency_order not in order_set:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=("The task plan references a dependency order that does not exist."),
                    )

        self_dependency = any(item["order"] in item["depends_on_orders"] for item in items)
        if self_dependency or TaskRepository.detect_cycle(items):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The task plan contains a circular dependency.",
            )

        if any(
            dependency_order > item["order"]
            for item in items
            for dependency_order in item["depends_on_orders"]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=("Task dependencies must reference tasks with an earlier order value."),
            )

    async def generate(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        request: TaskGenerateRequest,
        provider_name: str | None = None,
    ) -> TaskPlanResponse:
        project = await self._assert_project_access(
            user_id, project_id, required_roles=GENERATE_ROLES
        )
        if project.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tasks can only be generated for active projects.",
            )

        specification = await self.spec_repo.get_by_id(request.specification_id)
        if not specification or specification.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specification not found for this project",
            )
        if specification.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task planning requires an approved specification.",
            )

        if await self.task_repo.count_by_specification(specification.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A task plan already exists for this specification. "
                    "Create a new approved specification version to re-plan."
                ),
            )

        try:
            srs = SRSContent.model_validate(specification.content_json)
        except Exception:
            logger.error("Stored specification %s has an invalid payload", specification.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The stored specification is invalid.",
            )

        architecture: ArchitecturePlanContent | None = None
        if request.architecture_plan_id is not None:
            plan = await self.plan_repo.get_by_id(request.architecture_plan_id)
            if (
                not plan
                or plan.project_id != project_id
                or plan.specification_id != specification.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Architecture plan not found for this specification",
                )
            if plan.status != "approved":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only an approved architecture plan can be used for planning.",
                )
            try:
                architecture = ArchitecturePlanContent.model_validate(plan.content_json)
            except Exception:
                logger.error("Stored architecture plan %s has an invalid payload", plan.id)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="The stored architecture plan is invalid.",
                )

        project_context: dict[str, Any] = {
            "project_name": project.name,
            "project_description": project.description or "",
            "stack": project.stack_json,
        }

        try:
            provider = get_llm_provider(provider_name)
            generated = await provider.generate_tasks(
                srs=srs,
                architecture=architecture,
                project_context=project_context,
                additional_context=request.additional_context,
            )
            plan_content = (
                generated
                if isinstance(generated, TaskPlanContent)
                else TaskPlanContent.model_validate(generated)
            )
            self._validate_dependencies(plan_content)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Task planning failed for project %s (provider=%s, error=%s)",
                project_id,
                provider_name or "default",
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The LLM provider failed to generate a valid task plan. Please retry.",
            )

        task_data = [task.model_dump() for task in plan_content.tasks]
        dependency_pairs = [
            (task["order"], dependency_order)
            for task in task_data
            for dependency_order in task["depends_on_orders"]
        ]

        try:
            async with self.session.begin_nested():
                created_tasks = await self.task_repo.bulk_create(
                    project_id=project_id,
                    specification_id=specification.id,
                    task_data_list=task_data,
                )
                order_to_id = {task.order: task.id for task in created_tasks}
                await self.task_repo.create_dependencies(order_to_id, dependency_pairs)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("A concurrent task plan generation conflicted. Please retry."),
            )

        tasks = await self.task_repo.list_by_specification(specification.id)
        return TaskPlanResponse(
            planning_summary=plan_content.planning_summary,
            tasks=[self._to_response(task) for task in tasks],
        )

    async def get(self, user_id: uuid.UUID, task_id: uuid.UUID) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        await self._assert_project_access(user_id, task.project_id)
        return self._to_response(task)

    async def list_by_project(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        task_status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskResponse]:
        await self._assert_project_access(user_id, project_id)
        tasks = await self.task_repo.list_by_project(
            project_id,
            status=task_status,
            task_type=task_type,
            limit=limit,
            offset=offset,
        )
        return [self._to_response(task) for task in tasks]

    async def update(
        self, user_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdateRequest
    ) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        await self._assert_project_access(user_id, task.project_id, required_roles=GENERATE_ROLES)

        updates = data.model_dump(exclude_unset=True, exclude_none=True)
        if not updates:
            return self._to_response(task)

        await self.task_repo.update(task, **updates)
        if set(updates) & CONTENT_FIELDS:
            await self.task_repo.clear_approval(task)

        refreshed = await self.task_repo.get_by_id(task_id)
        if not refreshed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return self._to_response(refreshed)

    async def approve(self, user_id: uuid.UUID, task_id: uuid.UUID) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        await self._assert_project_access(user_id, task.project_id, required_roles=APPROVE_ROLES)
        if task.status in {"done", "cancelled"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A task with status '{task.status}' cannot be approved.",
            )
        if task.approved_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task is already approved.",
            )

        await self.task_repo.update(
            task,
            approved_by=user_id,
            approved_at=datetime.now(UTC),
        )
        refreshed = await self.task_repo.get_by_id(task_id)
        if not refreshed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return self._to_response(refreshed)
