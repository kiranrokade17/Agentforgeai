import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import get_coding_agent_provider
from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.db.models.user import User
from app.repositories.task_repo import TaskRepository
from app.schemas.agent_run import AgentRunSummary

router = APIRouter(tags=["Agent Runs"])

_AGENT_RUNS: dict[uuid.UUID, AgentRunSummary] = {}
_AGENT_RUN_EVENTS: dict[uuid.UUID, list[str]] = {}


@router.post(
    "/tasks/{task_id}/runs",
    response_model=AgentRunSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Queue an approved task for coding-agent execution",
)
async def create_agent_run(
    task_id: uuid.UUID,
    provider: str | None = Query(
        None,
        description="Coding agent provider: 'codex', 'claude_code', or 'mock'",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    task_repo = TaskRepository(db)
    task = await task_repo.get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    provider_name = (provider or settings.CODING_AGENT_PROVIDER).strip().lower()
    coding_agent = get_coding_agent_provider(provider_name)
    summary = await coding_agent.execute(
        task_id=task.id,
        task_title=task.title,
        repo_path=None,
        context={"project_id": str(task.project_id), "provider": provider_name},
    )
    _AGENT_RUNS[summary.id] = summary
    _AGENT_RUN_EVENTS.setdefault(summary.id, []).append(
        f"queued task {task_id} with provider {provider_name}"
    )
    return summary


@router.get(
    "/agent-runs/{run_id}",
    response_model=AgentRunSummary,
    summary="Fetch a coding-agent run summary",
)
async def get_agent_run(run_id: uuid.UUID):
    run = _AGENT_RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return run


@router.get(
    "/agent-runs/{run_id}/events",
    summary="Fetch execution events for a coding-agent run",
)
async def get_agent_run_events(run_id: uuid.UUID):
    events = _AGENT_RUN_EVENTS.get(run_id, [])
    return {"run_id": str(run_id), "events": events}
