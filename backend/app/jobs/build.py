import asyncio
import logging
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from uuid import UUID

from rq import get_current_job

from app.clients.ai import OpenRouterClient
from app.clients.database import DatabaseClient
from app.clients.http import HttpClient
from app.clients.mcp import MCPValidationClient
from app.clients.storage import FilesystemStorageClient
from app.clients.vector import MilvusVectorClient
from app.core.config import Settings, get_settings
from app.core.crypto import configured_secret_cipher
from app.core.exceptions import (
    ClientConnectionError,
    ClientRateLimitError,
    ClientTimeoutError,
    ClientUnavailableError,
)
from app.core.lifecycle import register_bounded_close
from app.core.logging import configure_logging
from app.domain.build_admission import BuildLeaseState
from app.observability import observe_build_job
from app.providers.ai.openrouter import OpenRouterProvider
from app.providers.milvus import MilvusVectorStore
from app.providers.storage import FilesystemArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.build_admission import BuildAdmissionRepository
from app.repositories.builds import BuildAIRunRepository, BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.cleanup import CleanupRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.projects import ProjectRepository
from app.repositories.settings import SettingsRepository
from app.repositories.sources import SourceRepository
from app.repositories.validation import ValidationRepository
from app.services.analysis import AnalysisService, SemanticReviewService
from app.services.analysis.retrieval import RetrievalService
from app.services.artifacts import ArtifactService
from app.services.build_admission import BuildAdmissionService
from app.services.builds.pipeline import BuildPipeline
from app.services.canonicalization import CanonicalizationService
from app.services.indexing import IndexingService
from app.services.settings import SettingsService
from app.services.validation import ValidationService


@dataclass(slots=True)
class _BuildJobClients:
    database: DatabaseClient
    storage_client: FilesystemStorageClient
    storage: FilesystemArtifactStorage
    http: HttpClient
    milvus: MilvusVectorClient
    stack: AsyncExitStack

    async def close(self) -> None:
        await self.stack.aclose()


async def _create_build_job_clients(settings: Settings) -> _BuildJobClients:
    stack = AsyncExitStack()
    await stack.__aenter__()
    try:
        database = DatabaseClient(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout_seconds=settings.database_pool_timeout_seconds,
        )
        register_bounded_close(
            stack,
            name="build-database",
            callback=database.close,
            timeout_seconds=settings.shutdown_timeout_seconds,
        )
        storage_client = await asyncio.to_thread(
            FilesystemStorageClient,
            settings.artifact_root,
        )
        register_bounded_close(
            stack,
            name="build-storage",
            callback=storage_client.close,
            timeout_seconds=settings.shutdown_timeout_seconds,
        )
        storage = FilesystemArtifactStorage(storage_client)
        http = HttpClient(timeout_seconds=settings.openrouter_timeout_seconds)
        register_bounded_close(
            stack,
            name="build-http",
            callback=http.close,
            timeout_seconds=settings.shutdown_timeout_seconds,
        )
        milvus = MilvusVectorClient(settings.milvus_uri, settings.milvus_token)
        register_bounded_close(
            stack,
            name="build-milvus",
            callback=milvus.close,
            timeout_seconds=settings.shutdown_timeout_seconds,
        )
    except BaseException:
        await stack.aclose()
        raise
    return _BuildJobClients(database, storage_client, storage, http, milvus, stack)


