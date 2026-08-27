import logging
from uuid import UUID

from app.clients.database import DatabaseClient
from app.core.exceptions import InvalidStateError, MCPlicaError, NotFoundError
from app.domain.deployments import (
    DeploymentStatus,
    RuntimeCommandAction,
)
from app.repositories.deployments import DeploymentRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.service import DeploymentRunner, is_retryable_deployment_error

logger = logging.getLogger("mcplica.runtime_commands.executor")


class RuntimeCommandExecutor:
    """Executes a leased command and records only observed runtime effectiveness."""

    def __init__(
        self,
        database: DatabaseClient,
        commands: RuntimeCommandRepository,
        deployments: DeploymentRepository,
        runner: DeploymentRunner,
        *,
        lease_seconds: float,
    ) -> None:
        self._database = database
        self._commands = commands
        self._deployments = deployments
        self._runner = runner
        self._lease_seconds = lease_seconds

    async def run(self, command_id: UUID) -> None:
        async with self._database.session_scope() as session:
            command = await self._commands.claim_for_execution(
                session,
                command_id,
                lease_seconds=self._lease_seconds,
            )
        if command is None:
            return
        try:
            if command.action == RuntimeCommandAction.DEPLOY:
                rollback_target_id = (
                    command.subject_id
                    if command.reason == "deployment.rollback_requested"
                    and command.subject_type == "deployment"
                    else None
                )
                await self._runner.run(
                    command.deployment_id,
                    final_attempt=False,
                    rollback_target_id=rollback_target_id,
                )
            else:
                await self._runner.stop(command.deployment_id)
            await self._verify_and_mark_effective(command_id)
        except Exception as exc:
            retryable = is_retryable_deployment_error(exc)
            code, summary = self._safe_error(exc)
            delay = min(300.0, float(2 ** min(command.attempt_count, 8)))
            async with self._database.session_scope() as session:
                await self._commands.mark_failed(
                    session,
                    command_id,
                    error_code=code,
                    error_summary=summary,
                    retryable=retryable,
                    retry_delay_seconds=delay,
                )
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

    async def _verify_and_mark_effective(self, command_id: UUID) -> None:
        async with self._database.session_scope() as session:
            command = await self._commands.get(session, command_id)
            if command is None:
                raise NotFoundError("Runtime lifecycle command was not found")
            deployment = await self._deployments.get(session, command.deployment_id)
            if deployment is None:
                raise NotFoundError("Runtime command deployment was not found")
            if command.action == RuntimeCommandAction.DEPLOY:
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
            await self._commands.mark_effective(session, command_id)

    @staticmethod
    def _safe_error(error: Exception) -> tuple[str, str]:
        if isinstance(error, MCPlicaError):
            return error.code.lower(), str(error)
        return "unexpected_runtime_command_error", "Runtime command failed unexpectedly"
