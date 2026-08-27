import hashlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.build_queue import BuildQueueClient
from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.domain.builds import (
    BuildConfiguration,
    BuildExclusionSnapshot,
    BuildRecord,
    BuildStatus,
    BuildTrigger,
)
from app.domain.canonicalization import CanonicalSnapshotRecord
from app.domain.validation import OperationExclusionRecord
from app.parsers.openapi.parser import parse_openapi
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildAIRunRepository, BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.repositories.validation import ValidationRepository
from app.services.artifacts import ArtifactService
from app.services.build_admission import BuildAdmissionDispatcher
from app.services.builds.service import BuildService, SourceConfigurationProvider
from app.services.settings import SettingsService

PROJECT_ID = UUID(int=701)
USER_ID = UUID(int=702)
SOURCE_VERSION_ID = UUID(int=703)
OLD_BUILD_ID = UUID(int=704)
NEW_BUILD_ID = UUID(int=705)
OLD_SNAPSHOT_ID = UUID(int=706)
NEW_SNAPSHOT_ID = UUID(int=707)
EXCLUSION_ID = UUID(int=708)
NOW = datetime(2026, 8, 27, tzinfo=UTC)


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        yield cast(AsyncSession, object())


class _Builds:
    def __init__(
        self,
        builds: dict[UUID, BuildRecord],
        configs: dict[UUID, BuildConfiguration],
    ) -> None:
        self.builds = builds
        self.configs = configs

    async def get(self, session: AsyncSession, build_id: UUID) -> BuildRecord | None:
        return self.builds.get(build_id)

    async def get_build_config(
        self, session: AsyncSession, build_id: UUID
    ) -> BuildConfiguration | None:
        return self.configs.get(build_id)

    async def get_enrichment(
        self, session: AsyncSession, build_id: UUID
    ) -> dict[str, object] | None:
        return None


class _Snapshots:
    def __init__(self, snapshots: dict[UUID, CanonicalSnapshotRecord]) -> None:
        self.snapshots = snapshots

    async def get(self, session: AsyncSession, snapshot_id: UUID) -> CanonicalSnapshotRecord | None:
        return self.snapshots.get(snapshot_id)


class _Projects:
    async def get(self, session: AsyncSession, project_id: UUID) -> object | None:
        return object() if project_id == PROJECT_ID else None


class _Validation:
    def __init__(self, exclusions: list[OperationExclusionRecord]) -> None:
        self.exclusions = exclusions

    async def list_exclusions(
        self, session: AsyncSession, project_id: UUID
    ) -> list[OperationExclusionRecord]:
        assert project_id == PROJECT_ID
        return list(self.exclusions)


