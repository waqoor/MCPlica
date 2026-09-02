import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import delete, update

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.domain.auth import UserRole
from app.domain.builds import BuildConfiguration, BuildStatus, BuildTrigger
from app.domain.deployments import (
    MCPAccessStatusRecord,
    MCPAuthMode,
    RuntimeEffectState,
)
from app.domain.journey import JourneyStepState
from app.domain.sources import (
    BoundSourceVersionRecord,
    ProjectSourceRecord,
    SourceConfigurationDiscoveryRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionRecord,
    source_configuration_fingerprint,
)
from app.domain.validation import ValidationStatus
from app.models.auth import User
from app.models.build import Build, BuildSourceVersion
from app.models.canonical import CanonicalSnapshot
from app.models.project import Project
from app.models.source import ProjectSource, SourceVersion
from app.models.validation import ValidationReport
from app.repositories.builds import BuildRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.repositories.validation import ValidationRepository
from app.services.deployment.preflight import DeploymentPreflight
from app.services.journey import JourneyService
from app.services.mcp_access import MCPAccessService
from app.services.settings import OperationalSettingsProvider
from app.services.sources import SourceService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=501)
PROJECT_ID = UUID(int=502)
OTHER_PROJECT_ID = UUID(int=503)
SOURCE_ID = UUID(int=504)
VERSION_ID = UUID(int=505)
BUILD_ID = UUID(int=506)
OTHER_BUILD_ID = UUID(int=507)
SNAPSHOT_ID = UUID(int=510)
NOW = datetime(2026, 8, 27, tzinfo=UTC)


def _binding(version_id: UUID = VERSION_ID) -> BoundSourceVersionRecord:
    return BoundSourceVersionRecord(
        source=ProjectSourceRecord(
            id=SOURCE_ID,
            project_id=PROJECT_ID,
            kind=SourceKind.OPENAPI,
            name="Journey API",
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
            is_primary=True,
            created_at=NOW,
        ),
        version=SourceVersionRecord(
            id=version_id,
            source_id=SOURCE_ID,
            content_sha256="a" * 64,
            media_type="application/json",
            storage_key="sources/journey.json",
            byte_size=1,
            detected_format="openapi-3.1-json",
            source_etag=None,
            source_last_modified=None,
            created_by=USER_ID,
            created_at=NOW,
        ),
    )


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


@dataclass(slots=True)
class _Operational:
    builders_can_deploy: bool
    mcp_base_domain: str = "mcp.localhost"
    max_upload_bytes: int = 1_000_000


class _OperationalProvider:
    def __init__(self, builders_can_deploy: bool) -> None:
        self.value = _Operational(builders_can_deploy)

    async def get_operational(self) -> _Operational:
        return self.value


class _SourceService:
    def __init__(self, version_id: UUID) -> None:
        self.version_id = version_id
        self.default_base_url = "https://api.example.com"
        self.active_server_ref: str | None = None
        self.server_mappings: dict[str, str] = {}

    async def discover_configuration(self, project_id: UUID) -> SourceConfigurationDiscoveryRecord:
        assert project_id == PROJECT_ID
        return SourceConfigurationDiscoveryRecord(
            source_version_ids=[self.version_id],
            configuration_sha256=source_configuration_fingerprint(
                bindings=[_binding(self.version_id)],
                default_base_url=self.default_base_url,
                active_server_ref=self.active_server_ref,
                server_mappings=self.server_mappings,
            ),
            servers=[],
            operations=[],
            security_schemes=[],
            security_requirements=[],
            routing_complete=True,
        )


class _AccessService:
    async def get_status(self, project_id: UUID) -> MCPAccessStatusRecord:
        return MCPAccessStatusRecord(
            project_id=project_id,
            mode=MCPAuthMode.STATIC_BEARER,
            configured=True,
            remediation=None,
            runtime_effect_state=RuntimeEffectState.EFFECTIVE,
            runtime_command_id=None,
            runtime_error_code=None,
        )


class _Preflight:
    async def validate(self, *args: object, **kwargs: object) -> object:
        return object()


