from unittest.mock import Mock
from uuid import uuid4

import pytest
from rq.job import validate_job_id

import app.clients.build_queue as build_queue_module
import app.clients.queue as deployment_queue_module
from app.clients.build_queue import BuildQueueClient
from app.clients.cache import RedisClient
from app.clients.queue import DeploymentQueueClient


@pytest.mark.asyncio
async def test_build_queue_uses_rq_valid_deterministic_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = Mock()

    def queue_factory(_name: str, *, connection: object) -> Mock:
        return queue

    monkeypatch.setattr(build_queue_module, "Queue", queue_factory)
    client = BuildQueueClient(
        "redis://unused:6379/0",
        "builds",
        job_timeout_seconds=60,
        max_attempts=3,
    )
    build_id = uuid4()
    admission_token = uuid4()

    await client.enqueue_build(build_id, admission_token)

    job_id = queue.enqueue.call_args.kwargs["job_id"]
    validate_job_id(job_id)
    assert job_id == f"mcplica-build-{build_id}-{admission_token}"
    assert queue.enqueue.call_args.args[:3] == (
        "app.jobs.build.run_build_job",
        str(build_id),
        str(admission_token),
    )


@pytest.mark.asyncio
async def test_deployment_queue_uses_attempt_scoped_runtime_command_job_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = Mock()

    def queue_factory(_name: str, *, connection: object) -> Mock:
        return queue

    monkeypatch.setattr(deployment_queue_module, "Queue", queue_factory)
    client = DeploymentQueueClient(
        "redis://unused:6379/0",
        "deployments",
        job_timeout_seconds=60,
        max_attempts=3,
    )
    command_id = uuid4()
    execution_token = uuid4()

    await client.enqueue_runtime_command(command_id, execution_token, 3)
    job_id = queue.enqueue.call_args.kwargs["job_id"]
    validate_job_id(job_id)
    assert job_id == f"mcplica-runtime-command-{command_id}-3"
    assert queue.enqueue.call_args.args[:3] == (
        "app.jobs.deploy.run_runtime_command_job",
        str(command_id),
        str(execution_token),
    )


def test_all_redis_clients_apply_explicit_socket_deadlines_without_timeout_retries() -> None:
    cache = RedisClient(
        "redis://unused:6379/0",
        socket_connect_timeout_seconds=1.25,
        socket_timeout_seconds=2.5,
    )
    build = BuildQueueClient(
        "redis://unused:6379/0",
        "builds",
        job_timeout_seconds=60,
        max_attempts=3,
        socket_connect_timeout_seconds=1.25,
        socket_timeout_seconds=2.5,
    )
    deployment = DeploymentQueueClient(
        "redis://unused:6379/0",
        "deployments",
        job_timeout_seconds=60,
        max_attempts=3,
        socket_connect_timeout_seconds=1.25,
        socket_timeout_seconds=2.5,
    )

    for connection in (cache.redis, build._connection, deployment._connection):
        options = connection.connection_pool.connection_kwargs
        assert options["socket_connect_timeout"] == 1.25
        assert options["socket_timeout"] == 2.5
        assert options["retry_on_timeout"] is False
