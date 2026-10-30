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
async def test_ci_status_sync_and_deployment_gate(client):
    token = await get_token(client, "ci@example.com", "CI")
    headers = {"Authorization": f"Bearer {token}"}

    deployment = await client.post(
        "/api/v1/deployments",
        json={"environment": "staging", "status": "queued", "version": "v1.2.2", "notes": "CI pending"},
        headers=headers,
    )
    assert deployment.status_code == 201, deployment.text
    deployment_id = deployment.json()["id"]

    status = await client.post(
        "/api/v1/ci/status",
        json={
            "deployment_id": deployment_id,
            "workflow": "backend-ci",
            "status": "success",
            "conclusion": "success",
            "branch": "main",
            "run_url": "https://github.com/example/repo/actions/runs/123",
        },
        headers=headers,
    )
    assert status.status_code == 201, status.text
    payload = status.json()
    assert payload["status"] == "success"
    assert payload["conclusion"] == "success"

    gate = await client.post(
        f"/api/v1/deployments/{deployment_id}/approve",
        json={"approved": True, "approver": "ops@example.com"},
        headers=headers,
    )
    assert gate.status_code == 200, gate.text
    assert gate.json()["status"] == "approved"
