from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.clients.runtime_files import RuntimeFilesClient
from app.core.config import Settings
from app.core.exceptions import (
    ClientConnectionError,
    ClientTimeoutError,
    ClientUnavailableError,
    DeployabilityError,
    DockerOperationError,
    ExecutionOwnershipError,
    InvalidStateError,
    MCPlicaError,
    NotFoundError,
    RuntimeHealthError,
)
from app.domain.deployments import (
    DeploymentIntent,
    DeploymentRecord,
    DeploymentStatus,
    MCPAuthConfigRecord,
    RuntimeCommandAction,
    is_rollback_eligible,
)
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository, LockedProjectDeploymentState
from app.repositories.mcp_access import MCPTokenVerifierRecord
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.command_dispatcher import RuntimeCommandDispatcher
from app.services.deployment.preflight import DeploymentPreflight, DeploymentPreflightResult
from app.services.deployment.runtime_manager import RuntimeManager
from app.services.deployment.secret_materializer import DeploymentSecretMaterializer

logger = logging.getLogger("mcplica.deployment")


class ExecutionCheckpoint(Protocol):
    async def __call__(self, session: AsyncSession | None = None) -> None: ...


async def _unfenced_execution_checkpoint(session: AsyncSession | None = None) -> None:
    del session


def is_retryable_deployment_error(error: Exception) -> bool:
    return isinstance(
        error,
        (
            ClientConnectionError,
            ClientTimeoutError,
            ClientUnavailableError,
            DockerOperationError,
        ),
    )


