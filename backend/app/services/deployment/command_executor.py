import asyncio
import logging
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.exceptions import (
    ExecutionOwnershipError,
    InvalidStateError,
    MCPlicaError,
    NotFoundError,
)
from app.domain.deployments import (
    DeploymentStatus,
    RuntimeCommandAction,
    RuntimeCommandLeaseState,
)
from app.repositories.deployments import DeploymentRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.service import DeploymentRunner, is_retryable_deployment_error

logger = logging.getLogger("mcplica.runtime_commands.executor")


class RuntimeCommandExecutor:
    """Execute one token-fenced command and record only observed effectiveness."""

    def __init__(
        self,
        database: DatabaseClient,
        commands: RuntimeCommandRepository,
        deployments: DeploymentRepository,
        runner: DeploymentRunner,
        *,
        lease_seconds: float,
        heartbeat_seconds: float,
    ) -> None:
        self._database = database
        self._commands = commands
        self._deployments = deployments
        self._runner = runner
        self._lease_seconds = lease_seconds
        self._heartbeat_seconds = heartbeat_seconds

    async def run(self, command_id: UUID, execution_token: UUID) -> None:
        claim_started = time.monotonic()
        async with self._database.session_scope() as session:
            command = await self._commands.claim_for_execution(
                session,
                command_id,
                execution_token,
                lease_seconds=self._lease_seconds,
            )
        if command is None:
            return

        heartbeat_stop = asyncio.Event()
        ownership_lost = asyncio.Event()
        owner_task = asyncio.current_task()
        assert owner_task is not None
        heartbeat_task = asyncio.create_task(
            _heartbeat_runtime_command(
                self._database,
                self._commands,
                command_id,
                execution_token,
                heartbeat_stop,
                ownership_lost,
                owner_task,
                interval_seconds=self._heartbeat_seconds,
                lease_seconds=self._lease_seconds,
                confirmed_deadline=claim_started + self._lease_seconds,
            ),
            name=f"runtime-command-heartbeat-{command_id}",
        )

        async def checkpoint(session: AsyncSession | None = None) -> None:
            if ownership_lost.is_set():
                raise ExecutionOwnershipError("Runtime command execution ownership is stale")
            if session is not None:
                await self._commands.require_execution_owner(
                    session,
                    command_id,
                    execution_token,
                )
                return
            async with self._database.session_scope() as owned_session:
                await self._commands.require_execution_owner(
                    owned_session,
                    command_id,
                    execution_token,
                )

        try:
            # The session lock prevents a replacement attempt from issuing concurrent
            # Docker effects while a stale external call is still returning. Row-token
            # checkpoints remain authoritative for every state write.
            async with self._database.project_advisory_lock(command.project_id):
                await checkpoint()
                if command.action == RuntimeCommandAction.DEPLOY:
                    rollback_target_id = (
                        command.subject_id
                        if command.reason == "deployment.rollback_requested"
                        and command.subject_type == "deployment"
                        else None
                    )
                    restart_target_id = (
                        command.subject_id
                        if command.reason == "deployment.restarted"
                        and command.subject_type == "deployment"
                        else None
                    )
                    await self._runner.run(
                        command.deployment_id,
                        final_attempt=False,
                        rollback_target_id=rollback_target_id,
                        restart_target_id=restart_target_id,
                        execution_checkpoint=checkpoint,
                    )
                else:
                    await self._runner.stop(
                        command.deployment_id,
                        execution_checkpoint=checkpoint,
                    )
                await self._verify_and_mark_effective(
                    command_id,
                    execution_token,
                    command.action,
                    command.deployment_id,
                )
        except asyncio.CancelledError:
            if ownership_lost.is_set():
                logger.info(
                    "runtime_command_execution_ownership_lost",
                    extra={"runtime_command_id": str(command_id)},
                )
                return
            raise
        except ExecutionOwnershipError:
            logger.info(
                "runtime_command_stale_execution_discarded",
                extra={"runtime_command_id": str(command_id)},
            )
            return
        except Exception as exc:
            retryable = is_retryable_deployment_error(exc)
            code, summary = self._safe_error(exc)
            delay = min(300.0, float(2 ** min(command.attempt_count, 8)))
            try:
                async with self._database.session_scope() as session:
                    await self._commands.mark_failed(
                        session,
                        command_id,
                        execution_token,
                        error_code=code,
                        error_summary=summary,
                        retryable=retryable,
                        retry_delay_seconds=delay,
                    )
            except ExecutionOwnershipError:
                logger.info(
                    "runtime_command_stale_failure_discarded",
                    extra={"runtime_command_id": str(command_id)},
                )
                return
            logger.warning(
                "runtime_command_execution_failed",
                extra={
                    "runtime_command_id": str(command_id),
                    "deployment_id": str(command.deployment_id),
                    "error_code": code,
                    "retryable": retryable,
                },
            )
            raise
        finally:
            heartbeat_stop.set()
            await heartbeat_task

    async def _verify_and_mark_effective(
        self,
        command_id: UUID,
        execution_token: UUID,
        action: RuntimeCommandAction,
        deployment_id: UUID,
    ) -> None:
        async with self._database.session_scope() as session:
            await self._commands.require_execution_owner(
                session,
                command_id,
                execution_token,
            )
            deployment = await self._deployments.get(session, deployment_id)
            if deployment is None:
                raise NotFoundError("Runtime command deployment was not found")
            if action == RuntimeCommandAction.DEPLOY:
                effective = deployment.status == DeploymentStatus.RUNNING
            else:
                effective = deployment.status in {
                    DeploymentStatus.STOPPED,
                    DeploymentStatus.FAILED,
                }
            if not effective:
                raise InvalidStateError(
                    "Runtime command completed without reaching its requested effective state"
                )
            await self._commands.mark_effective(session, command_id, execution_token)

    @staticmethod
    def _safe_error(error: Exception) -> tuple[str, str]:
        if isinstance(error, MCPlicaError):
            return error.code.lower(), str(error)
        return "unexpected_runtime_command_error", "Runtime command failed unexpectedly"


