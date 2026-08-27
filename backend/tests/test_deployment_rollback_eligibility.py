from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import InvalidStateError
from app.domain.deployments import (
    DeploymentActivationPhase,
    DeploymentActivationProof,
    DeploymentRecord,
    DeploymentStatus,
    has_successful_activation,
    is_rollback_eligible,
)
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository, LockedProjectDeploymentState
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.schemas.deployment import DeploymentRead
from app.services.deployment.command_dispatcher import RuntimeCommandDispatcher
from app.services.deployment.preflight import DeploymentPreflight
from app.services.deployment.service import DeploymentService

DEPLOYMENT_ID = UUID(int=801)
PROJECT_ID = UUID(int=802)
BUILD_ID = UUID(int=803)
OTHER_DEPLOYMENT_ID = UUID(int=804)


def _record(
    status: DeploymentStatus,
    *,
    successful: bool = False,
    legacy: bool = False,
) -> DeploymentRecord:
    now = datetime.now(UTC)
    record = DeploymentRecord(
        id=DEPLOYMENT_ID,
        project_id=PROJECT_ID,
        build_id=BUILD_ID,
        status=status,
        hostname="rollback.mcp.example.test",
        container_name="mcp-rollback",
        container_id="container-rollback" if successful else None,
        image_ref="runtime@sha256:" + "1" * 64,
        image_digest="sha256:" + "1" * 64 if successful else None,
        runtime_version="1.0.0",
        network_name="mcp-net-rollback",
        manifest_sha256="2" * 64,
        route_priority=100,
        stop_old_first=False,
        health_status="healthy" if successful else "failed",
        deployed_by=UUID(int=805),
        created_at=now - timedelta(minutes=2),
        started_at=now - timedelta(minutes=1) if successful else None,
        stopped_at=now if status is DeploymentStatus.STOPPED else None,
        failed_at=(
            now if status in {DeploymentStatus.FAILED, DeploymentStatus.UNHEALTHY} else None
        ),
        error_code=(
            "RUNTIME_STARTUP_ERROR"
            if status in {DeploymentStatus.FAILED, DeploymentStatus.UNHEALTHY}
            else None
        ),
        error_summary=None,
    )
    if not successful:
        return record.model_copy(
            update={
                "started_at": now - timedelta(minutes=1)
                if status is DeploymentStatus.FAILED
                else None,
                "activation_phase": (
                    DeploymentActivationPhase.FAILED if status is DeploymentStatus.FAILED else None
                ),
            }
        )
    if legacy:
        return record.model_copy(
            update={
                "activated_at": record.started_at,
                "activation_phase": DeploymentActivationPhase.LEGACY_RUNNING,
            }
        )
    verified_at = now - timedelta(seconds=30)
    proof = DeploymentActivationProof.verified(
        deployment_id=record.id,
        project_id=record.project_id,
        build_id=record.build_id,
        container_id=record.container_id or "",
        image_digest=record.image_digest or "",
        hostname=record.hostname,
        manifest_sha256=record.manifest_sha256,
        runtime_version=record.runtime_version,
        verified_at=verified_at,
    )
    return record.model_copy(
        update={
            "activated_at": now,
            "activation_phase": (
                DeploymentActivationPhase.FAILED
                if status is DeploymentStatus.UNHEALTHY
                else DeploymentActivationPhase.RUNNING
            ),
            "activation_verified_at": proof.verified_at,
            "activation_proof_sha256": proof.proof_sha256,
        }
    )


@pytest.mark.parametrize(
    ("record", "active_deployment_id", "expected"),
    [
        pytest.param(
            _record(DeploymentStatus.STOPPED),
            None,
            False,
            id="stopped-before-start",
        ),
        pytest.param(
            _record(DeploymentStatus.FAILED),
            None,
            False,
            id="failed-activation",
        ),
        pytest.param(
            _record(DeploymentStatus.STOPPED, successful=True),
            OTHER_DEPLOYMENT_ID,
            True,
            id="formerly-active",
        ),
        pytest.param(
            _record(DeploymentStatus.RUNNING, successful=True),
            DEPLOYMENT_ID,
            False,
            id="currently-active",
        ),
        pytest.param(
            _record(DeploymentStatus.STOPPING, successful=True),
            OTHER_DEPLOYMENT_ID,
            True,
            id="superseded",
        ),
        pytest.param(
            _record(DeploymentStatus.STOPPED, successful=True, legacy=True),
            OTHER_DEPLOYMENT_ID,
            True,
            id="verified-legacy-activation",
        ),
    ],
)
def test_rollback_eligibility_requires_activation_evidence_and_non_active_target(
    record: DeploymentRecord,
    active_deployment_id: UUID | None,
    expected: bool,
) -> None:
    assert (
        is_rollback_eligible(
            record,
            active_deployment_id=active_deployment_id,
        )
        is expected
    )
    read = DeploymentRead.from_record(
        record,
        tls=True,
        active_deployment_id=active_deployment_id,
    )
    assert read.rollback_eligible is expected


