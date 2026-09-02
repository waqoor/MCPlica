import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update

from app.clients.build_queue import BuildQueueClient
from app.clients.database import DatabaseClient
from app.clients.storage import FilesystemStorageClient
from app.core.config import Settings
from app.core.exceptions import InvalidStateError, NotFoundError
from app.domain.auth import UserRole
from app.domain.builds import BuildConfiguration, BuildStatus, BuildTrigger
from app.domain.cleanup import CleanupJobStatus
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.build import Build
from app.models.cleanup import CleanupJob, CleanupTarget
from app.models.project import Project
from app.providers.storage import ArtifactStorage, FilesystemArtifactStorage
from app.providers.vector import VectorStore
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildAIRunRepository, BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.cleanup import CleanupRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.repositories.validation import ValidationRepository
from app.services.artifacts import ArtifactService
from app.services.build_admission import BuildAdmissionDispatcher
from app.services.builds import BuildService
from app.services.builds.cancellation import BuildCancellationService
from app.services.builds.service import SourceConfigurationProvider
from app.services.cleanup import CleanupService, CleanupWorker
from app.services.settings import OperationalSettingsProvider, SettingsService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=9_001)
PROJECT_ID = UUID(int=9_002)
QUEUED_BUILD_ID = UUID(int=9_003)
RUNNING_BUILD_ID = UUID(int=9_004)
QUEUED_ADMISSION_TOKEN = UUID(int=9_005)
RUNNING_ADMISSION_TOKEN = UUID(int=9_006)


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


def _config() -> dict[str, object]:
    return BuildConfiguration(
        inbound_auth_mode="static_bearer",
        include_documentation_in_analysis=False,
        max_operations=100,
        max_context_chars=20_000,
        max_ai_concurrency=2,
        retrieval_top_k=5,
        source_max_bytes=1_000_000,
        document_max_bytes=1_000_000,
        document_max_text_chars=1_000_000,
        pdf_max_pages=10,
        documentation_chunk_chars=1_000,
        documentation_chunk_overlap_chars=100,
        max_document_chunks=1_000,
        embedding_batch_size=16,
        max_embedding_concurrency=2,
        runtime_timeout_ms=30_000,
        runtime_max_request_bytes=1_000_000,
        runtime_max_response_bytes=1_000_000,
        runtime_manifest_max_bytes=1_000_000,
        artifact_max_bytes=10_000_000,
    ).model_dump(mode="json")


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(CleanupTarget))
        await session.execute(delete(CleanupJob))
        await session.execute(delete(AuditEvent).where(AuditEvent.project_id == PROJECT_ID))
        await session.execute(
            update(Project)
            .where(Project.id == PROJECT_ID)
            .values(active_build_id=None, active_deployment_id=None)
        )
        await session.execute(delete(Project).where(Project.id == PROJECT_ID))
        await session.execute(delete(User).where(User.id == USER_ID))


def _build(
    build_id: UUID,
    sequence: int,
    status: BuildStatus,
    *,
    manifest_storage_key: str | None = None,
) -> Build:
    now = datetime.now(UTC)
    return Build(
        id=build_id,
        project_id=PROJECT_ID,
        sequence=sequence,
        status=status,
        pipeline_stage=status,
        trigger=BuildTrigger.INITIAL,
        canonical_snapshot_id=None,
        previous_build_id=None,
        compiler_version="1.0.0",
        manifest_schema_version="mcp-manifest/v1",
        runtime_compatibility=">=1.0,<2.0",
        analysis_model="analysis/model",
        validation_model="validation/model",
        embedding_model="embedding/model",
        embedding_dimensions=None,
        prompt_bundle_version="1.0.0",
        build_config_json=_config(),
        enrichment_json=None,
        enrichment_sha256=None,
        manifest_sha256="a" * 64 if manifest_storage_key else None,
        artifact_sha256=None,
        manifest_storage_key=manifest_storage_key,
        artifact_storage_key=None,
        error_code=None,
        error_summary=None,
        requested_by=USER_ID,
        started_at=now if status is not BuildStatus.QUEUED else None,
        completed_at=None,
    )


async def _seed(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="build-cancel-test@example.com",
                display_name="Build cancellation test",
                password_hash="unused",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                name="Build cancellation test",
                slug="build-cancellation-test",
                description=None,
                default_base_url=None,
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="build-cancellation-test.mcp.example.com",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=USER_ID,
            )
        )
        await session.flush()
        queued = _build(QUEUED_BUILD_ID, 1, BuildStatus.QUEUED)
        now = datetime.now(UTC)
        queued.admission_token = QUEUED_ADMISSION_TOKEN
        queued.admission_acquired_at = now
        queued.admission_enqueued_at = now
        queued.admission_heartbeat_at = now
        queued.admission_lease_expires_at = now + timedelta(minutes=5)
        queued.admission_attempt_count = 1
        session.add(queued)


class _Queue:
    async def cancel_queued_build(self, build_id: UUID, admission_token: UUID | None) -> bool:
        return build_id == QUEUED_BUILD_ID and admission_token == QUEUED_ADMISSION_TOKEN


class _Admission:
    def wake(self) -> None:
        return None


