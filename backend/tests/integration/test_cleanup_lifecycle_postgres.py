import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update

from app.clients.database import DatabaseClient
from app.clients.http import HttpClient
from app.clients.storage import BytesReader, FilesystemStorageClient
from app.core.exceptions import NotFoundError
from app.core.network_policy import UrlPolicy
from app.domain.auth import UserRole
from app.domain.builds import BuildStatus, BuildTrigger
from app.domain.cleanup import CleanupJobKind, CleanupJobStatus
from app.domain.indexing import IndexGenerationStatus
from app.domain.sources import SourceKind, SourceOrigin
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.build import Build
from app.models.cleanup import CleanupJob, CleanupTarget
from app.models.indexing import DocumentIndexGeneration
from app.models.project import Project
from app.models.source import ProjectSource, SourceVersion
from app.providers.storage import ArtifactStorage, FilesystemArtifactStorage
from app.providers.vector import VectorStore
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.cleanup import CleanupRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.projects import ProjectRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.repositories.sources import SourceRepository
from app.services.cleanup import CleanupService, CleanupWorker
from app.services.projects import ProjectDeploymentLifecycle, ProjectService
from app.services.settings import OperationalSettingsProvider
from app.services.sources import SourceService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=8_001)
PROJECT_ID = UUID(int=8_002)
SHARED_PROJECT_ID = UUID(int=8_003)
RETENTION_PROJECT_ID = UUID(int=8_004)
SOURCE_ID = UUID(int=8_010)
SHARED_SOURCE_ID = UUID(int=8_011)
RETENTION_SOURCE_ID = UUID(int=8_012)


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


@dataclass(slots=True)
class _Operational:
    max_upload_bytes: int = 1_000_000
    builders_can_deploy: bool = True
    mcp_base_domain: str = "mcp.localhost"
    source_retention_days: int | None = 30
    build_retention_count: int | None = 1


class _Settings:
    async def get_operational(self) -> _Operational:
        return _Operational()


class _VectorStore:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, UUID, UUID]] = []

    async def delete_generation(
        self, *, collection: str, project_id: UUID, generation_id: UUID
    ) -> None:
        self.deleted.append((collection, project_id, generation_id))


class _FailOnceStorage:
    def __init__(self, delegate: ArtifactStorage, failing_key: str) -> None:
        self.delegate = delegate
        self.failing_key = failing_key
        self.calls: list[str] = []
        self.failed = False

    async def delete(self, storage_key: str) -> None:
        self.calls.append(storage_key)
        if storage_key == self.failing_key and not self.failed:
            self.failed = True
            raise OSError("injected object-store outage")
        await self.delegate.delete(storage_key)


async def _cleanup(database: DatabaseClient) -> None:
    project_ids = {PROJECT_ID, SHARED_PROJECT_ID, RETENTION_PROJECT_ID}
    async with database.session_scope() as session:
        await session.execute(delete(CleanupTarget))
        await session.execute(delete(CleanupJob))
        await session.execute(delete(AuditEvent).where(AuditEvent.project_id.in_(project_ids)))
        await session.execute(
            update(Project)
            .where(Project.id.in_(project_ids))
            .values(active_build_id=None, active_deployment_id=None)
        )
        await session.execute(delete(Project).where(Project.id.in_(project_ids)))
        await session.execute(delete(User).where(User.id == USER_ID))


def _project(project_id: UUID, slug: str) -> Project:
    return Project(
        id=project_id,
        name=slug,
        slug=slug,
        description=None,
        default_base_url=None,
        active_server_ref=None,
        server_mappings={},
        mcp_hostname=f"{slug}.mcp.example.com",
        is_enabled=True,
        active_build_id=None,
        active_deployment_id=None,
        created_by=USER_ID,
    )


