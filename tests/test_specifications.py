"""
Phase 2 – Requirement Analyzer: integration tests.
Uses MockLLMProvider (no real API calls) to exercise all specification endpoints.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workspace_member import WorkspaceMember
from app.services import specification_service

# ── Helpers ──────────────────────────────────────────────────────────────────


async def register_and_login(client: AsyncClient, email: str, name: str) -> str:
    await client.post(
        "/api/v1/auth/register", json={"name": name, "email": email, "password": "Password123!"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    return resp.json()["access_token"]


async def bootstrap(client: AsyncClient, email: str, name: str, ws_name: str, proj_name: str):
    """Return (headers, workspace_id, project_id) for a fresh owner user."""
    token = await register_and_login(client, email, name)
    headers = {"Authorization": f"Bearer {token}"}
    ws = await client.post("/api/v1/workspaces", json={"name": ws_name}, headers=headers)
    assert ws.status_code == 201, ws.text
    ws_id = ws.json()["id"]
    proj = await client.post(
        "/api/v1/projects",
        json={"workspace_id": ws_id, "name": proj_name, "description": "Phase 2 test project"},
        headers=headers,
    )
    assert proj.status_code == 201, proj.text
    return headers, ws_id, proj.json()["id"]


SAMPLE_REQUIREMENT = (
    "Build a SaaS task management tool with workspaces, boards, cards, "
    "real-time collaboration via websockets, and Stripe subscription billing."
)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_specification_uses_mock_provider(client: AsyncClient):
    """Generate returns 201 with a valid SRS using the mock provider."""
    headers, _, project_id = await bootstrap(
        client, "spec_gen1@test.com", "SpecGen1", "GenWS1", "ProjGen1"
    )
    resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert "project_id" in body
    assert "content_json" in body
    srs = body["content_json"]
    assert "project_summary" in srs
    assert isinstance(srs["functional_requirements"], list)
    assert isinstance(srs["user_stories"], list)
    assert isinstance(srs["non_functional_requirements"], list)


@pytest.mark.asyncio
async def test_generate_versioning_increments(client: AsyncClient):
    """Each new generate call for the same project increments the version."""
    headers, _, project_id = await bootstrap(
        client, "spec_ver@test.com", "SpecVer", "VerWS", "ProjVer"
    )
    payload = {"user_requirement": SAMPLE_REQUIREMENT}
    r1 = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json=payload,
        headers=headers,
    )
    r2 = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json=payload,
        headers=headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


@pytest.mark.asyncio
async def test_list_specifications_for_project(client: AsyncClient):
    """List returns all generated specifications, newest first."""
    headers, _, project_id = await bootstrap(
        client, "spec_list@test.com", "SpecList", "ListWS", "ProjList"
    )
    payload = {"user_requirement": SAMPLE_REQUIREMENT}
    for _ in range(3):
        r = await client.post(
            f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
            json=payload,
            headers=headers,
        )
        assert r.status_code == 201

    list_resp = await client.get(f"/api/v1/specifications/projects/{project_id}", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 3
    versions = [i["version"] for i in items]
    assert versions == sorted(versions, reverse=True)


@pytest.mark.asyncio
async def test_get_specification_by_id(client: AsyncClient):
    """Can retrieve a specification by its ID."""
    headers, _, project_id = await bootstrap(
        client, "spec_get@test.com", "SpecGet", "GetWS", "ProjGet"
    )
    gen_resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = gen_resp.json()["id"]
    get_resp = await client.get(f"/api/v1/specifications/{spec_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == spec_id


@pytest.mark.asyncio
async def test_update_draft_specification(client: AsyncClient):
    """Can edit title of a draft specification."""
    headers, _, project_id = await bootstrap(
        client, "spec_upd@test.com", "SpecUpd", "UpdWS", "ProjUpd"
    )
    gen_resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = gen_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/specifications/{spec_id}", json={"title": "My Custom SRS Title"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "My Custom SRS Title"


@pytest.mark.asyncio
async def test_approve_specification_human_gate(client: AsyncClient):
    """Owner can approve a draft; status transitions to 'approved'."""
    headers, _, project_id = await bootstrap(
        client, "spec_appr@test.com", "SpecAppr", "ApprWS", "ProjAppr"
    )
    gen_resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    assert gen_resp.status_code == 201
    spec_id = gen_resp.json()["id"]

    appr_resp = await client.post(f"/api/v1/specifications/{spec_id}/approve", headers=headers)
    assert appr_resp.status_code == 200
    body = appr_resp.json()
    assert body["status"] == "approved"
    assert body["approved_by"] is not None
    assert body["approved_at"] is not None


@pytest.mark.asyncio
async def test_cannot_edit_approved_specification(client: AsyncClient):
    """Editing an approved specification returns 409 Conflict."""
    headers, _, project_id = await bootstrap(
        client, "spec_lock@test.com", "SpecLock", "LockWS", "ProjLock"
    )
    gen_resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = gen_resp.json()["id"]
    await client.post(f"/api/v1/specifications/{spec_id}/approve", headers=headers)

    patch_resp = await client.patch(
        f"/api/v1/specifications/{spec_id}", json={"title": "Should be blocked"}, headers=headers
    )
    assert patch_resp.status_code == 409


@pytest.mark.asyncio
async def test_double_approve_returns_409(client: AsyncClient):
    """Approving an already-approved spec returns 409."""
    headers, _, project_id = await bootstrap(
        client, "spec_dbl@test.com", "SpecDbl", "DblWS", "ProjDbl"
    )
    gen_resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = gen_resp.json()["id"]
    await client.post(f"/api/v1/specifications/{spec_id}/approve", headers=headers)
    second = await client.post(f"/api/v1/specifications/{spec_id}/approve", headers=headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_workspace_isolation_for_specifications(client: AsyncClient):
    """User B cannot access User A's specifications."""
    headers_a, _, project_id_a = await bootstrap(
        client, "spec_iso_a@test.com", "IsoA", "IsoWS_A", "ProjIsoA"
    )
    gen_resp = await client.post(
        f"/api/v1/specifications/projects/{project_id_a}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers_a,
    )
    spec_id_a = gen_resp.json()["id"]

    # Register user B with their own workspace
    token_b = await register_and_login(client, "spec_iso_b@test.com", "IsoB")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # B cannot fetch A's spec
    get_resp = await client.get(f"/api/v1/specifications/{spec_id_a}", headers=headers_b)
    assert get_resp.status_code == 403

    # B cannot approve A's spec
    appr_resp = await client.post(f"/api/v1/specifications/{spec_id_a}/approve", headers=headers_b)
    assert appr_resp.status_code == 403

    # B cannot list A's project specs
    list_resp = await client.get(
        f"/api/v1/specifications/projects/{project_id_a}", headers=headers_b
    )
    assert list_resp.status_code == 403


