import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update

from app.clients.database import DatabaseClient
from app.clients.runtime_files import RuntimeFilesClient
from app.core.exceptions import DockerOperationError, RuntimeHealthError
from app.domain.auth import UserRole
from app.domain.builds import BuildStatus, BuildTrigger
from app.domain.deployments import (
    DeploymentActivationPhase,
    DeploymentActivationProof,
    DeploymentRecord,
    DeploymentStatus,
    RuntimeCommandAction,
    RuntimeCommandStatus,
)
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.build import Build
from app.models.deployment import Deployment
from app.models.project import Project
from app.models.runtime_command import RuntimeLifecycleCommand
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.preflight import DeploymentPreflight
from app.services.deployment.runtime_manager import RuntimeManager
from app.services.deployment.secret_materializer import DeploymentSecretMaterializer
from app.services.deployment.service import DeploymentRunner

pytestmark = pytest.mark.postgres_integration


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


async def _cleanup_test_rows(
    database: DatabaseClient,
    *,
    project_id: UUID,
    user_id: UUID,
) -> None:
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
        await session.execute(delete(Build).where(Build.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id == user_id))


async def _seed(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=UUID(int=101),
                email="runtime-command-test@example.com",
                display_name="Runtime command test",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=UUID(int=102),
                name="Runtime command test",
                slug="runtime-command-test",
                description=None,
                default_base_url="https://api.example.com",
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="runtime-command-test.mcp.example.com",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=UUID(int=101),
            )
        )
        await session.flush()
        session.add(
            Build(
                id=UUID(int=103),
                project_id=UUID(int=102),
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
                requested_by=UUID(int=101),
                started_at=None,
                completed_at=None,
            )
        )
        await session.flush()
        session.add(
            Deployment(
                id=UUID(int=104),
                project_id=UUID(int=102),
                build_id=UUID(int=103),
                previous_active_deployment_id=None,
                status=DeploymentStatus.PENDING,
                hostname="runtime-command-test.mcp.example.com",
                container_name="mcp-runtime-command-test",
                container_id=None,
                image_ref="runtime@sha256:" + "a" * 64,
                image_digest=None,
                runtime_version="1.0.0",
                network_name="mcp-runtime-command-test",
                manifest_sha256="b" * 64,
                auth_overlay_sha256=None,
                route_priority=1,
                stop_old_first=True,
                health_status=None,
                deployed_by=UUID(int=101),
                started_at=None,
                activated_at=None,
                stopped_at=None,
                failed_at=None,
                error_code=None,
                error_summary=None,
            )
        )


