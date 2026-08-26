from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class ProjectRepository:
    async def list(self, session: AsyncSession) -> list[Project]:
        result = await session.scalars(select(Project).order_by(Project.created_at.desc()))
        return list(result.all())

    async def get(self, session: AsyncSession, project_id: UUID) -> Project | None:
        return await session.get(Project, project_id)

    async def get_by_slug(self, session: AsyncSession, slug: str) -> Project | None:
        result = await session.scalars(select(Project).where(Project.slug == slug))
        return result.one_or_none()

    def add(self, session: AsyncSession, project: Project) -> None:
        session.add(project)

    async def delete(self, session: AsyncSession, project: Project) -> None:
        await session.delete(project)
