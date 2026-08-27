from typing import Protocol, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.exceptions import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.hostname import normalize_dns_hostname
from app.domain.auth import UserRole
from app.domain.cleanup import CleanupJobRecord
from app.domain.projects import ProjectRecord
from app.repositories.audit import AuditRepository
from app.repositories.projects import ProjectRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.cleanup import CleanupService
from app.services.deployment.effect_state import runtime_effect_update
from app.services.settings import OperationalSettingsProvider


class ProjectDeploymentLifecycle(Protocol):
    async def schedule_stop_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        reason: str,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
    ) -> object: ...

    def notify_runtime_commands(self) -> None: ...


class ProjectService:
    def __init__(
        self,
        database: DatabaseClient,
        repository: ProjectRepository,
        audit: AuditRepository,
        commands: RuntimeCommandRepository,
        deployments: ProjectDeploymentLifecycle,
        settings: OperationalSettingsProvider,
        cleanup: CleanupService | None = None,
    ) -> None:
        self._database = database
        self._repository = repository
        self._audit = audit
        self._commands = commands
        self._deployments = deployments
        self._settings = settings
        self._cleanup = cleanup

    async def list(self) -> list[ProjectRecord]:
        async with self._database.session_scope() as session:
            projects = await self._repository.list(session)
            return [await self._with_runtime_state(session, project) for project in projects]

    async def get(self, project_id: UUID) -> ProjectRecord:
        async with self._database.session_scope() as session:
            project = await self._repository.get(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            return await self._with_runtime_state(session, project)

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
        actor_role: UserRole,
        request_id: str | None,
    ) -> ProjectRecord:
        allowed = {
            "name",
            "description",
            "default_base_url",
            "active_server_ref",
            "server_mappings",
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
        if "server_mappings" in values:
            mappings = values["server_mappings"]
            if mappings is None:
                values["server_mappings"] = {}
            elif not isinstance(mappings, dict):
                raise ValidationError(
                    "Project server mappings must contain safe operation/server refs"
                )
            else:
                raw_mappings = cast(dict[object, object], mappings)
                if any(
                    not isinstance(operation_key, str)
                    or not operation_key.strip()
                    or len(operation_key) > 160
                    or not isinstance(server_ref, str)
                    or not server_ref.strip()
                    or len(server_ref) > 120
                    for operation_key, server_ref in raw_mappings.items()
                ):
                    raise ValidationError(
                        "Project server mappings must contain safe operation/server refs"
                    )
                values["server_mappings"] = {
                    cast(str, operation_key).strip(): cast(str, server_ref).strip()
                    for operation_key, server_ref in raw_mappings.items()
                }
        if "is_enabled" in values:
            operational = await self._settings.get_operational()
            can_manage_lifecycle = actor_role == UserRole.ADMIN or (
                actor_role == UserRole.BUILDER and operational.builders_can_deploy
            )
            if not can_manage_lifecycle:
                raise PermissionDeniedError("Deployment permission is required")
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
                await self._deployments.schedule_stop_project(
                    session,
                    project_id=project_id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                    reason="deployment.project_disabled",
                    subject_type="project",
                    subject_id=project_id,
                )
        if values.get("is_enabled") is False:
            self._deployments.notify_runtime_commands()
        return await self._load_runtime_state(project)

    async def _load_runtime_state(self, project: ProjectRecord) -> ProjectRecord:
        async with self._database.session_scope() as session:
            return await self._with_runtime_state(session, project)

    async def _with_runtime_state(
        self,
        session: AsyncSession,
        project: ProjectRecord,
    ) -> ProjectRecord:
        update = await runtime_effect_update(
            session,
            self._commands,
            project_id=project.id,
            subject_type="project",
            subject_id=project.id,
        )
        return project.model_copy(update=update)

    async def delete(
        self,
        project_id: UUID,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> CleanupJobRecord | None:
        async with self._database.session_scope() as session:
            project = await self._repository.lock(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            if await self._repository.has_active_deployment(session, project_id):
                raise InvalidStateError(
                    "Project cannot be deleted while an active deployment exists"
                )
            if await self._repository.has_nonterminal_build(session, project_id):
                raise InvalidStateError("Project cannot be deleted while a Build is in progress")
            cleanup_job = (
                await self._cleanup.capture_project_delete(
                    session,
                    project_id=project_id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                )
                if self._cleanup is not None
                else None
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
                metadata={
                    "slug": project.slug,
                    "cleanup_job_id": str(cleanup_job.id) if cleanup_job else None,
                },
            )
        if cleanup_job is not None:
            cleanup = self._cleanup
            assert cleanup is not None
            cleanup.notify()
        return cleanup_job
