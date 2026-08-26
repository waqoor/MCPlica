from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, project_service
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.projects import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    session: AsyncSession = Depends(db_session),
    service: ProjectService = Depends(project_service),
) -> list[ProjectRead]:
    projects = await service.list(session)
    return [ProjectRead.model_validate(project) for project in projects]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(db_session),
    service: ProjectService = Depends(project_service),
) -> ProjectRead:
    async with session.begin():
        project = await service.create(session, payload)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    session: AsyncSession = Depends(db_session),
    service: ProjectService = Depends(project_service),
) -> ProjectRead:
    project = await service.get(session, project_id)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(db_session),
    service: ProjectService = Depends(project_service),
) -> ProjectRead:
    async with session.begin():
        project = await service.update(session, project_id, payload)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    session: AsyncSession = Depends(db_session),
    service: ProjectService = Depends(project_service),
) -> Response:
    async with session.begin():
        await service.delete(session, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
