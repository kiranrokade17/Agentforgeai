import pytest


async def get_token(client, email: str, name: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_deployment_and_analytics_summary(client):
    token = await get_token(client, "analytics@example.com", "Analytics")
    headers = {"Authorization": f"Bearer {token}"}

    dep1 = await client.post(
        "/api/v1/deployments",
        json={"environment": "staging", "status": "succeeded", "version": "v1.2.0", "notes": "Ready"},
        headers=headers,
    )
    assert dep1.status_code == 201, dep1.text

    dep2 = await client.post(
        "/api/v1/deployments",
        json={"environment": "production", "status": "queued", "version": "v1.2.1", "notes": "Awaiting approval"},
        headers=headers,
    )
    assert dep2.status_code == 201, dep2.text

    deployments = await client.get("/api/v1/deployments", headers=headers)
    assert deployments.status_code == 200, deployments.text
    assert len(deployments.json()) >= 2

    summary = await client.get("/api/v1/analytics/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    payload = summary.json()
    assert payload["deployments_total"] >= 2
    assert payload["successful_deployments"] >= 1
    assert payload["status_breakdown"]["succeeded"] >= 1
