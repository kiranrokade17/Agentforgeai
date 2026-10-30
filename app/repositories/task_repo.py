import uuid
from collections import defaultdict, deque

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.task import Task, TaskDependency


def _task_load_options():
    return (selectinload(Task.dependencies).selectinload(TaskDependency.depends_on_task),)


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        result = await self.session.execute(
            select(Task).options(*_task_load_options()).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .options(*_task_load_options())
            .where(Task.project_id == project_id)
            .order_by(Task.order.asc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Task.status == status)
        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_by_specification(self, specification_id: uuid.UUID) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .options(*_task_load_options())
            .where(Task.specification_id == specification_id)
            .order_by(Task.order.asc())
        )
        return list(result.scalars().unique().all())

    async def count_by_specification(self, specification_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count(Task.id)).where(Task.specification_id == specification_id)
        )
        return int(result.scalar_one())

    async def bulk_create(
        self,
        project_id: uuid.UUID,
        specification_id: uuid.UUID,
        task_data_list: list,
    ) -> list[Task]:
        tasks = []
        for data in task_data_list:
            task = Task(
                project_id=project_id,
                specification_id=specification_id,
                order=data["order"],
                title=data["title"],
                description=data["description"],
                task_type=data.get("task_type", "backend"),
                priority=data.get("priority", "medium"),
                status="backlog",
                acceptance_criteria=data.get("acceptance_criteria", []),
                required_tests=data.get("required_tests", []),
                metadata_json=data.get("metadata_json", {}),
            )
            self.session.add(task)
            tasks.append(task)
        await self.session.flush()
        for task in tasks:
            await self.session.refresh(task)
        return tasks

    async def create_dependencies(
        self,
        order_to_id: dict[int, uuid.UUID],
        dependency_pairs: list[tuple[int, int]],
    ) -> None:
        for task_order, dep_order in dependency_pairs:
            if task_order not in order_to_id or dep_order not in order_to_id:
                raise ValueError("Dependency order does not exist in the generated plan")
            edge = TaskDependency(
                task_id=order_to_id[task_order],
                depends_on_task_id=order_to_id[dep_order],
            )
            self.session.add(edge)
        await self.session.flush()

    async def update(self, task: Task, **kwargs) -> Task:
        allowed = {
            "title",
            "description",
            "task_type",
            "priority",
            "status",
            "acceptance_criteria",
            "required_tests",
            "metadata_json",
            "approved_by",
            "approved_at",
        }
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(task, key, value)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def clear_approval(self, task: Task) -> Task:
        task.approved_by = None
        task.approved_at = None
        await self.session.flush()
        await self.session.refresh(task)
        return task

    @staticmethod
    def detect_cycle(items: list[dict]) -> bool:
        in_degree: dict[int, int] = defaultdict(int)
        graph: dict[int, list[int]] = defaultdict(list)
        orders = {item["order"] for item in items}

        for item in items:
            order = item["order"]
            in_degree.setdefault(order, 0)
            for dep in item.get("depends_on_orders", []):
                if dep in orders:
                    graph[dep].append(order)
                    in_degree[order] += 1

        queue = deque(order for order in orders if in_degree[order] == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited != len(orders)
