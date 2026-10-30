import pytest
from httpx import AsyncClient


async def get_token(client: AsyncClient, email: str, name: str) -> str:
    await client.post(
        "/api/v1/auth/register", json={"name": name, "email": email, "password": "Password123!"}
    )
    login_res = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_project_crud_and_workspace_isolation(client: AsyncClient):
    # User A registers and creates a project
    token_a = await get_token(client, "alice@example.com", "Alice")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    ws_res = await client.post("/api/v1/workspaces", json={"name": "Alice Corp"}, headers=headers_a)
    assert ws_res.status_code == 201
    workspace_a_id = ws_res.json()["id"]

    # Create project in Alice's workspace
    proj_payload = {
        "workspace_id": workspace_a_id,
        "name": "E-Commerce Core",
        "description": "High throughput checkout service",
        "stack_json": {"backend": "fastapi", "database": "postgresql"},
    }
    create_proj_res = await client.post("/api/v1/projects", json=proj_payload, headers=headers_a)
    assert create_proj_res.status_code == 201
    project_a = create_proj_res.json()
    assert project_a["name"] == "E-Commerce Core"
    project_a_id = project_a["id"]

    # User B registers
    token_b = await get_token(client, "bob@example.com", "Bob")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B attempts to access Alice's project -> MUST BE FORBIDDEN (403)
    unauthorized_get = await client.get(f"/api/v1/projects/{project_a_id}", headers=headers_b)
    assert unauthorized_get.status_code == 403

    # User B attempts to list projects in Alice's workspace -> MUST BE FORBIDDEN (403)
    unauthorized_list = await client.get(
        f"/api/v1/projects?workspace_id={workspace_a_id}", headers=headers_b
    )
    assert unauthorized_list.status_code == 403

    # User B attempts to create project in Alice's workspace -> MUST BE FORBIDDEN (403)
    unauthorized_create = await client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_a_id, "name": "Intruder Project"},
        headers=headers_b,
    )
    assert unauthorized_create.status_code == 403

    # Alice can update her project
    update_res = await client.patch(
        f"/api/v1/projects/{project_a_id}",
        json={"description": "Updated checkout service with payment integration"},
        headers=headers_a,
    )
    assert update_res.status_code == 200
    assert update_res.json()["description"] == "Updated checkout service with payment integration"
