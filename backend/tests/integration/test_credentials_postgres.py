import asyncio
import os
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.crypto import AesGcmSecretCipher
from app.core.exceptions import ConflictError, InvalidStateError, ValidationError
from app.domain.auth import UserRole
from app.domain.credentials import CredentialRecord, CredentialScheme
from app.domain.sources import (
    SecuritySchemeDiscoveryRecord,
    SourceConfigurationDiscoveryRecord,
)
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.credential import ProjectCredential
from app.models.project import Project
from app.repositories.audit import AuditRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.projects import ProjectRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.credentials import CredentialService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=24_001)
PROJECT_ID = UUID(int=24_002)


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


class _Discovery:
    async def discover_configuration(self, project_id: UUID) -> SourceConfigurationDiscoveryRecord:
        assert project_id == PROJECT_ID
        return SourceConfigurationDiscoveryRecord(
            source_version_ids=[UUID(int=24_100)],
            configuration_sha256="a" * 64,
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
                    applicable_operation_keys=["GET /matrix"],
                    optional_for_all_operations=False,
                    source_pointer="#/components/securitySchemes/bearerAuth",
                ),
                SecuritySchemeDiscoveryRecord(
                    name="alternateBearerAuth",
                    type="http_bearer",
                    location=None,
                    parameter_name=None,
                    token_url=None,
                    advertised_scopes=[],
                    applicable_operation_keys=["GET /matrix"],
                    optional_for_all_operations=False,
                    source_pointer="#/components/securitySchemes/alternateBearerAuth",
                ),
            ],
            security_requirements=[],
            routing_complete=True,
        )


class _UnavailableDiscovery(_Discovery):
    async def discover_configuration(self, project_id: UUID) -> SourceConfigurationDiscoveryRecord:
        del project_id
        raise AssertionError("secret rotation must not depend on current source discovery")


class _BarrierCredentialRepository(CredentialRepository):
    def __init__(self) -> None:
        super().__init__()
        self._barrier = asyncio.Barrier(2)
        self._observations = 0

    async def get(self, session: AsyncSession, credential_id: UUID) -> CredentialRecord | None:
        credential = await super().get(session, credential_id)
        if self._observations < 2:
            self._observations += 1
            await self._barrier.wait()
        return credential


class _Deployments:
    def __init__(self, *, fail_redeploy: bool = False) -> None:
        self.fail_redeploy = fail_redeploy
        self.redeploys = 0
        self.stops = 0
        self.notifications = 0

    async def schedule_redeploy_active(self, session: object, **values: object) -> None:
        del session, values
        self.redeploys += 1
        if self.fail_redeploy:
            raise RuntimeError("injected deployment scheduling failure")

    async def schedule_stop_project(self, session: object, **values: object) -> None:
        del session, values
        self.stops += 1

    def notify_runtime_commands(self) -> None:
        self.notifications += 1


def _service(
    database: DatabaseClient,
    *,
    discovery: _Discovery | None = None,
    deployments: _Deployments | None = None,
    credentials: CredentialRepository | None = None,
) -> CredentialService:
    return CredentialService(
        database,
        credentials or CredentialRepository(),
        ProjectRepository(),
        RuntimeCommandRepository(),
        AuditRepository(),
        AesGcmSecretCipher({"v1": b"c" * 32}, "v1"),
        deployments or _Deployments(),  # pyright: ignore[reportArgumentType]
        discovery or _Discovery(),  # pyright: ignore[reportArgumentType]
    )


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(AuditEvent).where(AuditEvent.project_id == PROJECT_ID))
        await session.execute(
            update(Project)
            .where(Project.id == PROJECT_ID)
            .values(active_build_id=None, active_deployment_id=None)
        )
        await session.execute(delete(Project).where(Project.id == PROJECT_ID))
        await session.execute(delete(User).where(User.id == USER_ID))


async def _seed(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="credential-service-test@example.com",
                display_name="Credential service test",
                password_hash="unused",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                name="Credential service test",
                slug="credential-service-test",
                description=None,
                default_base_url=None,
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="credential-service-test.mcp.example.com",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=USER_ID,
            )
        )


async def _create(service: CredentialService, name: str = "Primary bearer"):
    return await service.create(
        project_id=PROJECT_ID,
        name=name,
        scheme_type=CredentialScheme.BEARER,
        secret={"token": "initial-secret"},
        metadata={"security_scheme": " bearerAuth "},
        actor_user_id=USER_ID,
        request_id="credential-create",
    )


async def test_credential_lifecycle_encrypts_rotates_redeploys_and_revokes() -> None:
    database = DatabaseClient(_database_url(), pool_size=5, max_overflow=0)
    deployments = _Deployments()
    service = _service(database, deployments=deployments)
    try:
        await _cleanup(database)
        await _seed(database)
        credential = await _create(service)
        assert credential.name == "Primary bearer"
        assert credential.metadata == {"security_scheme": "bearerAuth"}
        assert await service.decrypt_for_execution(
            project_id=PROJECT_ID, credential_id=credential.id
        ) == {"token": "initial-secret"}
        assert [item.id for item in await service.list(PROJECT_ID)] == [credential.id]

        rotated = await service.rotate(
            project_id=PROJECT_ID,
            credential_id=credential.id,
            secret={"token": "rotated-secret"},
            metadata=None,
            actor_user_id=USER_ID,
            request_id="credential-rotate",
        )
        assert rotated.rotated_at is not None
        assert deployments.redeploys == deployments.notifications == 1
        assert await service.decrypt_for_execution(
            project_id=PROJECT_ID, credential_id=credential.id
        ) == {"token": "rotated-secret"}

        revoked = await service.revoke(
            project_id=PROJECT_ID,
            credential_id=credential.id,
            actor_user_id=USER_ID,
            request_id="credential-revoke",
        )
        assert revoked.revoked_at is not None
        assert deployments.stops == 1
        assert deployments.notifications == 2
        with pytest.raises(InvalidStateError, match="revoked"):
            await service.decrypt_for_execution(
                project_id=PROJECT_ID,
                credential_id=credential.id,
            )

        async with database.session_scope() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent.event_type)
                    .where(AuditEvent.project_id == PROJECT_ID)
                    .order_by(AuditEvent.created_at)
                )
            )
            assert events == [
                "credential.created",
                "credential.rotated",
                "credential.revoked",
            ]
    finally:
        await _cleanup(database)
        await database.close()