def _build_configuration() -> dict[str, object]:
    return BuildConfiguration(
        executable_configuration_sha256=source_configuration_fingerprint(
            bindings=[_binding()],
            default_base_url="https://api.example.com",
            active_server_ref=None,
            server_mappings={},
        ),
        inbound_auth_mode="static_bearer",
        default_base_url="https://api.example.com",
        active_server_ref=None,
        server_mappings={},
        include_documentation_in_analysis=False,
        max_operations=100,
        max_context_chars=10_000,
        max_ai_concurrency=2,
        retrieval_top_k=5,
        source_max_bytes=1_000,
        document_max_bytes=1_000,
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
    ).model_dump(mode="json")


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(
            update(Project)
            .where(Project.id.in_([PROJECT_ID, OTHER_PROJECT_ID]))
            .values(active_build_id=None, active_deployment_id=None)
        )
        await session.execute(
            delete(ValidationReport).where(
                ValidationReport.build_id.in_([BUILD_ID, OTHER_BUILD_ID])
            )
        )
        await session.execute(
            delete(BuildSourceVersion).where(
                BuildSourceVersion.build_id.in_([BUILD_ID, OTHER_BUILD_ID])
            )
        )
        await session.execute(delete(Build).where(Build.id.in_([BUILD_ID, OTHER_BUILD_ID])))
        await session.execute(delete(CanonicalSnapshot).where(CanonicalSnapshot.id == SNAPSHOT_ID))
        await session.execute(delete(ProjectSource).where(ProjectSource.id == SOURCE_ID))
        await session.execute(delete(Project).where(Project.id.in_([PROJECT_ID, OTHER_PROJECT_ID])))
        await session.execute(delete(User).where(User.id == USER_ID))