async def test_transactional_outbox_leases_replay_and_restart_reconciliation() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    commands = RuntimeCommandRepository()
    try:
        await _cleanup_test_rows(database, project_id=UUID(int=102), user_id=UUID(int=101))
        await _seed(database)
        with pytest.raises(RuntimeError, match="force rollback"):
            async with database.session_scope() as session:
                await commands.create(
                    session,
                    command_id=UUID(int=105),
                    project_id=UUID(int=102),
                    deployment_id=UUID(int=104),
                    build_id=UUID(int=103),
                    transition_id=UUID(int=106),
                    action=RuntimeCommandAction.DEPLOY,
                    reason="transaction_rollback_probe",
                    subject_type="project",
                    subject_id=UUID(int=102),
                    requested_by=UUID(int=101),
                    request_id="rollback-probe",
                    idempotency_key="runtime-command-rollback-probe",
                )
                raise RuntimeError("force rollback")
        async with database.session_scope() as session:
            assert await session.get(RuntimeLifecycleCommand, UUID(int=105)) is None

        async with database.session_scope() as session:
            created = await commands.create(
                session,
                command_id=UUID(int=107),
                project_id=UUID(int=102),
                deployment_id=UUID(int=104),
                build_id=UUID(int=103),
                transition_id=UUID(int=108),
                action=RuntimeCommandAction.DEPLOY,
                reason="worker_crash_probe",
                subject_type="project",
                subject_id=UUID(int=102),
                requested_by=UUID(int=101),
                request_id="worker-crash-probe",
                idempotency_key="runtime-command-worker-crash-probe",
            )
            replay = await commands.create(
                session,
                command_id=UUID(int=109),
                project_id=UUID(int=102),
                deployment_id=UUID(int=104),
                build_id=UUID(int=103),
                transition_id=UUID(int=108),
                action=RuntimeCommandAction.DEPLOY,
                reason="worker_crash_probe",
                subject_type="project",
                subject_id=UUID(int=102),
                requested_by=UUID(int=101),
                request_id="worker-crash-probe",
                idempotency_key="runtime-command-worker-crash-probe",
            )
            assert replay.id == created.id

        async def claim() -> list[UUID]:
            async with database.session_scope() as session:
                claimed = await commands.claim_due_for_dispatch(
                    session,
                    limit=10,
                    lease_seconds=30,
                )
                return [command.id for command in claimed]

        concurrent_claims = await asyncio.gather(claim(), claim())
        assert sum(value == UUID(int=107) for group in concurrent_claims for value in group) == 1

        async with database.session_scope() as session:
            running = await commands.claim_for_execution(
                session,
                UUID(int=107),
                lease_seconds=60,
            )
            assert running is not None
            assert running.status is RuntimeCommandStatus.RUNNING
            await session.execute(
                update(RuntimeLifecycleCommand)
                .where(RuntimeLifecycleCommand.id == UUID(int=107))
                .values(
                    lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
                    next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
                )
            )

        async with database.session_scope() as session:
            recovered = await commands.claim_due_for_dispatch(
                session,
                limit=10,
                lease_seconds=30,
            )
            assert [command.id for command in recovered] == [UUID(int=107)]
            assert recovered[0].attempt_count == 2

        async with database.session_scope() as session:
            await commands.mark_effective(session, UUID(int=107))
        async with database.session_scope() as session:
            effective = await session.scalar(
                select(RuntimeLifecycleCommand).where(RuntimeLifecycleCommand.id == UUID(int=107))
            )
            assert effective is not None
            assert effective.status is RuntimeCommandStatus.EFFECTIVE
            assert effective.effective_at is not None
            assert (
                await commands.claim_for_execution(
                    session,
                    UUID(int=107),
                    lease_seconds=60,
                )
                is None
            )

        # One authorization transition may require STOP-before-DEPLOY. Queue
        # delivery is allowed to duplicate/reorder messages, so the durable
        # repository itself must prevent the replacement from overtaking the
        # stop command.
        async with database.session_scope() as session:
            first = await commands.create(
                session,
                command_id=UUID(int=110),
                project_id=UUID(int=102),
                deployment_id=UUID(int=104),
                build_id=UUID(int=103),
                transition_id=UUID(int=112),
                action=RuntimeCommandAction.STOP,
                reason="ordered_transition_probe",
                subject_type="project",
                subject_id=UUID(int=102),
                requested_by=UUID(int=101),
                request_id="ordered-transition-probe",
                idempotency_key="runtime-command-ordered-stop",
            )
            second = await commands.create(
                session,
                command_id=UUID(int=111),
                project_id=UUID(int=102),
                deployment_id=UUID(int=104),
                build_id=UUID(int=103),
                transition_id=UUID(int=112),
                action=RuntimeCommandAction.DEPLOY,
                reason="ordered_transition_probe",
                subject_type="project",
                subject_id=UUID(int=102),
                requested_by=UUID(int=101),
                request_id="ordered-transition-probe",
                idempotency_key="runtime-command-ordered-deploy",
            )
            assert first.sequence < second.sequence

        async with database.session_scope() as session:
            ordered_claim = await commands.claim_due_for_dispatch(
                session,
                limit=10,
                lease_seconds=30,
            )
            assert [command.id for command in ordered_claim] == [UUID(int=110)]
            assert (
                await commands.claim_for_execution(
                    session,
                    UUID(int=111),
                    lease_seconds=60,
                )
                is None
            )
            await commands.mark_effective(session, UUID(int=110))

        async with database.session_scope() as session:
            next_claim = await commands.claim_due_for_dispatch(
                session,
                limit=10,
                lease_seconds=30,
            )
            assert [command.id for command in next_claim] == [UUID(int=111)]
    finally:
        await _cleanup_test_rows(database, project_id=UUID(int=102), user_id=UUID(int=101))
        await database.close()


