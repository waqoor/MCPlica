from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from app.api.deps import BuilderPrincipal, CsrfProtection, services
from app.container import ServiceContainer
from app.domain.sources import SourceKind, SourceVersionMetadataRecord
from app.schemas.cleanup import CleanupJobRead
from app.schemas.source import (
    SourceConfigurationDiscoveryRead,
    SourceCreate,
    SourceCreationRead,
    SourcePageRead,
    SourceRead,
    SourceSummaryRead,
    SourceUpdate,
    SourceUrlCreate,
    SourceVersionMetadataRead,
    SourceVersionPageRead,
    SourceVersionRead,
    SourceVersionSummaryRead,
)
from app.services.sources import SourceCreationResult

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


def _creation_read(result: SourceCreationResult) -> SourceCreationRead:
    return SourceCreationRead(
        source=SourceRead.model_validate(result.source),
        version=_version_read(result.version, deduplicated=result.deduplicated),
    )


@router.get("/projects/{project_id}/sources", response_model=SourcePageRead)
async def list_sources(
    project_id: UUID,
    _principal: BuilderPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SourcePageRead:
    items, total = await container.sources.list_summaries(
        project_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return SourcePageRead(
        items=[
            SourceSummaryRead(
                **SourceRead.model_validate(item.source).model_dump(),
                latest_version=(
                    SourceVersionSummaryRead(
                        **_version_read(item.latest_version).model_dump(),
                        operation_count=item.operation_count,
                        indexed_chunk_count=item.indexed_chunk_count,
                        metadata_build_id=item.metadata_build_id,
                        index_generation_id=item.index_generation_id,
                    )
                    if item.latest_version is not None
                    else None
                ),
                version_count=item.version_count,
                health=item.health,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/projects/{project_id}/source-configuration",
    response_model=SourceConfigurationDiscoveryRead,
)
async def discover_source_configuration(
    project_id: UUID,
    _principal: BuilderPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
) -> SourceConfigurationDiscoveryRead:
    return SourceConfigurationDiscoveryRead.model_validate(
        await container.sources.discover_configuration(project_id)
    )


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
    "/projects/{project_id}/sources/upload",
    response_model=SourceCreationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_source_with_first_version(
    project_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
    source_id: Annotated[UUID, Form()],
    kind: Annotated[SourceKind, Form()],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    file: Annotated[UploadFile, File()],
    is_primary: Annotated[bool, Form()] = False,
) -> SourceCreationRead:
    result = await container.sources.create_with_upload(
        source_id=source_id,
        project_id=project_id,
        kind=kind,
        name=name,
        is_primary=is_primary,
        content=file,
        media_type=file.content_type or "application/octet-stream",
        filename=file.filename,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _creation_read(result)


@router.post(
    "/projects/{project_id}/sources/url",
    response_model=SourceCreationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_url_source_with_first_version(
    project_id: UUID,
    payload: SourceUrlCreate,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> SourceCreationRead:
    result = await container.sources.create_with_url(
        source_id=payload.source_id,
        project_id=project_id,
        kind=payload.kind,
        name=payload.name,
        source_url=str(payload.source_url),
        is_primary=payload.is_primary,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _creation_read(result)


@router.patch(
    "/projects/{project_id}/sources/{source_id}",
    response_model=SourceRead,
)
async def update_source(
    project_id: UUID,
    source_id: UUID,
    payload: SourceUpdate,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> SourceRead:
    source = await container.sources.update(
        project_id=project_id,
        source_id=source_id,
        name=payload.name,
        is_primary=payload.is_primary,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return SourceRead.model_validate(source)


@router.delete(
    "/projects/{project_id}/sources/{source_id}",
    response_model=CleanupJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_source(
    project_id: UUID,
    source_id: UUID,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> CleanupJobRead:
    job = await container.sources.delete(
        project_id=project_id,
        source_id=source_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    if job is None:  # pragma: no cover - compatibility for isolated legacy service tests
        raise RuntimeError("Source cleanup service is not configured")
    return CleanupJobRead.model_validate(job)


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
    response_model=SourceVersionPageRead,
)
async def list_source_versions(
    project_id: UUID,
    source_id: UUID,
    _principal: BuilderPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> SourceVersionPageRead:
    items, total = await container.sources.list_versions_page(
        project_id,
        source_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return SourceVersionPageRead(
        items=[_version_read(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


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