async def _seed(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="journey-test@example.com",
                display_name="Journey test",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        for project_id, slug in (
            (PROJECT_ID, "journey-test"),
            (OTHER_PROJECT_ID, "journey-other"),
        ):
            session.add(
                Project(
                    id=project_id,
                    name=slug,
                    slug=slug,
                    description=None,
                    default_base_url="https://api.example.com",
                    active_server_ref=None,
                    server_mappings={},
                    mcp_hostname=f"{slug}.mcp.example.com",
                    is_enabled=True,
                    active_build_id=None,
                    active_deployment_id=None,
                    created_by=USER_ID,
                )
            )
        await session.flush()
        session.add(
            ProjectSource(
                id=SOURCE_ID,
                project_id=PROJECT_ID,
                kind=SourceKind.OPENAPI,
                name="Primary API",
                origin_type=SourceOrigin.UPLOAD,
                source_url=None,
                is_primary=True,
            )
        )
        await session.flush()
        session.add(
            SourceVersion(
                id=VERSION_ID,
                source_id=SOURCE_ID,
                content_sha256="1" * 64,
                media_type="application/json",
                storage_key="sources/v1.json",
                byte_size=100,
                detected_format="openapi-3.1-json",
                source_etag=None,
                source_last_modified=None,
                created_by=USER_ID,
                created_at=NOW,
            )
        )
        await session.flush()
        await SourceRepository().select_current_version(
            session,
            source_id=SOURCE_ID,
            version_id=VERSION_ID,
            source_etag=None,
            source_last_modified=None,
        )
        session.add(
            CanonicalSnapshot(
                id=SNAPSHOT_ID,
                project_id=PROJECT_ID,
                schema_version="canonical/v1",
                canonical_sha256="d" * 64,
                canonical_json={},
                source_version_ids=[VERSION_ID],
            )
        )
        await session.flush()
        session.add_all(
            [
                Build(
                    id=BUILD_ID,
                    project_id=PROJECT_ID,
                    sequence=1,
                    status=BuildStatus.READY,
                    trigger=BuildTrigger.INITIAL,
                    canonical_snapshot_id=SNAPSHOT_ID,
                    previous_build_id=None,
                    compiler_version="1.0.0",
                    manifest_schema_version="mcp-manifest/v1",
                    runtime_compatibility=">=1.0,<2.0",
                    analysis_model="analysis",
                    validation_model="validation",
                    embedding_model=None,
                    embedding_dimensions=None,
                    prompt_bundle_version="1.0.0",
                    build_config_json=_build_configuration(),
                    enrichment_json={},
                    enrichment_sha256="c" * 64,
                    manifest_sha256="a" * 64,
                    artifact_sha256="b" * 64,
                    manifest_storage_key="manifests/build.json",
                    artifact_storage_key="artifacts/build.zip",
                    error_code=None,
                    error_summary=None,
                    requested_by=USER_ID,
                    started_at=NOW,
                    completed_at=NOW,
                ),
                Build(
                    id=OTHER_BUILD_ID,
                    project_id=OTHER_PROJECT_ID,
                    sequence=1,
                    status=BuildStatus.QUEUED,
                    trigger=BuildTrigger.INITIAL,
                    canonical_snapshot_id=None,
                    previous_build_id=None,
                    compiler_version="1.0.0",
                    manifest_schema_version="mcp-manifest/v1",
                    runtime_compatibility=">=1.0,<2.0",
                    analysis_model="analysis",
                    validation_model="validation",
                    embedding_model=None,
                    embedding_dimensions=None,
                    prompt_bundle_version="1.0.0",
                    build_config_json=_build_configuration(),
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
                ),
            ]
        )
        await session.flush()
        session.add(
            BuildSourceVersion(
                build_id=BUILD_ID,
                source_version_id=VERSION_ID,
                source_id=SOURCE_ID,
                source_kind=SourceKind.OPENAPI,
                source_name="Primary API",
                source_origin_type=SourceOrigin.UPLOAD,
                source_url=None,
                source_is_primary=True,
                source_created_at=NOW,
                dependency_aliases=["Primary API"],
                binding_metadata_trustworthy=True,
            )
        )
        session.add(
            ValidationReport(
                id=UUID(int=508),
                build_id=BUILD_ID,
                overall_status=ValidationStatus.PASS,
                operation_source_count=1,
                operation_excluded_count=0,
                operation_expected_count=1,
                operation_generated_count=1,
                coverage_percent=100,
                blocking_error_count=0,
                warning_count=0,
                report_json={"findings": []},
            )
        )


def _service(
    database: DatabaseClient,
    source_service: _SourceService,
    *,
    builders_can_deploy: bool,
) -> JourneyService:
    return JourneyService(
        database,
        ProjectRepository(),
        SourceRepository(),
        BuildRepository(),
        ValidationRepository(),
        CredentialRepository(),
        DeploymentRepository(),
        cast(SourceService, source_service),
        cast(MCPAccessService, _AccessService()),
        cast(DeploymentPreflight, _Preflight()),
        cast(
            OperationalSettingsProvider,
            _OperationalProvider(builders_can_deploy),
        ),
        Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
    )


async def test_journey_rejects_cross_project_build_and_detects_stale_inputs() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    source_service = _SourceService(VERSION_ID)
    try:
        await _cleanup(database)
        await _seed(database)
        service = _service(database, source_service, builders_can_deploy=False)

        with pytest.raises(NotFoundError, match="for this project"):
            await service.get(
                PROJECT_ID,
                requested_build_id=OTHER_BUILD_ID,
                actor_role=UserRole.BUILDER,
            )

        ready = await service.get(
            PROJECT_ID,
            requested_build_id=BUILD_ID,
            actor_role=UserRole.BUILDER,
        )
        assert ready.resume_step == 10
        assert ready.preflight_ready
        assert not ready.deployable
        assert not ready.steps[9].authorized
        assert ready.deployability_reason_code == "DEPLOYMENT_PERMISSION_REQUIRED"
        assert all(step.state is JourneyStepState.COMPLETE for step in ready.steps[:9])

        changed_base_url = "https://replacement.example.com"
        async with database.session_scope() as session:
            await session.execute(
                update(Project)
                .where(Project.id == PROJECT_ID)
                .values(default_base_url=changed_base_url)
            )
        source_service.default_base_url = changed_base_url
        routing_stale = await service.get(
            PROJECT_ID,
            requested_build_id=BUILD_ID,
            actor_role=UserRole.ADMIN,
        )
        assert routing_stale.build_stale
        assert not routing_stale.preflight_ready
        assert routing_stale.deployability_reason_code == "BUILD_INPUTS_STALE"

        async with database.session_scope() as session:
            await session.execute(
                update(Project)
                .where(Project.id == PROJECT_ID)
                .values(default_base_url="https://api.example.com")
            )
        source_service.default_base_url = "https://api.example.com"
        restored = await service.get(
            PROJECT_ID,
            requested_build_id=BUILD_ID,
            actor_role=UserRole.ADMIN,
        )
        assert not restored.build_stale
        assert restored.preflight_ready

        replacement_id = UUID(int=509)
        async with database.session_scope() as session:
            session.add(
                SourceVersion(
                    id=replacement_id,
                    source_id=SOURCE_ID,
                    content_sha256="2" * 64,
                    media_type="application/json",
                    storage_key="sources/v2.json",
                    byte_size=100,
                    detected_format="openapi-3.1-json",
                    source_etag=None,
                    source_last_modified=None,
                    created_by=USER_ID,
                    created_at=NOW + timedelta(seconds=1),
                )
            )
        source_service.version_id = replacement_id
        stale = await service.get(
            PROJECT_ID,
            requested_build_id=BUILD_ID,
            actor_role=UserRole.ADMIN,
        )
        assert stale.build_stale
        assert stale.resume_step == 6
        assert stale.steps[6].state is JourneyStepState.STALE
        assert not stale.preflight_ready
        assert stale.deployability_reason_code == "BUILD_INPUTS_STALE"
    finally:
        await _cleanup(database)
        await database.close()
