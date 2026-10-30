from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import settings
from app.integrations.github import verify_signature

router = APIRouter(tags=["Webhooks"])

_GITHUB_DELIVERIES: set[str] = set()


@router.post(
    "/webhooks/github",
    status_code=status.HTTP_200_OK,
    summary="Verify and accept GitHub webhook events",
)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
):
    payload = await request.body()
    if not x_hub_signature_256:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing GitHub webhook signature")

    if not verify_signature(payload, settings.GITHUB_WEBHOOK_SECRET, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid GitHub webhook signature")

    if x_github_delivery:
        if x_github_delivery in _GITHUB_DELIVERIES:
            return {"ok": True, "duplicate": True, "event": x_github_event, "delivery_id": x_github_delivery}
        _GITHUB_DELIVERIES.add(x_github_delivery)

    return {"ok": True, "event": x_github_event, "delivery_id": x_github_delivery}
