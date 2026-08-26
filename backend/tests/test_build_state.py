from datetime import UTC, datetime
from itertools import pairwise
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
from app.services.builds.pipeline import BuildPipeline


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
    monkeypatch.setattr(
        pipeline,
        "_transition",
        AsyncMock(side_effect=InvalidStateError("concurrent transition")),
    )

    assert await pipeline.run(queued.id) == cancelled
