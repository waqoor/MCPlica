from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    AdminPrincipal,
    BuilderPrincipal,
    CsrfProtection,
    project_service,
)
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.projects import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    _principal: BuilderPrincipal,
    service: Annotated[ProjectService, Depends(project_service)],
) -> list[ProjectRead]:
    return [ProjectRead.model_validate(project) for project in await service.list()]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[ProjectService, Depends(project_service)],
) -> ProjectRead:
    project = await service.create(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        default_base_url=str(payload.default_base_url) if payload.default_base_url else None,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[ProjectService, Depends(project_service)],
) -> ProjectRead:
    return ProjectRead.model_validate(await service.get(project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    request: Request,
    principal: BuilderPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[ProjectService, Depends(project_service)],
) -> ProjectRead:
    project = await service.update(
        project_id,
        values=payload.model_dump(exclude_unset=True, mode="json"),
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[ProjectService, Depends(project_service)],
) -> Response:
    await service.delete(
        project_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
