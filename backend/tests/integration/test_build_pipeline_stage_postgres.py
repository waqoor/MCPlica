import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete, update

from app.clients.database import DatabaseClient
from app.domain.auth import UserRole
from app.domain.builds import PIPELINE_STATUSES, BuildConfiguration, BuildStatus, BuildTrigger
from app.models.auth import User
from app.models.build import Build
from app.models.project import Project
from app.repositories.builds import BuildRepository

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=18_001)
PROJECT_ID = UUID(int=18_002)


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


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
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
                email="pipeline-stage-test@example.com",
                display_name="Pipeline stage test",
                password_hash="unused",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                name="Pipeline stage test",
                slug="pipeline-stage-test",
                description=None,
                default_base_url=None,
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="pipeline-stage-test.mcp.example.com",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=USER_ID,
            )
        )


def _build(build_id: UUID, sequence: int, stage: BuildStatus) -> Build:
    now = datetime.now(UTC)
    return Build(
        id=build_id,
        project_id=PROJECT_ID,
        sequence=sequence,
        status=stage,
        pipeline_stage=stage,
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
        started_at=None if stage is BuildStatus.QUEUED else now,
        completed_at=None,
    )


async def test_failure_preserves_every_authoritative_pipeline_stage() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    repository = BuildRepository()
    try:
        await _cleanup(database)
        await _seed(database)
        for sequence, stage in enumerate(PIPELINE_STATUSES[:-1], start=1):
            build_id = UUID(int=18_100 + sequence)
            async with database.session_scope() as session:
                session.add(_build(build_id, sequence, stage))
                await session.flush()
                await repository.fail(
                    session,
                    build_id,
                    error_code=f"FAIL_{stage.value}",
                    error_summary=f"Injected failure during {stage.value}",
                )
                failed = await repository.get(session, build_id)
                assert failed is not None
                assert failed.status is BuildStatus.FAILED
                assert failed.pipeline_stage is stage
    finally:
        await _cleanup(database)
        await database.close()


async def test_monotonic_transition_persists_the_new_current_stage() -> None:
    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    repository = BuildRepository()
    build_id = UUID(int=18_200)
    try:
        await _cleanup(database)
        await _seed(database)
        async with database.session_scope() as session:
            session.add(_build(build_id, 1, BuildStatus.QUEUED))
        for current, target in zip(PIPELINE_STATUSES, PIPELINE_STATUSES[1:-1], strict=False):
            async with database.session_scope() as session:
                transitioned = await repository.transition(
                    session,
                    build_id,
                    expected=current,
                    target=target,
                )
                assert transitioned.status is target
                assert transitioned.pipeline_stage is target
    finally:
        await _cleanup(database)
        await database.close()