async def _seed_activation_retry(database: DatabaseClient) -> tuple[UUID, UUID]:
    user_id = UUID(int=201)
    project_id = UUID(int=202)
    old_build_id = UUID(int=203)
    new_build_id = UUID(int=204)
    old_deployment_id = UUID(int=205)
    candidate_id = UUID(int=206)
    now = datetime.now(UTC)
    proof = DeploymentActivationProof.verified(
        deployment_id=candidate_id,
        project_id=project_id,
        build_id=new_build_id,
        container_id="candidate-container-id",
        image_digest="sha256:candidate",
        hostname="activation-retry.mcp.example.com",
        manifest_sha256="d" * 64,
        runtime_version="1.0.0",
        verified_at=now,
    )
    async with database.session_scope() as session:
        session.add(
            User(
                id=user_id,
                email="activation-retry-test@example.com",
                display_name="Activation retry test",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=project_id,
                name="Activation retry test",
                slug="activation-retry-test",
                description=None,
                default_base_url="https://api.example.com",
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="activation-retry.mcp.example.com",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=user_id,
            )
        )
        await session.flush()
        for build_id, sequence, status in (
            (old_build_id, 1, BuildStatus.CANCELLED),
            (new_build_id, 2, BuildStatus.QUEUED),
        ):
            session.add(
                Build(
                    id=build_id,
                    project_id=project_id,
                    sequence=sequence,
                    status=status,
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
                    completed_at=now if status is BuildStatus.CANCELLED else None,
                    cancellation_requested_at=(now if status is BuildStatus.CANCELLED else None),
                    cancellation_requested_by=(
                        user_id if status is BuildStatus.CANCELLED else None
                    ),
                    cancellation_acknowledged_at=(now if status is BuildStatus.CANCELLED else None),
                )
            )
        await session.flush()
        session.add(
            Deployment(
                id=old_deployment_id,
                project_id=project_id,
                build_id=old_build_id,
                previous_active_deployment_id=None,
                status=DeploymentStatus.STOPPING,
                hostname="activation-retry.mcp.example.com",
                container_name="activation-retry-old",
                container_id="old-container-id",
                image_ref="runtime@sha256:" + "a" * 64,
                image_digest="sha256:old",
                runtime_version="1.0.0",
                network_name="activation-retry-network",
                manifest_sha256="c" * 64,
                auth_overlay_sha256=None,
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
        await session.flush()
        session.add(
            Deployment(
                id=candidate_id,
                project_id=project_id,
                build_id=new_build_id,
                previous_active_deployment_id=old_deployment_id,
                status=DeploymentStatus.HEALTHCHECK,
                hostname="activation-retry.mcp.example.com",
                container_name="activation-retry-candidate",
                container_id=proof.container_id,
                image_ref="runtime@sha256:" + "b" * 64,
                image_digest=proof.image_digest,
                runtime_version="1.0.0",
                network_name="activation-retry-network",
                manifest_sha256=proof.manifest_sha256,
                auth_overlay_sha256=None,
                route_priority=101,
                stop_old_first=False,
                health_status="activating",
                deployed_by=user_id,
                started_at=now,
                activated_at=None,
                activation_phase=DeploymentActivationPhase.VERIFIED,
                activation_verified_at=proof.verified_at,
                activation_proof_sha256=proof.proof_sha256,
                stopped_at=None,
                failed_at=None,
                error_code=None,
                error_summary=None,
            )
        )
        await session.flush()
        project = await session.get(Project, project_id)
        assert project is not None
        project.active_build_id = new_build_id
        project.active_deployment_id = candidate_id
    return old_deployment_id, candidate_id


class _ActivationFailureRuntime:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.cleanup_failure_injected = False
        self.candidate_dead = False

    async def revalidate_activation_candidate(
        self, deployment: DeploymentRecord
    ) -> DeploymentActivationProof:
        self.events.append(f"revalidate:{deployment.id}")
        if self.candidate_dead:
            raise RuntimeHealthError("Activation candidate died before retry")
        assert deployment.container_id is not None
        assert deployment.image_digest is not None
        return DeploymentActivationProof.verified(
            deployment_id=deployment.id,
            project_id=deployment.project_id,
            build_id=deployment.build_id,
            container_id=deployment.container_id,
            image_digest=deployment.image_digest,
            hostname=deployment.hostname,
            manifest_sha256=deployment.manifest_sha256,
            runtime_version=deployment.runtime_version,
        )

    async def stop(self, deployment: DeploymentRecord, *, remove: bool) -> None:
        self.events.append(f"stop:{deployment.id}:{remove}")
        if remove and not self.cleanup_failure_injected:
            self.cleanup_failure_injected = True
            raise DockerOperationError("Injected superseded cleanup failure")

    async def restore_activation_predecessor(
        self, deployment: DeploymentRecord
    ) -> DeploymentActivationProof:
        self.events.append(f"restore:{deployment.id}")
        assert deployment.container_id is not None
        assert deployment.image_digest is not None
        return DeploymentActivationProof.verified(
            deployment_id=deployment.id,
            project_id=deployment.project_id,
            build_id=deployment.build_id,
            container_id=deployment.container_id,
            image_digest=deployment.image_digest,
            hostname=deployment.hostname,
            manifest_sha256=deployment.manifest_sha256,
            runtime_version=deployment.runtime_version,
        )

    async def cleanup_failed(self, deployment: DeploymentRecord) -> None:
        self.events.append(f"cleanup-failed:{deployment.id}")

    async def cleanup_network_if_unused(self, deployment: DeploymentRecord) -> bool:
        self.events.append(f"cleanup-network:{deployment.id}")
        return True


class _ActivationFailureFiles:
    def __init__(self) -> None:
        self.removed: list[UUID] = []

    async def remove(self, deployment_id: UUID) -> None:
        self.removed.append(deployment_id)


async def test_activation_cleanup_failure_preserves_atomic_state_and_restores_predecessor() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    runtime = _ActivationFailureRuntime()
    files = _ActivationFailureFiles()
    deployments = DeploymentRepository()
    try:
        await _cleanup_test_rows(database, project_id=UUID(int=202), user_id=UUID(int=201))
        old_id, candidate_id = await _seed_activation_retry(database)
        runner = DeploymentRunner(
            database,
            deployments,
            AuditRepository(),
            cast(DeploymentPreflight, object()),
            cast(RuntimeFilesClient, files),
            cast(DeploymentSecretMaterializer, object()),
            cast(RuntimeManager, runtime),
        )

        with pytest.raises(DockerOperationError, match="cleanup failure"):
            await runner.run(candidate_id)
        async with database.session_scope() as session:
            candidate = await session.get(Deployment, candidate_id)
            predecessor = await session.get(Deployment, old_id)
            assert candidate is not None and candidate.status is DeploymentStatus.RUNNING
            assert candidate.activation_phase == DeploymentActivationPhase.RUNNING
            assert candidate.activation_verified_at is not None
            assert candidate.activation_proof_sha256 is not None
            assert predecessor is not None and predecessor.status is DeploymentStatus.STOPPED
            assert predecessor.health_status == "stopped"
            assert predecessor.stopped_at is not None
            assert candidate.started_at is not None
            assert predecessor.stopped_at <= candidate.started_at

        runtime.candidate_dead = True
        with pytest.raises(RuntimeHealthError, match="died before retry"):
            await runner.run(candidate_id)

        async with database.session_scope() as session:
            project = await session.get(Project, UUID(int=202))
            candidate = await session.get(Deployment, candidate_id)
            predecessor = await session.get(Deployment, old_id)
            assert project is not None
            assert project.active_deployment_id == old_id
            assert project.active_build_id == UUID(int=203)
            assert candidate is not None
            assert candidate.status is DeploymentStatus.UNHEALTHY
            assert candidate.activation_phase == DeploymentActivationPhase.FAILED
            assert candidate.error_code == "runtime_health_error"
            assert predecessor is not None and predecessor.status is DeploymentStatus.RUNNING
            assert predecessor.health_status == "healthy"
            assert predecessor.stopped_at is None

        assert runtime.events[:4] == [
            f"revalidate:{candidate_id}",
            f"stop:{old_id}:False",
            f"revalidate:{candidate_id}",
            f"stop:{old_id}:True",
        ]
        assert f"stop:{candidate_id}:False" in runtime.events
        assert f"restore:{old_id}" in runtime.events
        assert files.removed == [candidate_id]
    finally:
        await _cleanup_test_rows(database, project_id=UUID(int=202), user_id=UUID(int=201))
        await database.close()


async def test_activation_cleanup_retry_finishes_retired_runtime_removal() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    runtime = _ActivationFailureRuntime()
    files = _ActivationFailureFiles()
    deployments = DeploymentRepository()
    try:
        await _cleanup_test_rows(database, project_id=UUID(int=202), user_id=UUID(int=201))
        old_id, candidate_id = await _seed_activation_retry(database)
        runner = DeploymentRunner(
            database,
            deployments,
            AuditRepository(),
            cast(DeploymentPreflight, object()),
            cast(RuntimeFilesClient, files),
            cast(DeploymentSecretMaterializer, object()),
            cast(RuntimeManager, runtime),
        )

        with pytest.raises(DockerOperationError, match="cleanup failure"):
            await runner.run(candidate_id)
        await runner.run(candidate_id)

        async with database.session_scope() as session:
            project = await session.get(Project, UUID(int=202))
            candidate = await session.get(Deployment, candidate_id)
            predecessor = await session.get(Deployment, old_id)
            assert project is not None and project.active_deployment_id == candidate_id
            assert candidate is not None and candidate.status is DeploymentStatus.RUNNING
            assert predecessor is not None and predecessor.status is DeploymentStatus.STOPPED
            assert predecessor.stopped_at is not None
            assert candidate.started_at is not None
            assert predecessor.stopped_at <= candidate.started_at
        assert files.removed == [old_id]
    finally:
        await _cleanup_test_rows(database, project_id=UUID(int=202), user_id=UUID(int=201))
        await database.close()
