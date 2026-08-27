import asyncio
import logging
from uuid import UUID

from app.clients.database import DatabaseClient
from app.clients.queue import DeploymentQueueClient
from app.core.exceptions import MCPlicaError
from app.repositories.runtime_commands import RuntimeCommandRepository

logger = logging.getLogger("mcplica.runtime_commands.dispatcher")


class RuntimeCommandDispatcher:
    """Durably bridges PostgreSQL lifecycle commands to the best-effort RQ transport."""

    def __init__(
        self,
        database: DatabaseClient,
        commands: RuntimeCommandRepository,
        queue: DeploymentQueueClient,
        *,
        interval_seconds: float,
        lease_seconds: float,
        batch_size: int = 100,
    ) -> None:
        self._database = database
        self._commands = commands
        self._queue = queue
        self._interval_seconds = interval_seconds
        self._lease_seconds = lease_seconds
        self._batch_size = batch_size
        self._wake_event = asyncio.Event()

    def wake(self) -> None:
        self._wake_event.set()

    async def dispatch_once(self) -> int:
        async with self._database.session_scope() as session:
            commands = await self._commands.claim_due_for_dispatch(
                session,
                limit=self._batch_size,
                lease_seconds=self._lease_seconds,
            )
        for command in commands:
            try:
                await self._queue.enqueue_runtime_command(command.id, command.attempt_count)
            except MCPlicaError as exc:
                await self._record_dispatch_failure(command.id, exc)
            except Exception as exc:  # pragma: no cover - queue boundary safety net
                await self._record_dispatch_failure(command.id, exc)
        return len(commands)

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self.dispatch_once()
            except Exception:
                logger.exception("runtime_command_dispatch_cycle_failed")
            self._wake_event.clear()
            waiters = {
                asyncio.create_task(stop_event.wait()),
                asyncio.create_task(self._wake_event.wait()),
            }
            done, pending = await asyncio.wait(
                waiters,
                timeout=self._interval_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                _ = task.result()

    async def _record_dispatch_failure(self, command_id: UUID, error: Exception) -> None:
        code = (
            error.code.lower() if isinstance(error, MCPlicaError) else "runtime_queue_unavailable"
        )
        summary = str(error) if isinstance(error, MCPlicaError) else "Runtime queue is unavailable"
        async with self._database.session_scope() as session:
            await self._commands.mark_failed(
                session,
                command_id,
                error_code=code,
                error_summary=summary,
                retryable=True,
                retry_delay_seconds=self._interval_seconds,
            )
        logger.warning(
            "runtime_command_dispatch_failed",
            extra={"runtime_command_id": str(command_id), "error_code": code},
        )
