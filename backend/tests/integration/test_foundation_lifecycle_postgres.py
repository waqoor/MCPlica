import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import DeployabilityError, InvalidStateError
from app.domain.auth import UserRole
from app.domain.builds import BuildStatus, BuildTrigger
from app.domain.deployments import (
    DeployableBuildRecord,
    DeploymentActivationPhase,
    DeploymentIntent,
    DeploymentStatus,
    MCPAuthMode,
    RuntimeCommandAction,
    RuntimeEffectState,
)
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.build import Build
from app.models.deployment import Deployment
from app.models.mcp_access import MCPAccessToken, MCPAuthConfig
from app.models.project import Project
from app.models.runtime_command import RuntimeLifecycleCommand
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.mcp_access import MCPAccessRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.service import DeploymentService
from app.services.mcp_access import MCPAccessService

pytestmark = pytest.mark.postgres_integration


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


class _DeploymentRepository(DeploymentRepository):
    async def get_build(
        self,
        session: AsyncSession,
        build_id: UUID,
    ) -> DeployableBuildRecord | None:
        build = await session.get(Build, build_id)
        if build is None:
            return None
        return DeployableBuildRecord(
            id=build.id,
            project_id=build.project_id,
            status="READY",
            source_binding_metadata_trustworthy=True,
            executable_configuration_sha256="1" * 64,
            runtime_manifest_max_bytes=1_000_000,
            manifest_sha256="2" * 64,
            manifest_storage_key="manifests/foundation.json",
        )


class _StaleAwarePreflight:
    def __init__(self, *, fail_all: bool = False) -> None:
        self.current_configuration_requirements: list[bool] = []
        self.fail_all = fail_all

    async def validate(self, *args: object, **kwargs: object) -> None:
        del args
        require_current = bool(kwargs["require_current_configuration"])
        self.current_configuration_requirements.append(require_current)
        if require_current or self.fail_all:
            raise DeployabilityError(
                "Build source or routing configuration is no longer current",
                details={"reason_code": "BUILD_INPUTS_STALE"},
            )


class _Dispatcher:
    def __init__(self) -> None:
        self.wake_count = 0

    def wake(self) -> None:
        self.wake_count += 1


def _settings() -> Settings:
    return Settings(_env_file=None, env="test")  # pyright: ignore[reportCallIssue]


async def _cleanup(database: DatabaseClient, *, project_id: UUID, user_id: UUID) -> None:
    async with database.session_scope() as session:
        await session.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(active_build_id=None, active_deployment_id=None)
        )
        await session.execute(
            delete(RuntimeLifecycleCommand).where(RuntimeLifecycleCommand.project_id == project_id)
        )
        await session.execute(delete(AuditEvent).where(AuditEvent.project_id == project_id))
        await session.execute(delete(Deployment).where(Deployment.project_id == project_id))
        await session.execute(delete(MCPAccessToken).where(MCPAccessToken.project_id == project_id))
        await session.execute(delete(MCPAuthConfig).where(MCPAuthConfig.project_id == project_id))
        await session.execute(delete(Build).where(Build.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id == user_id))


async def _seed(
    database: DatabaseClient,
    *,
    project_id: UUID,
    user_id: UUID,
    build_id: UUID,
    deployment_id: UUID,
    token_ids: tuple[UUID, ...] = (),
) -> None:
    now = datetime.now(UTC)
    async with database.session_scope() as session:
        session.add(
            User(
                id=user_id,
                email=f"foundation-{user_id.int}@example.com",
                display_name="Foundation lifecycle test",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=project_id,
                name=f"Foundation {project_id.int}",
                slug=f"foundation-{project_id.int}",
                description=None,
                default_base_url="https://api.example.com",
                active_server_ref=None,
                server_mappings={},
                mcp_hostname=f"foundation-{project_id.int}.mcp.example.com",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=user_id,
            )
        )
        await session.flush()
        session.add(
            Build(
                id=build_id,
                project_id=project_id,
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
                requested_by=user_id,
                started_at=None,
                completed_at=None,
            )
        )
        await session.flush()
        session.add(
            Deployment(
                id=deployment_id,
                project_id=project_id,
                build_id=build_id,
                intent=DeploymentIntent.NORMAL,
                previous_active_deployment_id=None,
                status=DeploymentStatus.RUNNING,
                hostname=f"foundation-{project_id.int}.mcp.example.com",
                container_name=f"mcp-foundation-{deployment_id.int}",
                container_id=f"container-{deployment_id.int}",
                image_ref="runtime@sha256:" + "a" * 64,
                image_digest="sha256:" + "b" * 64,
                runtime_version="1.0.0",
                network_name=f"mcp-foundation-{project_id.int}",
                manifest_sha256="2" * 64,
                auth_overlay_sha256="3" * 64,
                route_priority=100,
                stop_old_first=False,
                health_status="healthy",
                deployed_by=user_id,
                started_at=now,
                activated_at=now,
                activation_phase=DeploymentActivationPhase.LEGACY_RUNNING,
                activation_verified_at=None,
                activation_proof_sha256=None,
                stopped_at=None,
                failed_at=None,
                error_code=None,
                error_summary=None,
            )
        )
        session.add(
            MCPAuthConfig(
                project_id=project_id,
                mode=MCPAuthMode.STATIC_BEARER,
                issuer_url=None,
                audiences=[],
                required_scopes=[],
                metadata_json={},
                updated_by=user_id,
                updated_at=now,
            )
        )
        for index, token_id in enumerate(token_ids):
            session.add(
                MCPAccessToken(
                    id=token_id,
                    project_id=project_id,
                    name=f"token-{index}",
                    token_prefix=f"mcp_token_{index}",
                    token_hash=f"sha256:{index + 1:064x}",
                    created_by=user_id,
                    expires_at=None,
                    last_used_at=None,
                    revoked_at=None,
                )
            )
        await session.flush()
        project = await session.get(Project, project_id)
        assert project is not None
        project.active_build_id = build_id
        project.active_deployment_id = deployment_id


