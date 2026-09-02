import asyncio
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import delete, update

from app.clients.build_queue import BuildQueueClient
from app.clients.database import DatabaseClient
from app.core.exceptions import InvalidStateError
from app.domain.auth import UserRole
from app.domain.build_admission import BuildAdmissionState, BuildLeaseState
from app.domain.builds import BuildConfiguration, BuildStatus, BuildTrigger
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.build import Build
from app.models.project import Project
from app.repositories.audit import AuditRepository
from app.repositories.build_admission import BuildAdmissionRepository
from app.repositories.builds import BuildRepository
from app.services.build_admission import BuildAdmissionDispatcher, BuildAdmissionService
from app.services.settings import OperationalSettingsProvider

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=10_001)
PROJECT_IDS = [UUID(int=10_010 + index) for index in range(4)]
BUILD_IDS = [UUID(int=10_020 + index) for index in range(4)]


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


def _configuration() -> dict[str, object]:
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


class _Settings:
    def __init__(self, concurrency: int) -> None:
        self.concurrency = concurrency

    async def get_operational(self) -> object:
        return SimpleNamespace(build_concurrency=self.concurrency)


class _Queue:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.calls: list[tuple[UUID, UUID]] = []

    async def enqueue_build(self, build_id: UUID, token: UUID) -> None:
        if self.fail_first:
            self.fail_first = False
            raise OSError("injected Redis outage")
        self.calls.append((build_id, token))


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(AuditEvent).where(AuditEvent.project_id.in_(PROJECT_IDS)))
        await session.execute(
            update(Project)
            .where(Project.id.in_(PROJECT_IDS))
            .values(active_build_id=None, active_deployment_id=None)
        )
        await session.execute(delete(Project).where(Project.id.in_(PROJECT_IDS)))
        await session.execute(delete(User).where(User.id == USER_ID))


async def _seed(database: DatabaseClient, count: int) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="build-admission-test@example.com",
                display_name="Build admission test",
                password_hash="unused",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        for index in range(count):
            project_id = PROJECT_IDS[index]
            session.add(
                Project(
                    id=project_id,
                    name=f"Admission {index}",
                    slug=f"admission-{index}",
                    description=None,
                    default_base_url=None,
                    active_server_ref=None,
                    server_mappings={},
                    mcp_hostname=f"admission-{index}.mcp.example.com",
                    is_enabled=True,
                    active_build_id=None,
                    active_deployment_id=None,
                    created_by=USER_ID,
                )
            )
        await session.flush()
        for index in range(count):
            session.add(
                Build(
                    id=BUILD_IDS[index],
                    project_id=PROJECT_IDS[index],
                    sequence=1,
                    status=BuildStatus.QUEUED,
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
                    build_config_json=_configuration(),
                    enrichment_json=None,
                    enrichment_sha256=None,
                    manifest_sha256=None,
                    artifact_sha256=None,
                    manifest_storage_key=None,
                    artifact_storage_key=None,
                    error_code=None,
                    error_summary=None,
                    requested_by=USER_ID,
                    started_at=None,
                    completed_at=None,
                )
            )


def _dispatcher(
    database: DatabaseClient,
    repository: BuildAdmissionRepository,
    queue: _Queue,
    settings: _Settings,
) -> BuildAdmissionDispatcher:
    return BuildAdmissionDispatcher(
        database,
        repository,
        cast(BuildQueueClient, queue),
        cast(OperationalSettingsProvider, settings),
        AuditRepository(),
        interval_seconds=0.1,
        lease_seconds=60,
    )


async def test_admission_is_cross_process_safe_and_dynamic_limit_drains(
    request: pytest.FixtureRequest,
) -> None:
    del request
    database = DatabaseClient(_database_url(), pool_size=8, max_overflow=0)
    repository = BuildAdmissionRepository()
    settings = _Settings(2)
    first_queue = _Queue()
    second_queue = _Queue()
    first = _dispatcher(database, repository, first_queue, settings)
    second = _dispatcher(database, repository, second_queue, settings)
    try:
        await _cleanup(database)
        await _seed(database, 4)
        results = await asyncio.gather(first.dispatch_once(), second.dispatch_once())
        calls = first_queue.calls + second_queue.calls
        assert sum(results) == 2
        assert len(calls) == len({build_id for build_id, _token in calls}) == 2

        overview = await first.overview()
        assert overview.configured_concurrency == 2
        assert overview.effective_concurrency == 2
        assert overview.waiting_count == 2
        waiting = [
            entry for entry in overview.entries if entry.state is BuildAdmissionState.WAITING
        ]
        assert [entry.position for entry in waiting] == [1, 2]

        settings.concurrency = 1
        builds = BuildRepository()
        async with database.session_scope() as session:
            await builds.fail(
                session,
                calls[0][0],
                error_code="TEST_DONE",
                error_summary="release first permit",
                admission_token=calls[0][1],
            )
        assert await first.dispatch_once() == 0

        async with database.session_scope() as session:
            await builds.fail(
                session,
                calls[1][0],
                error_code="TEST_DONE",
                error_summary="release second permit",
                admission_token=calls[1][1],
            )
        assert await first.dispatch_once() == 1
        assert (await first.overview()).effective_concurrency == 1

        settings.concurrency = 3
        assert await first.dispatch_once() == 1
        expanded = await first.overview()
        assert expanded.configured_concurrency == 3
        assert expanded.effective_concurrency == 2
        assert expanded.waiting_count == 0
    finally:
        await _cleanup(database)
        await database.close()