@pytest.mark.asyncio
async def test_generate_requirement_too_short(client: AsyncClient):
    """Request with requirement shorter than 10 chars returns 422."""
    headers, _, project_id = await bootstrap(
        client, "spec_short@test.com", "SpecShort", "ShortWS", "ProjShort"
    )
    resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": "Too short"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_specification_returns_404(client: AsyncClient):
    """Fetching a spec with a random UUID returns 404."""
    headers, _, _ = await bootstrap(client, "spec_404@test.com", "Spec404", "WS404", "Proj404")
    resp = await client.get(f"/api/v1/specifications/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


# == Phase 2 completion: lifecycle, RBAC, limits, and provider failure tests ==


async def add_member(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_id: str,
    email: str,
    name: str,
    role: str,
):
    """Register a user and grant them an explicit workspace role."""
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


@pytest.mark.asyncio
async def test_unsupported_provider_is_rejected_before_llm_call(client: AsyncClient):
    headers, _, project_id = await bootstrap(
        client, "spec_unsupported@test.com", "Unsupported", "UnsupportedWS", "UnsupportedProj"
    )
    resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=openai",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_oversized_requirement_is_rejected(client: AsyncClient):
    headers, _, project_id = await bootstrap(
        client, "spec_oversize@test.com", "Oversize", "OversizeWS", "OversizeProj"
    )
    resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": "x" * 10_001},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_whitespace_requirement_is_rejected(client: AsyncClient):
    headers, _, project_id = await bootstrap(
        client, "spec_whitespace@test.com", "Whitespace", "WhitespaceWS", "WhitespaceProj"
    )
    resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": "          "},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_generate_for_archived_project_returns_409(client: AsyncClient):
    headers, _, project_id = await bootstrap(
        client, "spec_archived@test.com", "Archived", "ArchivedWS", "ArchivedProj"
    )
    update = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "archived"},
        headers=headers,
    )
    assert update.status_code == 200, update.text

    resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_edit_structured_content_persists(client: AsyncClient):
    headers, _, project_id = await bootstrap(
        client, "spec_content@test.com", "Content", "ContentWS", "ContentProj"
    )
    generated = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    assert generated.status_code == 201
    spec_id = generated.json()["id"]
    content = generated.json()["content_json"]
    content["project_summary"] = "Edited summary"
    content["functional_requirements"][0]["title"] = "Edited requirement"
    content["assumptions"] = ["Edited assumption"]

    resp = await client.patch(
        f"/api/v1/specifications/{spec_id}",
        json={"content_json": content},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content_json"]["project_summary"] == "Edited summary"
    assert body["content_json"]["functional_requirements"][0]["title"] == "Edited requirement"
    assert body["content_json"]["assumptions"] == ["Edited assumption"]


@pytest.mark.asyncio
async def test_reject_lifecycle(client: AsyncClient):
    headers, _, project_id = await bootstrap(
        client, "spec_reject@test.com", "Reject", "RejectWS", "RejectProj"
    )
    generated = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = generated.json()["id"]

    reject = await client.post(f"/api/v1/specifications/{spec_id}/reject", headers=headers)
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"

    edit = await client.patch(
        f"/api/v1/specifications/{spec_id}",
        json={"title": "Should fail"},
        headers=headers,
    )
    assert edit.status_code == 409

    approve = await client.post(f"/api/v1/specifications/{spec_id}/approve", headers=headers)
    assert approve.status_code == 409

    reject_again = await client.post(f"/api/v1/specifications/{spec_id}/reject", headers=headers)
    assert reject_again.status_code == 409


@pytest.mark.asyncio
async def test_specification_rbac_for_developer_and_viewer(
    client: AsyncClient,
    db_session: AsyncSession,
):
    headers, workspace_id, project_id = await bootstrap(
        client, "spec_rbac_owner@test.com", "RbacOwner", "RbacWS", "RbacProj"
    )
    generated = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    spec_id = generated.json()["id"]

    developer = await add_member(
        client, db_session, workspace_id, "spec_rbac_dev@test.com", "RbacDev", "developer"
    )
    viewer = await add_member(
        client, db_session, workspace_id, "spec_rbac_viewer@test.com", "RbacViewer", "viewer"
    )

    dev_generate = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=developer,
    )
    assert dev_generate.status_code == 201, dev_generate.text

    viewer_generate = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=viewer,
    )
    assert viewer_generate.status_code == 403

    dev_approve = await client.post(f"/api/v1/specifications/{spec_id}/approve", headers=developer)
    assert dev_approve.status_code == 403

    viewer_approve = await client.post(f"/api/v1/specifications/{spec_id}/approve", headers=viewer)
    assert viewer_approve.status_code == 403

    dev_reject = await client.post(f"/api/v1/specifications/{spec_id}/reject", headers=developer)
    assert dev_reject.status_code == 403


