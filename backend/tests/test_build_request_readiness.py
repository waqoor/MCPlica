from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.build_queue import BuildQueueClient
from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import InvalidStateError
from app.domain.sources import (
    BoundSourceVersionRecord,
    OperationSecurityRequirementRecord,
    ProjectSourceRecord,
    SecuritySchemeDiscoveryRecord,
    SourceConfigurationDiscoveryRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionRecord,
    source_configuration_fingerprint,
)
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

PROJECT_ID = UUID(int=601)
SOURCE_ID = UUID(int=602)
VERSION_ID = UUID(int=603)
USER_ID = UUID(int=604)
NOW = datetime(2026, 8, 27, tzinfo=UTC)


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        yield cast(AsyncSession, object())


class _Builds:
    def __init__(self) -> None:
        self.create_called = False

    async def lock_project(self, session: AsyncSession, project_id: UUID) -> object:
        return SimpleNamespace(
            is_enabled=True,
            default_base_url="https://api.example.com",
            active_server_ref=None,
            server_mappings={},
        )

    async def latest_ready(self, session: AsyncSession, project_id: UUID) -> None:
        return None

    async def create(self, *args: object, **kwargs: object) -> None:
        self.create_called = True
        return None


class _Sources:
    async def latest_bound_versions(
        self, session: AsyncSession, project_id: UUID
    ) -> list[BoundSourceVersionRecord]:
        return [
            BoundSourceVersionRecord(
                source=ProjectSourceRecord(
                    id=SOURCE_ID,
                    project_id=PROJECT_ID,
                    kind=SourceKind.OPENAPI,
                    name="API",
                    origin_type=SourceOrigin.UPLOAD,
                    source_url=None,
                    is_primary=True,
                    created_at=NOW,
                ),
                version=SourceVersionRecord(
                    id=VERSION_ID,
                    source_id=SOURCE_ID,
                    content_sha256="a" * 64,
                    media_type="application/json",
                    storage_key="sources/api.json",
                    byte_size=100,
                    detected_format="openapi-3.1-json",
                    source_etag=None,
                    source_last_modified=None,
                    created_by=USER_ID,
                    created_at=NOW,
                ),
            )
        ]


class _Configuration:
    async def discover_configuration(self, project_id: UUID) -> SourceConfigurationDiscoveryRecord:
        return SourceConfigurationDiscoveryRecord(
            source_version_ids=[VERSION_ID],
            configuration_sha256=source_configuration_fingerprint(
                source_version_ids=[VERSION_ID],
                default_base_url="https://api.example.com",
                active_server_ref=None,
                server_mappings={},
            ),
            servers=[],
            operations=[],
            security_schemes=[
                SecuritySchemeDiscoveryRecord(
                    name="bearerAuth",
                    type="http_bearer",
                    location=None,
                    parameter_name=None,
                    token_url=None,
                    advertised_scopes=[],
                    applicable_operation_keys=["list_items"],
                    optional_for_all_operations=False,
                    source_pointer="#/components/securitySchemes/bearerAuth",
                )
            ],
            security_requirements=[
                OperationSecurityRequirementRecord(
                    operation_key="list_items",
                    alternatives=[{"bearerAuth": []}],
                    anonymous_allowed=False,
                )
            ],
            routing_complete=True,
        )


class _Validation:
    async def list_exclusions(self, session: AsyncSession, project_id: UUID) -> list[object]:
        return []


class _Credentials:
    async def list(self, session: AsyncSession, project_id: UUID) -> list[object]:
        return []


class _Settings:
    async def get_models(self) -> object:
        return SimpleNamespace(
            analysis_model="analysis-model",
            validation_model="validation-model",
            embedding_model="embedding-model",
            include_documentation_in_analysis=False,
        )

    async def get_operational(self) -> object:
        return SimpleNamespace(
            max_operations_per_project=100,
            max_document_chunks_per_project=100,
        )


@pytest.mark.asyncio
async def test_build_request_rejects_missing_mapping_before_row_or_queue() -> None:
    builds = _Builds()
    service = BuildService(
        cast(DatabaseClient, _Database()),
        cast(BuildRepository, builds),
        cast(BuildAIRunRepository, object()),
        cast(CanonicalRepository, object()),
        cast(SourceRepository, _Sources()),
        cast(SourceConfigurationProvider, _Configuration()),
        cast(ProjectRepository, object()),
        cast(CredentialRepository, _Credentials()),
        cast(ValidationRepository, _Validation()),
        cast(AuditRepository, object()),
        cast(SettingsService, _Settings()),
        cast(BuildQueueClient, object()),
        Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
        cast(ArtifactService, object()),
        None,
        cast(BuildAdmissionDispatcher, object()),
    )

    with pytest.raises(InvalidStateError) as captured:
        await service.create(
            project_id=PROJECT_ID,
            requested_by=USER_ID,
            request_id="request-1",
        )

    assert captured.value.details["reason_code"] == "CREDENTIAL_MAPPING_INCOMPLETE"
    assert captured.value.details["operation_keys"] == ["list_items"]
    assert not builds.create_called