def _canonical_snapshot(snapshot_id: UUID) -> CanonicalSnapshotRecord:
    source = {
        "openapi": "3.1.0",
        "info": {"title": "Pets", "version": "1.0"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "summary": "List pets",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=PROJECT_ID,
        source_version_id=SOURCE_VERSION_ID,
        content_sha256=hashlib.sha256(b"pets").hexdigest(),
    )
    return CanonicalSnapshotRecord(
        id=snapshot_id,
        project_id=PROJECT_ID,
        schema_version=canonical.schema_version,
        canonical_sha256="a" * 64,
        canonical=canonical,
        source_version_ids=[SOURCE_VERSION_ID],
        created_at=NOW,
    )


def _build(build_id: UUID, snapshot_id: UUID, sequence: int) -> BuildRecord:
    return BuildRecord(
        id=build_id,
        project_id=PROJECT_ID,
        sequence=sequence,
        status=BuildStatus.READY,
        trigger=BuildTrigger.MANUAL_REBUILD,
        canonical_snapshot_id=snapshot_id,
        previous_build_id=OLD_BUILD_ID if sequence > 1 else None,
        compiler_version="1.0.0",
        manifest_schema_version="mcp-manifest/v1",
        runtime_compatibility=">=1,<2",
        analysis_model="analysis/model",
        validation_model="validation/model",
        embedding_model=None,
        embedding_dimensions=None,
        prompt_bundle_version="1.0.0",
        enrichment_sha256=None,
        manifest_sha256=None,
        artifact_sha256=None,
        manifest_storage_key=None,
        artifact_storage_key=None,
        error_code=None,
        error_summary=None,
        requested_by=USER_ID,
        created_at=NOW,
        started_at=NOW,
        completed_at=NOW,
    )


def _config(
    exclusion: OperationExclusionRecord | None = None,
) -> BuildConfiguration:
    return BuildConfiguration(
        excluded_operations=(
            [
                BuildExclusionSnapshot(
                    id=exclusion.id,
                    operation_key=exclusion.operation_key,
                    reason_code=exclusion.reason_code,
                    reason=exclusion.reason,
                )
            ]
            if exclusion
            else []
        ),
        inbound_auth_mode="static_bearer",
        include_documentation_in_analysis=False,
        max_operations=100,
        max_context_chars=10_000,
        max_ai_concurrency=2,
        retrieval_top_k=5,
        source_max_bytes=10_000,
        document_max_bytes=10_000,
        document_max_text_chars=10_000,
        pdf_max_pages=10,
        documentation_chunk_chars=1_000,
        documentation_chunk_overlap_chars=100,
        max_document_chunks=100,
        embedding_batch_size=10,
        max_embedding_concurrency=2,
        runtime_timeout_ms=10_000,
        runtime_max_request_bytes=10_000,
        runtime_max_response_bytes=10_000,
        runtime_manifest_max_bytes=10_000,
        artifact_max_bytes=10_000,
    )


def _service(validation: _Validation) -> BuildService:
    old_snapshot = _canonical_snapshot(OLD_SNAPSHOT_ID)
    new_snapshot = old_snapshot.model_copy(update={"id": NEW_SNAPSHOT_ID})
    operation_key = old_snapshot.canonical.operations[0].key
    exclusion = OperationExclusionRecord(
        id=EXCLUSION_ID,
        project_id=PROJECT_ID,
        build_id=OLD_BUILD_ID,
        operation_key=operation_key,
        reason_code="user_requested",
        reason="Unsafe upstream operation",
        is_user_requested=True,
        created_by=USER_ID,
        created_at=NOW,
    )
    builds = _Builds(
        {
            OLD_BUILD_ID: _build(OLD_BUILD_ID, OLD_SNAPSHOT_ID, 1),
            NEW_BUILD_ID: _build(NEW_BUILD_ID, NEW_SNAPSHOT_ID, 2),
        },
        {
            OLD_BUILD_ID: _config(),
            NEW_BUILD_ID: _config(exclusion),
        },
    )
    return BuildService(
        cast(DatabaseClient, _Database()),
        cast(BuildRepository, builds),
        cast(BuildAIRunRepository, object()),
        cast(
            CanonicalRepository,
            _Snapshots(
                {
                    OLD_SNAPSHOT_ID: old_snapshot,
                    NEW_SNAPSHOT_ID: new_snapshot,
                }
            ),
        ),
        cast(SourceRepository, object()),
        cast(SourceConfigurationProvider, object()),
        cast(ProjectRepository, _Projects()),
        cast(CredentialRepository, object()),
        cast(ValidationRepository, validation),
        cast(AuditRepository, object()),
        cast(SettingsService, object()),
        cast(BuildQueueClient, object()),
        Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
        cast(ArtifactService, object()),
        None,
        cast(BuildAdmissionDispatcher, object()),
    )


@pytest.mark.asyncio
async def test_current_policy_never_rewrites_historical_build_operations() -> None:
    validation = _Validation([])
    service = _service(validation)

    old_before = (await service.operations(OLD_BUILD_ID))[0]
    operation_key = old_before.key
    validation.exclusions = [
        OperationExclusionRecord(
            id=EXCLUSION_ID,
            project_id=PROJECT_ID,
            build_id=OLD_BUILD_ID,
            operation_key=operation_key,
            reason_code="user_requested",
            reason="Unsafe upstream operation",
            is_user_requested=True,
            created_by=USER_ID,
            created_at=NOW,
        )
    ]

    current_policy = await service.list_exclusions(project_id=PROJECT_ID)
    old_after = (await service.operations(OLD_BUILD_ID))[0]
    rebuilt = (await service.operations(NEW_BUILD_ID))[0]

    assert not old_before.excluded_in_build
    assert old_after == old_before
    assert current_policy[0].operation_key == operation_key
    assert rebuilt.excluded_in_build
    assert rebuilt.build_exclusion_id == EXCLUSION_ID
    assert rebuilt.build_exclusion_reason == "Unsafe upstream operation"


@pytest.mark.asyncio
async def test_operation_page_filters_and_returns_current_policy_separately() -> None:
    current = OperationExclusionRecord(
        id=EXCLUSION_ID,
        project_id=PROJECT_ID,
        build_id=OLD_BUILD_ID,
        operation_key=_canonical_snapshot(OLD_SNAPSHOT_ID).canonical.operations[0].key,
        reason_code="user_requested",
        reason="Unsafe upstream operation",
        is_user_requested=True,
        created_by=USER_ID,
        created_at=NOW,
    )
    service = _service(_Validation([current]))

    page, total, policy_change_count = await service.operations_page(
        OLD_BUILD_ID,
        search="list pets",
        method="GET",
        scope="current-excluded",
        limit=50,
        offset=0,
    )

    assert total == 1
    assert policy_change_count == 1
    assert page[0].operation.excluded_in_build is False
    assert page[0].current_exclusion_id == EXCLUSION_ID
    assert page[0].current_exclusion_reason == "Unsafe upstream operation"


@pytest.mark.asyncio
async def test_listing_policy_rejects_an_unknown_project() -> None:
    service = _service(_Validation([]))

    with pytest.raises(NotFoundError, match="Project was not found"):
        await service.list_exclusions(project_id=UUID(int=999))
