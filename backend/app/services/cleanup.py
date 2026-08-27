from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.exceptions import MCPlicaError, NotFoundError
from app.domain.cleanup import (
    CleanupJobKind,
    CleanupJobRecord,
    CleanupTargetRecord,
    CleanupTargetType,
)
from app.providers.storage import ArtifactStorage
from app.providers.vector import VectorStore
from app.repositories.audit import AuditRepository
from app.repositories.cleanup import CleanupRepository, lock_object_reference
from app.services.settings import OperationalSettingsProvider

logger = logging.getLogger("mcplica.cleanup")


class CleanupService:
    def __init__(
        self,
        database: DatabaseClient,
        repository: CleanupRepository,
        audit: AuditRepository,
        *,
        orphan_guard_delay_seconds: float,
        notify: Callable[[], None] | None = None,
    ) -> None:
        self._database = database
        self._repository = repository
        self._audit = audit
        self._orphan_guard_delay_seconds = orphan_guard_delay_seconds
        self._notify = notify or (lambda: None)

    def notify(self) -> None:
        self._notify()

    async def get(self, job_id: UUID) -> CleanupJobRecord:
        async with self._database.session_scope() as session:
            job = await self._repository.get_job(session, job_id)
            if job is None:
                raise NotFoundError("Cleanup job was not found")
            return job

    async def list(
        self, *, project_id: UUID | None = None, limit: int = 100
    ) -> list[CleanupJobRecord]:
        async with self._database.session_scope() as session:
            return await self._repository.list_jobs(session, project_id=project_id, limit=limit)

    async def capture_project_delete(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> CleanupJobRecord:
        job = await self._repository.create_job(
            session,
            kind=CleanupJobKind.PROJECT_DELETE,
            idempotency_key=f"project-delete:{project_id}",
            project_id=project_id,
            requested_by=actor_user_id,
            request_id=request_id,
        )
        await self._repository.capture_project_targets(session, job.id, project_id)
        await self._repository.finalize_empty_job(session, job.id)
        refreshed = await self._repository.get_job(session, job.id)
        assert refreshed is not None
        return refreshed

    async def capture_source_delete(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        source_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> CleanupJobRecord:
        job = await self._repository.create_job(
            session,
            kind=CleanupJobKind.SOURCE_DELETE,
            idempotency_key=f"source-delete:{source_id}",
            project_id=project_id,
            requested_by=actor_user_id,
            request_id=request_id,
        )
        await self._repository.capture_source_targets(session, job.id, source_id)
        await self._repository.finalize_empty_job(session, job.id)
        refreshed = await self._repository.get_job(session, job.id)
        assert refreshed is not None
        return refreshed

    async def capture_build_cancellation(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        build_id: UUID,
        actor_user_id: UUID | None,
        request_id: str | None,
    ) -> CleanupJobRecord:
        job = await self._repository.create_job(
            session,
            kind=CleanupJobKind.ORPHAN_GUARD,
            idempotency_key=f"build-cancellation:{build_id}",
            project_id=project_id,
            requested_by=actor_user_id,
            request_id=request_id,
        )
        await self._repository.capture_build_target(session, job.id, build_id)
        await self._repository.finalize_empty_job(session, job.id)
        refreshed = await self._repository.get_job(session, job.id)
        assert refreshed is not None
        return refreshed

    async def arm_orphan_guard(
        self,
        *,
        project_id: UUID,
        storage_key: str,
        actor_user_id: UUID | None,
        request_id: str | None,
    ) -> UUID:
        guard_nonce = uuid4()
        async with self._database.session_scope() as session:
            job = await self._repository.create_job(
                session,
                kind=CleanupJobKind.ORPHAN_GUARD,
                idempotency_key=f"orphan-guard:{guard_nonce}",
                project_id=project_id,
                requested_by=actor_user_id,
                request_id=request_id,
            )
            await self._repository.add_object_target(
                session,
                job.id,
                storage_key,
                not_before=datetime.now(UTC) + timedelta(seconds=self._orphan_guard_delay_seconds),
            )
        return job.id

    async def resolve_orphan_guard(self, job_id: UUID) -> None:
        async with self._database.session_scope() as session:
            targets = await session.scalars(select_cleanup_targets(job_id))
            for target in targets:
                if target.storage_key is None:
                    continue
                await lock_object_reference(session, target.storage_key)
                if await self._repository.object_is_referenced(session, target.storage_key):
                    await self._repository.mark_completed(
                        session, target.id, skipped_referenced=True
                    )

    async def release_orphan_guard(self, job_id: UUID) -> None:
        async with self._database.session_scope() as session:
            await self._repository.make_job_due(session, job_id)
        self.notify()


def select_cleanup_targets(job_id: UUID):  # type: ignore[no-untyped-def]
    from app.models.cleanup import CleanupTarget

    return select(CleanupTarget).where(CleanupTarget.job_id == job_id)


class CleanupWorker:
    def __init__(
        self,
        database: DatabaseClient,
        repository: CleanupRepository,
        audit: AuditRepository,
        storage: ArtifactStorage,
        vector_store: VectorStore,
        settings: OperationalSettingsProvider,
        *,
        interval_seconds: float,
        lease_seconds: float,
        max_attempts: int,
        retention_interval_seconds: float,
        batch_size: int = 100,
    ) -> None:
        self._database = database
        self._repository = repository
        self._audit = audit
        self._storage = storage
        self._vector_store = vector_store
        self._settings = settings
        self._interval_seconds = interval_seconds
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._retention_interval_seconds = retention_interval_seconds
        self._batch_size = batch_size
        self._wake_event = asyncio.Event()
        self._next_retention_at = datetime.min.replace(tzinfo=UTC)

    def wake(self) -> None:
        self._wake_event.set()

    async def prepare_retention_once(self) -> int:
        operational = await self._settings.get_operational()
        if operational.build_retention_count is None and operational.source_retention_days is None:
            return 0
        async with self._database.session_scope() as session:
            project_ids = await self._repository.list_project_ids(session)
        created = 0
        for project_id in project_ids:
            async with self._database.session_scope() as session:
                job = await self._repository.prepare_retention_job(
                    session,
                    project_id=project_id,
                    build_retention_count=operational.build_retention_count,
                    source_retention_days=operational.source_retention_days,
                )
                if job is not None:
                    created += 1
                    await self._audit.append(
                        session,
                        actor_user_id=None,
                        event_type="cleanup.retention_scheduled",
                        entity_type="cleanup_job",
                        entity_id=job.id,
                        project_id=project_id,
                        metadata={
                            "build_retention_count": operational.build_retention_count,
                            "source_retention_days": operational.source_retention_days,
                            "target_count": job.total_targets,
                        },
                    )
        return created

    async def dispatch_once(self) -> int:
        now = datetime.now(UTC)
        if now >= self._next_retention_at:
            await self.prepare_retention_once()
            self._next_retention_at = now + timedelta(seconds=self._retention_interval_seconds)
        return await self.process_due_targets_once()

    async def process_due_targets_once(self) -> int:
        """Process leased cleanup targets without running the retention scheduler."""
        async with self._database.session_scope() as session:
            targets = await self._repository.claim_due_targets(
                session,
                limit=self._batch_size,
                lease_seconds=self._lease_seconds,
            )
        for target in targets:
            await self._process(target)
        return len(targets)

    async def _process(self, target: CleanupTargetRecord) -> None:
        try:
            async with self._database.session_scope() as session:
                if target.target_type is CleanupTargetType.OBJECT:
                    assert target.storage_key is not None
                    await lock_object_reference(session, target.storage_key)
                    referenced = await self._repository.object_is_referenced(
                        session, target.storage_key
                    )
                    if not referenced:
                        await self._storage.delete(target.storage_key)
                else:
                    assert target.collection_name is not None
                    assert target.vector_project_id is not None
                    assert target.generation_id is not None
                    referenced = await self._repository.vector_is_referenced(
                        session,
                        collection_name=target.collection_name,
                        project_id=target.vector_project_id,
                        generation_id=target.generation_id,
                    )
                    if not referenced:
                        await self._vector_store.delete_generation(
                            collection=target.collection_name,
                            project_id=target.vector_project_id,
                            generation_id=target.generation_id,
                        )
                await self._repository.mark_completed(
                    session,
                    target.id,
                    skipped_referenced=referenced,
                )
                await self._append_terminal_audit(session, target.job_id)
        except Exception as exc:
            code = exc.code.lower() if isinstance(exc, MCPlicaError) else "cleanup_target_failed"
            summary = str(exc) if isinstance(exc, MCPlicaError) else type(exc).__name__
            delay = min(
                3_600.0,
                self._interval_seconds * (2 ** max(0, target.attempt_count - 1)),
            )
            async with self._database.session_scope() as session:
                await self._repository.mark_failed(
                    session,
                    target.id,
                    error_code=code,
                    error_summary=summary,
                    max_attempts=self._max_attempts,
                    retry_delay_seconds=delay,
                )
                await self._append_terminal_audit(session, target.job_id)
            logger.warning(
                "cleanup_target_failed",
                extra={
                    "cleanup_target_id": str(target.id),
                    "cleanup_job_id": str(target.job_id),
                    "error_code": code,
                },
            )

    async def _append_terminal_audit(self, session: AsyncSession, job_id: UUID) -> None:
        job = await self._repository.get_job(session, job_id)
        if job is None or job.completed_at is None:
            return
        await self._audit.append(
            session,
            actor_user_id=job.requested_by,
            event_type=("cleanup.failed" if job.failed_targets else "cleanup.completed"),
            entity_type="cleanup_job",
            entity_id=job.id,
            project_id=job.project_id,
            request_id=job.request_id,
            metadata={
                "kind": job.kind.value,
                "total_targets": job.total_targets,
                "completed_targets": job.completed_targets,
                "skipped_targets": job.skipped_targets,
                "failed_targets": job.failed_targets,
                "last_error_code": job.last_error_code,
            },
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self.dispatch_once()
            except Exception:
                logger.exception("cleanup_dispatch_cycle_failed")
            self._wake_event.clear()
            waiters = {
                asyncio.create_task(stop_event.wait()),
                asyncio.create_task(self._wake_event.wait()),
            }
            _done, pending = await asyncio.wait(
                waiters,
                timeout=self._interval_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
