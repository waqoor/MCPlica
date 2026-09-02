from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeployabilityError
from app.domain.sources import source_configuration_fingerprint
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository


class ExecutableConfigurationProvider(Protocol):
    async def current_sha256(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> str: ...


class ExecutableConfigurationIdentity:
    """Derive the deployable source+routing identity from authoritative rows."""

    def __init__(
        self,
        projects: ProjectRepository,
        sources: SourceRepository,
    ) -> None:
        self._projects = projects
        self._sources = sources

    async def current_sha256(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> str:
        project = await self._projects.get(session, project_id)
        if project is None:
            raise DeployabilityError(
                "Project configuration is unavailable",
                details={
                    "reason_code": "PROJECT_NOT_FOUND",
                    "field": "project_id",
                    "remediation": "Reload the project before deployment.",
                },
            )
        bindings = await self._sources.latest_bound_versions(session, project_id)
        return source_configuration_fingerprint(
            bindings=bindings,
            default_base_url=project.default_base_url,
            active_server_ref=project.active_server_ref,
            server_mappings=project.server_mappings,
        )
