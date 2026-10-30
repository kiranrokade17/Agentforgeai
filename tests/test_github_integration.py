import hashlib
import hmac

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
async def test_github_webhook_verification_and_pr_approval(client):
    token = await get_token(client, "github@example.com", "Github")
    headers = {"Authorization": f"Bearer {token}"}

    repo = await client.post(
        "/api/v1/repositories",
        json={"name": "phase6-demo", "owner": "agentforge", "default_branch": "main"},
        headers=headers,
    )
    assert repo.status_code == 201, repo.text
    repository_id = repo.json()["id"]

    pr = await client.post(
        "/api/v1/pull-requests",
        json={
            "repository_id": repository_id,
            "title": "Phase 6 GitHub integration",
            "head_branch": "feature/phase-6",
            "base_branch": "main",
        },
        headers=headers,
    )
    assert pr.status_code == 201, pr.text
    assert pr.json()["status"] == "draft"

    repos = await client.get("/api/v1/repositories", headers=headers)
    assert repos.status_code == 200, repos.text
    assert any(item["name"] == "phase6-demo" for item in repos.json())

    pr_id = pr.json()["id"]
    approved = await client.post(f"/api/v1/pull-requests/{pr_id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    pr_list = await client.get("/api/v1/pull-requests", headers=headers)
    assert pr_list.status_code == 200, pr_list.text
    assert any(item["id"] == pr_id and item["status"] == "approved" for item in pr_list.json())

    payload = b'{"action":"opened","repository":{"full_name":"agentforge/phase6-demo"}}'
    secret = "dev_github_webhook_secret_32_chars"
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    webhook = await client.post(
        "/api/v1/webhooks/github",
        content=payload,
        headers={
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert webhook.status_code == 200, webhook.text
    assert webhook.json()["ok"] is True

    bad_webhook = await client.post(
        "/api/v1/webhooks/github",
        content=payload,
        headers={
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "00000000-0000-0000-0000-000000000002",
        },
    )
    assert bad_webhook.status_code == 401, bad_webhook.text
