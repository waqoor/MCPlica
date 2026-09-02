from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateError, NotFoundError
from app.domain.builds import TERMINAL_STATUSES
from app.models.build import Build


async def require_build_execution_owner(
    session: AsyncSession,
    *,
    build_id: UUID,
    admission_token: UUID,
    allow_cancellation: bool = False,
) -> Build:
    """Lock and verify the live lease before an ownership-sensitive write."""

    database_now = await session.scalar(select(func.clock_timestamp()))
    assert database_now is not None
    build = await session.scalar(select(Build).where(Build.id == build_id).with_for_update())
    if build is None:
        raise NotFoundError("Build was not found")
    if (
        build.admission_token != admission_token
        or build.admission_lease_expires_at is None
        or build.admission_lease_expires_at <= database_now
        or build.status in TERMINAL_STATUSES
    ):
        raise InvalidStateError(
            "Build execution ownership is stale",
            details={"reason_code": "BUILD_EXECUTION_OWNERSHIP_LOST"},
        )
    if build.cancellation_requested_at is not None and not allow_cancellation:
        raise InvalidStateError(
            "Build cancellation is pending acknowledgement",
            details={"reason_code": "BUILD_CANCELLATION_REQUESTED"},
        )
    return build
