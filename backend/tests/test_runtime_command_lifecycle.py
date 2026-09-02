import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.clients.queue import DeploymentQueueClient
from app.core.exceptions import (
    ClientUnavailableError,
    PermissionDeniedError,
    RuntimeHealthError,
)
from app.domain.auth import UserRole
from app.domain.deployments import (
    DeploymentRecord,
    DeploymentStatus,
    RuntimeCommandAction,
    RuntimeCommandLeaseRenewal,
    RuntimeCommandLeaseState,
    RuntimeCommandRecord,
    RuntimeCommandStatus,
)
from app.domain.projects import ProjectRecord
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.projects import ProjectRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.command_dispatcher import RuntimeCommandDispatcher
from app.services.deployment.command_executor import (
    RuntimeCommandExecutor,
    _heartbeat_runtime_command,
)
from app.services.deployment.service import DeploymentRunner
from app.services.projects import ProjectDeploymentLifecycle, ProjectService
from app.services.settings import OperationalSettingsProvider, OperationalSettingsView


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        yield cast(AsyncSession, object())

    @asynccontextmanager
    async def project_advisory_lock(self, project_id: UUID) -> AsyncGenerator[None]:
        del project_id
        yield


def _command(
    *,
    status: RuntimeCommandStatus = RuntimeCommandStatus.PENDING,
    attempt_count: int = 1,
) -> RuntimeCommandRecord:
    now = datetime.now(UTC)
    return RuntimeCommandRecord(
        id=UUID(int=1),
        sequence=1,
        project_id=UUID(int=2),
        deployment_id=UUID(int=3),
        build_id=UUID(int=4),
        transition_id=UUID(int=5),
        action=RuntimeCommandAction.DEPLOY,
        status=status,
        reason="authorization_changed",
        subject_type="project_credential",
        subject_id=UUID(int=6),
        idempotency_key="deployment:3:deploy",
        requested_by=UUID(int=7),
        request_id="request-1",
        attempt_count=attempt_count,
        retryable=True,
        next_attempt_at=now,
        dispatched_at=now,
        started_at=now if status == RuntimeCommandStatus.RUNNING else None,
        effective_at=None,
        failed_at=None,
        lease_expires_at=(
            now + timedelta(seconds=60)
            if status in {RuntimeCommandStatus.DISPATCHED, RuntimeCommandStatus.RUNNING}
            else None
        ),
        execution_token=(
            UUID(int=9)
            if status in {RuntimeCommandStatus.DISPATCHED, RuntimeCommandStatus.RUNNING}
            else None
        ),
        last_error_code=None,
        last_error_summary=None,
        created_at=now,
        updated_at=now,
    )


class _DispatchCommands:
    def __init__(self, command: RuntimeCommandRecord) -> None:
        self.command = command
        self.failures: list[tuple[str, bool]] = []
        self.claims = 0

    async def claim_due_for_dispatch(
        self, *args: object, **kwargs: object
    ) -> list[RuntimeCommandRecord]:
        del args, kwargs
        self.claims += 1
        if self.command.status == RuntimeCommandStatus.EFFECTIVE:
            return []
        return [
            self.command.model_copy(
                update={
                    "status": RuntimeCommandStatus.DISPATCHED,
                    "attempt_count": self.claims,
                    "execution_token": UUID(int=20 + self.claims),
                    "lease_expires_at": datetime.now(UTC) + timedelta(seconds=5),
                }
            )
        ]

    async def mark_dispatch_failed(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
        *,
        error_code: str,
        error_summary: str,
        retry_delay_seconds: float,
    ) -> bool:
        del session, command_id, execution_token, error_summary, retry_delay_seconds
        self.failures.append((error_code, True))
        return True


class _Queue:
    def __init__(self, *, fail_first: bool) -> None:
        self.fail_first = fail_first
        self.calls: list[tuple[UUID, UUID, int]] = []

    async def enqueue_runtime_command(
        self, command_id: UUID, execution_token: UUID, attempt: int
    ) -> None:
        self.calls.append((command_id, execution_token, attempt))
        if self.fail_first:
            self.fail_first = False
            raise ClientUnavailableError("queue unavailable")


async def test_enqueue_failure_remains_durable_and_restart_reconciliation_retries() -> None:
    commands = _DispatchCommands(_command())
    queue = _Queue(fail_first=True)
    first_process = RuntimeCommandDispatcher(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, commands),
        cast(DeploymentQueueClient, queue),
        interval_seconds=0.1,
        lease_seconds=5,
    )
    await first_process.dispatch_once()

    assert commands.failures == [("client_unavailable", True)]
    assert queue.calls == [(UUID(int=1), UUID(int=21), 1)]

    restarted_process = RuntimeCommandDispatcher(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, commands),
        cast(DeploymentQueueClient, queue),
        interval_seconds=0.1,
        lease_seconds=5,
    )
    await restarted_process.dispatch_once()

    assert queue.calls == [
        (UUID(int=1), UUID(int=21), 1),
        (UUID(int=1), UUID(int=22), 2),
    ]


