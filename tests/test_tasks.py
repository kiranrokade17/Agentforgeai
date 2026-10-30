import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workspace_member import WorkspaceMember
from app.schemas.planning import TaskItem, TaskPlanContent
from app.services import task_service

SAMPLE_REQUIREMENT = (
    "Build a SaaS task management tool with workspaces, boards, cards, "
    "real-time collaboration, and subscription billing."
)


async def register_and_login(client: AsyncClient, email: str, name: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": "Password123!"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def bootstrap_project(
    client: AsyncClient, email: str, name: str, workspace_name: str, project_name: str
):
    token = await register_and_login(client, email, name)
    headers = {"Authorization": f"Bearer {token}"}
    workspace = await client.post(
        "/api/v1/workspaces", json={"name": workspace_name}, headers=headers
    )
    assert workspace.status_code == 201, workspace.text
    workspace_id = workspace.json()["id"]
    project = await client.post(
        "/api/v1/projects",
        json={
            "workspace_id": workspace_id,
            "name": project_name,
            "description": "Phase 3 task planning test project",
        },
        headers=headers,
    )
    assert project.status_code == 201, project.text
    return headers, workspace_id, project.json()["id"]


async def bootstrap_approved_spec(
    client: AsyncClient, email: str, name: str, workspace_name: str, project_name: str
):
    headers, workspace_id, project_id = await bootstrap_project(
        client, email, name, workspace_name, project_name
    )
    specification = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    assert specification.status_code == 201, specification.text
    specification_id = specification.json()["id"]
    approved = await client.post(
        f"/api/v1/specifications/{specification_id}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    return headers, workspace_id, project_id, specification_id


async def add_member(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_id: str,
    email: str,
    name: str,
    role: str,
):
    token = await register_and_login(client, email, name)
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    db_session.add(
        WorkspaceMember(
            workspace_id=uuid.UUID(workspace_id),
            user_id=uuid.UUID(me.json()["id"]),
            role=role,
        )
    )
    await db_session.flush()
    return headers


async def generate_tasks(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    spec_id: str,
    architecture_plan_id: str | None = None,
):
    payload = {"specification_id": spec_id}
    if architecture_plan_id:
        payload["architecture_plan_id"] = architecture_plan_id
    return await client.post(
        f"/api/v1/projects/{project_id}/tasks/generate?provider=mock",
        json=payload,
        headers=headers,
    )


def plan_with(tasks: list[TaskItem]) -> TaskPlanContent:
    return TaskPlanContent(
        planning_summary="Validated task plan for dependency handling tests.",
        tasks=tasks,
    )


@pytest.mark.asyncio
async def test_generate_task_plan_persists_tasks_and_dependencies(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "task_gen@test.com", "TaskGen", "TaskWS", "TaskProj"
    )
    response = await generate_tasks(client, headers, project_id, spec_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["planning_summary"]
    assert len(body["tasks"]) == 5
    assert [task["order"] for task in body["tasks"]] == [1, 2, 3, 4, 5]
    assert body["tasks"][0]["status"] == "backlog"
    assert body["tasks"][0]["approved_at"] is None
    assert body["tasks"][1]["depends_on"][0]["order"] == 1
    assert [dep["order"] for dep in body["tasks"][2]["depends_on"]] == [1, 2]
    assert [dep["order"] for dep in body["tasks"][3]["depends_on"]] == [1, 2, 3]

    listing = await client.get(f"/api/v1/projects/{project_id}/tasks", headers=headers)
    assert listing.status_code == 200
    assert [task["order"] for task in listing.json()] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_task_generation_requires_approved_specification(client: AsyncClient):
    headers, _, project_id = await bootstrap_project(
        client,
        "task_unapproved@test.com",
        "TaskUnapproved",
        "TaskUnapprovedWS",
        "TaskUnapprovedProj",
    )
    specification = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = specification.json()["id"]

    response = await generate_tasks(client, headers, project_id, spec_id)
    assert response.status_code == 409, response.text
    assert "approved specification" in response.json()["detail"]


@pytest.mark.asyncio
async def test_task_plan_can_only_be_generated_once_per_specification(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "task_duplicate@test.com", "TaskDuplicate", "TaskDuplicateWS", "TaskDuplicateProj"
    )
    first = await generate_tasks(client, headers, project_id, spec_id)
    assert first.status_code == 201, first.text

    second = await generate_tasks(client, headers, project_id, spec_id)
    assert second.status_code == 409, second.text
    assert "already exists" in second.json()["detail"]


@pytest.mark.asyncio
async def test_task_generation_uses_only_approved_architecture_from_same_spec(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "task_arch@test.com", "TaskArch", "TaskArchWS", "TaskArchProj"
    )
    architecture = await client.post(
        f"/api/v1/projects/{project_id}/architecture/generate?provider=mock",
        json={"specification_id": spec_id},
        headers=headers,
    )
    assert architecture.status_code == 201, architecture.text
    plan_id = architecture.json()["id"]

    unapproved = await generate_tasks(
        client, headers, project_id, spec_id, architecture_plan_id=plan_id
    )
    assert unapproved.status_code == 409, unapproved.text

    await client.post(f"/api/v1/architecture/{plan_id}/approve", headers=headers)
    approved = await generate_tasks(
        client, headers, project_id, spec_id, architecture_plan_id=plan_id
    )
    assert approved.status_code == 201, approved.text


@pytest.mark.asyncio
async def test_task_rbac_editing_and_approval(
    client: AsyncClient,
    db_session: AsyncSession,
):
    headers, workspace_id, project_id, spec_id = await bootstrap_approved_spec(
        client, "task_rbac_owner@test.com", "TaskRbacOwner", "TaskRbacWS", "TaskRbacProj"
    )
    generated = await generate_tasks(client, headers, project_id, spec_id)
    task_id = generated.json()["tasks"][0]["id"]

    developer = await add_member(
        client, db_session, workspace_id, "task_rbac_dev@test.com", "TaskRbacDev", "developer"
    )
    viewer = await add_member(
        client, db_session, workspace_id, "task_rbac_viewer@test.com", "TaskRbacViewer", "viewer"
    )

    developer_edit = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Developer-edited task"},
        headers=developer,
    )
    assert developer_edit.status_code == 200, developer_edit.text
    assert developer_edit.json()["title"] == "Developer-edited task"

    developer_approve = await client.post(f"/api/v1/tasks/{task_id}/approve", headers=developer)
    assert developer_approve.status_code == 403

    viewer_edit = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Viewer edit"},
        headers=viewer,
    )
    assert viewer_edit.status_code == 403

    viewer_list = await client.get(f"/api/v1/projects/{project_id}/tasks", headers=viewer)
    assert viewer_list.status_code == 200

    approved = await client.post(f"/api/v1/tasks/{task_id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved_at"] is not None

    duplicate_approve = await client.post(f"/api/v1/tasks/{task_id}/approve", headers=headers)
    assert duplicate_approve.status_code == 409

    edited = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"description": "Edited after approval and requires review again."},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["approved_at"] is None
    assert edited.json()["approved_by"] is None


