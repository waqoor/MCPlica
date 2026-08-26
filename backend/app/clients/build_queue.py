import asyncio
from uuid import UUID

from redis import Redis
from rq import Queue, Retry

from app.clients.base import AsyncClient
from app.core.exceptions import ClientUnavailableError


class BuildQueueClient(AsyncClient):
    """Owns blocking Redis/RQ interaction for build orchestration."""

    def __init__(
        self,
        redis_url: str,
        queue_name: str,
        *,
        job_timeout_seconds: int,
        max_attempts: int,
    ) -> None:
        self._connection = Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            redis_url
        )
        self._queue = Queue(queue_name, connection=self._connection)
        self._job_timeout_seconds = job_timeout_seconds
        self._max_attempts = max_attempts

    async def health(self) -> bool:
        try:
            return await asyncio.to_thread(self._ping)
        except Exception:
            return False

    def _ping(self) -> bool:
        return bool(self._connection.ping())  # pyright: ignore[reportUnknownMemberType]

    async def enqueue_build(self, build_id: UUID) -> None:
        try:
            await asyncio.to_thread(self._enqueue_sync, str(build_id))
        except Exception as exc:
            raise ClientUnavailableError("Build queue is unavailable") from exc

    def _enqueue_sync(self, build_id: str) -> None:
        retry = (
            Retry(max=self._max_attempts - 1, interval=[5, 30, 120])
            if self._max_attempts > 1
            else None
        )
        self._queue.enqueue(  # pyright: ignore[reportUnknownMemberType]
            "app.jobs.build.run_build_job",
            build_id,
            job_id=f"mcplica-build-{build_id}",
            job_timeout=self._job_timeout_seconds,
            retry=retry,
            meta={"max_attempts": self._max_attempts},
            result_ttl=86_400,
            failure_ttl=604_800,
        )

    async def close(self) -> None:
        await asyncio.to_thread(self._connection.close)
