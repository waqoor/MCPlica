import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response, StreamingResponse

from app.api.deps import BuilderPrincipal, CsrfProtection, services
from app.container import ServiceContainer
from app.domain.builds import TERMINAL_STATUSES, BuildStatus, BuildTrigger
from app.schemas.build import (
    BuildAIRunRead,
    BuildCreate,
    BuildDiffRead,
    BuildRead,
    OperationExclusionCreate,
    OperationExclusionRead,
    OperationRead,
    ValidationFindingRead,
    ValidationReportRead,
    ValidationSourceRefRead,
)
from app.services.builds import BuildService

router = APIRouter(tags=["builds"])


def _builds(
    container: Annotated[ServiceContainer, Depends(services)],
) -> BuildService:
    return container.builds


def _read(value: object) -> BuildRead:
    return BuildRead.model_validate(value)


@router.get("/builds", response_model=list[BuildRead])
async def list_builds(
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
    project_id: UUID | None = None,
    build_status: Annotated[BuildStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[BuildRead]:
    builds = await service.list_all(
        project_id=project_id,
        status=build_status,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return [_read(build) for build in builds]


@router.get("/projects/{project_id}/builds", response_model=list[BuildRead])
async def list_project_builds(
    project_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[BuildRead]:
    return [
        _read(build)
        for build in await service.list_for_project(
            project_id,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    ]


@router.post(
    "/projects/{project_id}/builds",
    response_model=BuildRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_build(
    project_id: UUID,
    payload: BuildCreate,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[BuildService, Depends(_builds)],
) -> BuildRead:
    build = await service.create(
        project_id=project_id,
        requested_by=principal.user.id,
        request_id=request.state.request_id,
        requested_trigger=payload.trigger,
    )
    return _read(build)


@router.post(
    "/projects/{project_id}/review",
    response_model=BuildRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def review_project(
    project_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[BuildService, Depends(_builds)],
) -> BuildRead:
    build = await service.create(
        project_id=project_id,
        requested_by=principal.user.id,
        request_id=request.state.request_id,
        requested_trigger=BuildTrigger.MANUAL_REVIEW,
    )
    return _read(build)


@router.post(
    "/projects/{project_id}/rebuild",
    response_model=BuildRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rebuild_project(
    project_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[BuildService, Depends(_builds)],
) -> BuildRead:
    build = await service.create(
        project_id=project_id,
        requested_by=principal.user.id,
        request_id=request.state.request_id,
        requested_trigger=BuildTrigger.MANUAL_REBUILD,
    )
    return _read(build)


@router.get("/builds/{build_id}", response_model=BuildRead)
async def get_build(
    build_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> BuildRead:
    return _read(await service.get(build_id))


@router.post("/builds/{build_id}/cancel", response_model=BuildRead)
async def cancel_build(
    build_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[BuildService, Depends(_builds)],
) -> BuildRead:
    build = await service.cancel(
        build_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _read(build)


@router.get("/builds/{build_id}/events")
async def build_events(
    build_id: UUID,
    request: Request,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> StreamingResponse:
    await service.get(build_id)

    async def stream() -> AsyncIterator[str]:
        prior: BuildStatus | None = None
        while not await request.is_disconnected():
            build = await service.get(build_id)
            if build.status != prior:
                payload = _read(build).model_dump(mode="json")
                yield f"event: build\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
                prior = build.status
            if build.status in TERMINAL_STATUSES:
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/builds/{build_id}/diff", response_model=BuildDiffRead)
async def get_build_diff(
    build_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> BuildDiffRead:
    return BuildDiffRead.model_validate((await service.diff(build_id)).model_dump())


@router.get("/builds/{build_id}/manifest")
async def get_build_manifest(
    build_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> Response:
    value = await service.manifest_bytes(build_id)
    return Response(
        content=value,
        media_type="application/json",
        headers={"Content-Disposition": f'inline; filename="manifest-{build_id}.json"'},
    )


@router.get("/builds/{build_id}/validation", response_model=ValidationReportRead)
async def get_build_validation(
    build_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> ValidationReportRead:
    report = await service.validation_report(build_id)
    return ValidationReportRead(
        **report.model_dump(exclude={"findings"}),
        findings=[
            ValidationFindingRead(
                **finding.model_dump(exclude={"source_ref"}),
                source_ref=(
                    ValidationSourceRefRead(
                        source_version_id=finding.source_ref.source_version_id,
                        path=finding.source_ref.pointer,
                    )
                    if finding.source_ref
                    else None
                ),
            )
            for finding in report.findings
        ],
    )


@router.get("/builds/{build_id}/export")
async def export_build(
    build_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> Response:
    build, value = await service.export(build_id)
    return Response(
        content=value,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="mcplica-build-{build.sequence}-{build.id}.zip"'
            )
        },
    )


@router.get("/builds/{build_id}/operations", response_model=list[OperationRead])
async def get_build_operations(
    build_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> list[OperationRead]:
    return [
        OperationRead.model_validate(item.model_dump())
        for item in await service.operations(build_id)
    ]


@router.get("/builds/{build_id}/ai-runs", response_model=list[BuildAIRunRead])
async def get_build_ai_runs(
    build_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[BuildService, Depends(_builds)],
) -> list[BuildAIRunRead]:
    return [
        BuildAIRunRead.model_validate(item.model_dump(exclude={"response"}))
        for item in await service.ai_runs(build_id)
    ]


@router.post(
    "/projects/{project_id}/operation-exclusions",
    response_model=OperationExclusionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_operation_exclusion(
    project_id: UUID,
    payload: OperationExclusionCreate,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[BuildService, Depends(_builds)],
) -> OperationExclusionRead:
    exclusion = await service.create_exclusion(
        project_id=project_id,
        operation_key=payload.operation_key,
        reason=payload.reason,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return OperationExclusionRead.model_validate(exclusion.model_dump())


@router.delete(
    "/projects/{project_id}/operation-exclusions/{exclusion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_operation_exclusion(
    project_id: UUID,
    exclusion_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[BuildService, Depends(_builds)],
) -> Response:
    await service.delete_exclusion(
        project_id=project_id,
        exclusion_id=exclusion_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
