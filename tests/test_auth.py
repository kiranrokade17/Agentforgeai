import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    payload = {"name": "Alex Developer", "email": "alex@example.com", "password": "Password123!"}
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alex@example.com"
    assert data["name"] == "Alex Developer"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"name": "Jane Doe", "email": "jane@example.com", "password": "Password123!"}
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    reg_payload = {"name": "Sam Smith", "email": "sam@example.com", "password": "Password123!"}
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {"email": "sam@example.com", "password": "Password123!"}
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    reg_payload = {"name": "Dana User", "email": "dana@example.com", "password": "Password123!"}
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {"email": "dana@example.com", "password": "WrongPassword!"}
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    reg_payload = {
        "name": "Taylor Swift",
        "email": "taylor@example.com",
        "password": "Password123!",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await client.post(
        "/api/v1/auth/login", json={"email": "taylor@example.com", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]

    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "taylor@example.com"
