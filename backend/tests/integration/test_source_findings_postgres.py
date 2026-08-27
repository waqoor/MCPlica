from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update

from app.clients.database import DatabaseClient
from app.clients.http import HttpClient
from app.clients.storage import FilesystemStorageClient
from app.core.exceptions import SourceParseError
from app.core.network_policy import UrlPolicy
from app.domain.auth import UserRole
from app.domain.builds import BuildConfiguration, BuildTrigger
from app.domain.sources import SourceKind, SourceOrigin
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.build import Build, BuildSourceVersion
from app.models.project import Project
from app.models.source import ProjectSource
from app.providers.storage import FilesystemArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.builds import BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.services.builds.pipeline import BuildPipeline
from app.services.canonicalization import CanonicalizationService
from app.services.settings import OperationalSettingsProvider
from app.services.sources import SourceService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=701)
PROJECT_ID = UUID(int=702)
BUILD_ID = UUID(int=703)
ROOT_SOURCE_ID = UUID(int=704)
EXTERNAL_SOURCE_ID = UUID(int=705)


def _database_url() -> str:
    import os

    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


def _config() -> BuildConfiguration:
    return BuildConfiguration(
        inbound_auth_mode="static_bearer",
        include_documentation_in_analysis=False,
        max_operations=1_000,
        max_context_chars=120_000,
        max_ai_concurrency=4,
        retrieval_top_k=5,
        source_max_bytes=1_000_000,
        document_max_bytes=1_000_000,
        document_max_text_chars=1_000_000,
        pdf_max_pages=100,
        documentation_chunk_chars=2_000,
        documentation_chunk_overlap_chars=200,
        max_document_chunks=1_000,
        embedding_batch_size=64,
        max_embedding_concurrency=4,
        runtime_timeout_ms=30_000,
        runtime_max_request_bytes=10_000_000,
        runtime_max_response_bytes=2_000_000,
        runtime_manifest_max_bytes=10_000_000,
        artifact_max_bytes=10_000_000,
    )


@dataclass(slots=True)
class _Operational:
    max_upload_bytes: int = 1_000_000
    builders_can_deploy: bool = True
    mcp_base_domain: str = "mcp.localhost"


class _Settings:
    async def get_operational(self) -> _Operational:
        return _Operational()


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(
            update(Project)
            .where(Project.id == PROJECT_ID)
            .values(active_build_id=None, active_deployment_id=None)
        )
        await session.execute(delete(AuditEvent).where(AuditEvent.project_id == PROJECT_ID))
        await session.execute(
            delete(BuildSourceVersion).where(
                BuildSourceVersion.build_id.in_(
                    select(Build.id).where(Build.project_id == PROJECT_ID)
                )
            )
        )
        await session.execute(delete(Build).where(Build.project_id == PROJECT_ID))
        await session.execute(delete(ProjectSource).where(ProjectSource.project_id == PROJECT_ID))
        await session.execute(delete(Project).where(Project.id == PROJECT_ID))
        await session.execute(delete(User).where(User.id == USER_ID))


async def _seed(
    database: DatabaseClient,
    storage: FilesystemArtifactStorage,
) -> tuple[UUID, UUID]:
    root_payload = (
        b'{"openapi":"3.1.0","info":{"title":"Root","version":"1"},'
        b'"servers":[{"url":"https://api.example.test"}],'
        b'"paths":{"/health":{"get":{"responses":{"200":{"description":"ok"}}}}}}'
    )
    broken_external = b"openapi: [\n"
    root_stored = await storage.put_bytes(
        f"projects/{PROJECT_ID}/sources",
        root_payload,
        max_bytes=1_000_000,
    )
    external_stored = await storage.put_bytes(
        f"projects/{PROJECT_ID}/sources",
        broken_external,
        max_bytes=1_000_000,
    )
    sources = SourceRepository()
    builds = BuildRepository()
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="source-findings-test@example.com",
                display_name="Source findings test",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                name="Source findings test",
                slug="source-findings-test",
                description=None,
                default_base_url="https://api.example.test",
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="source-findings-test.mcp.example.test",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=USER_ID,
            )
        )
        await session.flush()
        root_source = await sources.create_source(
            session,
            source_id=ROOT_SOURCE_ID,
            project_id=PROJECT_ID,
            kind=SourceKind.OPENAPI,
            name="root.json",
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
            is_primary=True,
        )
        external_source = await sources.create_source(
            session,
            source_id=EXTERNAL_SOURCE_ID,
            project_id=PROJECT_ID,
            kind=SourceKind.OPENAPI,
            name="broken.yaml",
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
            is_primary=False,
        )
        root_version = await sources.create_version(
            session,
            source_id=root_source.id,
            content_sha256=root_stored.content_sha256,
            media_type="application/json",
            storage_key=root_stored.storage_key,
            byte_size=root_stored.byte_size,
            detected_format="json",
            source_etag=None,
            source_last_modified=None,
            created_by=USER_ID,
        )
        external_version = await sources.create_version(
            session,
            source_id=external_source.id,
            content_sha256=external_stored.content_sha256,
            media_type="application/yaml",
            storage_key=external_stored.storage_key,
            byte_size=external_stored.byte_size,
            detected_format="yaml",
            source_etag=None,
            source_last_modified=None,
            created_by=USER_ID,
        )
        await builds.create(
            session,
            build_id=BUILD_ID,
            project_id=PROJECT_ID,
            trigger=BuildTrigger.INITIAL,
            source_version_ids=[root_version.id, external_version.id],
            requested_by=USER_ID,
            compiler_version="test",
            runtime_compatibility="test",
            analysis_model="test",
            validation_model="test",
            embedding_model=None,
            prompt_bundle_version="test",
            build_config=cast(dict[str, object], _config().model_dump(mode="json")),
        )
    return root_version.id, external_version.id