async def _run(
    build_id: UUID,
    admission_token: UUID,
    *,
    final_attempt: bool,
    attempt_number: int,
) -> None:
    started = time.perf_counter()
    outcome = "succeeded"
    job = get_current_job()
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    logger = logging.getLogger("mcplica.builder")
    clients = await _create_build_job_clients(settings)
    database = clients.database
    storage = clients.storage
    http = clients.http
    milvus_client = clients.milvus
    admission = BuildAdmissionService(
        database,
        BuildAdmissionRepository(),
        lease_seconds=settings.build_admission_lease_seconds,
    )
    heartbeat_stop = asyncio.Event()
    admission_lost = asyncio.Event()
    cancellation_requested = asyncio.Event()
    heartbeat_task: asyncio.Task[BuildLeaseState] | None = None
    keep_lease_for_retry = False
    try:
        begin_started = time.monotonic()
        initial_lease = await admission.begin(build_id, admission_token)
        if initial_lease.state is BuildLeaseState.LOST:
            outcome = "stale_admission"
            logger.info(
                "build.admission_rejected",
                extra={"build_id": str(build_id)},
            )
            return
        owner_task = asyncio.current_task()
        assert owner_task is not None
        heartbeat_task = asyncio.create_task(
            _heartbeat_admission(
                admission,
                build_id,
                admission_token,
                heartbeat_stop,
                admission_lost,
                cancellation_requested,
                owner_task,
                interval_seconds=settings.build_admission_heartbeat_seconds,
                lease_seconds=settings.build_admission_lease_seconds,
                confirmed_deadline=begin_started + settings.build_admission_lease_seconds,
            ),
            name=f"build-admission-heartbeat-{build_id}",
        )
        pipeline = _pipeline(
            settings,
            database=database,
            storage=storage,
            http=http,
            milvus_client=milvus_client,
        )
        try:
            await pipeline.run(build_id, admission_token)
        except asyncio.CancelledError:
            if cancellation_requested.is_set():
                outcome = "cancelled"
                await pipeline.acknowledge_cancellation(build_id, admission_token)
                return
            if admission_lost.is_set():
                outcome = "admission_lost"
                return
            raise
        except Exception as exc:
            retryable = is_retryable_build_error(exc)
            outcome = "retry_scheduled" if retryable and not final_attempt else "failed"
            await pipeline.record_attempt_failure(
                build_id,
                exc,
                attempt_number=attempt_number,
                retry_scheduled=retryable and not final_attempt,
                admission_token=admission_token,
            )
            if final_attempt or not retryable:
                await pipeline.fail_from_exception(
                    build_id,
                    exc,
                    admission_token=admission_token,
                )
            keep_lease_for_retry = retryable and not final_attempt
            if final_attempt or retryable:
                raise
    finally:
        heartbeat_stop.set()
        try:
            if heartbeat_task is not None:
                lease_state = await heartbeat_task
                if lease_state is BuildLeaseState.LOST:
                    outcome = "admission_lost"
            if keep_lease_for_retry:
                await admission.heartbeat(build_id, admission_token)
            else:
                await admission.release(build_id, admission_token)
        finally:
            duration = time.perf_counter() - started
            observe_build_job(outcome, duration)
            logger.info(
                "build.job_completed",
                extra={
                    "service": "mcplica-builder",
                    "component": "build-job",
                    "job_id": job.id if job is not None else None,
                    "build_id": str(build_id),
                    "attempt_number": attempt_number,
                    "duration_ms": round(duration * 1_000, 3),
                    "error_code": None if outcome == "succeeded" else outcome,
                },
            )
            await clients.close()


async def _heartbeat_admission(
    admission: BuildAdmissionService,
    build_id: UUID,
    token: UUID,
    stop_event: asyncio.Event,
    admission_lost: asyncio.Event,
    cancellation_requested: asyncio.Event,
    owner_task: asyncio.Task[object],
    *,
    interval_seconds: float,
    lease_seconds: float,
    confirmed_deadline: float,
) -> BuildLeaseState:
    while not stop_event.is_set():
        remaining = confirmed_deadline - time.monotonic()
        if remaining <= 0:
            admission_lost.set()
            owner_task.cancel()
            return BuildLeaseState.LOST
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=min(interval_seconds, remaining),
            )
            return BuildLeaseState.OWNED
        except TimeoutError:
            try:
                renewal_started = time.monotonic()
                async with asyncio.timeout(max(0.001, confirmed_deadline - renewal_started)):
                    renewal = await admission.heartbeat(build_id, token)
                if renewal.state is BuildLeaseState.CANCELLATION_REQUESTED:
                    cancellation_requested.set()
                    owner_task.cancel()
                    return renewal.state
                if renewal.state is BuildLeaseState.LOST:
                    admission_lost.set()
                    owner_task.cancel()
                    return renewal.state
                confirmed_deadline = renewal_started + lease_seconds
            except Exception:
                logging.getLogger("mcplica.builder").exception(
                    "build.admission_heartbeat_failed",
                    extra={"build_id": str(build_id)},
                )
    return BuildLeaseState.OWNED


