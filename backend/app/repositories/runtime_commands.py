from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import ExecutionOwnershipError
from app.domain.deployments import (
    RuntimeCommandAction,
    RuntimeCommandLeaseRenewal,
    RuntimeCommandLeaseState,
    RuntimeCommandRecord,
    RuntimeCommandStatus,
)
from app.models.runtime_command import RuntimeLifecycleCommand


def _to_domain(model: RuntimeLifecycleCommand) -> RuntimeCommandRecord:
    return RuntimeCommandRecord(
        id=model.id,
        sequence=model.sequence,
        project_id=model.project_id,
        deployment_id=model.deployment_id,
        build_id=model.build_id,
        transition_id=model.transition_id,
        action=model.action,
        status=model.status,
        reason=model.reason,
        subject_type=model.subject_type,
        subject_id=model.subject_id,
        idempotency_key=model.idempotency_key,
        requested_by=model.requested_by,
        request_id=model.request_id,
        attempt_count=model.attempt_count,
        retryable=model.retryable,
        next_attempt_at=model.next_attempt_at,
        dispatched_at=model.dispatched_at,
        started_at=model.started_at,
        effective_at=model.effective_at,
        failed_at=model.failed_at,
        lease_expires_at=model.lease_expires_at,
        execution_token=model.execution_token,
        last_error_code=model.last_error_code,
        last_error_summary=model.last_error_summary,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class RuntimeCommandRepository:
    @staticmethod
    async def _database_now(session: AsyncSession) -> datetime:
        now = await session.scalar(select(func.clock_timestamp()))
        assert now is not None
        return now

    async def create(
        self,
        session: AsyncSession,
        *,
        command_id: UUID,
        project_id: UUID,
        deployment_id: UUID,
        build_id: UUID,
        transition_id: UUID,
        action: RuntimeCommandAction,
        reason: str,
        subject_type: str | None,
        subject_id: UUID | None,
        requested_by: UUID,
        request_id: str | None,
        idempotency_key: str,
    ) -> RuntimeCommandRecord:
        existing = await session.scalar(
            select(RuntimeLifecycleCommand).where(
                RuntimeLifecycleCommand.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return _to_domain(existing)
        now = await self._database_now(session)
        model = RuntimeLifecycleCommand(
            id=command_id,
            project_id=project_id,
            deployment_id=deployment_id,
            build_id=build_id,
            transition_id=transition_id,
            action=action,
            status=RuntimeCommandStatus.PENDING,
            reason=reason,
            subject_type=subject_type,
            subject_id=subject_id,
            idempotency_key=idempotency_key,
            requested_by=requested_by,
            request_id=request_id,
            attempt_count=0,
            retryable=True,
            next_attempt_at=now,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def get(self, session: AsyncSession, command_id: UUID) -> RuntimeCommandRecord | None:
        model = await session.get(RuntimeLifecycleCommand, command_id)
        return _to_domain(model) if model is not None else None

    async def claim_due_for_dispatch(
        self,
        session: AsyncSession,
        *,
        limit: int,
        lease_seconds: float,
    ) -> list[RuntimeCommandRecord]:
        now = await self._database_now(session)
        predecessor = aliased(RuntimeLifecycleCommand)
        models = list(
            await session.scalars(
                select(RuntimeLifecycleCommand)
                .where(
                    RuntimeLifecycleCommand.status.in_(
                        {
                            RuntimeCommandStatus.PENDING,
                            RuntimeCommandStatus.DISPATCHED,
                            RuntimeCommandStatus.RUNNING,
                            RuntimeCommandStatus.FAILED,
                        }
                    ),
                    RuntimeLifecycleCommand.retryable.is_(True),
                    RuntimeLifecycleCommand.next_attempt_at <= now,
                    or_(
                        RuntimeLifecycleCommand.lease_expires_at.is_(None),
                        RuntimeLifecycleCommand.lease_expires_at <= now,
                    ),
                    ~exists(
                        select(predecessor.id).where(
                            predecessor.transition_id == RuntimeLifecycleCommand.transition_id,
                            predecessor.sequence < RuntimeLifecycleCommand.sequence,
                            predecessor.status != RuntimeCommandStatus.EFFECTIVE,
                        )
                    ),
                )
                .order_by(
                    RuntimeLifecycleCommand.next_attempt_at.asc(),
                    RuntimeLifecycleCommand.sequence.asc(),
                )
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        for model in models:
            model.status = RuntimeCommandStatus.DISPATCHED
            model.execution_token = uuid4()
            model.attempt_count += 1
            model.dispatched_at = now
            model.failed_at = None
            model.lease_expires_at = lease_expires_at
            model.next_attempt_at = lease_expires_at
        await session.flush()
        for model in models:
            await session.refresh(model)
        return [_to_domain(model) for model in models]

    async def claim_for_execution(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
        *,
        lease_seconds: float,
    ) -> RuntimeCommandRecord | None:
        now = await self._database_now(session)
        model = await session.scalar(
            select(RuntimeLifecycleCommand)
            .where(RuntimeLifecycleCommand.id == command_id)
            .with_for_update()
        )
        if (
            model is None
            or model.status != RuntimeCommandStatus.DISPATCHED
            or model.execution_token != execution_token
            or model.lease_expires_at is None
            or model.lease_expires_at <= now
        ):
            return None
        predecessor = aliased(RuntimeLifecycleCommand)
        predecessor_id = await session.scalar(
            select(predecessor.id)
            .where(
                predecessor.transition_id == model.transition_id,
                predecessor.sequence < model.sequence,
                predecessor.status != RuntimeCommandStatus.EFFECTIVE,
            )
            .limit(1)
        )
        if predecessor_id is not None:
            # Queue delivery may be duplicated or reordered.  A later command in
            # one lifecycle transition must never overtake an earlier stop.
            return None
        model.status = RuntimeCommandStatus.RUNNING
        model.started_at = now
        model.failed_at = None
        execution_lease_expires_at = now + timedelta(seconds=lease_seconds)
        model.lease_expires_at = execution_lease_expires_at
        model.next_attempt_at = execution_lease_expires_at
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def renew_execution(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
        *,
        lease_seconds: float,
    ) -> RuntimeCommandLeaseRenewal:
        now = await self._database_now(session)
        try:
            model = await self.require_execution_owner(
                session,
                command_id,
                execution_token,
                database_now=now,
            )
        except ExecutionOwnershipError:
            return RuntimeCommandLeaseRenewal(
                state=RuntimeCommandLeaseState.LOST,
                database_now=now,
            )
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        model.lease_expires_at = lease_expires_at
        model.next_attempt_at = lease_expires_at
        await session.flush()
        return RuntimeCommandLeaseRenewal(
            state=RuntimeCommandLeaseState.OWNED,
            database_now=now,
            lease_expires_at=lease_expires_at,
        )

    async def require_execution_owner(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
        *,
        database_now: datetime | None = None,
    ) -> RuntimeLifecycleCommand:
        now = database_now or await self._database_now(session)
        model = await session.scalar(
            select(RuntimeLifecycleCommand)
            .where(RuntimeLifecycleCommand.id == command_id)
            .with_for_update()
        )
        if (
            model is None
            or model.status != RuntimeCommandStatus.RUNNING
            or model.execution_token != execution_token
            or model.lease_expires_at is None
            or model.lease_expires_at <= now
        ):
            raise ExecutionOwnershipError(
                "Runtime command execution ownership is stale",
                details={"reason_code": "RUNTIME_COMMAND_EXECUTION_OWNERSHIP_LOST"},
            )
        predecessor = aliased(RuntimeLifecycleCommand)
        blocked = await session.scalar(
            select(
                exists(
                    select(predecessor.id).where(
                        predecessor.transition_id == model.transition_id,
                        predecessor.sequence < model.sequence,
                        predecessor.status != RuntimeCommandStatus.EFFECTIVE,
                    )
                )
            )
        )
        if blocked:
            raise ExecutionOwnershipError(
                "Runtime command predecessor is no longer effective",
                details={"reason_code": "RUNTIME_COMMAND_PREDECESSOR_NOT_EFFECTIVE"},
            )
        return model

    async def mark_effective(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
    ) -> None:
        now = await self._database_now(session)
        model = await self.require_execution_owner(
            session,
            command_id,
            execution_token,
            database_now=now,
        )
        model.status = RuntimeCommandStatus.EFFECTIVE
        model.retryable = False
        model.effective_at = now
        model.failed_at = None
        model.lease_expires_at = None
        model.execution_token = None
        model.last_error_code = None
        model.last_error_summary = None
        await session.flush()

    async def mark_failed(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
        *,
        error_code: str,
        error_summary: str,
        retryable: bool,
        retry_delay_seconds: float,
    ) -> None:
        now = await self._database_now(session)
        model = await self.require_execution_owner(
            session,
            command_id,
            execution_token,
            database_now=now,
        )
        self._apply_failure(
            model,
            now=now,
            error_code=error_code,
            error_summary=error_summary,
            retryable=retryable,
            retry_delay_seconds=retry_delay_seconds,
        )
        await session.flush()

    async def mark_dispatch_failed(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
        *,
        error_code: str,
        error_summary: str,
        retry_delay_seconds: float,
    ) -> bool:
        now = await self._database_now(session)
        model = await session.scalar(
            select(RuntimeLifecycleCommand)
            .where(RuntimeLifecycleCommand.id == command_id)
            .with_for_update()
        )
        if (
            model is None
            or model.status != RuntimeCommandStatus.DISPATCHED
            or model.execution_token != execution_token
            or model.lease_expires_at is None
            or model.lease_expires_at <= now
        ):
            return False
        self._apply_failure(
            model,
            now=now,
            error_code=error_code,
            error_summary=error_summary,
            retryable=True,
            retry_delay_seconds=retry_delay_seconds,
        )
        await session.flush()
        return True

    @staticmethod
    def _apply_failure(
        model: RuntimeLifecycleCommand,
        *,
        now: datetime,
        error_code: str,
        error_summary: str,
        retryable: bool,
        retry_delay_seconds: float,
    ) -> None:
        model.status = RuntimeCommandStatus.FAILED
        model.retryable = retryable
        model.failed_at = now
        model.lease_expires_at = None
        model.execution_token = None
        model.next_attempt_at = now + timedelta(seconds=retry_delay_seconds)
        model.last_error_code = error_code[:128]
        model.last_error_summary = error_summary[:2_000]

    async def latest_for_subject(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> RuntimeCommandRecord | None:
        model = await session.scalar(
            select(RuntimeLifecycleCommand)
            .where(
                RuntimeLifecycleCommand.project_id == project_id,
                RuntimeLifecycleCommand.subject_type == subject_type,
                RuntimeLifecycleCommand.subject_id == subject_id,
            )
            .order_by(RuntimeLifecycleCommand.sequence.desc())
            .limit(1)
        )
        return _to_domain(model) if model is not None else None

    async def list_transition(
        self,
        session: AsyncSession,
        transition_id: UUID,
    ) -> list[RuntimeCommandRecord]:
        models = await session.scalars(
            select(RuntimeLifecycleCommand)
            .where(RuntimeLifecycleCommand.transition_id == transition_id)
            .order_by(RuntimeLifecycleCommand.sequence.asc())
        )
        return [_to_domain(model) for model in models]