@pytest.mark.asyncio
async def test_list_specifications_pagination(client: AsyncClient):
    headers, _, project_id = await bootstrap(
        client, "spec_paging@test.com", "Paging", "PagingWS", "PagingProj"
    )
    for _ in range(3):
        resp = await client.post(
            f"/api/v1/specifications/projects/{project_id}/generate?provider=mock",
            json={"user_requirement": SAMPLE_REQUIREMENT},
            headers=headers,
        )
        assert resp.status_code == 201

    first_page = await client.get(
        f"/api/v1/specifications/projects/{project_id}?limit=2&offset=0",
        headers=headers,
    )
    assert first_page.status_code == 200
    assert [item["version"] for item in first_page.json()] == [3, 2]

    second_page = await client.get(
        f"/api/v1/specifications/projects/{project_id}?limit=2&offset=2",
        headers=headers,
    )
    assert second_page.status_code == 200
    assert [item["version"] for item in second_page.json()] == [1]


@pytest.mark.asyncio
async def test_llm_failure_is_mapped_to_safe_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    headers, _, project_id = await bootstrap(
        client, "spec_failure@test.com", "Failure", "FailureWS", "FailureProj"
    )

    class FailingProvider:
        async def generate_srs(self, *args, **kwargs):
            raise RuntimeError("upstream secret detail that must not leak")

    monkeypatch.setattr(specification_service, "get_llm_provider", lambda _name: FailingProvider())

    resp = await client.post(
        f"/api/v1/specifications/projects/{project_id}/generate",
        json={"user_requirement": SAMPLE_REQUIREMENT},
        headers=headers,
    )
    assert resp.status_code == 502, resp.text
    assert "upstream secret detail" not in resp.text
    assert "valid specification" in resp.json()["detail"]
