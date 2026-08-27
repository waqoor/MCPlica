import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import CsrfProtection, CurrentPrincipal, DeployerPrincipal, deployment_service
from app.domain.deployments import DeploymentRecord, DeploymentStatus
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentPageRead,
    DeploymentRead,
    DeploymentRollback,
)
from app.services.deployment.service import DeploymentService

router = APIRouter(tags=["deployments"])


def _read(
    request: Request,
    deployment: DeploymentRecord,
    *,
    active_deployment_id: UUID | None,
) -> DeploymentRead:
    return DeploymentRead.from_record(
        deployment,
        tls=bool(request.app.state.settings.traefik_tls),
        active_deployment_id=active_deployment_id,
    )


@router.get("/projects/{project_id}/deployments", response_model=DeploymentPageRead)
async def list_deployments(
    project_id: UUID,
    request: Request,
    _principal: CurrentPrincipal,
    service: Annotated[DeploymentService, Depends(deployment_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> DeploymentPageRead:
    active_deployment_id = await service.active_deployment_id(project_id)
    deployments, total, has_active = await service.page(
        project_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return DeploymentPageRead(
        items=[
            _read(request, item, active_deployment_id=active_deployment_id) for item in deployments
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_active=has_active,
    )


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
    return _read(
        request,
        deployment,
        active_deployment_id=await service.active_deployment_id(project_id),
    )


@router.get("/deployments/{deployment_id}", response_model=DeploymentRead)
async def get_deployment(
    deployment_id: UUID,
    request: Request,
    _principal: CurrentPrincipal,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> DeploymentRead:
    deployment = await service.get(deployment_id)
    return _read(
        request,
        deployment,
        active_deployment_id=await service.active_deployment_id(deployment.project_id),
    )


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
    return _read(
        request,
        deployment,
        active_deployment_id=await service.active_deployment_id(deployment.project_id),
    )


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
    return _read(
        request,
        deployment,
        active_deployment_id=await service.active_deployment_id(deployment.project_id),
    )


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
    return _read(
        request,
        deployment,
        active_deployment_id=await service.active_deployment_id(project_id),
    )


@router.get("/deployments/{deployment_id}/events")
async def deployment_events(
    deployment_id: UUID,
    request: Request,
    _principal: CurrentPrincipal,
    service: Annotated[DeploymentService, Depends(deployment_service)],
) -> StreamingResponse:
    # Resolve before response headers are committed.  Missing resources must
    # use the normal structured 404 envelope, never a 200 stream that aborts on
    # its first iterator step.
    initial = await service.get(deployment_id)

    async def stream() -> AsyncGenerator[str]:
        previous: str | None = None
        deployment = initial
        while True:
            if await request.is_disconnected():
                return
            payload = _read(
                request,
                deployment,
                active_deployment_id=await service.active_deployment_id(deployment.project_id),
            ).model_dump(mode="json")
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
            deployment = await service.get(deployment_id)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
