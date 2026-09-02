import asyncio
from uuid import UUID

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry as RedisRetry
from rq import Queue, Retry

from app.clients.base import AsyncClient
from app.core.exceptions import ClientUnavailableError


class DeploymentQueueClient(AsyncClient):
    """Owns the blocking RQ/Redis boundary used by deployment APIs."""

    def __init__(
        self,
        redis_url: str,
        queue_name: str,
        *,
        job_timeout_seconds: int,
        max_attempts: int = 3,
        socket_connect_timeout_seconds: float = 2.0,
        socket_timeout_seconds: float = 4.0,
    ) -> None:
        if socket_connect_timeout_seconds <= 0 or socket_timeout_seconds <= 0:
            raise ValueError("Redis socket timeouts must be positive")
        self._connection = Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            redis_url,
            socket_connect_timeout=socket_connect_timeout_seconds,
            socket_timeout=socket_timeout_seconds,
            retry=RedisRetry(NoBackoff(), 0),
            retry_on_timeout=False,
        )
        self._queue = Queue(queue_name, connection=self._connection)
        self._job_timeout_seconds = job_timeout_seconds
        self._max_attempts = max_attempts

    async def health(self) -> bool:
        try:
            return await asyncio.to_thread(self._ping)
        except Exception:
            return False

    async def enqueue_runtime_command(
        self,
        command_id: UUID,
        execution_token: UUID,
        dispatch_attempt: int,
    ) -> None:
        await self._enqueue(
            "app.jobs.deploy.run_runtime_command_job",
            command_id,
            execution_token,
            job_id=f"mcplica-runtime-command-{command_id}-{dispatch_attempt}",
        )

    async def _enqueue(self, function: str, *arguments: UUID, job_id: str) -> None:
        try:
            await asyncio.to_thread(
                self._enqueue_sync,
                function,
                tuple(str(argument) for argument in arguments),
                job_id,
            )
        except Exception as exc:
            raise ClientUnavailableError("Deployment queue is unavailable") from exc

    def _ping(self) -> bool:
        return bool(self._connection.ping())  # pyright: ignore[reportUnknownMemberType]

    def _enqueue_sync(self, function: str, arguments: tuple[str, ...], job_id: str) -> None:
        retry = (
            Retry(max=self._max_attempts - 1, interval=[5, 30, 120])
            if self._max_attempts > 1
            else None
        )
        self._queue.enqueue(  # pyright: ignore[reportUnknownMemberType]
            function,
            *arguments,
            job_id=job_id,
            job_timeout=self._job_timeout_seconds,
            retry=retry,
            result_ttl=86_400,
            failure_ttl=604_800,
        )

    async def close(self) -> None:
        await asyncio.to_thread(self._connection.close)
