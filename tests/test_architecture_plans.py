import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workspace_member import WorkspaceMember
from app.services import architecture_plan_service

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
            "description": "Phase 3 architecture test project",
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


async def generate_plan(client: AsyncClient, headers: dict, project_id: str, spec_id: str):
    return await client.post(
        f"/api/v1/projects/{project_id}/architecture/generate?provider=mock",
        json={"specification_id": spec_id},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_generate_architecture_plan_uses_mock_provider(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "arch_gen@test.com", "ArchGen", "ArchWS", "ArchProj"
    )
    response = await generate_plan(client, headers, project_id, spec_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_id"] == project_id
    assert body["specification_id"] == spec_id
    assert body["version"] == 1
    assert body["status"] == "draft"
    assert body["approved_at"] is None
    assert body["content_json"]["overview"]
    assert body["content_json"]["affected_components"]
    assert body["content_json"]["new_api_endpoints"]


@pytest.mark.asyncio
async def test_architecture_generation_requires_approved_specification(client: AsyncClient):
    headers, _, project_id = await bootstrap_project(
        client,
        "arch_unapproved@test.com",
        "ArchUnapproved",
        "ArchUnapprovedWS",
        "ArchUnapprovedProj",
    )
    specification = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = specification.json()["id"]

    response = await generate_plan(client, headers, project_id, spec_id)
    assert response.status_code == 409, response.text
    assert "approved specification" in response.json()["detail"]


@pytest.mark.asyncio
async def test_architecture_cross_project_specification_is_hidden(client: AsyncClient):
    headers, _, project_id, _ = await bootstrap_approved_spec(
        client, "arch_cross@test.com", "ArchCross", "ArchCrossWS", "ArchCrossProj"
    )
    other_project = await client.post(
        "/api/v1/projects",
        json={
            "workspace_id": (
                await client.get(f"/api/v1/projects/{project_id}", headers=headers)
            ).json()["workspace_id"],
            "name": "Other Project",
        },
        headers=headers,
    )
    assert other_project.status_code == 201, other_project.text
    other_spec = await client.post(
        f"/api/v1/specifications/projects/{other_project.json()['id']}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    other_spec_id = other_spec.json()["id"]
    await client.post(f"/api/v1/specifications/{other_spec_id}/approve", headers=headers)

    response = await generate_plan(client, headers, project_id, other_spec_id)
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_architecture_versioning_and_listing(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "arch_versions@test.com", "ArchVersions", "ArchVersionsWS", "ArchVersionsProj"
    )
    first = await generate_plan(client, headers, project_id, spec_id)
    second = await generate_plan(client, headers, project_id, spec_id)
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["version"] == 2

    listing = await client.get(
        f"/api/v1/projects/{project_id}/architecture?limit=1&offset=0",
        headers=headers,
    )
    assert listing.status_code == 200
    assert [item["version"] for item in listing.json()] == [2]


@pytest.mark.asyncio
async def test_architecture_edit_and_approval_lock(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "arch_edit@test.com", "ArchEdit", "ArchEditWS", "ArchEditProj"
    )
    generated = await generate_plan(client, headers, project_id, spec_id)
    plan = generated.json()
    content = plan["content_json"]
    content["overview"] = "Updated architecture overview for the approved scope."
    content["assumptions"] = ["Updated assumption"]

    updated = await client.patch(
        f"/api/v1/architecture/{plan['id']}",
        json={"title": "Updated architecture", "content_json": content},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Updated architecture"
    assert updated.json()["content_json"]["assumptions"] == ["Updated assumption"]

    approved = await client.post(f"/api/v1/architecture/{plan['id']}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] is not None
    assert approved.json()["approved_at"] is not None

    locked = await client.patch(
        f"/api/v1/architecture/{plan['id']}",
        json={"title": "Should fail"},
        headers=headers,
    )
    assert locked.status_code == 409, locked.text

    reject_approved = await client.post(
        f"/api/v1/architecture/{plan['id']}/reject", headers=headers
    )
    assert reject_approved.status_code == 409, reject_approved.text


@pytest.mark.asyncio
async def test_architecture_reject_lifecycle(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "arch_reject@test.com", "ArchReject", "ArchRejectWS", "ArchRejectProj"
    )
    plan = (await generate_plan(client, headers, project_id, spec_id)).json()

    rejected = await client.post(f"/api/v1/architecture/{plan['id']}/reject", headers=headers)
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    duplicate = await client.post(f"/api/v1/architecture/{plan['id']}/reject", headers=headers)
    assert duplicate.status_code == 409

    approve = await client.post(f"/api/v1/architecture/{plan['id']}/approve", headers=headers)
    assert approve.status_code == 409


@pytest.mark.asyncio
async def test_architecture_rbac_for_developer_and_viewer(
    client: AsyncClient,
    db_session: AsyncSession,
):
    headers, workspace_id, project_id, spec_id = await bootstrap_approved_spec(
        client, "arch_rbac_owner@test.com", "ArchRbacOwner", "ArchRbacWS", "ArchRbacProj"
    )
    developer = await add_member(
        client, db_session, workspace_id, "arch_rbac_dev@test.com", "ArchRbacDev", "developer"
    )
    viewer = await add_member(
        client, db_session, workspace_id, "arch_rbac_viewer@test.com", "ArchRbacViewer", "viewer"
    )

    developer_generate = await generate_plan(client, developer, project_id, spec_id)
    assert developer_generate.status_code == 201, developer_generate.text
    plan_id = developer_generate.json()["id"]

    developer_approve = await client.post(
        f"/api/v1/architecture/{plan_id}/approve", headers=developer
    )
    assert developer_approve.status_code == 403

    viewer_generate = await generate_plan(client, viewer, project_id, spec_id)
    assert viewer_generate.status_code == 403

    viewer_get = await client.get(f"/api/v1/architecture/{plan_id}", headers=viewer)
    assert viewer_get.status_code == 200


@pytest.mark.asyncio
async def test_architecture_workspace_isolation(client: AsyncClient):
    headers_a, _, project_id_a, spec_id_a = await bootstrap_approved_spec(
        client, "arch_iso_a@test.com", "ArchIsoA", "ArchIsoWS_A", "ArchIsoProjA"
    )
    plan = (await generate_plan(client, headers_a, project_id_a, spec_id_a)).json()

    token_b = await register_and_login(client, "arch_iso_b@test.com", "ArchIsoB")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    assert (
        await client.get(f"/api/v1/architecture/{plan['id']}", headers=headers_b)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/projects/{project_id_a}/architecture", headers=headers_b)
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/architecture/{plan['id']}/approve", headers=headers_b)
    ).status_code == 403


@pytest.mark.asyncio
async def test_architecture_archived_project_generation_is_rejected(client: AsyncClient):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "arch_archived@test.com", "ArchArchived", "ArchArchivedWS", "ArchArchivedProj"
    )
    update = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "archived"},
        headers=headers,
    )
    assert update.status_code == 200, update.text

    response = await generate_plan(client, headers, project_id, spec_id)
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_architecture_llm_failure_is_mapped_to_safe_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    headers, _, project_id, spec_id = await bootstrap_approved_spec(
        client, "arch_failure@test.com", "ArchFailure", "ArchFailureWS", "ArchFailureProj"
    )

    class FailingProvider:
        async def generate_architecture_plan(self, *args, **kwargs):
            raise RuntimeError("upstream secret detail that must not leak")

    monkeypatch.setattr(
        architecture_plan_service,
        "get_llm_provider",
        lambda _name: FailingProvider(),
    )

    response = await generate_plan(client, headers, project_id, spec_id)
    assert response.status_code == 502, response.text
    assert "upstream secret detail" not in response.text
    assert "valid architecture plan" in response.json()["detail"]
