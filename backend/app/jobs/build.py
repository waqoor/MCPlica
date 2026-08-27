import asyncio
import logging
import time
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
from app.core.logging import configure_logging
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
    database = DatabaseClient(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
    )
    storage_client = await asyncio.to_thread(FilesystemStorageClient, settings.artifact_root)
    storage = FilesystemArtifactStorage(storage_client)
    http = HttpClient(timeout_seconds=settings.openrouter_timeout_seconds)
    milvus_client = MilvusVectorClient(settings.milvus_uri, settings.milvus_token)
    admission = BuildAdmissionService(
        database,
        BuildAdmissionRepository(),
        lease_seconds=settings.build_admission_lease_seconds,
    )
    heartbeat_stop = asyncio.Event()
    admission_lost = asyncio.Event()
    heartbeat_task: asyncio.Task[bool] | None = None
    keep_lease_for_retry = False
    try:
        if not await admission.begin(build_id, admission_token):
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
                owner_task,
                interval_seconds=settings.build_admission_heartbeat_seconds,
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
            await pipeline.run(build_id)
        except asyncio.CancelledError:
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
            )
            if final_attempt or not retryable:
                await pipeline.fail_from_exception(build_id, exc)
            keep_lease_for_retry = retryable and not final_attempt
            if final_attempt or retryable:
                raise
    finally:
        heartbeat_stop.set()
        if heartbeat_task is not None:
            lease_retained = await heartbeat_task
            if not lease_retained:
                outcome = "admission_lost"
        if keep_lease_for_retry:
            await admission.heartbeat(build_id, admission_token)
        else:
            await admission.release(build_id, admission_token)
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
        await milvus_client.close()
        await http.close()
        await storage_client.close()
        await database.close()


async def _heartbeat_admission(
    admission: BuildAdmissionService,
    build_id: UUID,
    token: UUID,
    stop_event: asyncio.Event,
    admission_lost: asyncio.Event,
    owner_task: asyncio.Task[object],
    *,
    interval_seconds: float,
) -> bool:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            return True
        except TimeoutError:
            try:
                if not await admission.heartbeat(build_id, token):
                    admission_lost.set()
                    owner_task.cancel()
                    return False
            except Exception:
                logging.getLogger("mcplica.builder").exception(
                    "build.admission_heartbeat_failed",
                    extra={"build_id": str(build_id)},
                )
    return True


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
    return isinstance(
        exc,
        (
            ClientConnectionError,
            ClientRateLimitError,
            ClientTimeoutError,
            ClientUnavailableError,
        ),
    )


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
