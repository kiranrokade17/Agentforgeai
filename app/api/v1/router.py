from fastapi import APIRouter

from app.api.v1.agent_runs import router as agent_runs_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.architecture_plans import router as architecture_plans_router
from app.api.v1.auth import router as auth_router
from app.api.v1.deployments import router as deployments_router
from app.api.v1.projects import router as projects_router
from app.api.v1.pull_requests import router as pull_requests_router
from app.api.v1.quality import router as quality_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.specifications import router as specifications_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(workspaces_router)
api_router.include_router(projects_router)
api_router.include_router(specifications_router)
api_router.include_router(architecture_plans_router)
api_router.include_router(tasks_router)
api_router.include_router(agent_runs_router)
api_router.include_router(quality_router)
api_router.include_router(repositories_router)
api_router.include_router(pull_requests_router)
api_router.include_router(deployments_router)
api_router.include_router(analytics_router)
api_router.include_router(webhooks_router)