def _deployment_service(
    database: DatabaseClient,
    repository: DeploymentRepository,
    preflight: _StaleAwarePreflight,
) -> tuple[DeploymentService, _Dispatcher]:
    dispatcher = _Dispatcher()
    return (
        DeploymentService(
            database,
            repository,
            RuntimeCommandRepository(),
            AuditRepository(),
            dispatcher,  # type: ignore[arg-type]
            preflight,  # type: ignore[arg-type]
            _settings(),
        ),
        dispatcher,
    )


async def test_stop_first_transition_commits_ordered_stop_then_security_refresh() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    project_id, user_id, build_id, deployment_id = (
        UUID(int=30_001),
        UUID(int=30_002),
        UUID(int=30_003),
        UUID(int=30_004),
    )
    transition_id = UUID(int=30_005)
    repository = _DeploymentRepository()
    preflight = _StaleAwarePreflight()
    service, dispatcher = _deployment_service(database, repository, preflight)
    try:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await _seed(
            database,
            project_id=project_id,
            user_id=user_id,
            build_id=build_id,
            deployment_id=deployment_id,
        )

        async with database.session_scope() as session:
            replacement = await service.schedule_redeploy_active(
                session,
                project_id=project_id,
                actor_user_id=user_id,
                request_id="credential-rotation",
                stop_old_first=True,
                event_type="deployment.credential_rotation_requested",
                subject_type="project_credential",
                subject_id=UUID(int=30_006),
                transition_id=transition_id,
                intent=DeploymentIntent.SECURITY_REFRESH,
            )
        assert replacement is not None
        assert replacement.build_id == build_id
        assert replacement.intent is DeploymentIntent.SECURITY_REFRESH
        assert preflight.current_configuration_requirements == [False]

        async with database.session_scope() as session:
            prior = await session.get(Deployment, deployment_id)
            assert prior is not None and prior.status is DeploymentStatus.STOPPING
            commands = list(
                await session.scalars(
                    select(RuntimeLifecycleCommand)
                    .where(RuntimeLifecycleCommand.transition_id == transition_id)
                    .order_by(RuntimeLifecycleCommand.sequence)
                )
            )
            assert [command.action for command in commands] == [
                RuntimeCommandAction.STOP,
                RuntimeCommandAction.DEPLOY,
            ]
            assert commands[0].deployment_id == deployment_id
            assert commands[1].deployment_id == replacement.id

        with pytest.raises(InvalidStateError, match="already in progress"):
            await service.request(
                project_id=project_id,
                build_id=build_id,
                actor_user_id=user_id,
                request_id="unrelated-deploy",
            )
        assert dispatcher.wake_count == 0
    finally:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await database.close()


