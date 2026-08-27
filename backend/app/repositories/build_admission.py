from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.build_admission import (
    BuildAdmissionClaim,
    BuildAdmissionOverview,
    BuildAdmissionState,
    QueuedBuildAdmission,
)
from app.domain.builds import TERMINAL_STATUSES, BuildStatus
from app.models.build import Build

_ADMISSION_LOCK_ID = int.from_bytes(b"MCPlicaA", byteorder="big", signed=True)


class BuildAdmissionRepository:
    """PostgreSQL-backed leases for globally bounded Build execution."""

    async def lock_dispatch(self, session: AsyncSession) -> None:
        await session.execute(select(func.pg_advisory_xact_lock(_ADMISSION_LOCK_ID)))

    async def claim_available(
        self,
        session: AsyncSession,
        *,
        configured_concurrency: int,
        lease_seconds: float,
    ) -> list[BuildAdmissionClaim]:
        await self.lock_dispatch(session)
        now = datetime.now(UTC)
        await session.execute(
            update(Build)
            .where(
                Build.admission_token.is_not(None),
                or_(
                    Build.status.in_(TERMINAL_STATUSES),
                    Build.cancellation_requested_at.is_not(None),
                    Build.admission_lease_expires_at <= now,
                ),
            )
            .values(
                admission_token=None,
                admission_enqueued_at=None,
                admission_heartbeat_at=None,
                admission_lease_expires_at=None,
                admission_released_at=now,
            )
        )
        active = int(
            await session.scalar(
                select(func.count(Build.id)).where(
                    Build.admission_token.is_not(None),
                    Build.admission_lease_expires_at > now,
                    Build.status.not_in(TERMINAL_STATUSES),
                    Build.cancellation_requested_at.is_(None),
                )
            )
            or 0
        )
        available = max(0, configured_concurrency - active)
        if available == 0:
            return []
        candidates = list(
            await session.scalars(
                select(Build)
                .where(
                    Build.status.not_in(TERMINAL_STATUSES),
                    Build.cancellation_requested_at.is_(None),
                    Build.admission_token.is_(None),
                )
                .order_by(
                    case((Build.status == BuildStatus.QUEUED, 1), else_=0),
                    Build.created_at,
                    Build.id,
                )
                .limit(available)
                .with_for_update(skip_locked=True)
            )
        )
        claims: list[BuildAdmissionClaim] = []
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        for build in candidates:
            token = uuid4()
            build.admission_token = token
            build.admission_acquired_at = now
            build.admission_enqueued_at = None
            build.admission_heartbeat_at = now
            build.admission_lease_expires_at = lease_expires_at
            build.admission_released_at = None
            build.admission_attempt_count += 1
            claims.append(
                BuildAdmissionClaim(
                    build_id=build.id,
                    project_id=build.project_id,
                    requested_by=build.requested_by,
                    status=build.status,
                    token=token,
                    attempt_count=build.admission_attempt_count,
                    lease_expires_at=lease_expires_at,
                )
            )
        await session.flush()
        return claims

    async def mark_enqueued(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        token: UUID,
    ) -> bool:
        result = await session.execute(
            update(Build)
            .where(Build.id == build_id, Build.admission_token == token)
            .values(admission_enqueued_at=datetime.now(UTC))
        )
        return bool(getattr(result, "rowcount", 0))

    async def begin_or_renew(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        token: UUID,
        lease_seconds: float,
        serialize_with_dispatch: bool = False,
    ) -> bool:
        if serialize_with_dispatch:
            await self.lock_dispatch(session)
        now = datetime.now(UTC)
        result = await session.execute(
            update(Build)
            .where(
                Build.id == build_id,
                Build.admission_token == token,
                Build.status.not_in(TERMINAL_STATUSES),
                Build.cancellation_requested_at.is_(None),
            )
            .values(
                admission_heartbeat_at=now,
                admission_lease_expires_at=now + timedelta(seconds=lease_seconds),
            )
        )
        return bool(getattr(result, "rowcount", 0))

    async def release(
        self,
        session: AsyncSession,
        *,
        build_id: UUID,
        token: UUID,
    ) -> bool:
        now = datetime.now(UTC)
        result = await session.execute(
            update(Build)
            .where(Build.id == build_id, Build.admission_token == token)
            .values(
                admission_token=None,
                admission_enqueued_at=None,
                admission_heartbeat_at=None,
                admission_lease_expires_at=None,
                admission_released_at=now,
            )
        )
        return bool(getattr(result, "rowcount", 0))

    async def overview(
        self,
        session: AsyncSession,
        *,
        configured_concurrency: int,
        limit: int,
    ) -> BuildAdmissionOverview:
        now = datetime.now(UTC)
        active_models = list(
            await session.scalars(
                select(Build)
                .where(
                    Build.admission_token.is_not(None),
                    Build.admission_lease_expires_at > now,
                    Build.status.not_in(TERMINAL_STATUSES),
                    Build.cancellation_requested_at.is_(None),
                )
                .order_by(Build.admission_acquired_at, Build.id)
            )
        )
        waiting_statement = (
            select(Build)
            .where(
                Build.status.not_in(TERMINAL_STATUSES),
                Build.cancellation_requested_at.is_(None),
                or_(
                    Build.admission_token.is_(None),
                    Build.admission_lease_expires_at <= now,
                ),
            )
            .order_by(
                case((Build.status == BuildStatus.QUEUED, 1), else_=0),
                Build.created_at,
                Build.id,
            )
        )
        waiting_count = int(
            await session.scalar(select(func.count()).select_from(waiting_statement.subquery()))
            or 0
        )
        waiting_models = list(await session.scalars(waiting_statement.limit(limit)))
        entries = [
            QueuedBuildAdmission(
                build_id=build.id,
                project_id=build.project_id,
                status=build.status,
                state=(
                    BuildAdmissionState.ADMITTED
                    if build.status is BuildStatus.QUEUED
                    else BuildAdmissionState.RUNNING
                ),
                admitted_at=build.admission_acquired_at,
                lease_expires_at=build.admission_lease_expires_at,
            )
            for build in active_models
        ]
        entries.extend(
            QueuedBuildAdmission(
                build_id=build.id,
                project_id=build.project_id,
                status=build.status,
                state=BuildAdmissionState.WAITING,
                position=position,
            )
            for position, build in enumerate(waiting_models, start=1)
        )
        return BuildAdmissionOverview(
            configured_concurrency=configured_concurrency,
            effective_concurrency=len(active_models),
            waiting_count=waiting_count,
            entries=entries,
        )
