import asyncio
import logging
from uuid import UUID

from app.clients.build_queue import BuildQueueClient
from app.clients.database import DatabaseClient
from app.domain.build_admission import BuildAdmissionOverview
from app.repositories.audit import AuditRepository
from app.repositories.build_admission import BuildAdmissionRepository
from app.services.settings import OperationalSettingsProvider

logger = logging.getLogger("mcplica.build_admission")


class BuildAdmissionService:
    """Validates and renews the reservation presented by a Build worker."""

    def __init__(
        self,
        database: DatabaseClient,
        repository: BuildAdmissionRepository,
        *,
        lease_seconds: float,
    ) -> None:
        self._database = database
        self._repository = repository
        self._lease_seconds = lease_seconds

    async def begin(self, build_id: UUID, token: UUID) -> bool:
        async with self._database.session_scope() as session:
            return await self._repository.begin_or_renew(
                session,
                build_id=build_id,
                token=token,
                lease_seconds=self._lease_seconds,
                serialize_with_dispatch=True,
            )

    async def heartbeat(self, build_id: UUID, token: UUID) -> bool:
        async with self._database.session_scope() as session:
            return await self._repository.begin_or_renew(
                session,
                build_id=build_id,
                token=token,
                lease_seconds=self._lease_seconds,
            )

    async def release(self, build_id: UUID, token: UUID) -> bool:
        async with self._database.session_scope() as session:
            return await self._repository.release(
                session,
                build_id=build_id,
                token=token,
            )


class BuildAdmissionDispatcher:
    """Claims durable Build leases and delivers only admitted work to RQ."""

    def __init__(
        self,
        database: DatabaseClient,
        repository: BuildAdmissionRepository,
        queue: BuildQueueClient,
        settings: OperationalSettingsProvider,
        audit: AuditRepository,
        *,
        interval_seconds: float,
        lease_seconds: float,
    ) -> None:
        self._database = database
        self._repository = repository
        self._queue = queue
        self._settings = settings
        self._audit = audit
        self._interval_seconds = interval_seconds
        self._lease_seconds = lease_seconds
        self._wake_event = asyncio.Event()

    def wake(self) -> None:
        self._wake_event.set()

    async def overview(self, *, limit: int = 200) -> BuildAdmissionOverview:
        operational = await self._settings.get_operational()
        async with self._database.session_scope() as session:
            return await self._repository.overview(
                session,
                configured_concurrency=operational.build_concurrency,
                limit=limit,
            )

    async def dispatch_once(self) -> int:
        operational = await self._settings.get_operational()
        async with self._database.session_scope() as session:
            claims = await self._repository.claim_available(
                session,
                configured_concurrency=operational.build_concurrency,
                lease_seconds=self._lease_seconds,
            )
        enqueued = 0
        for claim in claims:
            try:
                await self._queue.enqueue_build(claim.build_id, claim.token)
            except Exception as exc:
                async with self._database.session_scope() as session:
                    released = await self._repository.release(
                        session,
                        build_id=claim.build_id,
                        token=claim.token,
                    )
                    if released:
                        await self._audit.append(
                            session,
                            actor_user_id=claim.requested_by,
                            event_type="build.admission_enqueue_failed",
                            entity_type="build",
                            entity_id=claim.build_id,
                            project_id=claim.project_id,
                            metadata={
                                "admission_attempt": claim.attempt_count,
                                "failure_category": type(exc).__name__,
                            },
                        )
                logger.warning(
                    "build_admission_enqueue_failed",
                    extra={
                        "build_id": str(claim.build_id),
                        "admission_attempt": claim.attempt_count,
                    },
                )
                continue
            async with self._database.session_scope() as session:
                marked = await self._repository.mark_enqueued(
                    session,
                    build_id=claim.build_id,
                    token=claim.token,
                )
                if marked:
                    await self._audit.append(
                        session,
                        actor_user_id=claim.requested_by,
                        event_type="build.admitted",
                        entity_type="build",
                        entity_id=claim.build_id,
                        project_id=claim.project_id,
                        metadata={
                            "admission_attempt": claim.attempt_count,
                            "configured_concurrency": operational.build_concurrency,
                            "resumed_status": claim.status.value,
                        },
                    )
                    enqueued += 1
        return enqueued

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self.dispatch_once()
            except Exception:
                logger.exception("build_admission_dispatch_cycle_failed")
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
