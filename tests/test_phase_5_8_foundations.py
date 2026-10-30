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
async def test_phase_5_8_foundation_endpoints(client):
    token = await get_token(client, "phase58@example.com", "Phase58")
    headers = {"Authorization": f"Bearer {token}"}

    test_run = await client.post(
        "/api/v1/quality/test-runs",
        json={
            "task_id": "11111111-1111-4111-8111-111111111111",
            "command": "pytest -q",
            "status": "passed",
            "exit_code": 0,
            "summary": "Core API contract checks passed",
            "duration_ms": 2500,
        },
        headers=headers,
    )
    assert test_run.status_code == 201, test_run.text
    payload = test_run.json()
    assert payload["status"] == "passed"
    assert payload["command"] == "pytest -q"

    review = await client.post(
        "/api/v1/quality/reviews",
        json={
            "task_id": "11111111-1111-4111-8111-111111111111",
            "summary": "No blocking issues found",
            "status": "approved",
            "findings": [
                {"severity": "low", "title": "Typo in schema description", "file": "app/schemas/foo.py"}
            ],
        },
        headers=headers,
    )
    assert review.status_code == 201, review.text
    review_payload = review.json()
    assert review_payload["status"] == "approved"
    assert review_payload["findings"][0]["severity"] == "low"

    repository = await client.post(
        "/api/v1/repositories",
        json={
            "name": "agentforge-ai",
            "owner": "agentforge",
            "default_branch": "main",
            "provider": "github",
        },
        headers=headers,
    )
    assert repository.status_code == 201, repository.text
    repo_payload = repository.json()
    assert repo_payload["name"] == "agentforge-ai"

    pull_request = await client.post(
        "/api/v1/pull-requests",
        json={
            "repository_id": repo_payload["id"],
            "title": "Add execution policy foundation",
            "head_branch": "feature/phase-5-foundation",
            "base_branch": "main",
            "status": "draft",
        },
        headers=headers,
    )
    assert pull_request.status_code == 201, pull_request.text
    pr_payload = pull_request.json()
    assert pr_payload["title"] == "Add execution policy foundation"

    deployment = await client.post(
        "/api/v1/deployments",
        json={
            "environment": "staging",
            "status": "queued",
            "version": "v1.2.3",
            "notes": "Ready for review",
        },
        headers=headers,
    )
    assert deployment.status_code == 201, deployment.text
    assert deployment.json()["environment"] == "staging"
