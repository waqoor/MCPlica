import asyncio
from datetime import UTC, datetime
from itertools import pairwise
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import (
    AIAnalysisError,
    ClientUnavailableError,
    CompilationError,
    InvalidStateError,
)
from app.domain.builds import (
    PIPELINE_STATUSES,
    BuildConfiguration,
    BuildRecord,
    BuildStatus,
    BuildTrigger,
    next_status,
)
from app.jobs.build import is_retryable_build_error
from app.services.analysis import AnalysisService
from app.services.builds.pipeline import BuildCancellationRequested, BuildPipeline


def test_build_state_machine_is_adjacent_and_terminal() -> None:
    for current, target in pairwise(PIPELINE_STATUSES):
        assert next_status(current) is target
    for terminal in (BuildStatus.READY, BuildStatus.FAILED, BuildStatus.CANCELLED):
        with pytest.raises(ValueError, match="terminal"):
            next_status(terminal)


def test_build_worker_retries_only_transient_provider_failures() -> None:
    assert is_retryable_build_error(ClientUnavailableError("temporary"))
    assert not is_retryable_build_error(AIAnalysisError("invalid structured output"))
    assert not is_retryable_build_error(CompilationError("invalid deterministic mapping"))


def test_frozen_build_configuration_rejects_invalid_chunk_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        BuildConfiguration(
            inbound_auth_mode="static_bearer",
            include_documentation_in_analysis=True,
            max_operations=1_000,
            max_context_chars=120_000,
            max_ai_concurrency=4,
            retrieval_top_k=5,
            source_max_bytes=1_000,
            document_max_bytes=1_000,
            document_max_text_chars=10_000,
            pdf_max_pages=10,
            documentation_chunk_chars=500,
            documentation_chunk_overlap_chars=500,
            max_document_chunks=100,
            embedding_batch_size=32,
            max_embedding_concurrency=4,
            runtime_timeout_ms=30_000,
            runtime_max_request_bytes=10_000,
            runtime_max_response_bytes=10_000,
            runtime_manifest_max_bytes=10_000,
            artifact_max_bytes=100_000,
        )


async def test_pipeline_observes_concurrent_cancellation_as_a_clean_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    queued = BuildRecord(
        id=uuid4(),
        project_id=uuid4(),
        sequence=1,
        status=BuildStatus.QUEUED,
        trigger=BuildTrigger.INITIAL,
        canonical_snapshot_id=None,
        previous_build_id=None,
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
        requested_by=uuid4(),
        created_at=now,
        started_at=None,
        completed_at=None,
    )
    cancelled = queued.model_copy(
        update={
            "status": BuildStatus.CANCELLED,
            "completed_at": now,
            "cancellation_requested_at": now,
            "cancellation_requested_by": queued.requested_by,
            "cancellation_acknowledged_at": now,
        }
    )
    dependency = cast(Any, object())
    pipeline = BuildPipeline(
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
    )
    monkeypatch.setattr(pipeline, "_get", AsyncMock(side_effect=[queued, cancelled]))
    monkeypatch.setattr(pipeline, "_cancellation_checkpoint", AsyncMock())
    monkeypatch.setattr(
        pipeline,
        "_transition",
        AsyncMock(side_effect=InvalidStateError("concurrent transition")),
    )

    assert await pipeline.run(queued.id) == cancelled


@pytest.mark.parametrize("status", PIPELINE_STATUSES[:-1])
async def test_pipeline_acknowledges_cancellation_before_every_stage_boundary(
    monkeypatch: pytest.MonkeyPatch,
    status: BuildStatus,
) -> None:
    now = datetime.now(UTC)
    requested_by = uuid4()
    build = BuildRecord(
        id=uuid4(),
        project_id=uuid4(),
        sequence=1,
        status=status,
        trigger=BuildTrigger.INITIAL,
        canonical_snapshot_id=None,
        previous_build_id=None,
        compiler_version="1.0.0",
        manifest_schema_version="mcp-manifest/v1",
        runtime_compatibility=">=1,<2",
        analysis_model="analysis/model",
        validation_model="validation/model",
        embedding_model="embedding/model",
        embedding_dimensions=None,
        prompt_bundle_version="1.0.0",
        enrichment_sha256=None,
        manifest_sha256=None,
        artifact_sha256=None,
        manifest_storage_key=None,
        artifact_storage_key=None,
        error_code=None,
        error_summary=None,
        requested_by=requested_by,
        created_at=now,
        started_at=now if status is not BuildStatus.QUEUED else None,
        completed_at=None,
        cancellation_requested_at=now,
        cancellation_requested_by=requested_by,
    )
    cancelled = build.model_copy(
        update={
            "status": BuildStatus.CANCELLED,
            "completed_at": now,
            "cancellation_acknowledged_at": now,
        }
    )
    dependency = cast(Any, object())
    pipeline = BuildPipeline(
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
        dependency,
    )
    checkpoint = AsyncMock(side_effect=BuildCancellationRequested)
    acknowledge = AsyncMock(return_value=cancelled)
    monkeypatch.setattr(pipeline, "_get", AsyncMock(return_value=build))
    monkeypatch.setattr(pipeline, "_cancellation_checkpoint", checkpoint)
    monkeypatch.setattr(pipeline, "_acknowledge_cancellation", acknowledge)

    assert await pipeline.run(build.id) == cancelled
    checkpoint.assert_awaited_once_with(build.id)
    acknowledge.assert_awaited_once_with(build.id)


async def test_analysis_cancellation_stops_all_concurrent_operation_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = cast(Any, object())
    service = AnalysisService(dependency, dependency, dependency, dependency)
    operations = [SimpleNamespace(key=f"operation-{index}") for index in range(4)]
    all_started = asyncio.Event()
    started = 0
    cancelled_siblings = 0

    async def analyze_operation(**kwargs: Any) -> None:
        nonlocal started, cancelled_siblings
        operation = kwargs["operation"]
        started += 1
        if started == len(operations):
            all_started.set()
        await all_started.wait()
        if operation.key == "operation-0":
            raise BuildCancellationRequested
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled_siblings += 1
            raise

    monkeypatch.setattr(service, "_analyze_operation", analyze_operation)

    with pytest.raises(BuildCancellationRequested):
        await service.analyze(
            build_id=uuid4(),
            canonical=cast(Any, SimpleNamespace(operations=operations)),
            generation=dependency,
            model="analysis/model",
            include_documentation=False,
            max_context_chars=20_000,
            max_concurrency=4,
            retrieval_top_k=5,
            cancellation_check=AsyncMock(),
        )

    assert started == 4
    assert cancelled_siblings == 3
