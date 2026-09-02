from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.builds import BuildRecord, BuildStatus
from app.domain.cleanup import CleanupJobKind, CleanupJobRecord
from app.repositories.audit import AuditRepository
from app.repositories.build_execution import require_build_execution_owner
from app.repositories.builds import BuildRepository
from app.repositories.cleanup import CleanupRepository


@dataclass(frozen=True, slots=True)
class BuildCancellationAcknowledgement:
    build: BuildRecord
    cleanup_job: CleanupJobRecord | None
    changed: bool


class BuildCancellationService:
    """One idempotent, fenced cancellation acknowledgement and cleanup path."""

    def __init__(
        self,
        builds: BuildRepository,
        cleanup: CleanupRepository | None,
        audit: AuditRepository,
    ) -> None:
        self._builds = builds
        self._cleanup = cleanup
        self._audit = audit

    async def acknowledge(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        admission_token: UUID,
        actor_user_id: UUID | None,
        request_id: str | None,
        acknowledgement: str,
    ) -> BuildCancellationAcknowledgement:
        current = await self._builds.get(session, build_id)
        if current is None:
            raise NotFoundError("Build was not found")
        if current.status is BuildStatus.CANCELLED:
            return BuildCancellationAcknowledgement(current, None, False)
        owned = await require_build_execution_owner(
            session,
            build_id=build_id,
            admission_token=admission_token,
            allow_cancellation=True,
        )
        cleanup_job = None
        if self._cleanup is not None:
            cleanup_job = await self._cleanup.create_job(
                session,
                kind=CleanupJobKind.ORPHAN_GUARD,
                idempotency_key=f"build-cancellation:{build_id}",
                project_id=owned.project_id,
                requested_by=owned.cancellation_requested_by,
                request_id=request_id,
            )
            await self._cleanup.capture_build_target(session, cleanup_job.id, build_id)
            await self._cleanup.finalize_empty_job(session, cleanup_job.id)
            cleanup_job = await self._cleanup.get_job(session, cleanup_job.id)
        cancelled = await self._builds.acknowledge_cancellation(
            session,
            build_id,
            admission_token=admission_token,
        )
        await self._audit.append(
            session,
            actor_user_id=actor_user_id or cancelled.cancellation_requested_by,
            event_type="build.cancelled",
            entity_type="build",
            entity_id=build_id,
            project_id=cancelled.project_id,
            request_id=request_id,
            metadata={
                "acknowledgement": acknowledgement,
                "cleanup_job_id": str(cleanup_job.id) if cleanup_job else None,
            },
        )
        return BuildCancellationAcknowledgement(cancelled, cleanup_job, True)