class _FailOnceStorage:
    def __init__(self, delegate: FilesystemArtifactStorage, failing_key: str) -> None:
        self.delegate = delegate
        self.failing_key = failing_key
        self.calls = 0

    async def delete(self, storage_key: str) -> None:
        assert storage_key == self.failing_key
        self.calls += 1
        if self.calls == 1:
            raise OSError("injected object-store outage")
        await self.delegate.delete(storage_key)


async def test_cancellation_is_request_then_effective_acknowledgement(
    tmp_path: Path,
) -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    storage = FilesystemArtifactStorage(FilesystemStorageClient(str(tmp_path)))
    builds = BuildRepository()
    cleanup_repository = CleanupRepository()
    cleanup = CleanupService(
        database,
        cleanup_repository,
        AuditRepository(),
        orphan_guard_delay_seconds=300,
    )
    try:
        await _cleanup(database)
        await _seed(database)
        service = BuildService(
            database,
            builds,
            cast(BuildAIRunRepository, object()),
            cast(CanonicalRepository, object()),
            cast(SourceRepository, object()),
            cast(SourceConfigurationProvider, object()),
            cast(ProjectRepository, object()),
            cast(CredentialRepository, object()),
            cast(ValidationRepository, object()),
            AuditRepository(),
            cast(SettingsService, object()),
            cast(BuildQueueClient, _Queue()),
            Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
            ArtifactService(storage),
            cleanup,
            cast(BuildAdmissionDispatcher, _Admission()),
        )

        queued = await service.cancel(
            QUEUED_BUILD_ID,
            actor_user_id=USER_ID,
            request_id="cancel-queued",
        )
        assert queued.status is BuildStatus.CANCELLED
        assert queued.pipeline_stage is BuildStatus.QUEUED
        assert queued.cancellation_requested_at is not None
        assert queued.cancellation_acknowledged_at is not None
        assert queued.admission_token is None

        partial_manifest_key = "build-cancellation/running-manifest.json"
        await storage.put_exact(partial_manifest_key, b"partial manifest")
        async with database.session_scope() as session:
            running_model = _build(
                RUNNING_BUILD_ID,
                2,
                BuildStatus.ANALYZING,
                manifest_storage_key=partial_manifest_key,
            )
            lease_time = datetime.now(UTC)
            running_model.admission_token = RUNNING_ADMISSION_TOKEN
            running_model.admission_acquired_at = lease_time
            running_model.admission_heartbeat_at = lease_time
            running_model.admission_lease_expires_at = lease_time + timedelta(minutes=5)
            running_model.admission_attempt_count = 1
            session.add(running_model)

        running = await service.cancel(
            RUNNING_BUILD_ID,
            actor_user_id=USER_ID,
            request_id="cancel-running",
        )
        assert running.status is BuildStatus.ANALYZING
        assert running.cancellation_requested_at is not None
        assert running.cancellation_acknowledged_at is None
        assert running.completed_at is None

        async with database.session_scope() as session:
            with pytest.raises(InvalidStateError, match="cancellation"):
                await builds.transition(
                    session,
                    RUNNING_BUILD_ID,
                    expected=BuildStatus.ANALYZING,
                    target=BuildStatus.COMPILING,
                    admission_token=RUNNING_ADMISSION_TOKEN,
                )
        async with database.session_scope() as session:
            build = await builds.get(session, RUNNING_BUILD_ID)
            assert build is not None
            result = await BuildCancellationService(
                builds,
                cleanup_repository,
                AuditRepository(),
            ).acknowledge(
                session,
                build_id=RUNNING_BUILD_ID,
                admission_token=RUNNING_ADMISSION_TOKEN,
                actor_user_id=USER_ID,
                request_id="worker-ack",
                acknowledgement="worker",
            )
            acknowledged = result.build
            job = result.cleanup_job
            assert job is not None
            assert acknowledged.status is BuildStatus.CANCELLED
            assert acknowledged.pipeline_stage is BuildStatus.ANALYZING
            assert acknowledged.cancellation_acknowledged_at is not None
            assert acknowledged.manifest_storage_key is None
            assert job.status is CleanupJobStatus.PENDING
            assert job.total_targets == 1

        failing_storage = _FailOnceStorage(storage, partial_manifest_key)
        worker = CleanupWorker(
            database,
            cleanup_repository,
            AuditRepository(),
            cast(ArtifactStorage, failing_storage),
            cast(VectorStore, object()),
            cast(OperationalSettingsProvider, object()),
            # A zero retry delay makes the target immediately due again. The worker must
            # still attempt a given target at most once in a single dispatch cycle.
            interval_seconds=0,
            lease_seconds=5,
            max_attempts=3,
            retention_interval_seconds=3_600,
        )
        assert await worker.process_due_targets_once() == 1
        retrying = await cleanup.get(job.id)
        assert retrying.status is CleanupJobStatus.RETRYING
        async with database.session_scope() as session:
            await cleanup_repository.make_job_due(session, job.id)
        assert await worker.process_due_targets_once() == 1
        completed = await cleanup.get(job.id)
        assert completed.status is CleanupJobStatus.COMPLETED
        assert failing_storage.calls == 2
        with pytest.raises(NotFoundError):
            await storage.get(partial_manifest_key)

        async with database.session_scope() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.project_id == PROJECT_ID)
                    .order_by(AuditEvent.created_at)
                )
            )
            assert [event.event_type for event in events].count("build.cancellation_requested") == 2
            assert [event.event_type for event in events].count("build.cancelled") == 2
    finally:
        await _cleanup(database)
        await database.close()