def _failed_build(
    build_id: UUID,
    project_id: UUID,
    sequence: int,
    *,
    created_at: datetime,
    manifest_key: str | None = None,
    artifact_key: str | None = None,
) -> Build:
    return Build(
        id=build_id,
        project_id=project_id,
        sequence=sequence,
        status=BuildStatus.FAILED,
        trigger=BuildTrigger.INITIAL,
        canonical_snapshot_id=None,
        previous_build_id=None,
        compiler_version="1.0.0",
        manifest_schema_version="mcp-manifest/v1",
        runtime_compatibility=">=1.0,<2.0",
        analysis_model=None,
        validation_model=None,
        embedding_model=None,
        embedding_dimensions=None,
        prompt_bundle_version=None,
        build_config_json={"runtime_manifest_max_bytes": 10_000_000},
        enrichment_json=None,
        enrichment_sha256=None,
        manifest_sha256="a" * 64 if manifest_key else None,
        artifact_sha256="b" * 64 if artifact_key else None,
        manifest_storage_key=manifest_key,
        artifact_storage_key=artifact_key,
        error_code="INJECTED",
        error_summary="test",
        requested_by=USER_ID,
        started_at=created_at,
        completed_at=created_at,
        created_at=created_at,
    )


async def _seed(database: DatabaseClient, storage: FilesystemArtifactStorage) -> None:
    now = datetime.now(UTC)
    shared_key = "shared/source.json"
    manifest_key = "manifests/deleted.json"
    artifact_key = "exports/deleted.zip"
    chunk_key = "chunks/deleted.json"
    for key, value in (
        (shared_key, b"shared"),
        (manifest_key, b"manifest"),
        (artifact_key, b"export"),
        (chunk_key, b"chunks"),
    ):
        await storage.put_exact(key, value)
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="cleanup-test@example.com",
                display_name="Cleanup test",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add_all(
            [
                _project(PROJECT_ID, "cleanup-deleted"),
                _project(SHARED_PROJECT_ID, "cleanup-shared"),
                _project(RETENTION_PROJECT_ID, "cleanup-retention"),
            ]
        )
        await session.flush()
        session.add_all(
            [
                ProjectSource(
                    id=SOURCE_ID,
                    project_id=PROJECT_ID,
                    kind=SourceKind.DOCUMENTATION,
                    name="Deleted source",
                    origin_type=SourceOrigin.UPLOAD,
                    source_url=None,
                    is_primary=False,
                ),
                ProjectSource(
                    id=SHARED_SOURCE_ID,
                    project_id=SHARED_PROJECT_ID,
                    kind=SourceKind.DOCUMENTATION,
                    name="Shared source",
                    origin_type=SourceOrigin.UPLOAD,
                    source_url=None,
                    is_primary=False,
                ),
                ProjectSource(
                    id=RETENTION_SOURCE_ID,
                    project_id=RETENTION_PROJECT_ID,
                    kind=SourceKind.DOCUMENTATION,
                    name="Retention source",
                    origin_type=SourceOrigin.UPLOAD,
                    source_url=None,
                    is_primary=False,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                SourceVersion(
                    id=UUID(int=8_020),
                    source_id=SOURCE_ID,
                    content_sha256="1" * 64,
                    media_type="application/json",
                    storage_key=shared_key,
                    byte_size=6,
                    detected_format="json",
                    created_by=USER_ID,
                ),
                SourceVersion(
                    id=UUID(int=8_021),
                    source_id=SHARED_SOURCE_ID,
                    content_sha256="2" * 64,
                    media_type="application/json",
                    storage_key=shared_key,
                    byte_size=6,
                    detected_format="json",
                    created_by=USER_ID,
                ),
            ]
        )
        build = _failed_build(
            UUID(int=8_030),
            PROJECT_ID,
            1,
            created_at=now,
            manifest_key=manifest_key,
            artifact_key=artifact_key,
        )
        session.add(build)
        await session.flush()
        session.add(
            DocumentIndexGeneration(
                id=UUID(int=8_031),
                project_id=PROJECT_ID,
                build_id=build.id,
                embedding_model="embedding/test",
                dimensions=3,
                collection_name="chunks_3",
                generation_key="3" * 64,
                chunk_count=1,
                chunk_manifest_storage_key=chunk_key,
                chunk_manifest_sha256="4" * 64,
                source_fingerprint="5" * 64,
                status=IndexGenerationStatus.FAILED,
                error_summary="test",
                completed_at=now,
            )
        )


def _worker(
    database: DatabaseClient,
    repository: CleanupRepository,
    storage: ArtifactStorage,
    vector: _VectorStore,
) -> CleanupWorker:
    return CleanupWorker(
        database,
        repository,
        AuditRepository(),
        storage,
        cast(VectorStore, vector),
        cast(OperationalSettingsProvider, _Settings()),
        interval_seconds=0.1,
        lease_seconds=5,
        max_attempts=3,
        retention_interval_seconds=3_600,
    )


async def test_project_delete_cleanup_is_reference_aware_and_exact(
    tmp_path: Path,
) -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    storage = FilesystemArtifactStorage(FilesystemStorageClient(str(tmp_path)))
    repository = CleanupRepository()
    vector = _VectorStore()
    try:
        await _cleanup(database)
        await _seed(database, storage)
        cleanup = CleanupService(
            database,
            repository,
            AuditRepository(),
            orphan_guard_delay_seconds=300,
        )
        service = ProjectService(
            database,
            ProjectRepository(),
            AuditRepository(),
            cast(RuntimeCommandRepository, object()),
            cast(ProjectDeploymentLifecycle, object()),
            cast(OperationalSettingsProvider, _Settings()),
            cleanup,
        )

        job = await service.delete(
            PROJECT_ID,
            actor_user_id=USER_ID,
            request_id="delete-project",
        )
        assert job is not None
        assert job.total_targets == 5
        async with database.session_scope() as session:
            assert await session.get(Project, PROJECT_ID) is None
        assert await storage.get("manifests/deleted.json") == b"manifest"

        worker = _worker(database, repository, storage, vector)
        assert await worker.process_due_targets_once() == 5
        completed = await cleanup.get(job.id)
        assert completed.status is CleanupJobStatus.COMPLETED
        assert completed.completed_targets == 4
        assert completed.skipped_targets == 1
        assert await storage.get("shared/source.json") == b"shared"
        with pytest.raises(NotFoundError):
            await storage.get("manifests/deleted.json")
        assert vector.deleted == [("chunks_3", PROJECT_ID, UUID(int=8_031))]
    finally:
        await _cleanup(database)
        await database.close()


async def test_cleanup_partial_failure_retries_without_replaying_success(
    tmp_path: Path,
) -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    base_storage = FilesystemArtifactStorage(FilesystemStorageClient(str(tmp_path)))
    repository = CleanupRepository()
    vector = _VectorStore()
    first_key = "retry/first"
    failing_key = "retry/failing"
    try:
        await _cleanup(database)
        await _seed(database, base_storage)
        await base_storage.put_exact(first_key, b"first")
        await base_storage.put_exact(failing_key, b"failing")
        async with database.session_scope() as session:
            job = await repository.create_job(
                session,
                kind=CleanupJobKind.ORPHAN_GUARD,
                idempotency_key="cleanup-retry-test",
                project_id=None,
                requested_by=USER_ID,
                request_id="retry",
            )
            await repository.add_object_target(session, job.id, first_key)
            await repository.add_object_target(session, job.id, failing_key)
        failing_storage = _FailOnceStorage(base_storage, failing_key)
        worker = _worker(
            database,
            repository,
            cast(ArtifactStorage, failing_storage),
            vector,
        )
        assert await worker.process_due_targets_once() == 2
        async with database.session_scope() as session:
            await repository.make_job_due(session, job.id)
        assert await worker.process_due_targets_once() == 1
        result = CleanupService(
            database,
            repository,
            AuditRepository(),
            orphan_guard_delay_seconds=300,
        )
        completed = await result.get(job.id)
        assert completed.status is CleanupJobStatus.COMPLETED
        assert failing_storage.calls.count(first_key) == 1
        assert failing_storage.calls.count(failing_key) == 2
    finally:
        await _cleanup(database)
        await database.close()


async def test_retention_preserves_latest_and_exact_cutoff_and_removes_old_builds(
    tmp_path: Path,
) -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    storage = FilesystemArtifactStorage(FilesystemStorageClient(str(tmp_path)))
    repository = CleanupRepository()
    vector = _VectorStore()
    fixed_now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    cutoff = fixed_now - timedelta(days=30)
    try:
        await _cleanup(database)
        await _seed(database, storage)
        keys = ["retention/latest", "retention/boundary", "retention/expired"]
        for key in keys:
            await storage.put_exact(key, key.encode())
        async with database.session_scope() as session:
            session.add_all(
                [
                    SourceVersion(
                        id=UUID(int=8_040),
                        source_id=RETENTION_SOURCE_ID,
                        content_sha256="6" * 64,
                        media_type="text/plain",
                        storage_key=keys[0],
                        byte_size=1,
                        detected_format="text",
                        created_by=USER_ID,
                        created_at=fixed_now,
                    ),
                    SourceVersion(
                        id=UUID(int=8_041),
                        source_id=RETENTION_SOURCE_ID,
                        content_sha256="7" * 64,
                        media_type="text/plain",
                        storage_key=keys[1],
                        byte_size=1,
                        detected_format="text",
                        created_by=USER_ID,
                        created_at=cutoff,
                    ),
                    SourceVersion(
                        id=UUID(int=8_042),
                        source_id=RETENTION_SOURCE_ID,
                        content_sha256="8" * 64,
                        media_type="text/plain",
                        storage_key=keys[2],
                        byte_size=1,
                        detected_format="text",
                        created_by=USER_ID,
                        created_at=cutoff - timedelta(microseconds=1),
                    ),
                    _failed_build(
                        UUID(int=8_043),
                        RETENTION_PROJECT_ID,
                        1,
                        created_at=fixed_now - timedelta(days=2),
                    ),
                    _failed_build(
                        UUID(int=8_044),
                        RETENTION_PROJECT_ID,
                        2,
                        created_at=fixed_now - timedelta(days=1),
                    ),
                ]
            )
        async with database.session_scope() as session:
            job = await repository.prepare_retention_job(
                session,
                project_id=RETENTION_PROJECT_ID,
                build_retention_count=1,
                source_retention_days=30,
                now=fixed_now,
            )
        assert job is not None
        async with database.session_scope() as session:
            assert await session.get(SourceVersion, UUID(int=8_040)) is not None
            assert await session.get(SourceVersion, UUID(int=8_041)) is not None
            assert await session.get(SourceVersion, UUID(int=8_042)) is None
            assert await session.get(Build, UUID(int=8_043)) is None
            assert await session.get(Build, UUID(int=8_044)) is not None
        worker = _worker(database, repository, storage, vector)
        assert await worker.process_due_targets_once() == 1
        with pytest.raises(NotFoundError):
            await storage.get(keys[2])
        assert await storage.get(keys[1]) == keys[1].encode()
    finally:
        await _cleanup(database)
        await database.close()


async def test_upload_persistence_failure_is_durably_compensated(tmp_path: Path) -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    storage = FilesystemArtifactStorage(FilesystemStorageClient(str(tmp_path)))
    repository = CleanupRepository()
    vector = _VectorStore()
    try:
        await _cleanup(database)
        async with database.session_scope() as session:
            session.add(
                User(
                    id=USER_ID,
                    email="cleanup-test@example.com",
                    display_name="Cleanup test",
                    password_hash="not-used",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )
        cleanup = CleanupService(
            database,
            repository,
            AuditRepository(),
            orphan_guard_delay_seconds=300,
        )
        service = SourceService(
            database,
            SourceRepository(),
            ProjectRepository(),
            cast(BuildRepository, object()),
            cast(CanonicalRepository, object()),
            cast(IndexGenerationRepository, object()),
            AuditRepository(),
            storage,
            cast(HttpClient, object()),
            UrlPolicy(),
            cast(OperationalSettingsProvider, _Settings()),
            canonicalization=None,
            document_max_bytes=1_000_000,
            fetch_max_bytes=1_000_000,
            fetch_max_redirects=1,
            fetch_max_attempts=1,
            cleanup=cleanup,
        )
        with pytest.raises(NotFoundError):
            await service.create_with_upload(
                source_id=UUID(int=8_050),
                project_id=UUID(int=8_099),
                kind=SourceKind.OPENAPI,
                name="Orphaned upload",
                is_primary=True,
                content=BytesReader(
                    b'{"openapi":"3.1.0","info":{"title":"T","version":"1"},"paths":{}}'
                ),
                media_type="application/json",
                filename="openapi.json",
                actor_user_id=USER_ID,
                request_id="orphan-upload",
            )
        stored_files = [path for path in tmp_path.rglob("*") if path.is_file()]
        assert len(stored_files) == 1

        worker = _worker(database, repository, storage, vector)
        assert await worker.process_due_targets_once() == 1
        assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
        async with database.session_scope() as session:
            job = await session.scalar(
                select(CleanupJob).where(CleanupJob.kind == CleanupJobKind.ORPHAN_GUARD)
            )
            assert job is not None
            assert job.status is CleanupJobStatus.COMPLETED
    finally:
        await _cleanup(database)
        await database.close()
