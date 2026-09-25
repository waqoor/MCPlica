import os

from redis.client import Pipeline
from rq import Worker


class RegistrationRecoveringWorker(Worker):
    """Repair missing healthcheck metadata as the owning RQ worker progresses."""

    _registration_owner_pid: int | None = None

    def register_birth(self) -> None:
        super().register_birth()
        self._registration_owner_pid = os.getpid()

    def register_death(self) -> None:
        # Revoke ownership even when Redis is unavailable during shutdown.
        self._registration_owner_pid = None
        super().register_death()

    @property
    def dequeue_timeout(self) -> int:
        # RQ's default idle wait is 405s, longer than Compose's unhealthy window.
        # Wake the normal work loop sooner without shortening worker expiry.
        return min(super().dequeue_timeout, 30)

    def heartbeat(self, timeout: int | None = None, pipeline: Pipeline | None = None) -> None:
        if pipeline is None:
            # Keep metadata writes and RQ's expiry in the same transaction.
            with self.connection.pipeline() as heartbeat_pipeline:  # pyright: ignore[reportUnknownMemberType]
                self.heartbeat(timeout=timeout, pipeline=heartbeat_pipeline)
                heartbeat_pipeline.execute()
            return

        super().heartbeat(timeout=timeout, pipeline=pipeline)
        if (
            self._registration_owner_pid != os.getpid()
            or self.pid != os.getpid()
            or self.is_horse
            or self.hostname is None
        ):
            return

        # RQ 2.12's maintain_heartbeats() inspects result[0] for its HSET.
        # Append only; never execute a caller-owned pipeline or rewrite birth/state.
        pipeline.hsetnx(self.key, "hostname", self.hostname)
        pipeline.hsetnx(self.key, "queues", ",".join(self.queue_names()))