async def _heartbeat_runtime_command(
    database: DatabaseClient,
    commands: RuntimeCommandRepository,
    command_id: UUID,
    execution_token: UUID,
    stop_event: asyncio.Event,
    ownership_lost: asyncio.Event,
    owner_task: asyncio.Task[object],
    *,
    interval_seconds: float,
    lease_seconds: float,
    confirmed_deadline: float,
) -> RuntimeCommandLeaseState:
    while not stop_event.is_set():
        remaining = confirmed_deadline - time.monotonic()
        if remaining <= 0:
            ownership_lost.set()
            owner_task.cancel()
            return RuntimeCommandLeaseState.LOST
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=min(interval_seconds, remaining),
            )
            return RuntimeCommandLeaseState.OWNED
        except TimeoutError:
            pass

        try:
            renewal_started = time.monotonic()
            async with asyncio.timeout(max(0.001, confirmed_deadline - renewal_started)):
                async with database.session_scope() as session:
                    renewal = await commands.renew_execution(
                        session,
                        command_id,
                        execution_token,
                        lease_seconds=lease_seconds,
                    )
            if renewal.state is RuntimeCommandLeaseState.LOST:
                ownership_lost.set()
                owner_task.cancel()
                return renewal.state
            assert renewal.lease_expires_at is not None
            confirmed_seconds = max(
                0.0,
                (renewal.lease_expires_at - renewal.database_now).total_seconds(),
            )
            confirmed_deadline = renewal_started + confirmed_seconds
        except Exception:
            logger.exception(
                "runtime_command_execution_heartbeat_failed",
                extra={"runtime_command_id": str(command_id)},
            )
    return RuntimeCommandLeaseState.OWNED