async def test_expired_running_lease_is_redispatched_after_worker_crash() -> None:
    commands = _DispatchCommands(_command(status=RuntimeCommandStatus.RUNNING))
    queue = _Queue(fail_first=False)
    restarted_process = RuntimeCommandDispatcher(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, commands),
        cast(DeploymentQueueClient, queue),
        interval_seconds=0.1,
        lease_seconds=5,
    )

    assert await restarted_process.dispatch_once() == 1
    assert queue.calls == [(UUID(int=1), UUID(int=21), 1)]


async def test_runtime_heartbeat_database_outage_stops_at_confirmed_deadline() -> None:
    class _UnavailableCommands:
        async def renew_execution(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            raise ClientUnavailableError("database unavailable")

    owner = asyncio.create_task(asyncio.sleep(60))
    stop = asyncio.Event()
    lost = asyncio.Event()
    state = await _heartbeat_runtime_command(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, _UnavailableCommands()),
        UUID(int=1),
        UUID(int=9),
        stop,
        lost,
        owner,
        interval_seconds=0.005,
        lease_seconds=0.03,
        confirmed_deadline=time.monotonic() + 0.03,
    )

    assert state is RuntimeCommandLeaseState.LOST
    assert lost.is_set()
    with pytest.raises(asyncio.CancelledError):
        await owner


async def test_runtime_heartbeat_renews_from_database_time_until_stopped() -> None:
    stop = asyncio.Event()

    class _RenewingCommands:
        async def renew_execution(
            self, *args: object, **kwargs: object
        ) -> RuntimeCommandLeaseRenewal:
            del args, kwargs
            now = datetime.now(UTC)
            stop.set()
            return RuntimeCommandLeaseRenewal(
                state=RuntimeCommandLeaseState.OWNED,
                database_now=now,
                lease_expires_at=now + timedelta(seconds=1),
            )

    owner = asyncio.create_task(asyncio.sleep(60))
    lost = asyncio.Event()
    state = await _heartbeat_runtime_command(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, _RenewingCommands()),
        UUID(int=1),
        UUID(int=9),
        stop,
        lost,
        owner,
        interval_seconds=0.001,
        lease_seconds=1,
        confirmed_deadline=time.monotonic() + 1,
    )

    assert state is RuntimeCommandLeaseState.OWNED
    assert lost.is_set() is False
    owner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owner


async def test_runtime_heartbeat_cancels_owner_when_database_rejects_token() -> None:
    class _LostCommands:
        async def renew_execution(
            self, *args: object, **kwargs: object
        ) -> RuntimeCommandLeaseRenewal:
            del args, kwargs
            now = datetime.now(UTC)
            return RuntimeCommandLeaseRenewal(
                state=RuntimeCommandLeaseState.LOST,
                database_now=now,
            )

    owner = asyncio.create_task(asyncio.sleep(60))
    stop = asyncio.Event()
    lost = asyncio.Event()
    state = await _heartbeat_runtime_command(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, _LostCommands()),
        UUID(int=1),
        UUID(int=9),
        stop,
        lost,
        owner,
        interval_seconds=0.001,
        lease_seconds=1,
        confirmed_deadline=time.monotonic() + 1,
    )

    assert state is RuntimeCommandLeaseState.LOST
    assert lost.is_set()
    with pytest.raises(asyncio.CancelledError):
        await owner


def _deployment(status: DeploymentStatus) -> DeploymentRecord:
    now = datetime.now(UTC)
    return DeploymentRecord(
        id=UUID(int=3),
        project_id=UUID(int=2),
        build_id=UUID(int=4),
        status=status,
        hostname="project.mcp.example.com",
        container_name="mcp-project",
        container_id="container" if status == DeploymentStatus.RUNNING else None,
        image_ref="runtime@sha256:" + "a" * 64,
        image_digest="sha256:" + "b" * 64 if status == DeploymentStatus.RUNNING else None,
        runtime_version="1.0.0",
        network_name="mcp-project",
        manifest_sha256="c" * 64,
        route_priority=1,
        stop_old_first=True,
        health_status="healthy" if status == DeploymentStatus.RUNNING else None,
        deployed_by=UUID(int=7),
        created_at=now,
        started_at=now if status == DeploymentStatus.RUNNING else None,
        activated_at=now if status == DeploymentStatus.RUNNING else None,
        stopped_at=None,
        failed_at=None,
        error_code=None,
        error_summary=None,
    )


