from typing import Protocol
from uuid import UUID

from app.clients.database import DatabaseClient
from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError, ValidationError
from app.core.hostname import normalize_dns_hostname
from app.domain.projects import ProjectRecord
from app.repositories.audit import AuditRepository
from app.repositories.projects import ProjectRepository
from app.services.settings import OperationalSettingsProvider


class ProjectDeploymentLifecycle(Protocol):
    async def stop_project(
        self,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> object: ...


class ProjectService:
    def __init__(
        self,
        database: DatabaseClient,
        repository: ProjectRepository,
        audit: AuditRepository,
        deployments: ProjectDeploymentLifecycle,
        settings: OperationalSettingsProvider,
    ) -> None:
        self._database = database
        self._repository = repository
        self._audit = audit
        self._deployments = deployments
        self._settings = settings

    async def list(self) -> list[ProjectRecord]:
        async with self._database.session_scope() as session:
            return await self._repository.list(session)

    async def get(self, project_id: UUID) -> ProjectRecord:
        async with self._database.session_scope() as session:
            project = await self._repository.get(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            return project

    async def create(
        self,
        *,
        name: str,
        slug: str,
        description: str | None,
        default_base_url: str | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> ProjectRecord:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Project name cannot be empty")
        try:
            normalized_slug = normalize_dns_hostname(slug)
        except ValueError as exc:
            raise ValidationError("Project slug must be a DNS label") from exc
        if not 3 <= len(normalized_slug) <= 63 or "." in normalized_slug:
            raise ValidationError("Project slug must be a 3 to 63 character DNS label")
        operational = await self._settings.get_operational()
        hostname = f"{normalized_slug}.{operational.mcp_base_domain}"
        async with self._database.session_scope() as session:
            await self._repository.lock_slug(session, normalized_slug)
            if await self._repository.get_by_slug(session, normalized_slug):
                raise ConflictError(f"Project slug {normalized_slug!r} already exists")
            project = await self._repository.create(
                session,
                name=normalized_name,
                slug=normalized_slug,
                description=description,
                default_base_url=default_base_url,
                mcp_hostname=hostname,
                created_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="project.created",
                entity_type="project",
                entity_id=project.id,
                project_id=project.id,
                request_id=request_id,
                metadata={"slug": project.slug, "mcp_hostname": project.mcp_hostname},
            )
            return project

    async def update(
        self,
        project_id: UUID,
        *,
        values: dict[str, object],
        actor_user_id: UUID,
        request_id: str | None,
    ) -> ProjectRecord:
        allowed = {
            "name",
            "description",
            "default_base_url",
            "active_server_ref",
            "is_enabled",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported project fields: {', '.join(sorted(unknown))}")
        if "name" in values:
            name = values["name"]
            if not isinstance(name, str) or not name.strip():
                raise ValidationError("Project name cannot be empty")
            values["name"] = name.strip()
        if "is_enabled" in values and not isinstance(values["is_enabled"], bool):
            raise ValidationError("Project enabled state must be a boolean")
        async with self._database.session_scope() as session:
            if await self._repository.lock(session, project_id) is None:
                raise NotFoundError("Project was not found")
            project = await self._repository.update(session, project_id, values)
            if project is None:
                raise NotFoundError("Project was not found")
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="project.updated",
                entity_type="project",
                entity_id=project.id,
                project_id=project.id,
                request_id=request_id,
                metadata={"changed_fields": sorted(values)},
            )
        if values.get("is_enabled") is False:
            await self._deployments.stop_project(
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        return project

    async def delete(
        self,
        project_id: UUID,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> None:
        async with self._database.session_scope() as session:
            project = await self._repository.lock(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            if await self._repository.has_active_deployment(session, project_id):
                raise InvalidStateError(
                    "Project cannot be deleted while an active deployment exists"
                )
            await self._repository.delete(session, project_id)
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="project.deleted",
                entity_type="project",
                entity_id=project_id,
                project_id=project_id,
                request_id=request_id,
                metadata={"slug": project.slug},
            )