def _pipeline(
    database: DatabaseClient,
    storage: FilesystemArtifactStorage,
) -> BuildPipeline:
    sources = SourceRepository()
    projects = ProjectRepository()
    builds = BuildRepository()
    canonicalization = CanonicalizationService(
        database,
        projects,
        sources,
        CanonicalRepository(),
        storage,
    )
    unused = cast(Any, object())
    return BuildPipeline(
        database,
        builds,
        projects,
        sources,
        unused,
        unused,
        AuditRepository(),
        storage,
        canonicalization,
        unused,
        unused,
        unused,
        unused,
    )


def _source_service(
    database: DatabaseClient,
    storage: FilesystemArtifactStorage,
) -> SourceService:
    return SourceService(
        database,
        SourceRepository(),
        ProjectRepository(),
        BuildRepository(),
        CanonicalRepository(),
        IndexGenerationRepository(),
        AuditRepository(),
        storage,
        cast(HttpClient, object()),
        UrlPolicy(),
        cast(OperationalSettingsProvider, _Settings()),
        canonicalization=None,
        document_max_bytes=1_000_000,
        fetch_max_bytes=1_000_000,
        fetch_max_redirects=2,
        fetch_max_attempts=1,
    )


async def test_two_source_parse_failure_is_durable_idempotent_and_exact(
    tmp_path: Path,
) -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    storage = FilesystemArtifactStorage(FilesystemStorageClient(str(tmp_path)))
    try:
        await _cleanup(database)
        root_version_id, external_version_id = await _seed(database, storage)
        pipeline = _pipeline(database, storage)

        with pytest.raises(SourceParseError) as first_failure:
            await pipeline.run(BUILD_ID)
        assert first_failure.value.details["source_version_id"] == str(external_version_id)
        assert first_failure.value.details["source_pointer"] == "#"
        assert first_failure.value.details["line"] == 2
        assert first_failure.value.details["column"] == 1

        with pytest.raises(SourceParseError):
            await pipeline.run(BUILD_ID)

        repository = SourceRepository()
        async with database.session_scope() as session:
            root_findings = await repository.list_findings_for_version(
                session,
                root_version_id,
                build_id=BUILD_ID,
            )
            external_findings = await repository.list_findings_for_version(
                session,
                external_version_id,
                build_id=BUILD_ID,
            )
        assert root_findings == []
        assert len(external_findings) == 1
        finding = external_findings[0]
        assert finding.stage == "parsing"
        assert finding.code == "SOURCE_PARSE_ERROR"
        assert finding.pointer == "#"
        assert (finding.line, finding.column) == (2, 1)
        assert finding.details["source_version_id"] == str(external_version_id)

        await pipeline.fail_from_exception(BUILD_ID, first_failure.value)
        source_service = _source_service(database, storage)
        root_metadata = await source_service.metadata(root_version_id)
        external_metadata = await source_service.metadata(external_version_id)
        assert root_metadata.parse_status == "pending"
        assert root_metadata.errors == []
        assert external_metadata.parse_status == "invalid"
        assert len(external_metadata.errors) == 1
        assert external_metadata.errors[0].source_version_id == external_version_id
        assert external_metadata.errors[0].pointer == "#"
        assert external_metadata.errors[0].line == 2
        assert external_metadata.metadata_build_id == BUILD_ID

        async with database.session_scope() as session:
            failed_build = await BuildRepository().get(session, BUILD_ID)
        assert failed_build is not None
        await pipeline._record_source_finding(
            failed_build,
            SourceParseError(
                "Injected safe parser evidence",
                details={
                    "source_version_id": str(external_version_id),
                    "source_pointer": "#/credentials",
                    "api_key": "must-not-persist",
                },
            ),
            stage="parsing",
        )
        async with database.session_scope() as session:
            redacted_findings = await repository.list_findings_for_version(
                session,
                external_version_id,
                build_id=BUILD_ID,
            )
        redacted = next(item for item in redacted_findings if item.pointer == "#/credentials")
        assert redacted.details["api_key"] == "[REDACTED]"
        assert "must-not-persist" not in str(redacted.model_dump(mode="json"))
    finally:
        await _cleanup(database)
        await database.close()
