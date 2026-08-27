import asyncio
import logging
from collections.abc import Awaitable
from typing import Protocol
from uuid import UUID

from app.clients.database import DatabaseClient
from app.clients.docker import DockerClient
from app.clients.queue import DeploymentQueueClient
from app.clients.runtime_files import RuntimeFilesClient
from app.clients.storage import FilesystemStorageClient
from app.core.config import Settings, get_settings
from app.core.crypto import configured_secret_cipher
from app.providers.storage import FilesystemArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.mcp_access import MCPAccessRepository
from app.repositories.projects import ProjectRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.repositories.sources import SourceRepository
from app.services.builds.configuration_identity import ExecutableConfigurationIdentity
from app.services.credentials import CredentialService
from app.services.deployment.command_dispatcher import RuntimeCommandDispatcher
from app.services.deployment.command_executor import RuntimeCommandExecutor
from app.services.deployment.preflight import DeploymentPreflight
from app.services.deployment.runtime_manager import RuntimeManager
from app.services.deployment.secret_materializer import DeploymentSecretMaterializer
from app.services.deployment.service import DeploymentRunner, DeploymentService

logger = logging.getLogger("mcplica.deployment.job")


class _AsyncClosable(Protocol):
    async def close(self) -> None: ...


async def _runner(
    settings: Settings,
) -> tuple[
    RuntimeCommandExecutor,
    DatabaseClient,
    FilesystemStorageClient,
    RuntimeFilesClient,
    DockerClient,
    DeploymentQueueClient,
]:
    if settings.secret_encryption_key is None:
        raise ValueError("deployment worker requires the configured secret encryption key")
    cipher = configured_secret_cipher(
        settings.secret_encryption_key.get_secret_value(),
        settings.secret_encryption_key_version,
    )
    database = DatabaseClient(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
    )
    storage: FilesystemStorageClient | None = None
    runtime_files: RuntimeFilesClient | None = None
    docker: DockerClient | None = None
    queue: DeploymentQueueClient | None = None
    try:
        storage = await asyncio.to_thread(FilesystemStorageClient, settings.artifact_root)
        runtime_files = RuntimeFilesClient(
            settings.runtime_worker_root,
            docker_host_root=settings.runtime_host_root,
            runtime_uid=settings.runtime_uid,
            runtime_gid=settings.runtime_gid,
            max_manifest_bytes=settings.runtime_manifest_max_bytes,
            max_secret_bundle_bytes=settings.runtime_secret_bundle_max_bytes,
        )
        docker = await DockerClient.connect(settings.docker_base_url)
        deployments = DeploymentRepository()
        commands = RuntimeCommandRepository()
        access = MCPAccessRepository()
        audit = AuditRepository()
        credentials_repository = CredentialRepository()
        projects = ProjectRepository()
        sources = SourceRepository()
        queue = DeploymentQueueClient(
            settings.redis_url,
            settings.deployment_queue_name,
            job_timeout_seconds=settings.deployment_job_timeout_seconds,
            max_attempts=settings.deployment_job_max_attempts,
        )
        dispatcher = RuntimeCommandDispatcher(
            database,
            commands,
            queue,
            interval_seconds=settings.runtime_command_dispatch_interval_seconds,
            lease_seconds=settings.runtime_command_dispatch_lease_seconds,
        )
        artifact_storage = FilesystemArtifactStorage(storage)
        preflight = DeploymentPreflight(
            access,
            credentials_repository,
            ExecutableConfigurationIdentity(projects, sources),
            artifact_storage,
            settings,
            manifest_max_bytes=settings.runtime_manifest_max_bytes,
        )
        deployment_service = DeploymentService(
            database,
            deployments,
            commands,
            audit,
            dispatcher,
            preflight,
            settings,
        )
        credentials = CredentialService(
            database,
            credentials_repository,
            projects,
            commands,
            audit,
            cipher,
            deployment_service,
        )
        runner = DeploymentRunner(
            database,
            deployments,
            audit,
            preflight,
            runtime_files,
            DeploymentSecretMaterializer(credentials, settings),
            RuntimeManager(docker, settings),
        )
        executor = RuntimeCommandExecutor(
            database,
            commands,
            deployments,
            runner,
            lease_seconds=settings.runtime_command_execution_lease_seconds,
        )
        return executor, database, storage, runtime_files, docker, queue
    except Exception:
        await _close_resources(database, storage, runtime_files, docker, queue)
        raise


async def _close_resources(*resources: _AsyncClosable | None) -> None:
    close_operations: list[Awaitable[None]] = []
    for resource in resources:
        if resource is None:
            continue
        close_operations.append(resource.close())
    results = await asyncio.gather(*close_operations, return_exceptions=True)
    if any(isinstance(result, BaseException) for result in results):
        logger.warning("deployment_job_resource_cleanup_failed")


async def _run(command_id: UUID) -> None:
    executor, database, storage, runtime_files, docker, queue = await _runner(get_settings())
    try:
        await executor.run(command_id)
    finally:
        await _close_resources(docker, queue, runtime_files, storage, database)


def run_runtime_command_job(command_id: str) -> None:
    asyncio.run(_run(UUID(command_id)))
