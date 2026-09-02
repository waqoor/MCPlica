from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import DeployabilityError
from app.domain.deployments import DeployableBuildRecord
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository, LockedProjectDeploymentState
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.command_dispatcher import RuntimeCommandDispatcher
from app.services.deployment.preflight import DeploymentPreflight
from app.services.deployment.service import DeploymentService

PROJECT_ID = UUID(int=301)
BUILD_ID = UUID(int=302)
ACTOR_ID = UUID(int=303)


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        yield cast(AsyncSession, object())


class _Deployments:
    def __init__(self) -> None:
        self.create_calls = 0

    async def lock_project(
        self, session: AsyncSession, project_id: UUID
    ) -> LockedProjectDeploymentState:
        assert project_id == PROJECT_ID
        return LockedProjectDeploymentState(
            id=PROJECT_ID,
            hostname="preflight.mcp.localhost",
            is_enabled=True,
            active_build_id=None,
            active_deployment_id=None,
        )

    async def has_in_progress(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        transition_stopping_ids: set[UUID] | None = None,
    ) -> bool:
        del transition_stopping_ids
        return False

    async def get_build(self, session: AsyncSession, build_id: UUID) -> DeployableBuildRecord:
        assert build_id == BUILD_ID
        return DeployableBuildRecord(
            id=BUILD_ID,
            project_id=PROJECT_ID,
            status="READY",
            runtime_manifest_max_bytes=10_000_000,
            manifest_sha256="a" * 64,
            manifest_storage_key="manifests/build.json",
        )

    async def next_route_priority(self, session: AsyncSession, project_id: UUID) -> int:
        raise AssertionError("Route allocation must not run after a failed preflight")

    async def create(self, *args: object, **kwargs: object) -> None:
        self.create_calls += 1
        raise AssertionError("A failed preflight must not create a deployment")


class _RejectingPreflight:
    async def validate(self, *args: object, **kwargs: object) -> None:
        raise DeployabilityError(
            "Inbound MCP authentication is incomplete or incompatible",
            details={
                "reason_code": "ACCESS_CONFIG_INVALID",
                "field": "access",
                "remediation": "Add an unexpired static token.",
            },
        )


class _Dispatcher:
    def __init__(self) -> None:
        self.wake_calls = 0

    def wake(self) -> None:
        self.wake_calls += 1


@pytest.mark.asyncio
async def test_failed_preflight_creates_no_deployment_outbox_or_dispatch() -> None:
    deployments = _Deployments()
    dispatcher = _Dispatcher()
    service = DeploymentService(
        cast(DatabaseClient, _Database()),
        cast(DeploymentRepository, deployments),
        cast(RuntimeCommandRepository, object()),
        cast(AuditRepository, object()),
        cast(RuntimeCommandDispatcher, dispatcher),
        cast(DeploymentPreflight, _RejectingPreflight()),
        Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
    )

    with pytest.raises(DeployabilityError) as error:
        await service.request(
            project_id=PROJECT_ID,
            build_id=BUILD_ID,
            actor_user_id=ACTOR_ID,
            request_id="preflight-request",
        )

    assert error.value.status_code == 409
    assert error.value.code == "DEPLOYABILITY_PREFLIGHT_FAILED"
    assert error.value.details["field"] == "access"
    assert deployments.create_calls == 0
    assert dispatcher.wake_calls == 0
