from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.builds import TERMINAL_STATUSES
from app.domain.deployments import DeploymentStatus
from app.domain.projects import ProjectRecord
from app.models.build import Build
from app.models.deployment import Deployment
from app.models.project import Project


def _to_domain(model: Project) -> ProjectRecord:
    return ProjectRecord(
        id=model.id,
        name=model.name,
        slug=model.slug,
        description=model.description,
        default_base_url=model.default_base_url,
        active_server_ref=model.active_server_ref,
        server_mappings=model.server_mappings,
        mcp_hostname=model.mcp_hostname,
        is_enabled=model.is_enabled,
        active_build_id=model.active_build_id,
        active_deployment_id=model.active_deployment_id,
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class ProjectRepository:
    async def lock_slug(self, session: AsyncSession, slug: str) -> None:
        await session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(f"mcplica:project-slug:{slug.casefold()}", 0)
                )
            )
        )

    async def list(self, session: AsyncSession) -> list[ProjectRecord]:
        result = await session.scalars(
            select(Project).order_by(Project.created_at.desc(), Project.id.desc())
        )
        return [_to_domain(model) for model in result]

    async def list_page(
        self, session: AsyncSession, *, page: int, page_size: int
    ) -> tuple[list[ProjectRecord], int]:
        total = int(await session.scalar(select(func.count()).select_from(Project)) or 0)
        result = await session.scalars(
            select(Project)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [_to_domain(model) for model in result], total

    async def get(self, session: AsyncSession, project_id: UUID) -> ProjectRecord | None:
        model = await session.get(Project, project_id)
        return _to_domain(model) if model else None

    async def lock(self, session: AsyncSession, project_id: UUID) -> ProjectRecord | None:
        model = await session.scalar(
            select(Project).where(Project.id == project_id).with_for_update()
        )
        return _to_domain(model) if model else None

    async def get_by_slug(self, session: AsyncSession, slug: str) -> ProjectRecord | None:
        model = await session.scalar(select(Project).where(Project.slug == slug))
        return _to_domain(model) if model else None

    async def create(
        self,
        session: AsyncSession,
        *,
        name: str,
        slug: str,
        description: str | None,
        default_base_url: str | None,
        mcp_hostname: str,
        created_by: UUID,
    ) -> ProjectRecord:
        model = Project(
            name=name,
            slug=slug,
            description=description,
            default_base_url=default_base_url,
            active_server_ref=None,
            server_mappings={},
            mcp_hostname=mcp_hostname,
            is_enabled=True,
            created_by=created_by,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def update(
        self,
        session: AsyncSession,
        project_id: UUID,
        values: dict[str, object],
    ) -> ProjectRecord | None:
        if values:
            await session.execute(update(Project).where(Project.id == project_id).values(**values))
        return await self.get(session, project_id)

    async def has_active_deployment(self, session: AsyncSession, project_id: UUID) -> bool:
        deployment_id = await session.scalar(
            select(Deployment.id)
            .where(
                Deployment.project_id == project_id,
                Deployment.status.in_(
                    {
                        DeploymentStatus.PENDING,
                        DeploymentStatus.DEPLOYING,
                        DeploymentStatus.HEALTHCHECK,
                        DeploymentStatus.RUNNING,
                        DeploymentStatus.UNHEALTHY,
                        DeploymentStatus.STOPPING,
                    }
                ),
            )
            .limit(1)
        )
        return deployment_id is not None

    async def has_nonterminal_build(self, session: AsyncSession, project_id: UUID) -> bool:
        build_id = await session.scalar(
            select(Build.id)
            .where(
                Build.project_id == project_id,
                Build.status.not_in(TERMINAL_STATUSES),
            )
            .limit(1)
        )
        return build_id is not None

    async def delete(self, session: AsyncSession, project_id: UUID) -> None:
        model = await session.get(Project, project_id)
        if model is not None:
            await session.delete(model)
