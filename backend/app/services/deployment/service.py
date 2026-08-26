import hashlib
import logging
from collections.abc import Sequence
from uuid import UUID, uuid4

from mcp_contracts import MCPManifest

from app.clients.database import DatabaseClient
from app.clients.queue import DeploymentQueueClient
from app.clients.runtime_files import RuntimeFilesClient
from app.core.config import Settings
from app.core.exceptions import (
    ClientConnectionError,
    ClientTimeoutError,
    ClientUnavailableError,
    DockerOperationError,
    InvalidStateError,
    MCPlicaError,
    NotFoundError,
    RuntimeHealthError,
    ValidationError,
)
from app.domain.deployments import (
    DeploymentRecord,
    DeploymentStatus,
    MCPAuthConfigRecord,
)
from app.providers.storage import ArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.mcp_access import MCPAccessRepository, MCPTokenVerifierRecord
from app.services.deployment.runtime_manager import RuntimeManager
from app.services.deployment.secret_materializer import DeploymentSecretMaterializer
from app.validators.manifest import validate_manifest

logger = logging.getLogger("mcplica.deployment")


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
        audit: AuditRepository,
        queue: DeploymentQueueClient,
        settings: Settings,
    ) -> None:
        self._database = database
        self._deployments = deployments
        self._audit = audit
        self._queue = queue
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

    async def request(
        self,
        *,
        project_id: UUID,
        build_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool = False,
        event_type: str = "deployment.requested",
    ) -> DeploymentRecord:
        async with self._database.session_scope() as session:
            project = await self._deployments.lock_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            if not project.is_enabled:
                raise InvalidStateError("Disabled projects cannot be deployed")
            if await self._deployments.has_in_progress(session, project_id):
                raise InvalidStateError("A deployment is already in progress for this project")
            build = await self._deployments.get_build(session, build_id)
            if build is None or build.project_id != project_id:
                raise NotFoundError("Build was not found")
            if build.status.lower() != "ready":
                raise InvalidStateError("Only READY builds can be deployed")
            if not build.manifest_sha256 or not build.manifest_storage_key:
                raise InvalidStateError("READY build has no immutable manifest artifact")
            if len(build.manifest_sha256) != 64 or any(
                value not in "0123456789abcdef" for value in build.manifest_sha256.lower()
            ):
                raise InvalidStateError("Build manifest identity is invalid")
            deployment_id = uuid4()
            project_fragment = project_id.hex
            deployment_fragment = deployment_id.hex
            route_priority = await self._deployments.next_route_priority(session, project_id)
            if route_priority >= 2_147_482_647:
                raise InvalidStateError("Project route priority space is exhausted")
            deployment = await self._deployments.create(
                session,
                deployment_id=deployment_id,
                project_id=project_id,
                build_id=build_id,
                hostname=project.hostname,
                container_name=f"mcp-{project_fragment}-{deployment_fragment}",
                image_ref=self._settings.mcp_runtime_image,
                runtime_version=self._settings.mcp_runtime_version,
                network_name=f"mcp-net-{project_fragment}",
                manifest_sha256=build.manifest_sha256.lower(),
                route_priority=route_priority,
                stop_old_first=stop_old_first,
                deployed_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type=event_type,
                entity_type="deployment",
                entity_id=deployment.id,
                project_id=project_id,
                request_id=request_id,
                metadata={
                    "build_id": str(build_id),
                    "stop_old_first": stop_old_first,
                },
            )
        try:
            await self._queue.enqueue_deploy(deployment.id)
        except MCPlicaError:
            await self._mark_enqueue_failed(deployment.id, actor_user_id, request_id)
            raise
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
            project = await self._deployments.lock_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            build_id = project.active_build_id
            stoppable = await self._deployments.list_stoppable_for_project(session, project_id)
            deployments_to_stop = [
                deployment
                for deployment in stoppable
                if stop_old_first
                or deployment.status
                in {
                    DeploymentStatus.PENDING,
                    DeploymentStatus.DEPLOYING,
                    DeploymentStatus.HEALTHCHECK,
                }
            ]
        for deployment in deployments_to_stop:
            await self.stop(
                deployment.id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        if build_id is None:
            return None
        return await self.request(
            project_id=project_id,
            build_id=build_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            stop_old_first=stop_old_first,
            event_type=event_type,
        )

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
        target = await self.get(target_deployment_id)
        if target.project_id != project_id:
            raise NotFoundError("Rollback deployment was not found")
        if target.status not in {
            DeploymentStatus.RUNNING,
            DeploymentStatus.STOPPING,
            DeploymentStatus.STOPPED,
        }:
            raise InvalidStateError("Rollback target was never a successful deployment")
        return await self.request(
            project_id=project_id,
            build_id=target.build_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            event_type="deployment.rollback_requested",
        )

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
            stopped = await self._deployments.transition(
                session,
                deployment_id,
                expected={
                    DeploymentStatus.PENDING,
                    DeploymentStatus.DEPLOYING,
                    DeploymentStatus.HEALTHCHECK,
                    DeploymentStatus.RUNNING,
                    DeploymentStatus.UNHEALTHY,
                    DeploymentStatus.STOPPING,
                },
                status=DeploymentStatus.STOPPING,
            )
            assert stopped is not None
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="deployment.stop_requested",
                entity_type="deployment",
                entity_id=deployment_id,
                project_id=current.project_id,
                request_id=request_id,
            )
        await self._queue.enqueue_stop(deployment_id)
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
            if await self._deployments.get_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            deployments = await self._deployments.list_stoppable_for_project(session, project_id)
        stopped: list[DeploymentRecord] = []
        for deployment in deployments:
            stopped.append(
                await self.stop(
                    deployment.id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                )
            )
        return stopped

    async def _mark_enqueue_failed(
        self, deployment_id: UUID, actor_user_id: UUID, request_id: str | None
    ) -> None:
        async with self._database.session_scope() as session:
            deployment = await self._deployments.mark_failed(
                session,
                deployment_id,
                error_code="deployment_queue_unavailable",
                error_summary="Deployment could not be queued",
            )
            if deployment is not None:
                await self._audit.append(
                    session,
                    actor_user_id=actor_user_id,
                    event_type="deployment.failed",
                    entity_type="deployment",
                    entity_id=deployment_id,
                    project_id=deployment.project_id,
                    request_id=request_id,
                    metadata={"error_code": "deployment_queue_unavailable"},
                )


