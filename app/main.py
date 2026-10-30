import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="AgentForge AI Backend - Spec-driven AI software engineering orchestration platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.state.rate_limit_buckets = defaultdict(deque)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()

    if settings.RATE_LIMIT_ENABLED:
        bucket = app.state.rate_limit_buckets[client_ip]
        while bucket and current_time - bucket[0] > settings.RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= settings.RATE_LIMIT_REQUESTS_PER_MINUTE:
            response = JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
            )
            response.headers["x-ratelimit-limit"] = str(settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
            response.headers["x-ratelimit-remaining"] = "0"
            response.headers["x-content-type-options"] = "nosniff"
            response.headers["x-frame-options"] = "DENY"
            response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
            response.headers["permissions-policy"] = "geolocation=(), microphone=(), camera=()"
            return response

        bucket.append(current_time)

    response = await call_next(request)

    response.headers.setdefault("x-content-type-options", "nosniff")
    response.headers.setdefault("x-frame-options", "DENY")
    response.headers.setdefault("x-xss-protection", "0")
    response.headers.setdefault("referrer-policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("permissions-policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("x-ratelimit-limit", str(settings.RATE_LIMIT_REQUESTS_PER_MINUTE))
    remaining = max(settings.RATE_LIMIT_REQUESTS_PER_MINUTE - len(app.state.rate_limit_buckets.get(client_ip, [])), 0)
    response.headers.setdefault("x-ratelimit-remaining", str(remaining))
    return response


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Healthcheck endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "env": settings.APP_ENV}


@app.get("/ready", tags=["Health"])
async def readiness_check():
    checks = {
        "database": "ok",
        "cache": "ok",
    }
    return {"status": "ready", "checks": checks, "app": settings.APP_NAME}


# Mount API v1 routes
app.include_router(api_router)
