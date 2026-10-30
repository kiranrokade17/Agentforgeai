from typing import Any

from app.agents.base import BaseLLMProvider
from app.schemas.planning import (
    AffectedComponent,
    ArchitecturePlanContent,
    TaskItem,
    TaskPlanContent,
)
from app.schemas.specification import (
    FunctionalRequirement,
    NonFunctionalRequirement,
    SRSContent,
    UserStory,
)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic offline provider for CI and unit tests – never calls an external API."""

    async def generate_srs(
        self, user_requirement: str, project_context: dict[str, Any] | None = None
    ) -> SRSContent:
        return SRSContent(
            project_summary=f"Automated specification generated from requirement: '{user_requirement[:60]}...'",
            functional_requirements=[
                FunctionalRequirement(
                    id="FR-01",
                    title="Core Functional Workflow",
                    description="The system must implement the requested behavior with robust error handling.",
                    priority="critical",
                    acceptance_criteria=[
                        "Valid input payloads process successfully and return expected state",
                        "Invalid or malformed inputs return RFC-7807 compliant error responses",
                        "State changes are transactionally persisted to PostgreSQL",
                    ],
                ),
                FunctionalRequirement(
                    id="FR-02",
                    title="Audit and Observability",
                    description="Execution transitions and errors must be recorded to audit logs.",
                    priority="high",
                    acceptance_criteria=[
                        "Every operation generates a structured event with timestamp",
                        "Security-sensitive fields are sanitized before logging",
                    ],
                ),
            ],
            non_functional_requirements=[
                NonFunctionalRequirement(
                    category="Security",
                    requirement="Enforce multi-tenant workspace isolation and token authentication",
                    metric="Zero cross-tenant data leakage",
                ),
                NonFunctionalRequirement(
                    category="Performance",
                    requirement="API endpoints should respond within acceptable p95 latencies",
                    metric="p95 < 200ms",
                ),
            ],
            user_stories=[
                UserStory(
                    id="US-01",
                    as_a="Software Engineer",
                    i_want="a reliable API endpoint",
                    so_that="I can automate software delivery workflows",
                    acceptance_criteria=[
                        "HTTP POST returns 201 Created on valid input",
                        "Token claims are verified on every request",
                    ],
                )
            ],
            assumptions=[
                "Client communicates using standard JSON payloads over HTTPS",
                "PostgreSQL 16 and Redis are available for persistence and task queues",
            ],
            risks=[
                "High request volume could strain connection pools if concurrency limits are not tuned",
                "Network partitions between API server and external providers",
            ],
            open_questions=[
                "Should rate limits be enforced per user or per workspace quota?",
                "Are webhooks required for asynchronous state notifications?",
            ],
        )

    async def generate_architecture_plan(
        self,
        srs: SRSContent,
        project_context: dict[str, Any] | None = None,
        repo_context: str | None = None,
    ) -> ArchitecturePlanContent:
        return ArchitecturePlanContent(
            overview=(
                "The system will follow a layered FastAPI modular-monolith architecture with "
                "a PostgreSQL persistence layer, Redis for background queues, and a Next.js "
                "frontend consuming versioned REST APIs."
            ),
            affected_components=[
                AffectedComponent(
                    name="Task Management API",
                    layer="backend",
                    change_type="create",
                    description="New FastAPI router and service layer for task CRUD operations",
                ),
                AffectedComponent(
                    name="tasks table",
                    layer="database",
                    change_type="create",
                    description="New Alembic migration to create the tasks and task_dependencies tables",
                ),
                AffectedComponent(
                    name="Task Board UI",
                    layer="frontend",
                    change_type="create",
                    description="Next.js page with Kanban-style task board using shadcn/ui components",
                ),
            ],
            new_api_endpoints=[
                "POST /api/v1/projects/{project_id}/tasks/generate",
                "GET  /api/v1/projects/{project_id}/tasks",
                "GET  /api/v1/tasks/{task_id}",
                "PATCH /api/v1/tasks/{task_id}",
            ],
            database_changes=[
                "CREATE TABLE tasks (id, project_id, specification_id, order, title, description, task_type, priority, status, ...)",
                "CREATE TABLE task_dependencies (task_id, depends_on_task_id)",
            ],
            external_dependencies=["sqlalchemy", "alembic", "pydantic"],
            security_considerations=[
                "All task endpoints validate workspace membership before proceeding",
                "Task status transitions are gated by role: only owners/admins may mark tasks done",
            ],
            assumptions=["One specification can have at most one active task plan at a time"],
            open_questions=["Should task re-planning create new tasks or update existing ones?"],
        )

    async def generate_tasks(
        self,
        srs: SRSContent,
        architecture: ArchitecturePlanContent | None = None,
        project_context: dict[str, Any] | None = None,
        additional_context: str | None = None,
    ) -> TaskPlanContent:
        return TaskPlanContent(
            planning_summary=(
                "Tasks are ordered from foundational database work up through service "
                "layer, API routes, and finally frontend integration. Each task has "
                "explicit acceptance criteria derived from the approved SRS."
            ),
            tasks=[
                TaskItem(
                    order=1,
                    title="Database schema – tasks and task_dependencies tables",
                    description=(
                        "Write and apply an Alembic migration creating the `tasks` table "
                        "(id, project_id, specification_id, order, title, description, task_type, "
                        "priority, status, acceptance_criteria, required_tests, metadata_json) "
                        "and the `task_dependencies` association table."
                    ),
                    task_type="database",
                    priority="critical",
                    acceptance_criteria=[
                        "Alembic migration applies cleanly on a fresh PostgreSQL 16 database",
                        "All CHECK constraints are enforced for task_type, priority, and status",
                        "Foreign key cascade-delete works: deleting a project removes all tasks",
                    ],
                    required_tests=[
                        "Alembic migration upgrade/downgrade round-trip test",
                        "Constraint violation unit tests for invalid enum values",
                    ],
                    depends_on_orders=[],
                    metadata_json={"estimated_hours": 2},
                ),
                TaskItem(
                    order=2,
                    title="Task ORM model and repository",
                    description=(
                        "Implement the SQLAlchemy Task and TaskDependency ORM models, "
                        "the TaskRepository (CRUD: create, get_by_id, list_by_project, "
                        "list_by_specification, update, bulk_create), and circular-dependency "
                        "detection utility using topological sort (Kahn's algorithm)."
                    ),
                    task_type="backend",
                    priority="critical",
                    acceptance_criteria=[
                        "TaskRepository.create persists a task and returns it with a valid UUID",
                        "Circular dependency detection raises ValueError for direct and transitive cycles",
                        "list_by_project returns tasks ordered by task.order ascending",
                    ],
                    required_tests=[
                        "Unit tests for TaskRepository CRUD operations against in-memory SQLite",
                        "Unit tests for circular dependency detection covering direct, transitive, and self-reference cycles",
                    ],
                    depends_on_orders=[1],
                    metadata_json={"estimated_hours": 4},
                ),
                TaskItem(
                    order=3,
                    title="Task planning service and LLM integration",
                    description=(
                        "Implement TaskService.generate_plan() which: fetches the approved specification, "
                        "optionally fetches an approved architecture plan, calls the configured LLM provider "
                        "via generate_tasks(), validates output, checks for circular dependencies, "
                        "bulk-creates Task rows and TaskDependency edges in a single transaction."
                    ),
                    task_type="backend",
                    priority="critical",
                    acceptance_criteria=[
                        "Calling generate_plan on an approved spec creates at least 1 task in the database",
                        "Service rejects planning if specification.status != 'approved'",
                        "Circular dependency in LLM output raises 409 Conflict before any DB write",
                    ],
                    required_tests=[
                        "Integration test using MockLLMProvider that verifies DB state after generate_plan",
                        "Unit test for rejection when specification is not approved",
                        "Unit test for circular dependency rejection",
                    ],
                    depends_on_orders=[1, 2],
                    metadata_json={"estimated_hours": 6},
                ),
                TaskItem(
                    order=4,
                    title="Task REST API routes",
                    description=(
                        "Implement FastAPI router with endpoints: "
                        "POST /projects/{project_id}/tasks/generate (generate task plan from approved spec), "
                        "GET /projects/{project_id}/tasks (list tasks, filterable by status/type), "
                        "GET /tasks/{task_id} (get single task), "
                        "PATCH /tasks/{task_id} (update title, description, priority, status, acceptance_criteria). "
                        "All endpoints enforce workspace RBAC."
                    ),
                    task_type="backend",
                    priority="high",
                    acceptance_criteria=[
                        "POST generate returns 201 with full task list",
                        "PATCH status to 'done' succeeds for owner/admin; 403 for viewer",
                        "GET list returns tasks in order ascending",
                    ],
                    required_tests=[
                        "Integration tests for all 4 endpoints using MockLLMProvider",
                        "RBAC isolation test: user B cannot access user A's tasks",
                    ],
                    depends_on_orders=[1, 2, 3],
                    metadata_json={"estimated_hours": 5},
                ),
                TaskItem(
                    order=5,
                    title="Architecture plan generation endpoint",
                    description=(
                        "Implement ArchitecturePlanService.generate(), get(), update(), and approve(). "
                        "Add FastAPI router with: "
                        "POST /projects/{project_id}/architecture/generate, "
                        "GET /projects/{project_id}/architecture, "
                        "GET /architecture/{plan_id}, "
                        "PATCH /architecture/{plan_id}, "
                        "POST /architecture/{plan_id}/approve."
                    ),
                    task_type="backend",
                    priority="high",
                    acceptance_criteria=[
                        "POST generate returns 201 with ArchitecturePlanContent",
                        "Only owners/admins may approve; 403 for developer/viewer",
                        "Approved plan is locked from further editing (409 on PATCH)",
                    ],
                    required_tests=[
                        "Integration tests for generate, approve, and edit-lock using MockLLMProvider",
                        "Workspace isolation test for architecture plan endpoints",
                    ],
                    depends_on_orders=[1],
                    metadata_json={"estimated_hours": 5},
                ),
            ],
        )