def test_activation_proof_is_bound_to_exact_runtime_identity() -> None:
    activated = _record(DeploymentStatus.STOPPED, successful=True)

    assert has_successful_activation(activated)
    assert not has_successful_activation(activated.model_copy(update={"manifest_sha256": "3" * 64}))
    assert not has_successful_activation(
        activated.model_copy(update={"runtime_version": "different"})
    )


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        yield cast(AsyncSession, object())


class _Deployments:
    def __init__(
        self,
        target: DeploymentRecord,
        *,
        active_deployment_id: UUID | None,
    ) -> None:
        self.target = target
        self.active_deployment_id = active_deployment_id

    async def lock_project(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> LockedProjectDeploymentState:
        return LockedProjectDeploymentState(
            id=project_id,
            hostname="rollback.mcp.example.test",
            is_enabled=True,
            active_build_id=None,
            active_deployment_id=self.active_deployment_id,
        )

    async def get_for_update(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> DeploymentRecord | None:
        return self.target if deployment_id == self.target.id else None


class _Dispatcher:
    def __init__(self) -> None:
        self.wake_calls = 0

    def wake(self) -> None:
        self.wake_calls += 1


def _service(
    target: DeploymentRecord,
    *,
    active_deployment_id: UUID | None,
) -> tuple[DeploymentService, _Dispatcher]:
    dispatcher = _Dispatcher()
    service = DeploymentService(
        cast(DatabaseClient, _Database()),
        cast(
            DeploymentRepository,
            _Deployments(target, active_deployment_id=active_deployment_id),
        ),
        cast(RuntimeCommandRepository, object()),
        cast(AuditRepository, object()),
        cast(RuntimeCommandDispatcher, dispatcher),
        cast(DeploymentPreflight, object()),
        Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
    )
    return service, dispatcher


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "active_deployment_id", "message"),
    [
        (
            _record(DeploymentStatus.STOPPED),
            OTHER_DEPLOYMENT_ID,
            "never a successful deployment",
        ),
        (
            _record(DeploymentStatus.RUNNING, successful=True),
            DEPLOYMENT_ID,
            "already the active deployment",
        ),
    ],
)
async def test_rollback_rejects_ineligible_target_before_creating_candidate(
    target: DeploymentRecord,
    active_deployment_id: UUID | None,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, dispatcher = _service(
        target,
        active_deployment_id=active_deployment_id,
    )
    request = AsyncMock()
    monkeypatch.setattr(service, "_request_in_session", request)

    with pytest.raises(InvalidStateError, match=message):
        await service.rollback(
            project_id=PROJECT_ID,
            target_deployment_id=target.id,
            actor_user_id=UUID(int=810),
            request_id="rollback-test",
        )

    request.assert_not_awaited()
    assert dispatcher.wake_calls == 0


@pytest.mark.asyncio
async def test_rollback_atomically_creates_candidate_from_formerly_active_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _record(DeploymentStatus.STOPPED, successful=True)
    candidate = target.model_copy(
        update={
            "id": UUID(int=811),
            "status": DeploymentStatus.PENDING,
            "started_at": None,
            "activated_at": None,
            "activation_phase": None,
            "activation_verified_at": None,
            "activation_proof_sha256": None,
            "stopped_at": None,
        }
    )
    service, dispatcher = _service(
        target,
        active_deployment_id=OTHER_DEPLOYMENT_ID,
    )
    request = AsyncMock(return_value=candidate)
    monkeypatch.setattr(service, "_request_in_session", request)

    result = await service.rollback(
        project_id=PROJECT_ID,
        target_deployment_id=target.id,
        actor_user_id=UUID(int=810),
        request_id="rollback-test",
    )

    assert result is candidate
    await_args = request.await_args
    assert await_args is not None
    assert await_args.kwargs["build_id"] == target.build_id
    assert await_args.kwargs["subject_type"] == "deployment"
    assert await_args.kwargs["subject_id"] == target.id
    assert await_args.kwargs["require_current_configuration"] is False
    assert dispatcher.wake_calls == 1
