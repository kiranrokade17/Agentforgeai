import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str, name: str = "Test User") -> str:
    await client.post(
        "/api/v1/auth/register", json={"name": name, "email": email, "password": "Password123!"}
    )
    login_res = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_create_and_list_workspaces(client: AsyncClient):
    token = await get_auth_token(client, "workspace_user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # List initial workspaces (user gets a personal workspace created on registration)
    initial_list = await client.get("/api/v1/workspaces", headers=headers)
    assert initial_list.status_code == 200
    assert len(initial_list.json()) >= 1

    # Create a new organization workspace
    create_res = await client.post(
        "/api/v1/workspaces", json={"name": "Engineering Team"}, headers=headers
    )
    assert create_res.status_code == 201
    created_ws = create_res.json()
    assert created_ws["name"] == "Engineering Team"
    assert "id" in created_ws

    # Verify new workspace appears in the list
    updated_list = await client.get("/api/v1/workspaces", headers=headers)
    assert updated_list.status_code == 200
    names = [w["name"] for w in updated_list.json()]
    assert "Engineering Team" in names