async def test_final_token_revocation_commits_one_stop_and_no_invalid_replacement() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    project_id, user_id, build_id, deployment_id, token_id = (
        UUID(int=31_001),
        UUID(int=31_002),
        UUID(int=31_003),
        UUID(int=31_004),
        UUID(int=31_005),
    )
    repository = _DeploymentRepository()
    deployment_service, dispatcher = _deployment_service(
        database,
        repository,
        _StaleAwarePreflight(),
    )
    access_service = MCPAccessService(
        database,
        MCPAccessRepository(),
        repository,
        RuntimeCommandRepository(),
        AuditRepository(),
        deployment_service,
        _settings(),
    )
    try:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await _seed(
            database,
            project_id=project_id,
            user_id=user_id,
            build_id=build_id,
            deployment_id=deployment_id,
            token_ids=(token_id,),
        )

        revoked = await access_service.revoke_token(
            project_id=project_id,
            token_id=token_id,
            actor_user_id=user_id,
            request_id="last-token-revoke",
        )
        duplicate = await access_service.revoke_token(
            project_id=project_id,
            token_id=token_id,
            actor_user_id=user_id,
            request_id="last-token-revoke-duplicate",
        )

        assert revoked.revoked_at is not None
        assert duplicate.revoked_at == revoked.revoked_at
        assert revoked.runtime_effect_state is RuntimeEffectState.PENDING
        async with database.session_scope() as session:
            assert (
                await session.scalar(
                    select(func.count(Deployment.id)).where(Deployment.project_id == project_id)
                )
                == 1
            )
            stored = await session.get(Deployment, deployment_id)
            assert stored is not None and stored.status is DeploymentStatus.STOPPING
            commands = list(
                await session.scalars(
                    select(RuntimeLifecycleCommand).where(
                        RuntimeLifecycleCommand.project_id == project_id
                    )
                )
            )
            assert len(commands) == 1
            assert commands[0].action is RuntimeCommandAction.STOP
            assert commands[0].subject_id == token_id
        assert dispatcher.wake_count == 1
    finally:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await database.close()


async def test_security_refresh_ignores_source_drift_but_normal_deploy_does_not() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    project_id, user_id, build_id, deployment_id, first_token, second_token = (
        UUID(int=32_001),
        UUID(int=32_002),
        UUID(int=32_003),
        UUID(int=32_004),
        UUID(int=32_005),
        UUID(int=32_006),
    )
    repository = _DeploymentRepository()
    preflight = _StaleAwarePreflight()
    deployment_service, _ = _deployment_service(database, repository, preflight)
    access_service = MCPAccessService(
        database,
        MCPAccessRepository(),
        repository,
        RuntimeCommandRepository(),
        AuditRepository(),
        deployment_service,
        _settings(),
    )
    try:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await _seed(
            database,
            project_id=project_id,
            user_id=user_id,
            build_id=build_id,
            deployment_id=deployment_id,
            token_ids=(first_token, second_token),
        )

        await access_service.revoke_token(
            project_id=project_id,
            token_id=first_token,
            actor_user_id=user_id,
            request_id="subset-revoke-after-source-drift",
        )
        assert preflight.current_configuration_requirements == [False]
        async with database.session_scope() as session:
            replacement = await session.scalar(
                select(Deployment).where(
                    Deployment.project_id == project_id,
                    Deployment.id != deployment_id,
                )
            )
            assert replacement is not None
            assert replacement.build_id == build_id
            assert replacement.intent is DeploymentIntent.SECURITY_REFRESH
            replacement.status = DeploymentStatus.FAILED
            replacement.failed_at = datetime.now(UTC)
            replacement.error_code = "test_cleanup"

        with pytest.raises(DeployabilityError) as stale:
            await deployment_service.request(
                project_id=project_id,
                build_id=build_id,
                actor_user_id=user_id,
                request_id="ordinary-stale-deploy",
            )
        assert stale.value.details["reason_code"] == "BUILD_INPUTS_STALE"
        assert preflight.current_configuration_requirements == [False, True]
    finally:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await database.close()


async def test_unsafe_security_refresh_commits_a_stop_instead_of_rolling_back() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    project_id, user_id, build_id, deployment_id = (
        UUID(int=33_001),
        UUID(int=33_002),
        UUID(int=33_003),
        UUID(int=33_004),
    )
    repository = _DeploymentRepository()
    preflight = _StaleAwarePreflight(fail_all=True)
    service, dispatcher = _deployment_service(database, repository, preflight)
    try:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await _seed(
            database,
            project_id=project_id,
            user_id=user_id,
            build_id=build_id,
            deployment_id=deployment_id,
        )

        async with database.session_scope() as session:
            replacement = await service.schedule_redeploy_active(
                session,
                project_id=project_id,
                actor_user_id=user_id,
                request_id="unsafe-security-refresh",
                stop_old_first=False,
                event_type="deployment.mcp_auth_change_requested",
                subject_type="mcp_auth_config",
                subject_id=project_id,
                intent=DeploymentIntent.SECURITY_REFRESH,
                fallback_to_stop=True,
            )
        assert replacement is None

        async with database.session_scope() as session:
            deployment = await session.get(Deployment, deployment_id)
            commands = list(
                await session.scalars(
                    select(RuntimeLifecycleCommand).where(
                        RuntimeLifecycleCommand.project_id == project_id
                    )
                )
            )
        assert deployment is not None
        assert deployment.status is DeploymentStatus.STOPPING
        assert len(commands) == 1
        assert commands[0].action is RuntimeCommandAction.STOP
        assert dispatcher.wake_count == 0
    finally:
        await _cleanup(database, project_id=project_id, user_id=user_id)
        await database.close()