async def test_concurrent_rotation_serializes_and_rejects_stale_writer() -> None:
    database = DatabaseClient(_database_url(), pool_size=6, max_overflow=0)
    try:
        await _cleanup(database)
        await _seed(database)
        credential = await _create(_service(database))
        deployments = _Deployments()
        service = _service(
            database,
            deployments=deployments,
            credentials=_BarrierCredentialRepository(),
        )

        results = await asyncio.gather(
            service.rotate(
                project_id=PROJECT_ID,
                credential_id=credential.id,
                secret={"token": "winner-one"},
                metadata=None,
                actor_user_id=USER_ID,
                request_id="rotate-one",
            ),
            service.rotate(
                project_id=PROJECT_ID,
                credential_id=credential.id,
                secret={"token": "winner-two"},
                metadata=None,
                actor_user_id=USER_ID,
                request_id="rotate-two",
            ),
            return_exceptions=True,
        )

        assert sum(not isinstance(result, Exception) for result in results) == 1
        assert sum(isinstance(result, ConflictError) for result in results) == 1
        assert deployments.redeploys == deployments.notifications == 1
        secret = await service.decrypt_for_execution(
            project_id=PROJECT_ID,
            credential_id=credential.id,
        )
        assert secret["token"] in {"winner-one", "winner-two"}
    finally:
        await _cleanup(database)
        await database.close()


async def test_rotation_rejects_mapping_changes_without_mutating_secret_or_runtime() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    deployments = _Deployments()
    service = _service(database, deployments=deployments)
    try:
        await _cleanup(database)
        await _seed(database)
        credential = await _create(service)

        with pytest.raises(ValidationError, match="immutable during secret rotation"):
            await service.rotate(
                project_id=PROJECT_ID,
                credential_id=credential.id,
                secret={"token": "must-not-commit"},
                metadata={"security_scheme": "alternateBearerAuth"},
                actor_user_id=USER_ID,
                request_id="credential-remap-rejected",
            )

        stored = next(item for item in await service.list(PROJECT_ID) if item.id == credential.id)
        assert stored.metadata == {"security_scheme": "bearerAuth"}
        assert stored.rotated_at is None
        assert await service.decrypt_for_execution(
            project_id=PROJECT_ID,
            credential_id=credential.id,
        ) == {"token": "initial-secret"}
        assert deployments.redeploys == deployments.notifications == 0
        async with database.session_scope() as session:
            event_types = list(
                await session.scalars(
                    select(AuditEvent.event_type).where(AuditEvent.project_id == PROJECT_ID)
                )
            )
            assert event_types == ["credential.created"]
    finally:
        await _cleanup(database)
        await database.close()


async def test_secret_rotation_uses_frozen_mapping_after_current_source_drift() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    deployments = _Deployments()
    try:
        await _cleanup(database)
        await _seed(database)
        credential = await _create(_service(database))
        service = _service(
            database,
            discovery=_UnavailableDiscovery(),
            deployments=deployments,
        )

        rotated = await service.rotate(
            project_id=PROJECT_ID,
            credential_id=credential.id,
            secret={"token": "source-drift-safe-secret"},
            metadata={"security_scheme": " bearerAuth "},
            actor_user_id=USER_ID,
            request_id="credential-rotate-after-source-drift",
        )

        assert rotated.metadata == {"security_scheme": "bearerAuth"}
        assert await service.decrypt_for_execution(
            project_id=PROJECT_ID,
            credential_id=credential.id,
        ) == {"token": "source-drift-safe-secret"}
        assert deployments.redeploys == deployments.notifications == 1
    finally:
        await _cleanup(database)
        await database.close()


async def test_rotation_rolls_back_secret_and_audit_when_redeploy_scheduling_fails() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    try:
        await _cleanup(database)
        await _seed(database)
        credential = await _create(_service(database))
        failing = _service(database, deployments=_Deployments(fail_redeploy=True))

        with pytest.raises(RuntimeError, match="scheduling failure"):
            await failing.rotate(
                project_id=PROJECT_ID,
                credential_id=credential.id,
                secret={"token": "must-rollback"},
                metadata=None,
                actor_user_id=USER_ID,
                request_id="rotate-rollback",
            )

        assert await failing.decrypt_for_execution(
            project_id=PROJECT_ID,
            credential_id=credential.id,
        ) == {"token": "initial-secret"}
        async with database.session_scope() as session:
            stored = await session.get(ProjectCredential, credential.id)
            assert stored is not None
            assert stored.rotated_at is None
            event_types = list(
                await session.scalars(
                    select(AuditEvent.event_type).where(AuditEvent.project_id == PROJECT_ID)
                )
            )
            assert event_types == ["credential.created"]
    finally:
        await _cleanup(database)
        await database.close()