class _ExecutionCommands:
    def __init__(self) -> None:
        self.command = _command(status=RuntimeCommandStatus.DISPATCHED)
        self.effective = False
        self.failure: tuple[str, bool] | None = None

    async def claim_for_execution(self, *args: object, **kwargs: object):
        del args, kwargs
        return (
            None
            if self.effective
            else self.command.model_copy(
                update={
                    "status": RuntimeCommandStatus.RUNNING,
                    "lease_expires_at": datetime.now(UTC) + timedelta(seconds=60),
                }
            )
        )

    async def get(self, *args: object, **kwargs: object):
        del args, kwargs
        return self.command

    async def mark_effective(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.effective = True

    async def require_execution_owner(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    async def mark_failed(
        self,
        session: AsyncSession,
        command_id: UUID,
        execution_token: UUID,
        *,
        error_code: str,
        error_summary: str,
        retryable: bool,
        retry_delay_seconds: float,
    ) -> None:
        del session, command_id, execution_token, error_summary, retry_delay_seconds
        self.failure = (error_code, retryable)


class _ExecutionDeployments:
    def __init__(self) -> None:
        self.status = DeploymentStatus.PENDING

    async def get(self, *args: object, **kwargs: object) -> DeploymentRecord:
        del args, kwargs
        return _deployment(self.status)


class _Runner:
    def __init__(self, deployments: _ExecutionDeployments, error: Exception | None = None) -> None:
        self.deployments = deployments
        self.error = error
        self.calls = 0
        self.rollback_target_ids: list[UUID | None] = []

    async def run(
        self,
        deployment_id: UUID,
        *,
        final_attempt: bool,
        rollback_target_id: UUID | None = None,
        execution_checkpoint: object | None = None,
    ) -> None:
        del deployment_id, final_attempt, execution_checkpoint
        self.calls += 1
        self.rollback_target_ids.append(rollback_target_id)
        if self.error is not None:
            raise self.error
        self.deployments.status = DeploymentStatus.RUNNING

    async def stop(
        self, deployment_id: UUID, *, execution_checkpoint: object | None = None
    ) -> None:
        del deployment_id, execution_checkpoint
        self.calls += 1
        self.deployments.status = DeploymentStatus.STOPPED


async def test_command_replay_is_idempotent_after_exact_effect_acknowledgement() -> None:
    commands = _ExecutionCommands()
    deployments = _ExecutionDeployments()
    runner = _Runner(deployments)
    executor = RuntimeCommandExecutor(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, commands),
        cast(DeploymentRepository, deployments),
        cast(DeploymentRunner, runner),
        lease_seconds=60,
        heartbeat_seconds=10,
    )

    await executor.run(UUID(int=1), UUID(int=9))
    await executor.run(UUID(int=1), UUID(int=9))

    assert commands.effective is True
    assert runner.calls == 1
    assert runner.rollback_target_ids == [None]


async def test_stop_command_is_effective_only_after_runtime_is_stopped() -> None:
    commands = _ExecutionCommands()
    commands.command = commands.command.model_copy(update={"action": RuntimeCommandAction.STOP})
    deployments = _ExecutionDeployments()
    runner = _Runner(deployments)
    executor = RuntimeCommandExecutor(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, commands),
        cast(DeploymentRepository, deployments),
        cast(DeploymentRunner, runner),
        lease_seconds=60,
        heartbeat_seconds=10,
    )

    await executor.run(UUID(int=1), UUID(int=9))

    assert commands.effective is True
    assert deployments.status is DeploymentStatus.STOPPED
    assert runner.calls == 1


async def test_rollback_command_passes_its_durable_target_to_worker_preflight() -> None:
    commands = _ExecutionCommands()
    rollback_target_id = UUID(int=8)
    commands.command = commands.command.model_copy(
        update={
            "reason": "deployment.rollback_requested",
            "subject_type": "deployment",
            "subject_id": rollback_target_id,
        }
    )
    deployments = _ExecutionDeployments()
    runner = _Runner(deployments)
    executor = RuntimeCommandExecutor(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, commands),
        cast(DeploymentRepository, deployments),
        cast(DeploymentRunner, runner),
        lease_seconds=60,
        heartbeat_seconds=10,
    )

    await executor.run(UUID(int=1), UUID(int=9))

    assert commands.effective is True
    assert runner.rollback_target_ids == [rollback_target_id]


