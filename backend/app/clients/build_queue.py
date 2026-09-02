import asyncio
from uuid import UUID

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry as RedisRetry
from rq import Queue, Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus

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

    def _ping(self) -> bool:
        return bool(self._connection.ping())  # pyright: ignore[reportUnknownMemberType]

    async def enqueue_build(self, build_id: UUID, admission_token: UUID) -> None:
        try:
            await asyncio.to_thread(
                self._enqueue_sync,
                str(build_id),
                str(admission_token),
            )
        except Exception as exc:
            raise ClientUnavailableError("Build queue is unavailable") from exc

    def _enqueue_sync(self, build_id: str, admission_token: str) -> None:
        retry = (
            Retry(max=self._max_attempts - 1, interval=[5, 30, 120])
            if self._max_attempts > 1
            else None
        )
        self._queue.enqueue(  # pyright: ignore[reportUnknownMemberType]
            "app.jobs.build.run_build_job",
            build_id,
            admission_token,
            job_id=f"mcplica-build-{build_id}-{admission_token}",
            job_timeout=self._job_timeout_seconds,
            retry=retry,
            meta={"max_attempts": self._max_attempts},
            result_ttl=86_400,
            failure_ttl=604_800,
        )

    async def cancel_queued_build(self, build_id: UUID, admission_token: UUID | None) -> bool:
        """Cancel work that has not started; running jobs stop cooperatively via PostgreSQL."""
        if admission_token is None:
            return False
        try:
            return await asyncio.to_thread(
                self._cancel_queued_sync,
                str(build_id),
                str(admission_token),
            )
        except Exception as exc:
            raise ClientUnavailableError("Build queue is unavailable") from exc

    def _cancel_queued_sync(self, build_id: str, admission_token: str) -> bool:
        try:
            job = Job.fetch(  # pyright: ignore[reportUnknownMemberType]
                f"mcplica-build-{build_id}-{admission_token}",
                connection=self._connection,
            )
        except NoSuchJobError:
            return False
        status = job.get_status(refresh=True)
        if status not in {
            JobStatus.QUEUED,
            JobStatus.DEFERRED,
            JobStatus.SCHEDULED,
        }:
            return False
        job.cancel(enqueue_dependents=False)
        return True

    async def close(self) -> None:
        await asyncio.to_thread(self._connection.close)
