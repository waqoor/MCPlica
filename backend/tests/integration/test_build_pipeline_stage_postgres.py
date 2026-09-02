import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select, update

from app.clients.database import DatabaseClient
from app.core.exceptions import InvalidStateError
from app.domain.auth import UserRole
from app.domain.builds import PIPELINE_STATUSES, BuildConfiguration, BuildStatus, BuildTrigger
from app.domain.validation import ValidationStatus
from app.models.auth import User
from app.models.build import Build, BuildAIRun
from app.models.indexing import DocumentIndexGeneration
from app.models.project import Project
from app.models.validation import ValidationReport
from app.repositories.builds import BuildAIRunRepository, BuildRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.validation import ValidationRepository

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
        admission_token=_token(build_id),
        admission_acquired_at=now,
        admission_heartbeat_at=now,
        admission_lease_expires_at=now + timedelta(minutes=5),
        admission_attempt_count=1,
    )


def _token(build_id: UUID) -> UUID:
    return UUID(int=build_id.int + 1_000)


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
                    admission_token=_token(build_id),
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
                    admission_token=_token(build_id),
                )
                assert transitioned.status is target
                assert transitioned.pipeline_stage is target
    finally:
        await _cleanup(database)
        await database.close()


async def test_reclaimed_build_rejects_every_stale_result_writer() -> None:
    """ISS-002-008: an obsolete owner cannot publish any pipeline evidence."""

    database = DatabaseClient(_database_url(), pool_size=4, max_overflow=0)
    build_id = UUID(int=18_300)
    stale_token = _token(build_id)
    current_token = UUID(int=19_301)
    ai_runs = BuildAIRunRepository()
    generations = IndexGenerationRepository()
    validations = ValidationRepository()
    try:
        await _cleanup(database)
        await _seed(database)
        async with database.session_scope() as session:
            session.add(_build(build_id, 1, BuildStatus.ANALYZING))
        async with database.session_scope() as session:
            await session.execute(
                update(Build)
                .where(Build.id == build_id)
                .values(admission_token=current_token, admission_attempt_count=2)
            )

        async with database.session_scope() as session:
            with pytest.raises(InvalidStateError, match="ownership is stale"):
                await ai_runs.create(
                    session,
                    build_id=build_id,
                    run_key="stale-analysis",
                    stage="analysis",
                    operation_key=None,
                    model="analysis/model",
                    prompt_template_id="analysis",
                    prompt_template_version="1",
                    input_context_sha256="1" * 64,
                    retrieved_chunk_ids=[],
                    response_schema_id="analysis/v1",
                    response_sha256="2" * 64,
                    response_json={"accepted": True},
                    usage=None,
                    cost=None,
                    latency_ms=1,
                    status="succeeded",
                    admission_token=stale_token,
                )
        async with database.session_scope() as session:
            with pytest.raises(InvalidStateError, match="ownership is stale"):
                await generations.prepare(
                    session,
                    generation_id=UUID(int=18_302),
                    project_id=PROJECT_ID,
                    build_id=build_id,
                    embedding_model="embedding/model",
                    generation_key="3" * 64,
                    source_fingerprint="4" * 64,
                    admission_token=stale_token,
                )
        async with database.session_scope() as session:
            with pytest.raises(InvalidStateError, match="ownership is stale"):
                await validations.create_report(
                    session,
                    build_id=build_id,
                    overall_status=ValidationStatus.PASS,
                    operation_source_count=0,
                    operation_excluded_count=0,
                    operation_expected_count=0,
                    operation_generated_count=0,
                    coverage_percent=100,
                    blocking_error_count=0,
                    warning_count=0,
                    findings=[],
                    admission_token=stale_token,
                )

        async with database.session_scope() as session:
            assert (
                await session.scalar(
                    select(func.count(BuildAIRun.id)).where(BuildAIRun.build_id == build_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count(DocumentIndexGeneration.id)).where(
                        DocumentIndexGeneration.build_id == build_id
                    )
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count(ValidationReport.id)).where(
                        ValidationReport.build_id == build_id
                    )
                )
                == 0
            )

        async with database.session_scope() as session:
            accepted = await ai_runs.create(
                session,
                build_id=build_id,
                run_key="current-analysis",
                stage="analysis",
                operation_key=None,
                model="analysis/model",
                prompt_template_id="analysis",
                prompt_template_version="1",
                input_context_sha256="5" * 64,
                retrieved_chunk_ids=[],
                response_schema_id="analysis/v1",
                response_sha256="6" * 64,
                response_json={"accepted": True},
                usage=None,
                cost=None,
                latency_ms=1,
                status="succeeded",
                admission_token=current_token,
            )
            assert accepted.run_key == "current-analysis"
    finally:
        await _cleanup(database)
        await database.close()
