from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.project import Project
from app.repositories.projects import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    async def list(self, session: AsyncSession) -> list[Project]:
        return await self.repository.list(session)

    async def get(self, session: AsyncSession, project_id: UUID) -> Project:
        project = await self.repository.get(session, project_id)
        if not project:
            raise NotFoundError("Project was not found")
        return project

    async def create(self, session: AsyncSession, data: ProjectCreate) -> Project:
        if await self.repository.get_by_slug(session, data.slug):
            raise ConflictError(f"Project slug {data.slug!r} already exists")
        project = Project(name=data.name, slug=data.slug, description=data.description)
        self.repository.add(session, project)
        await session.flush()
        await session.refresh(project)
        return project

    async def update(
        self, session: AsyncSession, project_id: UUID, data: ProjectUpdate
    ) -> Project:
        project = await self.get(session, project_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        await session.flush()
        await session.refresh(project)
        return project

    async def delete(self, session: AsyncSession, project_id: UUID) -> None:
        project = await self.get(session, project_id)
        await self.repository.delete(session, project)
