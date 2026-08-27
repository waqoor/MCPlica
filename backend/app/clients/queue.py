import asyncio
from uuid import UUID

from redis import Redis
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
    ) -> None:
        self._connection = Redis.from_url(redis_url)  # pyright: ignore[reportUnknownMemberType]
        self._queue = Queue(queue_name, connection=self._connection)
        self._job_timeout_seconds = job_timeout_seconds
        self._max_attempts = max_attempts

    async def health(self) -> bool:
        try:
            return await asyncio.to_thread(self._ping)
        except Exception:
            return False

    async def enqueue_runtime_command(self, command_id: UUID, dispatch_attempt: int) -> None:
        await self._enqueue(
            "app.jobs.deploy.run_runtime_command_job",
            command_id,
            job_id=f"mcplica-runtime-command-{command_id}-{dispatch_attempt}",
        )

    async def _enqueue(self, function: str, deployment_id: UUID, *, job_id: str) -> None:
        try:
            await asyncio.to_thread(
                self._enqueue_sync,
                function,
                str(deployment_id),
                job_id,
            )
        except Exception as exc:
            raise ClientUnavailableError("Deployment queue is unavailable") from exc

    def _ping(self) -> bool:
        return bool(self._connection.ping())  # pyright: ignore[reportUnknownMemberType]

    def _enqueue_sync(self, function: str, deployment_id: str, job_id: str) -> None:
        retry = (
            Retry(max=self._max_attempts - 1, interval=[5, 30, 120])
            if self._max_attempts > 1
            else None
        )
        self._queue.enqueue(  # pyright: ignore[reportUnknownMemberType]
            function,
            deployment_id,
            job_id=job_id,
            job_timeout=self._job_timeout_seconds,
            retry=retry,
            result_ttl=86_400,
            failure_ttl=604_800,
        )

    async def close(self) -> None:
        await asyncio.to_thread(self._connection.close)
