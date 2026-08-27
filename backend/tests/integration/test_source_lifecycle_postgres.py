from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update

from app.clients.database import DatabaseClient
from app.clients.http import FetchedResponse, HttpClient
from app.clients.storage import BytesReader, FilesystemStorageClient
from app.core.exceptions import ClientUnavailableError, ConflictError, SourceParseError
from app.core.network_policy import UrlPolicy
from app.domain.auth import UserRole
from app.domain.builds import BuildStatus, BuildTrigger
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
from app.services.settings import OperationalSettingsProvider
from app.services.sources import SourceService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=401)
PROJECT_ID = UUID(int=402)


def _database_url() -> str:
    import os

    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


@dataclass(slots=True)
class _Operational:
    max_upload_bytes: int = 1_000_000
    builders_can_deploy: bool = True
    mcp_base_domain: str = "mcp.localhost"


class _Settings:
    async def get_operational(self) -> _Operational:
        return _Operational()


class _Http:
    async def fetch_bounded(self, url: str, **kwargs: object) -> FetchedResponse:
        if "unavailable" in url:
            raise ClientUnavailableError("Injected source fetch failure")
        return FetchedResponse(
            status_code=200,
            url=url,
            headers={"Content-Type": "application/json", "ETag": '"source-v1"'},
            body=_openapi_bytes(),
        )


def _openapi_bytes() -> bytes:
    return b'{"openapi":"3.1.0","info":{"title":"Inventory","version":"1"},"paths":{}}'


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


async def _seed(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="source-lifecycle-test@example.com",
                display_name="Source lifecycle test",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                name="Source lifecycle test",
                slug="source-lifecycle-test",
                description=None,
                default_base_url="https://api.example.com",
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="source-lifecycle-test.mcp.example.com",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=USER_ID,
            )
        )


def _service(database: DatabaseClient, tmp_path: Path) -> SourceService:
    return SourceService(
        database,
        SourceRepository(),
        ProjectRepository(),
        cast(BuildRepository, object()),
        cast(CanonicalRepository, object()),
        cast(IndexGenerationRepository, object()),
        AuditRepository(),
        FilesystemArtifactStorage(FilesystemStorageClient(str(tmp_path))),
        cast(HttpClient, _Http()),
        UrlPolicy(),
        cast(OperationalSettingsProvider, _Settings()),
        canonicalization=None,
        document_max_bytes=1_000_000,
        fetch_max_bytes=1_000_000,
        fetch_max_redirects=2,
        fetch_max_attempts=1,
    )


async def test_compound_source_creation_retry_primary_switch_and_recovery(
    tmp_path: Path,
) -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    try:
        await _cleanup(database)
        await _seed(database)
        service = _service(database, tmp_path)

        invalid_id = UUID(int=403)
        with pytest.raises(SourceParseError):
            await service.create_with_upload(
                source_id=invalid_id,
                project_id=PROJECT_ID,
                kind=SourceKind.OPENAPI,
                name="Invalid API",
                is_primary=True,
                content=BytesReader(b"not an OpenAPI document"),
                media_type="application/json",
                filename="openapi.json",
                actor_user_id=USER_ID,
                request_id="invalid-upload",
            )
        assert await service.list(PROJECT_ID) == []
        assert list((tmp_path / ".tmp").iterdir()) == []

        with pytest.raises(ClientUnavailableError):
            await service.create_with_url(
                source_id=UUID(int=404),
                project_id=PROJECT_ID,
                kind=SourceKind.OPENAPI,
                name="Unavailable API",
                source_url="https://unavailable.example.com/openapi.json",
                is_primary=True,
                actor_user_id=USER_ID,
                request_id="invalid-url",
            )
        assert await service.list(PROJECT_ID) == []

        first_id = UUID(int=405)
        first = await service.create_with_upload(
            source_id=first_id,
            project_id=PROJECT_ID,
            kind=SourceKind.OPENAPI,
            name="Primary API",
            is_primary=False,
            content=BytesReader(_openapi_bytes()),
            media_type="application/json",
            filename="openapi.json",
            actor_user_id=USER_ID,
            request_id="first-upload",
        )
        assert first.source.is_primary
        assert not first.deduplicated

        replay = await service.create_with_upload(
            source_id=first_id,
            project_id=PROJECT_ID,
            kind=SourceKind.OPENAPI,
            name="Primary API",
            is_primary=False,
            content=BytesReader(b"this retry body is intentionally not consumed"),
            media_type="application/json",
            filename="openapi.json",
            actor_user_id=USER_ID,
            request_id="first-upload-retry",
        )
        assert replay.source.id == first.source.id
        assert replay.version.id == first.version.id
        assert replay.deduplicated

        second = await service.create_with_url(
            source_id=UUID(int=406),
            project_id=PROJECT_ID,
            kind=SourceKind.OPENAPI,
            name="Replacement API",
            source_url="https://api.example.com/openapi.json",
            is_primary=False,
            actor_user_id=USER_ID,
            request_id="second-url",
        )
        assert not second.source.is_primary

        promoted = await service.update(
            project_id=PROJECT_ID,
            source_id=second.source.id,
            name=None,
            is_primary=True,
            actor_user_id=USER_ID,
            request_id="promote-second",
        )
        assert promoted.is_primary
        sources = {source.id: source for source in await service.list(PROJECT_ID)}
        assert not sources[first_id].is_primary
        assert sources[second.source.id].is_primary

        documentation = await service.create_with_upload(
            source_id=UUID(int=407),
            project_id=PROJECT_ID,
            kind=SourceKind.DOCUMENTATION,
            name="Guide",
            is_primary=False,
            content=BytesReader(b"# Inventory guide"),
            media_type="text/markdown",
            filename="guide.md",
            actor_user_id=USER_ID,
            request_id="documentation-upload",
        )
        assert not documentation.source.is_primary

        await service.delete(
            project_id=PROJECT_ID,
            source_id=second.source.id,
            actor_user_id=USER_ID,
            request_id="delete-primary",
        )
        sources = {source.id: source for source in await service.list(PROJECT_ID)}
        assert sources[first_id].is_primary
        assert second.source.id not in sources

        empty = await service.create(
            project_id=PROJECT_ID,
            kind=SourceKind.DOCUMENTATION,
            name="Recoverable empty source",
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
            is_primary=False,
            actor_user_id=USER_ID,
            request_id="empty-source",
        )
        await service.delete(
            project_id=PROJECT_ID,
            source_id=empty.id,
            actor_user_id=USER_ID,
            request_id="delete-empty-source",
        )
        assert empty.id not in {source.id for source in await service.list(PROJECT_ID)}

        async with database.session_scope() as session:
            build = Build(
                id=UUID(int=408),
                project_id=PROJECT_ID,
                sequence=1,
                status=BuildStatus.QUEUED,
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
                build_config_json={},
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
            session.add(build)
            await session.flush()
            session.add(
                BuildSourceVersion(
                    build_id=build.id,
                    source_version_id=first.version.id,
                )
            )
        with pytest.raises(ConflictError, match="immutable Build"):
            await service.delete(
                project_id=PROJECT_ID,
                source_id=first.source.id,
                actor_user_id=USER_ID,
                request_id="protected-delete",
            )
    finally:
        await _cleanup(database)
        await database.close()