async def test_enqueue_failure_and_expired_worker_are_reclaimed_without_stale_execution() -> None:
    database = DatabaseClient(_database_url(), pool_size=6, max_overflow=0)
    repository = BuildAdmissionRepository()
    settings = _Settings(1)
    queue = _Queue(fail_first=True)
    dispatcher = _dispatcher(database, repository, queue, settings)
    try:
        await _cleanup(database)
        await _seed(database, 2)
        assert await dispatcher.dispatch_once() == 0
        async with database.session_scope() as session:
            first_after_failure = await session.get(Build, BUILD_IDS[0])
            assert first_after_failure is not None
            assert first_after_failure.status is BuildStatus.QUEUED
            assert first_after_failure.admission_token is None
            assert first_after_failure.admission_attempt_count == 1

        assert await dispatcher.dispatch_once() == 1
        build_id, stale_token = queue.calls[-1]
        async with database.session_scope() as session:
            await session.execute(
                update(Build)
                .where(Build.id == build_id)
                .values(
                    status=BuildStatus.ANALYZING,
                    started_at=datetime.now(UTC),
                    admission_lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
        assert await dispatcher.dispatch_once() == 1
        resumed_build_id, current_token = queue.calls[-1]
        assert resumed_build_id == build_id
        assert current_token != stale_token

        worker_admission = BuildAdmissionService(
            database,
            repository,
            lease_seconds=60,
        )
        assert (await worker_admission.begin(build_id, stale_token)).state is BuildLeaseState.LOST
        assert (
            await worker_admission.begin(build_id, current_token)
        ).state is BuildLeaseState.OWNED
        with pytest.raises(InvalidStateError, match="ownership is stale"):
            async with database.session_scope() as session:
                await BuildRepository().transition(
                    session,
                    build_id,
                    expected=BuildStatus.ANALYZING,
                    target=BuildStatus.COMPILING,
                    admission_token=stale_token,
                )
        async with database.session_scope() as session:
            resumed = await session.get(Build, build_id)
            assert resumed is not None
            assert resumed.admission_attempt_count == 3
            assert resumed.admission_heartbeat_at is not None
        assert await worker_admission.release(build_id, current_token)
    finally:
        await _cleanup(database)
        await database.close()


async def test_cancelled_build_keeps_live_owner_and_dead_owner_is_recovered() -> None:
    """ISS-002-007: cancellation is a handoff, not silent lease deletion."""

    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    repository = BuildAdmissionRepository()
    queue = _Queue()
    dispatcher = _dispatcher(database, repository, queue, _Settings(1))
    try:
        await _cleanup(database)
        await _seed(database, 1)
        assert await dispatcher.dispatch_once() == 1
        build_id, original_token = queue.calls[-1]
        async with database.session_scope() as session:
            await session.execute(
                update(Build)
                .where(Build.id == build_id)
                .values(cancellation_requested_at=datetime.now(UTC))
            )

        service = BuildAdmissionService(database, repository, lease_seconds=60)
        renewal = await service.heartbeat(build_id, original_token)
        assert renewal.state is BuildLeaseState.CANCELLATION_REQUESTED
        assert await dispatcher.dispatch_once() == 0

        async with database.session_scope() as session:
            await session.execute(
                update(Build)
                .where(Build.id == build_id)
                .values(admission_lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        assert await dispatcher.dispatch_once() == 1
        recovered_build_id, recovered_token = queue.calls[-1]
        assert recovered_build_id == build_id
        assert recovered_token != original_token
        recovered = await service.begin(build_id, recovered_token)
        assert recovered.state is BuildLeaseState.CANCELLATION_REQUESTED
    finally:
        await _cleanup(database)
        await database.close()
