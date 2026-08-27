from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.api.deps import BuilderPrincipal, CsrfProtection, services
from app.container import ServiceContainer
from app.domain.sources import SourceVersionMetadataRecord
from app.schemas.source import (
    SourceCreate,
    SourceRead,
    SourceVersionMetadataRead,
    SourceVersionRead,
)

router = APIRouter(tags=["sources"])


def _version_read(result: object, *, deduplicated: bool = False) -> SourceVersionRead:
    return SourceVersionRead.model_validate(result).model_copy(
        update={"deduplicated": deduplicated}
    )


def _metadata_read(result: SourceVersionMetadataRecord) -> SourceVersionMetadataRead:
    return SourceVersionMetadataRead(
        **SourceVersionRead.model_validate(result.version).model_dump(),
        **result.model_dump(exclude={"version"}),
    )


@router.get("/projects/{project_id}/sources", response_model=list[SourceRead])
async def list_sources(
    project_id: UUID,
    _principal: BuilderPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
) -> list[SourceRead]:
    return [SourceRead.model_validate(item) for item in await container.sources.list(project_id)]


@router.post(
    "/projects/{project_id}/sources",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    project_id: UUID,
    payload: SourceCreate,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> SourceRead:
    source = await container.sources.create(
        project_id=project_id,
        kind=payload.kind,
        name=payload.name,
        origin_type=payload.origin_type,
        source_url=str(payload.source_url) if payload.source_url else None,
        is_primary=payload.is_primary,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return SourceRead.model_validate(source)


@router.post(
    "/projects/{project_id}/sources/{source_id}/versions",
    response_model=SourceVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source_version(
    project_id: UUID,
    source_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
    file: Annotated[UploadFile, File()],
) -> SourceVersionRead:
    result = await container.sources.add_upload_version(
        project_id=project_id,
        source_id=source_id,
        content=file,
        media_type=file.content_type or "application/octet-stream",
        filename=file.filename,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _version_read(result.version, deduplicated=result.deduplicated)


@router.post(
    "/projects/{project_id}/sources/{source_id}/refresh",
    response_model=SourceVersionRead,
)
async def refresh_source(
    project_id: UUID,
    source_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> SourceVersionRead:
    result = await container.sources.refresh(
        project_id=project_id,
        source_id=source_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _version_read(result.version, deduplicated=result.deduplicated)


@router.get(
    "/projects/{project_id}/sources/{source_id}/versions",
    response_model=list[SourceVersionRead],
)
async def list_source_versions(
    project_id: UUID,
    source_id: UUID,
    _principal: BuilderPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
) -> list[SourceVersionRead]:
    return [
        _version_read(item) for item in await container.sources.list_versions(project_id, source_id)
    ]


@router.get(
    "/source-versions/{version_id}/metadata",
    response_model=SourceVersionMetadataRead,
)
async def source_version_metadata(
    version_id: UUID,
    _principal: BuilderPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
) -> SourceVersionMetadataRead:
    return _metadata_read(await container.sources.metadata(version_id))
