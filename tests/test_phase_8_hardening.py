import pytest

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_hardening_headers_and_readiness(client):
    original_limit = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
    original_window = settings.RATE_LIMIT_WINDOW_SECONDS
    original_enabled = settings.RATE_LIMIT_ENABLED
    try:
        settings.RATE_LIMIT_REQUESTS_PER_MINUTE = 5
        settings.RATE_LIMIT_WINDOW_SECONDS = 60
        settings.RATE_LIMIT_ENABLED = True
        app.state.rate_limit_buckets.clear()

        response = await client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

        ready = await client.get("/ready")
        assert ready.status_code == 200
        ready_payload = ready.json()
        assert ready_payload["status"] == "ready"
        assert ready_payload["checks"]["database"] in {"ok", "available"}
    finally:
        settings.RATE_LIMIT_REQUESTS_PER_MINUTE = original_limit
        settings.RATE_LIMIT_WINDOW_SECONDS = original_window
        settings.RATE_LIMIT_ENABLED = original_enabled
        app.state.rate_limit_buckets.clear()


@pytest.mark.asyncio
async def test_rate_limiter_blocks_abuse(client):
    original_limit = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
    original_window = settings.RATE_LIMIT_WINDOW_SECONDS
    original_enabled = settings.RATE_LIMIT_ENABLED
    try:
        settings.RATE_LIMIT_REQUESTS_PER_MINUTE = 5
        settings.RATE_LIMIT_WINDOW_SECONDS = 60
        settings.RATE_LIMIT_ENABLED = True
        app.state.rate_limit_buckets.clear()

        for _ in range(5):
            response = await client.get("/health")
            assert response.status_code == 200

        blocked = await client.get("/health")
        assert blocked.status_code == 429
        assert blocked.headers["x-ratelimit-limit"] == "5"
    finally:
        settings.RATE_LIMIT_REQUESTS_PER_MINUTE = original_limit
        settings.RATE_LIMIT_WINDOW_SECONDS = original_window
        settings.RATE_LIMIT_ENABLED = original_enabled
        app.state.rate_limit_buckets.clear()