class DeploymentRunner:
    """Worker-side idempotent deployment state machine."""

    def __init__(
        self,
        database: DatabaseClient,
        deployments: DeploymentRepository,
        access: MCPAccessRepository,
        audit: AuditRepository,
        artifact_storage: ArtifactStorage,
        runtime_files: RuntimeFilesClient,
        secret_materializer: DeploymentSecretMaterializer,
        runtime_manager: RuntimeManager,
        *,
        manifest_max_bytes: int,
    ) -> None:
        self._database = database
        self._deployments = deployments
        self._access = access
        self._audit = audit
        self._artifact_storage = artifact_storage
        self._runtime_files = runtime_files
        self._secrets = secret_materializer
        self._runtime = runtime_manager
        self._manifest_max_bytes = manifest_max_bytes

    async def run(self, deployment_id: UUID, *, final_attempt: bool = True) -> None:
        deployment: DeploymentRecord | None = None
        activated = False
        terminal_running: DeploymentRecord | None = None
        activation_pending: DeploymentRecord | None = None
        manifest_storage_key: str | None = None
        auth_config: MCPAuthConfigRecord | None = None
        token_verifiers: list[MCPTokenVerifierRecord] = []
        active: DeploymentRecord | None = None
        try:
            async with self._database.session_scope() as session:
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
                        auth_config = await self._access.get_config(session, deployment.project_id)
                        token_verifiers = await self._access.active_verifiers(
                            session, deployment.project_id
                        )
                        active_id = project.active_deployment_id
                        active = (
                            await self._deployments.get(session, active_id)
                            if active_id is not None and active_id != deployment.id
                            else None
                        )
                        manifest_storage_key = build.manifest_storage_key
            if terminal_running is not None:
                activated = True
                await self._cleanup_superseded(terminal_running)
                return
            if activation_pending is not None:
                activated = True
                await self._finish_activation(activation_pending)
                return
            if manifest_storage_key is None:
                raise InvalidStateError("Deployment build has no manifest artifact")

            manifest_bytes = await self._artifact_storage.get(
                manifest_storage_key,
                max_bytes=self._manifest_max_bytes,
            )
            if hashlib.sha256(manifest_bytes).hexdigest() != deployment.manifest_sha256:
                raise ValidationError("Deployment manifest hash verification failed")
            manifest = MCPManifest.model_validate_json(manifest_bytes)
            validate_manifest(manifest)
            if manifest.project.id != str(deployment.project_id) or manifest.build.build_id != str(
                deployment.build_id
            ):
                raise InvalidStateError("Build manifest identity does not match deployment")
            bundle = await self._secrets.build_bundle(
                project_id=deployment.project_id,
                hostname=deployment.hostname,
                manifest=manifest,
                auth_config=auth_config,
                token_verifiers=token_verifiers,
            )
            mounts = await self._runtime_files.materialize(
                deployment.id,
                manifest_bytes=manifest_bytes,
                manifest_sha256=deployment.manifest_sha256,
                secret_bundle=bundle,
            )
            if deployment.stop_old_first and active is not None:
                await self._stop_existing(
                    active,
                    event_type="deployment.replacement_stopped",
                )
            async with self._database.session_scope() as session:
                deployment = await self._deployments.transition(
                    session,
                    deployment.id,
                    expected={DeploymentStatus.DEPLOYING, DeploymentStatus.HEALTHCHECK},
                    status=DeploymentStatus.HEALTHCHECK,
                    values={"health_status": "starting"},
                )
                if deployment is None:
                    raise InvalidStateError("Deployment was cancelled before startup")
            provisioned = await self._runtime.provision(deployment, mounts)
            async with self._database.session_scope() as session:
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
                activated = await self._deployments.begin_activation(session, deployment.id)
                if not activated:
                    raise InvalidStateError("Deployment was cancelled before activation")
            activated = True
            await self._finish_activation(deployment)
        except Exception as exc:
            if deployment is None:
                raise
            if activated:
                logger.error(
                    "post_activation_cleanup_failed",
                    extra={"deployment_id": str(deployment.id)},
                )
                raise
            await self._cleanup_failed_without_masking(deployment)
            code, summary, unhealthy = self._safe_failure(exc)
            if not final_attempt and is_retryable_deployment_error(exc):
                async with self._database.session_scope() as session:
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
            if failed is not None and (final_attempt or is_retryable_deployment_error(exc)):
                raise

    async def stop(self, deployment_id: UUID) -> None:
        deployment = await self._get_required(deployment_id)
        if deployment.status in {DeploymentStatus.STOPPED, DeploymentStatus.FAILED}:
            return
        await self._runtime.stop(deployment, remove=True)
        await self._runtime_files.remove(deployment.id)
        async with self._database.session_scope() as session:
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
        await self._runtime.cleanup_network_if_unused(deployment)

    async def _stop_existing(
        self,
        deployment: DeploymentRecord,
        *,
        event_type: str = "deployment.superseded",
    ) -> None:
        await self._runtime.stop(deployment, remove=True)
        await self._runtime_files.remove(deployment.id)
        async with self._database.session_scope() as session:
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

    async def _cleanup_superseded(self, running: DeploymentRecord) -> None:
        async with self._database.session_scope() as session:
            superseded = await self._deployments.find_superseded_running(session, running)
        for deployment in superseded:
            await self._stop_existing(deployment, event_type="deployment.superseded")

    async def _finish_activation(self, deployment: DeploymentRecord) -> None:
        await self._cleanup_superseded(deployment)
        async with self._database.session_scope() as session:
            running = await self._deployments.complete_activation(session, deployment.id)
            if running is None:
                raise InvalidStateError("Deployment could not complete activation")
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
                },
            )

    async def _get_required(self, deployment_id: UUID) -> DeploymentRecord:
        async with self._database.session_scope() as session:
            deployment = await self._deployments.get(session, deployment_id)
            if deployment is None:
                raise NotFoundError("Deployment was not found")
            return deployment

    async def _cleanup_failed_without_masking(self, deployment: DeploymentRecord) -> None:
        try:
            await self._runtime.cleanup_failed(deployment)
        except MCPlicaError:
            logger.warning(
                "failed_runtime_cleanup_failed",
                extra={"deployment_id": str(deployment.id)},
            )
        try:
            await self._runtime_files.remove(deployment.id)
        except MCPlicaError:
            logger.warning(
                "failed_runtime_secret_cleanup_failed",
                extra={"deployment_id": str(deployment.id)},
            )
        try:
            await self._runtime.cleanup_network_if_unused(deployment)
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
