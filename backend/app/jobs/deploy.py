import asyncio
import logging
from collections.abc import Awaitable
from typing import Protocol
from uuid import UUID

from rq import get_current_job

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
from app.services.credentials import CredentialService
from app.services.deployment.runtime_manager import RuntimeManager
from app.services.deployment.secret_materializer import DeploymentSecretMaterializer
from app.services.deployment.service import DeploymentRunner, DeploymentService

logger = logging.getLogger("mcplica.deployment.job")


class _AsyncClosable(Protocol):
    async def close(self) -> None: ...


async def _runner(
    settings: Settings,
) -> tuple[
    DeploymentRunner,
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
        access = MCPAccessRepository()
        audit = AuditRepository()
        credentials_repository = CredentialRepository()
        projects = ProjectRepository()
        queue = DeploymentQueueClient(
            settings.redis_url,
            settings.deployment_queue_name,
            job_timeout_seconds=settings.deployment_job_timeout_seconds,
            max_attempts=settings.deployment_job_max_attempts,
        )
        deployment_service = DeploymentService(
            database,
            deployments,
            audit,
            queue,
            settings,
        )
        credentials = CredentialService(
            database,
            credentials_repository,
            projects,
            audit,
            cipher,
            deployment_service,
        )
        runner = DeploymentRunner(
            database,
            deployments,
            access,
            audit,
            FilesystemArtifactStorage(storage),
            runtime_files,
            DeploymentSecretMaterializer(credentials, settings),
            RuntimeManager(docker, settings),
            manifest_max_bytes=settings.runtime_manifest_max_bytes,
        )
        return runner, database, storage, runtime_files, docker, queue
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


async def _run(deployment_id: UUID, *, stop: bool) -> None:
    runner, database, storage, runtime_files, docker, queue = await _runner(get_settings())
    try:
        if stop:
            await runner.stop(deployment_id)
        else:
            job = get_current_job()
            final_attempt = job is None or not job.should_retry
            await runner.run(deployment_id, final_attempt=final_attempt)
    finally:
        await _close_resources(docker, queue, runtime_files, storage, database)


def run_deployment_job(deployment_id: str) -> None:
    asyncio.run(_run(UUID(deployment_id), stop=False))


def run_stop_deployment_job(deployment_id: str) -> None:
    asyncio.run(_run(UUID(deployment_id), stop=True))
