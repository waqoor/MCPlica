import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import CsrfProtection, CurrentPrincipal, DeployerPrincipal, deployment_service
from app.domain.deployments import DeploymentRecord, DeploymentStatus
from app.schemas.deployment import DeploymentCreate, DeploymentRead, DeploymentRollback
from app.services.deployment.service import DeploymentService

router = APIRouter(tags=["deployments"])


def _read(request: Request, deployment: DeploymentRecord) -> DeploymentRead:
    return DeploymentRead.from_record(
        deployment,
        tls=bool(request.app.state.settings.traefik_tls),
    )


@router.get("/projects/{project_id}/deployments", response_model=list[DeploymentRead])
async def list_deployments(
    project_id: UUID,
    request: Request,
    _principal: CurrentPrincipal,
    service: Annotated[DeploymentService, Depends(deployment_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DeploymentRead]:
    return [
        _read(request, item) for item in await service.list(project_id, limit=limit, offset=offset)
    ]


@router.post(
    "/projects/{project_id}/deployments",
    response_model=DeploymentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_deployment(
    project_id: UUID,
    payload: DeploymentCreate,
    request: Request,
    principal: DeployerPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> DeploymentRead:
    deployment = await service.request(
        project_id=project_id,
        build_id=payload.build_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _read(request, deployment)


@router.get("/deployments/{deployment_id}", response_model=DeploymentRead)
async def get_deployment(
    deployment_id: UUID,
    request: Request,
    _principal: CurrentPrincipal,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> DeploymentRead:
    return _read(request, await service.get(deployment_id))


@router.post(
    "/deployments/{deployment_id}/stop",
    response_model=DeploymentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_deployment(
    deployment_id: UUID,
    request: Request,
    principal: DeployerPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> DeploymentRead:
    deployment = await service.stop(
        deployment_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _read(request, deployment)


@router.post(
    "/deployments/{deployment_id}/restart",
    response_model=DeploymentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def restart_deployment(
    deployment_id: UUID,
    request: Request,
    principal: DeployerPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> DeploymentRead:
    deployment = await service.restart(
        deployment_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _read(request, deployment)


@router.post(
    "/projects/{project_id}/rollback",
    response_model=DeploymentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rollback_deployment(
    project_id: UUID,
    payload: DeploymentRollback,
    request: Request,
    principal: DeployerPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> DeploymentRead:
    deployment = await service.rollback(
        project_id=project_id,
        target_deployment_id=payload.target_deployment_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _read(request, deployment)


@router.get("/deployments/{deployment_id}/events")
async def deployment_events(
    deployment_id: UUID,
    request: Request,
    _principal: CurrentPrincipal,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> StreamingResponse:
    async def stream() -> AsyncGenerator[str]:
        previous: str | None = None
        while not await request.is_disconnected():
            deployment = await service.get(deployment_id)
            payload = _read(request, deployment).model_dump(mode="json")
            serialized = json.dumps(payload, separators=(",", ":"))
            if serialized != previous:
                yield f"event: deployment\ndata: {serialized}\n\n"
                previous = serialized
            if deployment.status in {
                DeploymentStatus.RUNNING,
                DeploymentStatus.UNHEALTHY,
                DeploymentStatus.STOPPED,
                DeploymentStatus.FAILED,
            }:
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
