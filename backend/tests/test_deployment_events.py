from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from fastapi import Request

from app.api.deployments import deployment_events
from app.core.exceptions import NotFoundError
from app.domain.deployments import DeploymentRecord, DeploymentStatus
from app.services.deployment.service import DeploymentService


def _record(status: DeploymentStatus = DeploymentStatus.RUNNING) -> DeploymentRecord:
    now = datetime(2026, 8, 27, tzinfo=UTC)
    return DeploymentRecord(
        id=UUID(int=1),
        project_id=UUID(int=2),
        build_id=UUID(int=3),
        status=status,
        hostname="runtime.example.test",
        container_name="runtime",
        container_id="container",
        image_ref="runtime:1",
        image_digest="sha256:image",
        runtime_version="1.0.0",
        network_name="runtime-network",
        manifest_sha256="a" * 64,
        route_priority=1,
        stop_old_first=False,
        health_status="healthy",
        deployed_by=UUID(int=4),
        created_at=now,
        started_at=now,
        activated_at=now,
        stopped_at=None,
        failed_at=None,
        error_code=None,
        error_summary=None,
    )


class _Service:
    def __init__(self, record: DeploymentRecord | None) -> None:
        self.record = record
        self.get_calls = 0

    async def get(self, deployment_id: UUID) -> DeploymentRecord:
        self.get_calls += 1
        if self.record is None or deployment_id != self.record.id:
            raise NotFoundError("Deployment not found")
        return self.record

    async def active_deployment_id(self, project_id: UUID) -> UUID | None:
        return self.record.id if self.record and self.record.project_id == project_id else None


class _Request:
    def __init__(self, disconnected: bool) -> None:
        self.disconnected = disconnected
        self.app = SimpleNamespace(
            state=SimpleNamespace(settings=SimpleNamespace(traefik_tls=True))
        )

    async def is_disconnected(self) -> bool:
        return self.disconnected


@pytest.mark.asyncio
async def test_missing_deployment_fails_before_stream_headers_are_created() -> None:
    service = _Service(None)
    with pytest.raises(NotFoundError):
        await deployment_events(
            UUID(int=1),
            cast(Request, _Request(False)),
            cast(object, None),
            cast(DeploymentService, service),
        )
    assert service.get_calls == 1


@pytest.mark.asyncio
async def test_existing_terminal_deployment_seeds_one_event_without_refetch() -> None:
    service = _Service(_record())
    response = await deployment_events(
        UUID(int=1),
        cast(Request, _Request(False)),
        cast(object, None),
        cast(DeploymentService, service),
    )
    chunks = [chunk async for chunk in response.body_iterator]
    assert len(chunks) == 1
    assert '"status":"running"' in cast(str, chunks[0])
    assert service.get_calls == 1


@pytest.mark.asyncio
async def test_disconnected_client_stops_without_emitting_or_polling() -> None:
    service = _Service(_record(DeploymentStatus.PENDING))
    response = await deployment_events(
        UUID(int=1),
        cast(Request, _Request(True)),
        cast(object, None),
        cast(DeploymentService, service),
    )
    assert [chunk async for chunk in response.body_iterator] == []
    assert service.get_calls == 1