def _pipeline(
    settings: Settings,
    *,
    database: DatabaseClient,
    storage: FilesystemArtifactStorage,
    http: HttpClient,
    milvus_client: MilvusVectorClient,
) -> BuildPipeline:
    audit = AuditRepository()
    builds = BuildRepository()
    ai_runs = BuildAIRunRepository()
    projects = ProjectRepository()
    sources = SourceRepository()
    snapshots = CanonicalRepository()
    generations = IndexGenerationRepository()
    reports = ValidationRepository()
    settings_repository = SettingsRepository()
    cipher = configured_secret_cipher(
        (
            settings.secret_encryption_key.get_secret_value()
            if settings.secret_encryption_key is not None
            else None
        ),
        settings.secret_encryption_key_version,
        previous_encoded_keys={
            version: key.get_secret_value()
            for version, key in settings.secret_encryption_previous_keys.items()
        },
        allow_ephemeral=settings.env == "test",
    )
    settings_service = SettingsService(
        database,
        settings_repository,
        audit,
        cipher,
        settings,
    )

    async def resolve_openrouter_key() -> str | None:
        return await settings_service.resolve_openrouter_api_key()

    openrouter = OpenRouterClient(
        http,
        resolve_openrouter_key,
        settings.openrouter_base_url,
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
        max_attempts=settings.openrouter_max_attempts,
        timeout_seconds=settings.openrouter_timeout_seconds,
    )
    ai = OpenRouterProvider(
        openrouter,
        structured_attempts=settings.openrouter_structured_max_attempts,
    )
    vector_store = MilvusVectorStore(milvus_client, settings.milvus_collection)
    canonicalization = CanonicalizationService(
        database,
        projects,
        sources,
        snapshots,
        storage,
    )
    indexing = IndexingService(
        database,
        sources,
        generations,
        storage,
        ai,
        vector_store,
    )
    retrieval = RetrievalService(ai, vector_store)
    analysis = AnalysisService(database, ai, retrieval, ai_runs)
    semantic_review = SemanticReviewService(database, ai, ai_runs)
    artifacts = ArtifactService(storage)
    validation = ValidationService(
        database,
        reports,
        semantic_review,
        MCPValidationClient(
            validator_endpoint=str(settings.mcp_runtime_validator_url),
            timeout_seconds=settings.mcp_runtime_validator_timeout_seconds,
        ),
        runtime_version=settings.mcp_runtime_version,
    )
    return BuildPipeline(
        database,
        builds,
        projects,
        sources,
        generations,
        reports,
        audit,
        storage,
        canonicalization,
        indexing,
        analysis,
        validation,
        artifacts,
        CleanupRepository(),
    )


def is_retryable_build_error(exc: Exception) -> bool:
    retryable = (
        ClientConnectionError,
        ClientRateLimitError,
        ClientTimeoutError,
        ClientUnavailableError,
    )
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, retryable):
            return True
        current = current.__cause__
    return False


def run_build_job(build_id: str, admission_token: str) -> None:
    job = get_current_job()
    final_attempt = job is None or not job.should_retry
    retries_left = job.retries_left if job is not None and job.retries_left is not None else 0
    raw_max_attempts = job.meta.get("max_attempts") if job is not None else None
    max_attempts = (
        raw_max_attempts
        if isinstance(raw_max_attempts, int) and raw_max_attempts > 0
        else retries_left + 1
    )
    attempt_number = max(1, max_attempts - retries_left)
    asyncio.run(
        _run(
            UUID(build_id),
            UUID(admission_token),
            final_attempt=final_attempt,
            attempt_number=attempt_number,
        )
    )
