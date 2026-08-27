import hashlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from mcp_contracts import CanonicalApi, SemanticProvenance

from app.domain.analysis import EnrichmentSnapshot, OperationEnrichment
from app.domain.builds import BuildConfiguration, BuildRecord, BuildStatus, BuildTrigger
from app.domain.indexing import DocumentIndexGenerationRecord, IndexGenerationStatus
from app.parsers.openapi.parser import parse_openapi
from app.prompts import OPERATION_ENRICHMENT_PROMPT
from app.services.analysis.reuse import select_reusable_enrichment
from app.services.analysis.service import AnalysisService


def _canonical(summary: str = "List products") -> CanonicalApi:
    return parse_openapi(
        {
            "openapi": "3.1.0",
            "info": {"title": "Products", "version": "1.0"},
            "servers": [{"url": "https://products.example.com"}],
            "paths": {
                "/products": {
                    "get": {
                        "operationId": "listProducts",
                        "summary": summary,
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        },
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(summary.encode()).hexdigest(),
    )


def _config(*, include_documentation: bool = False) -> BuildConfiguration:
    return BuildConfiguration(
        inbound_auth_mode="static_bearer",
        include_documentation_in_analysis=include_documentation,
        max_operations=1_000,
        max_context_chars=120_000,
        max_ai_concurrency=4,
        retrieval_top_k=5,
        source_max_bytes=1_000,
        document_max_bytes=1_000,
        document_max_text_chars=100_000,
        pdf_max_pages=100,
        documentation_chunk_chars=6_000,
        documentation_chunk_overlap_chars=500,
        max_document_chunks=1_000,
        embedding_batch_size=32,
        max_embedding_concurrency=4,
        runtime_timeout_ms=30_000,
        runtime_max_request_bytes=10_000,
        runtime_max_response_bytes=10_000,
        runtime_manifest_max_bytes=10_000,
        artifact_max_bytes=100_000,
    )


def _build(
    build_id: int,
    *,
    status: BuildStatus,
    trigger: BuildTrigger,
    previous_build_id: UUID | None,
) -> BuildRecord:
    now = datetime(2026, 8, 26, tzinfo=UTC)
    return BuildRecord(
        id=UUID(int=build_id),
        project_id=UUID(int=1),
        sequence=build_id,
        status=status,
        trigger=trigger,
        canonical_snapshot_id=UUID(int=100 + build_id),
        previous_build_id=previous_build_id,
        compiler_version="1.0.0",
        manifest_schema_version="mcp-manifest/v1",
        runtime_compatibility=">=1,<2",
        analysis_model="analysis/model",
        validation_model="validation/model",
        embedding_model=None,
        embedding_dimensions=0,
        prompt_bundle_version="1.0.0",
        enrichment_sha256=None,
        manifest_sha256=None,
        artifact_sha256=None,
        manifest_storage_key=None,
        artifact_storage_key=None,
        error_code=None,
        error_summary=None,
        requested_by=UUID(int=9),
        created_at=now,
        started_at=now,
        completed_at=now if status is BuildStatus.READY else None,
    )


def _generation(build_id: int, fingerprint: str = "a" * 64) -> DocumentIndexGenerationRecord:
    now = datetime(2026, 8, 26, tzinfo=UTC)
    return DocumentIndexGenerationRecord(
        id=UUID(int=200 + build_id),
        project_id=UUID(int=1),
        build_id=UUID(int=build_id),
        embedding_model=None,
        dimensions=0,
        collection_name=None,
        generation_key="b" * 64,
        chunk_count=0,
        chunk_manifest_storage_key="build-index-chunks/example",
        chunk_manifest_sha256="c" * 64,
        source_fingerprint=fingerprint,
        status=IndexGenerationStatus.READY,
        error_summary=None,
        created_at=now,
        completed_at=now,
    )


def _enrichment(operation_key: str) -> OperationEnrichment:
    return OperationEnrichment(
        operation_key=operation_key,
        title="List products",
        description="List the available products.",
        category="products",
        keywords=["products"],
        documentation_chunk_ids=[],
        relationship_hints=[],
        confidence=0.9,
        warnings=[],
        provenance=SemanticProvenance(
            provider="openrouter",
            model="analysis/model",
            prompt_template_id=OPERATION_ENRICHMENT_PROMPT.id,
            prompt_template_version=OPERATION_ENRICHMENT_PROMPT.version,
            context_sha256="d" * 64,
            retrieved_chunk_ids=[],
        ),
    )


def test_reuse_policy_is_conservative_and_manual_builds_force_analysis() -> None:
    previous_canonical = _canonical()
    current_canonical = _canonical()
    operation_key = current_canonical.operations[0].key
    previous = _build(
        20,
        status=BuildStatus.READY,
        trigger=BuildTrigger.INITIAL,
        previous_build_id=None,
    )
    current = _build(
        21,
        status=BuildStatus.ANALYZING,
        trigger=BuildTrigger.SOURCE_CHANGE,
        previous_build_id=previous.id,
    )
    enrichment = EnrichmentSnapshot(operations={operation_key: _enrichment(operation_key)})

    def select(
        *,
        current_build: BuildRecord = current,
        selected_canonical: CanonicalApi = current_canonical,
    ) -> dict[str, OperationEnrichment]:
        return select_reusable_enrichment(
            current_build=current_build,
            previous_build=previous,
            current_canonical=selected_canonical,
            previous_canonical=previous_canonical,
            current_generation=_generation(21),
            previous_generation=_generation(20),
            current_config=_config(),
            previous_config=_config(),
            previous_enrichment=enrichment,
            prompt_template_id=OPERATION_ENRICHMENT_PROMPT.id,
            prompt_template_version=OPERATION_ENRICHMENT_PROMPT.version,
        )

    assert select() == enrichment.operations

    manual = current.model_copy(update={"trigger": BuildTrigger.MANUAL_REVIEW})
    assert select(current_build=manual) == {}
    changed = _canonical("Delete all products")
    assert select(selected_canonical=changed) == {}


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[object]:
        yield object()


class _Runs:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    async def get_by_run_key(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def create(self, *_args: object, **kwargs: object) -> None:
        self.created.append(kwargs)


class _MustNotRun:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"unexpected external analysis call: {name}")


async def test_reused_enrichment_is_audited_without_calling_ai_or_retrieval() -> None:
    canonical = _canonical()
    operation_key = canonical.operations[0].key
    runs = _Runs()
    service = AnalysisService(
        cast(Any, _Database()),
        cast(Any, _MustNotRun()),
        cast(Any, _MustNotRun()),
        cast(Any, runs),
    )
    result = await service.analyze(
        build_id=UUID(int=21),
        canonical=canonical,
        generation=_generation(21),
        model="analysis/model",
        include_documentation=False,
        max_context_chars=120_000,
        max_concurrency=4,
        retrieval_top_k=5,
        reusable={operation_key: _enrichment(operation_key)},
    )
    assert result.operations[operation_key].title == "List products"
    assert len(runs.created) == 1
    assert runs.created[0]["stage"] == "analysis_reuse"
    assert runs.created[0]["status"] == "succeeded"
    assert runs.created[0]["usage"] is None