class DeploymentService:
    """Control-plane deployment commands; this service never touches Docker."""

    def __init__(
        self,
        database: DatabaseClient,
        deployments: DeploymentRepository,
        commands: RuntimeCommandRepository,
        audit: AuditRepository,
        dispatcher: RuntimeCommandDispatcher,
        preflight: DeploymentPreflight,
        settings: Settings,
    ) -> None:
        self._database = database
        self._deployments = deployments
        self._commands = commands
        self._audit = audit
        self._dispatcher = dispatcher
        self._preflight = preflight
        self._settings = settings

    async def get(self, deployment_id: UUID) -> DeploymentRecord:
        async with self._database.session_scope() as session:
            deployment = await self._deployments.get(session, deployment_id)
            if deployment is None:
                raise NotFoundError("Deployment was not found")
            return deployment

    async def list(
        self, project_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[DeploymentRecord]:
        async with self._database.session_scope() as session:
            if await self._deployments.get_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return await self._deployments.list_for_project(
                session,
                project_id,
                limit=limit,
                offset=offset,
            )

    async def page(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[DeploymentRecord], int, bool]:
        async with self._database.session_scope() as session:
            if await self._deployments.get_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return (
                await self._deployments.list_for_project(
                    session,
                    project_id,
                    limit=limit,
                    offset=offset,
                ),
                await self._deployments.count_for_project(session, project_id),
                await self._deployments.has_in_progress(session, project_id),
            )

    async def active_deployment_id(self, project_id: UUID) -> UUID | None:
        async with self._database.session_scope() as session:
            project = await self._deployments.get_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            return project.active_deployment_id

    def notify_runtime_commands(self) -> None:
        self._dispatcher.wake()

    async def request(
        self,
        *,
        project_id: UUID,
        build_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool = False,
        event_type: str = "deployment.requested",
        subject_type: str | None = None,
        subject_id: UUID | None = None,
    ) -> DeploymentRecord:
        async with self._database.session_scope() as session:
            project = await self._deployments.lock_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            deployment = await self._request_in_session(
                session,
                project=project,
                build_id=build_id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                request_id=request_id,
                stop_old_first=stop_old_first,
                subject_type=subject_type,
                subject_id=subject_id,
                transition_id=uuid4(),
                intent=DeploymentIntent.NORMAL,
                transition_stopping_ids=set(),
            )
        self._dispatcher.wake()
        return deployment

    async def redeploy_active(
        self,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool,
        event_type: str,
    ) -> DeploymentRecord | None:
        async with self._database.session_scope() as session:
            deployment = await self.schedule_redeploy_active(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=stop_old_first,
                event_type=event_type,
            )
        self._dispatcher.wake()
        return deployment

    async def schedule_redeploy_active(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool,
        event_type: str,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
        transition_id: UUID | None = None,
        intent: DeploymentIntent = DeploymentIntent.NORMAL,
        fallback_to_stop: bool = False,
    ) -> DeploymentRecord | None:
        """Persist a replacement and its runtime commands in the caller's transaction."""

        transition_id = transition_id or uuid4()
        project = await self._deployments.lock_project(session, project_id)
        if project is None:
            raise NotFoundError("Project was not found")
        stoppable = await self._deployments.list_stoppable_for_project(session, project_id)
        target_build_id = project.active_build_id
        if project.active_deployment_id is not None:
            active = await self._deployments.get(session, project.active_deployment_id)
            if active is not None:
                target_build_id = active.build_id
        elif stoppable:
            # Security maintenance racing initial activation refreshes that exact
            # candidate instead of silently selecting a different project build.
            target_build_id = stoppable[0].build_id
        transition_stopping_ids: set[UUID] = set()
        for deployment in stoppable:
            if stop_old_first or deployment.status in {
                DeploymentStatus.PENDING,
                DeploymentStatus.DEPLOYING,
                DeploymentStatus.HEALTHCHECK,
            }:
                stopped = await self._schedule_stop_in_session(
                    session,
                    deployment,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                    reason=event_type,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    transition_id=transition_id,
                )
                transition_stopping_ids.add(stopped.id)
        if target_build_id is None or not project.is_enabled:
            if fallback_to_stop:
                await self.schedule_stop_project(
                    session,
                    project_id=project_id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                    reason=event_type,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    transition_id=transition_id,
                )
            return None
        try:
            return await self._request_in_session(
                session,
                project=project,
                build_id=target_build_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=stop_old_first,
                event_type=event_type,
                subject_type=subject_type,
                subject_id=subject_id,
                transition_id=transition_id,
                intent=intent,
                transition_stopping_ids=transition_stopping_ids,
            )
        except (InvalidStateError, NotFoundError, DeployabilityError):
            if not fallback_to_stop:
                raise
            await self.schedule_stop_project(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                reason=event_type,
                subject_type=subject_type,
                subject_id=subject_id,
                transition_id=transition_id,
            )
            return None

    async def restart(
        self,
        deployment_id: UUID,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> DeploymentRecord:
        current = await self.get(deployment_id)
        return await self.request(
            project_id=current.project_id,
            build_id=current.build_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            event_type="deployment.restarted",
        )

    async def rollback(
        self,
        *,
        project_id: UUID,
        target_deployment_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> DeploymentRecord:
        async with self._database.session_scope() as session:
            project = await self._deployments.lock_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            target = await self._deployments.get_for_update(session, target_deployment_id)
            if target is None or target.project_id != project_id:
                raise NotFoundError("Rollback deployment was not found")
            if not is_rollback_eligible(
                target,
                active_deployment_id=project.active_deployment_id,
            ):
                if target.id == project.active_deployment_id:
                    raise InvalidStateError("Rollback target is already the active deployment")
                raise InvalidStateError("Rollback target was never a successful deployment")
            deployment = await self._request_in_session(
                session,
                project=project,
                build_id=target.build_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=False,
                event_type="deployment.rollback_requested",
                subject_type="deployment",
                subject_id=target.id,
                transition_id=uuid4(),
                intent=DeploymentIntent.ROLLBACK,
                transition_stopping_ids=set(),
            )
        self._dispatcher.wake()
        return deployment

    async def stop(
        self,
        deployment_id: UUID,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> DeploymentRecord:
        async with self._database.session_scope() as session:
            current = await self._deployments.get_for_update(session, deployment_id)
            if current is None:
                raise NotFoundError("Deployment was not found")
            if current.status in {DeploymentStatus.STOPPED, DeploymentStatus.FAILED}:
                return current
            stopped = await self._schedule_stop_in_session(
                session,
                current,
                actor_user_id=actor_user_id,
                request_id=request_id,
                reason="deployment.stop_requested",
                transition_id=uuid4(),
            )
        self._dispatcher.wake()
        return stopped

    async def stop_active(
        self,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> DeploymentRecord | None:
        async with self._database.session_scope() as session:
            project = await self._deployments.get_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            active_id = project.active_deployment_id
        if active_id is None:
            return None
        return await self.stop(
            active_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )

    async def stop_project(
        self,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> Sequence[DeploymentRecord]:
        """Durably request every live/in-flight runtime for a project to stop."""

        async with self._database.session_scope() as session:
            stopped = await self.schedule_stop_project(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                reason="deployment.project_stop_requested",
            )
        self._dispatcher.wake()
        return stopped

    async def schedule_stop_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        reason: str,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
        transition_id: UUID | None = None,
    ) -> list[DeploymentRecord]:
        transition_id = transition_id or uuid4()
        if await self._deployments.lock_project(session, project_id) is None:
            raise NotFoundError("Project was not found")
        deployments = await self._deployments.list_stoppable_for_project(session, project_id)
        return [
            await self._schedule_stop_in_session(
                session,
                deployment,
                actor_user_id=actor_user_id,
                request_id=request_id,
                reason=reason,
                subject_type=subject_type,
                subject_id=subject_id,
                transition_id=transition_id,
            )
            for deployment in deployments
        ]

    async def _request_in_session(
        self,
        session: AsyncSession,
        *,
        project: LockedProjectDeploymentState,
        build_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool,
        event_type: str,
        subject_type: str | None,
        subject_id: UUID | None,
        transition_id: UUID,
        intent: DeploymentIntent,
        transition_stopping_ids: set[UUID],
    ) -> DeploymentRecord:
        if not project.is_enabled:
            raise InvalidStateError("Disabled projects cannot be deployed")
        if await self._deployments.has_in_progress(
            session,
            project.id,
            transition_stopping_ids=transition_stopping_ids,
        ):
            raise InvalidStateError("A deployment is already in progress for this project")
        build = await self._deployments.get_build(session, build_id)
        if build is None or build.project_id != project.id:
            raise NotFoundError("Build was not found")
        if build.status.lower() != "ready":
            raise InvalidStateError("Only READY builds can be deployed")
        if not build.manifest_sha256 or not build.manifest_storage_key:
            raise InvalidStateError("READY build has no immutable manifest artifact")
        if len(build.manifest_sha256) != 64 or any(
            value not in "0123456789abcdef" for value in build.manifest_sha256.lower()
        ):
            raise InvalidStateError("Build manifest identity is invalid")
        await self._preflight.validate(
            session,
            project_id=project.id,
            hostname=project.hostname,
            build=build,
            runtime_version=self._settings.mcp_runtime_version,
            require_current_configuration=intent is DeploymentIntent.NORMAL,
        )
        deployment_id = uuid4()
        route_priority = await self._deployments.next_route_priority(session, project.id)
        if route_priority >= 2_147_482_647:
            raise InvalidStateError("Project route priority space is exhausted")
        deployment = await self._deployments.create(
            session,
            deployment_id=deployment_id,
            project_id=project.id,
            build_id=build_id,
            intent=intent,
            previous_active_deployment_id=project.active_deployment_id,
            hostname=project.hostname,
            container_name=f"mcp-{project.id.hex}-{deployment_id.hex}",
            image_ref=self._settings.mcp_runtime_image,
            runtime_version=self._settings.mcp_runtime_version,
            network_name=f"mcp-net-{project.id.hex}",
            manifest_sha256=build.manifest_sha256.lower(),
            route_priority=route_priority,
            stop_old_first=stop_old_first,
            deployed_by=actor_user_id,
        )
        command = await self._commands.create(
            session,
            command_id=uuid4(),
            project_id=project.id,
            deployment_id=deployment.id,
            build_id=deployment.build_id,
            transition_id=transition_id,
            action=RuntimeCommandAction.DEPLOY,
            reason=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            requested_by=actor_user_id,
            request_id=request_id,
            idempotency_key=f"deployment:{deployment.id}:deploy",
        )
        await self._audit.append(
            session,
            actor_user_id=actor_user_id,
            event_type=event_type,
            entity_type="deployment",
            entity_id=deployment.id,
            project_id=project.id,
            request_id=request_id,
            metadata={
                "build_id": str(build_id),
                "stop_old_first": stop_old_first,
                "runtime_command_id": str(command.id),
                "intent": intent.value,
            },
        )
        return deployment

    async def _schedule_stop_in_session(
        self,
        session: AsyncSession,
        deployment: DeploymentRecord,
        *,
        actor_user_id: UUID,
        request_id: str | None,
        reason: str,
        transition_id: UUID,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
    ) -> DeploymentRecord:
        stopped = deployment
        if deployment.status != DeploymentStatus.STOPPING:
            transitioned = await self._deployments.transition(
                session,
                deployment.id,
                expected={
                    DeploymentStatus.PENDING,
                    DeploymentStatus.DEPLOYING,
                    DeploymentStatus.HEALTHCHECK,
                    DeploymentStatus.RUNNING,
                    DeploymentStatus.UNHEALTHY,
                },
                status=DeploymentStatus.STOPPING,
            )
            if transitioned is None:
                current = await self._deployments.get_for_update(session, deployment.id)
                if current is None:
                    raise NotFoundError("Deployment was not found")
                stopped = current
            else:
                stopped = transitioned
        command = await self._commands.create(
            session,
            command_id=uuid4(),
            project_id=deployment.project_id,
            deployment_id=deployment.id,
            build_id=deployment.build_id,
            transition_id=transition_id,
            action=RuntimeCommandAction.STOP,
            reason=reason,
            subject_type=subject_type,
            subject_id=subject_id,
            requested_by=actor_user_id,
            request_id=request_id,
            # A stop is idempotent within one durable transition, not for the
            # lifetime of a deployment.  A later operator transition must be
            # able to recover from a prior terminal command failure and must
            # remain ordered before its own replacement DEPLOY command.
            idempotency_key=f"deployment:{deployment.id}:stop:{transition_id}",
        )
        await self._audit.append(
            session,
            actor_user_id=actor_user_id,
            event_type="deployment.stop_requested",
            entity_type="deployment",
            entity_id=deployment.id,
            project_id=deployment.project_id,
            request_id=request_id,
            metadata={"reason": reason, "runtime_command_id": str(command.id)},
        )
        return stopped


class DeploymentRunner:
    """Worker-side idempotent deployment state machine."""

    def __init__(
        self,
        database: DatabaseClient,
        deployments: DeploymentRepository,
        audit: AuditRepository,
        preflight: DeploymentPreflight,
        runtime_files: RuntimeFilesClient,
        secret_materializer: DeploymentSecretMaterializer,
        runtime_manager: RuntimeManager,
    ) -> None:
        self._database = database
        self._deployments = deployments
        self._audit = audit
        self._preflight = preflight
        self._runtime_files = runtime_files
        self._secrets = secret_materializer
        self._runtime = runtime_manager

    async def run(
        self,
        deployment_id: UUID,
        *,
        final_attempt: bool = True,
        rollback_target_id: UUID | None = None,
        execution_checkpoint: ExecutionCheckpoint | None = None,
    ) -> None:
        checkpoint = execution_checkpoint or _unfenced_execution_checkpoint
        deployment: DeploymentRecord | None = None
        activated = False
        terminal_running: DeploymentRecord | None = None
        activation_pending: DeploymentRecord | None = None
        activation_failure_recorded = False
        preflight_result: DeploymentPreflightResult | None = None
        auth_config: MCPAuthConfigRecord | None = None
        token_verifiers: list[MCPTokenVerifierRecord] = []
        active: DeploymentRecord | None = None
        try:
            async with self._database.session_scope() as session:
                await checkpoint(session)
                deployment = await self._deployments.get_for_update(session, deployment_id)
                if deployment is None:
                    raise NotFoundError("Deployment was not found")
                if deployment.status == DeploymentStatus.RUNNING:
                    terminal_running = deployment
                elif deployment.status in {
                    DeploymentStatus.UNHEALTHY,
                    DeploymentStatus.STOPPED,
                    DeploymentStatus.FAILED,
                    DeploymentStatus.STOPPING,
                }:
                    return
                else:
                    terminal_running = None
                    project = await self._deployments.lock_project(session, deployment.project_id)
                    if project is None or not project.is_enabled:
                        raise InvalidStateError("Deployment project is unavailable")
                    if (
                        deployment.status == DeploymentStatus.HEALTHCHECK
                        and deployment.health_status == "activating"
                        and project.active_deployment_id == deployment.id
                    ):
                        activation_pending = deployment
                    else:
                        build = await self._deployments.get_build(session, deployment.build_id)
                        if (
                            build is None
                            or build.project_id != deployment.project_id
                            or build.status.lower() != "ready"
                            or not build.manifest_storage_key
                            or build.manifest_sha256 != deployment.manifest_sha256
                        ):
                            raise InvalidStateError("Deployment build is no longer deployable")
                        require_current_configuration = deployment.intent is DeploymentIntent.NORMAL
                        if deployment.intent is DeploymentIntent.ROLLBACK:
                            if rollback_target_id is None:
                                raise InvalidStateError(
                                    "Rollback deployment is missing its immutable target"
                                )
                            rollback_target = await self._deployments.get(
                                session, rollback_target_id
                            )
                            if (
                                rollback_target is None
                                or rollback_target.project_id != deployment.project_id
                                or rollback_target.build_id != deployment.build_id
                                or not is_rollback_eligible(
                                    rollback_target,
                                    active_deployment_id=project.active_deployment_id,
                                )
                            ):
                                raise InvalidStateError(
                                    "Rollback target is no longer eligible for activation"
                                )
                        elif rollback_target_id is not None:
                            raise InvalidStateError(
                                "Only rollback deployments may carry a rollback target"
                            )
                        deployment = await self._deployments.transition(
                            session,
                            deployment.id,
                            expected={
                                DeploymentStatus.PENDING,
                                DeploymentStatus.DEPLOYING,
                                DeploymentStatus.HEALTHCHECK,
                            },
                            status=DeploymentStatus.DEPLOYING,
                        )
                        assert deployment is not None
                        preflight_result = await self._preflight.validate(
                            session,
                            project_id=deployment.project_id,
                            hostname=deployment.hostname,
                            build=build,
                            runtime_version=deployment.runtime_version,
                            require_current_configuration=require_current_configuration,
                        )
                        auth_config = preflight_result.auth_config
                        token_verifiers = preflight_result.token_verifiers
                        active_id = project.active_deployment_id
                        active = (
                            await self._deployments.get(session, active_id)
                            if active_id is not None and active_id != deployment.id
                            else None
                        )
            if terminal_running is not None:
                try:
                    await checkpoint()
                    proof = await self._runtime.revalidate_activation_candidate(terminal_running)
                    await checkpoint()
                    async with self._database.session_scope() as session:
                        await checkpoint(session)
                        refreshed = await self._deployments.refresh_activation_proof(
                            session,
                            terminal_running.id,
                            proof,
                        )
                        if refreshed is None:
                            raise InvalidStateError(
                                "Running deployment activation proof could not be refreshed"
                            )
                except Exception as exc:
                    if isinstance(exc, ExecutionOwnershipError):
                        raise
                    await self._fail_activation_and_restore(
                        terminal_running,
                        exc,
                        checkpoint=checkpoint,
                    )
                    activation_failure_recorded = True
                    raise
                activated = True
                await self._cleanup_activation_predecessor(
                    terminal_running,
                    checkpoint=checkpoint,
                )
                await self._cleanup_superseded(terminal_running, checkpoint=checkpoint)
                return
            if activation_pending is not None:
                deployment = activation_pending
                try:
                    await checkpoint()
                    proof = await self._runtime.revalidate_activation_candidate(activation_pending)
                    await checkpoint()
                    async with self._database.session_scope() as session:
                        await checkpoint(session)
                        refreshed = await self._deployments.refresh_activation_proof(
                            session,
                            activation_pending.id,
                            proof,
                        )
                        if refreshed is None:
                            raise InvalidStateError(
                                "Activation proof could not be persisted before cleanup"
                            )
                except Exception as exc:
                    if isinstance(exc, ExecutionOwnershipError):
                        raise
                    await self._fail_activation_and_restore(
                        activation_pending,
                        exc,
                        checkpoint=checkpoint,
                    )
                    activation_failure_recorded = True
                    raise
                activated = True
                await self._finish_activation(activation_pending, checkpoint=checkpoint)
                return
            if preflight_result is None:
                raise InvalidStateError("Deployment preflight result is unavailable")
            manifest_bytes = preflight_result.manifest_bytes
            manifest = preflight_result.manifest
            await checkpoint()
            bundle = await self._secrets.build_bundle(
                project_id=deployment.project_id,
                hostname=deployment.hostname,
                manifest=manifest,
                auth_config=auth_config,
                token_verifiers=token_verifiers,
            )
            await checkpoint()
            mounts = await self._runtime_files.materialize(
                deployment.id,
                manifest_bytes=manifest_bytes,
                manifest_sha256=deployment.manifest_sha256,
                secret_bundle=bundle,
            )
            await checkpoint()
            if deployment.stop_old_first and active is not None:
                await self._stop_existing(
                    active,
                    event_type="deployment.replacement_stopped",
                    checkpoint=checkpoint,
                )
            async with self._database.session_scope() as session:
                await checkpoint(session)
                deployment = await self._deployments.transition(
                    session,
                    deployment.id,
                    expected={DeploymentStatus.DEPLOYING, DeploymentStatus.HEALTHCHECK},
                    status=DeploymentStatus.HEALTHCHECK,
                    values={
                        "health_status": "starting",
                        "auth_overlay_sha256": mounts.auth_overlay_sha256,
                    },
                )
                if deployment is None:
                    raise InvalidStateError("Deployment was cancelled before startup")
            await checkpoint()
            provisioned = await self._runtime.provision(deployment, mounts)
            await checkpoint()
            async with self._database.session_scope() as session:
                await checkpoint(session)
                deployment = await self._deployments.transition(
                    session,
                    deployment.id,
                    expected={DeploymentStatus.HEALTHCHECK},
                    status=DeploymentStatus.HEALTHCHECK,
                    values={
                        "container_id": provisioned.container_id,
                        "image_digest": provisioned.image_digest,
                        "health_status": provisioned.health_status,
                    },
                )
                if deployment is None:
                    raise InvalidStateError("Deployment was cancelled during startup")
                activated = await self._deployments.begin_activation(
                    session,
                    deployment.id,
                    provisioned.activation_proof,
                )
                if not activated:
                    raise InvalidStateError("Deployment was cancelled before activation")
            activated = True
            await self._finish_activation(deployment, checkpoint=checkpoint)
        except Exception as exc:
            if isinstance(exc, ExecutionOwnershipError):
                raise
            if deployment is None:
                raise
            if activated:
                logger.error(
                    "post_activation_cleanup_failed",
                    extra={"deployment_id": str(deployment.id)},
                )
                raise
            await self._cleanup_failed_without_masking(deployment, checkpoint=checkpoint)
            code, summary, unhealthy = self._safe_failure(exc)
            if not final_attempt and is_retryable_deployment_error(exc):
                async with self._database.session_scope() as session:
                    await checkpoint(session)
                    pending = await self._deployments.reset_for_retry(
                        session,
                        deployment.id,
                    )
                    if pending is not None:
                        await self._audit.append(
                            session,
                            actor_user_id=deployment.deployed_by,
                            event_type="deployment.retry_scheduled",
                            entity_type="deployment",
                            entity_id=deployment.id,
                            project_id=deployment.project_id,
                            metadata={"error_code": code},
                        )
                if pending is not None:
                    raise
                return
            async with self._database.session_scope() as session:
                await checkpoint(session)
                failed = await self._deployments.mark_failed(
                    session,
                    deployment.id,
                    error_code=code,
                    error_summary=summary,
                    unhealthy=unhealthy,
                )
                if failed is not None:
                    await self._audit.append(
                        session,
                        actor_user_id=deployment.deployed_by,
                        event_type="deployment.failed",
                        entity_type="deployment",
                        entity_id=deployment.id,
                        project_id=deployment.project_id,
                        metadata={"error_code": code},
                    )
            if activation_failure_recorded or (
                failed is not None and (final_attempt or is_retryable_deployment_error(exc))
            ):
                raise

    async def stop(
        self,
        deployment_id: UUID,
        *,
        execution_checkpoint: ExecutionCheckpoint | None = None,
    ) -> None:
        checkpoint = execution_checkpoint or _unfenced_execution_checkpoint
        await checkpoint()
        deployment = await self._get_required(deployment_id)
        if deployment.status in {DeploymentStatus.STOPPED, DeploymentStatus.FAILED}:
            return
        await checkpoint()
        await self._runtime.stop(deployment, remove=True)
        await checkpoint()
        await self._runtime_files.remove(deployment.id)
        await checkpoint()
        async with self._database.session_scope() as session:
            await checkpoint(session)
            await self._deployments.clear_active(session, deployment.project_id, deployment.id)
            await self._deployments.mark_stopped(session, deployment.id)
            await self._audit.append(
                session,
                actor_user_id=deployment.deployed_by,
                event_type="deployment.stopped",
                entity_type="deployment",
                entity_id=deployment.id,
                project_id=deployment.project_id,
            )
        await checkpoint()
        await self._runtime.cleanup_network_if_unused(deployment)
        await checkpoint()

    async def _stop_existing(
        self,
        deployment: DeploymentRecord,
        *,
        event_type: str = "deployment.superseded",
        checkpoint: ExecutionCheckpoint = _unfenced_execution_checkpoint,
    ) -> None:
        await checkpoint()
        await self._runtime.stop(deployment, remove=True)
        await checkpoint()
        await self._runtime_files.remove(deployment.id)
        await checkpoint()
        async with self._database.session_scope() as session:
            await checkpoint(session)
            await self._deployments.clear_active(session, deployment.project_id, deployment.id)
            await self._deployments.mark_stopped(session, deployment.id)
            await self._audit.append(
                session,
                actor_user_id=deployment.deployed_by,
                event_type=event_type,
                entity_type="deployment",
                entity_id=deployment.id,
                project_id=deployment.project_id,
            )

    async def _cleanup_superseded(
        self,
        running: DeploymentRecord,
        *,
        checkpoint: ExecutionCheckpoint = _unfenced_execution_checkpoint,
    ) -> None:
        await checkpoint()
        async with self._database.session_scope() as session:
            superseded = await self._deployments.find_superseded_running(session, running)
        for deployment in superseded:
            await self._stop_existing(
                deployment,
                event_type="deployment.superseded",
                checkpoint=checkpoint,
            )

    async def _remove_retired_runtime(
        self,
        deployment: DeploymentRecord,
        *,
        checkpoint: ExecutionCheckpoint = _unfenced_execution_checkpoint,
    ) -> None:
        """Remove a predecessor only after its control-plane retirement is committed."""

        await checkpoint()
        await self._runtime.stop(deployment, remove=True)
        await checkpoint()
        await self._runtime_files.remove(deployment.id)
        await checkpoint()
        await self._runtime.cleanup_network_if_unused(deployment)
        await checkpoint()

    async def _cleanup_activation_predecessor(
        self,
        running: DeploymentRecord,
        *,
        checkpoint: ExecutionCheckpoint = _unfenced_execution_checkpoint,
    ) -> None:
        previous_id = running.previous_active_deployment_id
        if previous_id is None:
            return
        await checkpoint()
        async with self._database.session_scope() as session:
            previous = await self._deployments.get(session, previous_id)
        if previous is None:
            return
        if previous.status == DeploymentStatus.STOPPED:
            await self._remove_retired_runtime(previous, checkpoint=checkpoint)
        elif previous.status in {DeploymentStatus.RUNNING, DeploymentStatus.STOPPING}:
            # Compatibility repair for an activation committed by an older worker.
            await self._stop_existing(
                previous,
                event_type="deployment.superseded",
                checkpoint=checkpoint,
            )

    async def _finish_activation(
        self,
        deployment: DeploymentRecord,
        *,
        checkpoint: ExecutionCheckpoint = _unfenced_execution_checkpoint,
    ) -> None:
        candidate = deployment
        predecessor: DeploymentRecord | None = None
        try:
            async with self._database.session_scope() as session:
                await checkpoint(session)
                retiring = await self._deployments.mark_retiring_previous(session, deployment.id)
                if not retiring:
                    raise InvalidStateError("Deployment activation proof is unavailable")
                refreshed_candidate = await self._deployments.get(session, deployment.id)
                if refreshed_candidate is None:
                    raise InvalidStateError("Deployment activation candidate disappeared")
                candidate = refreshed_candidate
                if candidate.previous_active_deployment_id is not None:
                    predecessor = await self._deployments.get(
                        session, candidate.previous_active_deployment_id
                    )
                    if predecessor is None or predecessor.status not in {
                        DeploymentStatus.STOPPING,
                        DeploymentStatus.STOPPED,
                    }:
                        raise InvalidStateError(
                            "Deployment predecessor is not ready for retirement"
                        )

            # Keep the predecessor container recoverable until the replacement has been
            # re-proved without it and both control-plane states commit atomically.
            if predecessor is not None and predecessor.status == DeploymentStatus.STOPPING:
                await checkpoint()
                await self._runtime.stop(predecessor, remove=False)
                await checkpoint()
            await checkpoint()
            proof = await self._runtime.revalidate_activation_candidate(candidate)
            await checkpoint()

            async with self._database.session_scope() as session:
                await checkpoint(session)
                refreshed = await self._deployments.refresh_activation_proof(
                    session,
                    candidate.id,
                    proof,
                )
                if refreshed is None:
                    raise InvalidStateError(
                        "Activation proof could not be persisted after predecessor retirement"
                    )
                running = await self._deployments.complete_activation(session, candidate.id)
                if running is None:
                    raise InvalidStateError("Deployment could not complete activation")
                if predecessor is not None and predecessor.status == DeploymentStatus.STOPPING:
                    await self._audit.append(
                        session,
                        actor_user_id=predecessor.deployed_by,
                        event_type="deployment.superseded",
                        entity_type="deployment",
                        entity_id=predecessor.id,
                        project_id=predecessor.project_id,
                    )
                await self._audit.append(
                    session,
                    actor_user_id=running.deployed_by,
                    event_type="deployment.running",
                    entity_type="deployment",
                    entity_id=running.id,
                    project_id=running.project_id,
                    metadata={
                        "build_id": str(running.build_id),
                        "image_digest": running.image_digest,
                        "activation_proof_sha256": running.activation_proof_sha256,
                    },
                )
        except Exception as exc:
            if isinstance(exc, ExecutionOwnershipError):
                raise
            await self._fail_activation_and_restore(
                candidate,
                exc,
                checkpoint=checkpoint,
            )
            raise

        # The predecessor is already STOPPED before RUNNING is observable. Container and
        # secret deletion are idempotent, so a command retry can finish interrupted cleanup.
        if predecessor is not None:
            await self._remove_retired_runtime(predecessor, checkpoint=checkpoint)
        await self._cleanup_superseded(running, checkpoint=checkpoint)

    async def _fail_activation_and_restore(
        self,
        candidate: DeploymentRecord,
        error: Exception,
        *,
        checkpoint: ExecutionCheckpoint = _unfenced_execution_checkpoint,
    ) -> None:
        code, summary, _ = self._safe_failure(error)
        previous: DeploymentRecord | None = None
        if candidate.previous_active_deployment_id is not None:
            await checkpoint()
            async with self._database.session_scope() as session:
                previous = await self._deployments.get(
                    session,
                    candidate.previous_active_deployment_id,
                )

        previous_runtime_ready = False
        try:
            # Remove the invalid candidate from edge selection before probing its predecessor.
            await checkpoint()
            await self._runtime.stop(candidate, remove=False)
            await checkpoint()
            if previous is not None:
                await self._runtime.restore_activation_predecessor(previous)
                await checkpoint()
                previous_runtime_ready = True
        except ExecutionOwnershipError:
            raise
        except MCPlicaError:
            logger.exception(
                "deployment_predecessor_restore_failed",
                extra={"deployment_id": str(candidate.id)},
            )

        async with self._database.session_scope() as session:
            await checkpoint(session)
            await self._deployments.restore_previous_after_failed_activation(
                session,
                candidate.id,
                previous_runtime_ready=previous_runtime_ready,
                error_code=code,
                error_summary=summary,
            )
            await self._audit.append(
                session,
                actor_user_id=candidate.deployed_by,
                event_type="deployment.activation_revalidation_failed",
                entity_type="deployment",
                entity_id=candidate.id,
                project_id=candidate.project_id,
                metadata={
                    "error_code": code,
                    "previous_runtime_restored": previous_runtime_ready,
                },
            )

    async def _get_required(self, deployment_id: UUID) -> DeploymentRecord:
        async with self._database.session_scope() as session:
            deployment = await self._deployments.get(session, deployment_id)
            if deployment is None:
                raise NotFoundError("Deployment was not found")
            return deployment

    async def _cleanup_failed_without_masking(
        self,
        deployment: DeploymentRecord,
        *,
        checkpoint: ExecutionCheckpoint = _unfenced_execution_checkpoint,
    ) -> None:
        try:
            await checkpoint()
            await self._runtime.cleanup_failed(deployment)
            await checkpoint()
        except ExecutionOwnershipError:
            raise
        except MCPlicaError:
            logger.warning(
                "failed_runtime_cleanup_failed",
                extra={"deployment_id": str(deployment.id)},
            )
        try:
            await checkpoint()
            await self._runtime_files.remove(deployment.id)
            await checkpoint()
        except ExecutionOwnershipError:
            raise
        except MCPlicaError:
            logger.warning(
                "failed_runtime_secret_cleanup_failed",
                extra={"deployment_id": str(deployment.id)},
            )
        try:
            await checkpoint()
            await self._runtime.cleanup_network_if_unused(deployment)
            await checkpoint()
        except ExecutionOwnershipError:
            raise
        except MCPlicaError:
            logger.warning(
                "failed_runtime_network_cleanup_failed",
                extra={"deployment_id": str(deployment.id)},
            )

    @staticmethod
    def _safe_failure(error: Exception) -> tuple[str, str, bool]:
        if isinstance(error, MCPlicaError):
            return error.code.lower(), str(error), isinstance(error, RuntimeHealthError)
        return (
            "unexpected_deployment_error",
            "Deployment failed due to an internal error",
            False,
        )