async def test_asynchronous_replacement_failure_is_retryable_and_never_effective() -> None:
    commands = _ExecutionCommands()
    deployments = _ExecutionDeployments()
    runner = _Runner(deployments, RuntimeHealthError("candidate unhealthy"))
    executor = RuntimeCommandExecutor(
        cast(DatabaseClient, _Database()),
        cast(RuntimeCommandRepository, commands),
        cast(DeploymentRepository, deployments),
        cast(DeploymentRunner, runner),
        lease_seconds=60,
        heartbeat_seconds=10,
    )

    with pytest.raises(RuntimeHealthError):
        await executor.run(UUID(int=1), UUID(int=9))

    assert commands.effective is False
    assert commands.failure == ("runtime_health_error", True)


class _TransactionalDatabase:
    def __init__(self) -> None:
        self.state: dict[str, object] = {"enabled": True, "command": False}

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        snapshot = deepcopy(self.state)
        try:
            yield cast(AsyncSession, object())
        except Exception:
            self.state = snapshot
            raise


def _project(enabled: bool) -> ProjectRecord:
    now = datetime.now(UTC)
    return ProjectRecord(
        id=UUID(int=2),
        name="Project",
        slug="project",
        description=None,
        default_base_url="https://api.example.com",
        active_server_ref=None,
        server_mappings={},
        mcp_hostname="project.mcp.example.com",
        is_enabled=enabled,
        active_build_id=UUID(int=4),
        active_deployment_id=UUID(int=3),
        created_by=UUID(int=7),
        created_at=now,
        updated_at=now,
    )


class _Projects:
    def __init__(self, database: _TransactionalDatabase) -> None:
        self.database = database

    async def lock(self, *args: object, **kwargs: object) -> ProjectRecord:
        del args, kwargs
        return _project(bool(self.database.state["enabled"]))

    async def update(
        self,
        session: AsyncSession,
        project_id: UUID,
        values: dict[str, object],
    ) -> ProjectRecord:
        del session, project_id
        self.database.state["enabled"] = values.get("is_enabled", self.database.state["enabled"])
        return _project(bool(self.database.state["enabled"]))


class _FailingLifecycle:
    def __init__(self, database: _TransactionalDatabase) -> None:
        self.database = database

    async def schedule_stop_project(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.database.state["command"] = True
        raise RuntimeError("outbox insert failed")

    def notify_runtime_commands(self) -> None:
        raise AssertionError("a rolled-back transaction must not notify the dispatcher")


class _NoopLifecycle:
    async def schedule_stop_project(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("metadata edits must not schedule runtime lifecycle work")

    def notify_runtime_commands(self) -> None:
        raise AssertionError("metadata edits must not notify runtime lifecycle work")


class _Audit:
    async def append(self, *args: object, **kwargs: object) -> None:
        return None


class _Settings:
    async def get_operational(self) -> OperationalSettingsView:
        return _SettingsView()


class _SettingsView:
    builders_can_deploy = False
    mcp_base_domain = "mcp.example.com"
    max_upload_bytes = 100_000_000


class _NoCommands:
    async def latest_for_subject(self, *args: object, **kwargs: object) -> None:
        return None


async def test_control_plane_mutation_rolls_back_when_outbox_insert_fails() -> None:
    database = _TransactionalDatabase()
    service = ProjectService(
        cast(DatabaseClient, database),
        cast(ProjectRepository, _Projects(database)),
        cast(AuditRepository, _Audit()),
        cast(RuntimeCommandRepository, _NoCommands()),
        cast(ProjectDeploymentLifecycle, _FailingLifecycle(database)),
        cast(OperationalSettingsProvider, _Settings()),
    )

    with pytest.raises(RuntimeError, match="outbox insert failed"):
        await service.update(
            UUID(int=2),
            values={"is_enabled": False},
            actor_user_id=UUID(int=7),
            actor_role=UserRole.ADMIN,
            request_id="request-1",
        )

    assert database.state == {"enabled": True, "command": False}


async def test_builder_without_deploy_permission_can_edit_metadata_but_not_lifecycle() -> None:
    database = _TransactionalDatabase()
    service = ProjectService(
        cast(DatabaseClient, database),
        cast(ProjectRepository, _Projects(database)),
        cast(AuditRepository, _Audit()),
        cast(RuntimeCommandRepository, _NoCommands()),
        cast(ProjectDeploymentLifecycle, _NoopLifecycle()),
        cast(OperationalSettingsProvider, _Settings()),
    )

    await service.update(
        UUID(int=2),
        values={"description": "Builder-authored metadata"},
        actor_user_id=UUID(int=7),
        actor_role=UserRole.BUILDER,
        request_id="metadata-request",
    )
    with pytest.raises(PermissionDeniedError, match="Deployment permission"):
        await service.update(
            UUID(int=2),
            values={"is_enabled": False},
            actor_user_id=UUID(int=7),
            actor_role=UserRole.BUILDER,
            request_id="lifecycle-request",
        )
    assert database.state["enabled"] is True
