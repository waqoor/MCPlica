from unittest.mock import Mock
from uuid import uuid4

import pytest
from rq.job import validate_job_id

import app.clients.build_queue as build_queue_module
import app.clients.queue as deployment_queue_module
from app.clients.build_queue import BuildQueueClient
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

    await client.enqueue_build(build_id)

    job_id = queue.enqueue.call_args.kwargs["job_id"]
    validate_job_id(job_id)
    assert job_id == f"mcplica-build-{build_id}"


@pytest.mark.asyncio
async def test_deployment_queue_uses_rq_valid_deterministic_job_ids(
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
    deployment_id = uuid4()

    await client.enqueue_deploy(deployment_id)
    deploy_job_id = queue.enqueue.call_args.kwargs["job_id"]
    validate_job_id(deploy_job_id)
    assert deploy_job_id == f"mcplica-deploy-{deployment_id}"

    await client.enqueue_stop(deployment_id)
    stop_job_id = queue.enqueue.call_args.kwargs["job_id"]
    validate_job_id(stop_job_id)
    assert stop_job_id == f"mcplica-stop-{deployment_id}"
