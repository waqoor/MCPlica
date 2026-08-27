from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminPrincipal, services
from app.container import ServiceContainer
from app.schemas.cleanup import CleanupJobRead

router = APIRouter(prefix="/cleanup-jobs", tags=["cleanup"])


@router.get("", response_model=list[CleanupJobRead])
async def list_cleanup_jobs(
    _principal: AdminPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
    project_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CleanupJobRead]:
    return [
        CleanupJobRead.model_validate(job)
        for job in await container.cleanup.list(project_id=project_id, limit=limit)
    ]


@router.get("/{job_id}", response_model=CleanupJobRead)
async def get_cleanup_job(
    job_id: UUID,
    _principal: AdminPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
) -> CleanupJobRead:
    return CleanupJobRead.model_validate(await container.cleanup.get(job_id))