@pytest.mark.asyncio
async def test_task_list_filters_and_status_update(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "task_filters@test.com", "TaskFilters", "TaskFiltersWS", "TaskFiltersProj"
    )
    generated = await generate_tasks(client, headers, project_id, spec_id)
    backend_task = next(
        task for task in generated.json()["tasks"] if task["task_type"] == "backend"
    )
    updated = await client.patch(
        f"/api/v1/tasks/{backend_task['id']}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text

    filtered = await client.get(
        f"/api/v1/projects/{project_id}/tasks?status=in_progress&type=backend",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert [task["id"] for task in filtered.json()] == [backend_task["id"]]

    invalid_filter = await client.get(
        f"/api/v1/projects/{project_id}/tasks?status=unknown", headers=headers
    )
    assert invalid_filter.status_code == 422


@pytest.mark.asyncio
async def test_task_workspace_isolation(client: AsyncClient):
    headers_a, _, project_id_a, spec_id_a = await bootstrap_approved_spec(
        client, "task_iso_a@test.com", "TaskIsoA", "TaskIsoWS_A", "TaskIsoProjA"
    )
    generated = await generate_tasks(client, headers_a, project_id_a, spec_id_a)
    task_id = generated.json()["tasks"][0]["id"]

    token_b = await register_and_login(client, "task_iso_b@test.com", "TaskIsoB")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    assert (await client.get(f"/api/v1/tasks/{task_id}", headers=headers_b)).status_code == 403
    assert (
        await client.get(f"/api/v1/projects/{project_id_a}/tasks", headers=headers_b)
    ).status_code == 403
    assert (
        await client.patch(f"/api/v1/tasks/{task_id}", json={"title": "Denied"}, headers=headers_b)
    ).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_items", "expected_status"),
    [
        (
            [
                TaskItem(
                    order=1,
                    title="First task",
                    description="First task description long enough.",
                    depends_on_orders=[2],
                ),
                TaskItem(
                    order=2,
                    title="Second task",
                    description="Second task description long enough.",
                    depends_on_orders=[1],
                ),
            ],
            409,
        ),
        (
            [
                TaskItem(
                    order=1,
                    title="Self dependent task",
                    description="Task cannot depend on itself in a valid plan.",
                    depends_on_orders=[1],
                )
            ],
            409,
        ),
        (
            [
                TaskItem(
                    order=1,
                    title="Unknown dependency task",
                    description="Dependency refers to an order that does not exist.",
                    depends_on_orders=[2],
                )
            ],
            422,
        ),
        (
            [
                TaskItem(
                    order=1,
                    title="Later dependency task",
                    description="A non-cyclic dependency points to a later task.",
                    depends_on_orders=[2],
                ),
                TaskItem(
                    order=2,
                    title="Independent task",
                    description="This task has no dependencies of its own.",
                ),
            ],
            422,
        ),
    ],
)
async def test_invalid_dependency_plans_are_rejected_without_writes(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    task_items: list[TaskItem],
    expected_status: int,
):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client,
        f"task_deps_{expected_status}_{uuid.uuid4().hex[:8]}@test.com",
        "TaskDeps",
        f"TaskDepsWS{uuid.uuid4().hex[:6]}",
        f"TaskDepsProj{uuid.uuid4().hex[:6]}",
    )
    plan = plan_with(task_items)

    class InvalidPlanProvider:
        async def generate_tasks(self, *args, **kwargs):
            return plan

    monkeypatch.setattr(task_service, "get_llm_provider", lambda _name: InvalidPlanProvider())

    response = await generate_tasks(client, headers, project_id, spec_id)
    assert response.status_code == expected_status, response.text

    listing = await client.get(f"/api/v1/projects/{project_id}/tasks", headers=headers)
    assert listing.status_code == 200
    assert listing.json() == []


@pytest.mark.asyncio
async def test_task_generation_llm_failure_is_mapped_to_safe_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "task_failure@test.com", "TaskFailure", "TaskFailureWS", "TaskFailureProj"
    )

    class FailingProvider:
        async def generate_tasks(self, *args, **kwargs):
            raise RuntimeError("upstream secret detail that must not leak")

    monkeypatch.setattr(task_service, "get_llm_provider", lambda _name: FailingProvider())

    response = await generate_tasks(client, headers, project_id, spec_id)
    assert response.status_code == 502, response.text
    assert "upstream secret detail" not in response.text
    assert "valid task plan" in response.json()["detail"]


@pytest.mark.asyncio
async def test_task_generation_for_archived_project_is_rejected(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "task_archived@test.com", "TaskArchived", "TaskArchivedWS", "TaskArchivedProj"
    )
    update = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "archived"},
        headers=headers,
    )
    assert update.status_code == 200, update.text

    response = await generate_tasks(client, headers, project_id, spec_id)
    assert response.status_code == 409, response.text
