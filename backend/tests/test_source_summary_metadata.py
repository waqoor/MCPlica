import hashlib
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.core.canonical_json import canonical_json_bytes
from app.domain.builds import BuildConfiguration, BuildRecord, BuildStatus, BuildTrigger
from app.domain.canonicalization import CanonicalSnapshotRecord
from app.domain.indexing import DocumentIndexGenerationRecord, IndexGenerationStatus
from app.domain.sources import (
    ProjectSourceRecord,
    SourceKind,
    SourceOrigin,
    SourceSummaryRecord,
    SourceVersionRecord,
)
from app.parsers.documentation import DocumentChunk
from app.parsers.openapi.parser import parse_openapi
from app.services.sources import SourceService

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PROJECT_ID = UUID(int=1)
USER_ID = UUID(int=2)
BUILD_ID = UUID(int=3)
SNAPSHOT_ID = UUID(int=4)
GENERATION_ID = UUID(int=5)
EXECUTABLE_SOURCE_ID = UUID(int=10)
EXECUTABLE_VERSION_ID = UUID(int=11)
DOCUMENT_SOURCE_IDS = (UUID(int=20), UUID(int=30))
DOCUMENT_VERSION_IDS = (UUID(int=21), UUID(int=31))


class _Storage:
    def __init__(self, manifest: bytes) -> None:
        self.manifest = manifest
        self.reads: list[tuple[str, int | None]] = []

    async def get(self, storage_key: str, *, max_bytes: int | None = None) -> bytes:
        self.reads.append((storage_key, max_bytes))
        return self.manifest


def _configuration() -> BuildConfiguration:
    return BuildConfiguration(
        include_documentation_in_analysis=True,
        max_operations=100,
        max_context_chars=10_000,
        max_ai_concurrency=2,
        retrieval_top_k=5,
        source_max_bytes=10_000,
        document_max_bytes=10_000,
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
    )


def _build() -> BuildRecord:
    return BuildRecord(
        id=BUILD_ID,
        project_id=PROJECT_ID,
        sequence=1,
        status=BuildStatus.READY,
        trigger=BuildTrigger.MANUAL_REBUILD,
        canonical_snapshot_id=SNAPSHOT_ID,
        previous_build_id=None,
        compiler_version="1.0.0",
        manifest_schema_version="mcp-manifest/v1",
        runtime_compatibility=">=1,<2",
        analysis_model="analysis/model",
        validation_model="validation/model",
        embedding_model="embedding/model",
        embedding_dimensions=3,
        prompt_bundle_version="1.0.0",
        enrichment_sha256=None,
        manifest_sha256=None,
        artifact_sha256=None,
        manifest_storage_key=None,
        artifact_storage_key=None,
        error_code=None,
        error_summary=None,
        requested_by=USER_ID,
        created_at=NOW,
        started_at=NOW,
        completed_at=NOW,
    )


def _snapshot() -> CanonicalSnapshotRecord:
    canonical = parse_openapi(
        {
            "openapi": "3.1.0",
            "info": {"title": "Pets", "version": "1.0"},
            "servers": [{"url": "https://api.example.test"}],
            "paths": {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        },
        project_id=PROJECT_ID,
        source_version_id=EXECUTABLE_VERSION_ID,
        content_sha256="a" * 64,
    )
    return CanonicalSnapshotRecord(
        id=SNAPSHOT_ID,
        project_id=PROJECT_ID,
        schema_version=canonical.schema_version,
        canonical_sha256="b" * 64,
        canonical=canonical,
        source_version_ids=[EXECUTABLE_VERSION_ID],
        created_at=NOW,
    )


def _source_summary(
    source_id: UUID,
    version_id: UUID,
    *,
    kind: SourceKind,
) -> SourceSummaryRecord:
    return SourceSummaryRecord(
        source=ProjectSourceRecord(
            id=source_id,
            project_id=PROJECT_ID,
            kind=kind,
            name=f"Source {source_id.int}",
            origin_type=SourceOrigin.UPLOAD,
            source_url=None,
            is_primary=kind is not SourceKind.DOCUMENTATION,
            created_at=NOW,
        ),
        latest_version=SourceVersionRecord(
            id=version_id,
            source_id=source_id,
            content_sha256=f"{version_id.int:064x}",
            media_type="application/json" if kind is not SourceKind.DOCUMENTATION else "text/plain",
            storage_key=f"sources/{version_id}",
            byte_size=100,
            detected_format="openapi" if kind is not SourceKind.DOCUMENTATION else "text",
            source_etag=None,
            source_last_modified=None,
            created_by=USER_ID,
            created_at=NOW,
        ),
        version_count=1,
        health="valid",
        metadata_build_id=BUILD_ID,
    )


def _chunk(source_version_id: UUID, ordinal: int) -> DocumentChunk:
    text = f"Documentation chunk {ordinal}"
    content_sha256 = hashlib.sha256(text.encode()).hexdigest()
    chunk_id = hashlib.sha256(f"{source_version_id}:{ordinal}".encode()).hexdigest()
    return DocumentChunk(
        chunk_id=f"chunk_{chunk_id}",
        project_id=PROJECT_ID,
        generation_id=GENERATION_ID,
        source_version_id=source_version_id,
        title="Documentation",
        section_path=["Documentation"],
        text=text,
        content_sha256=content_sha256,
    )


@pytest.mark.asyncio
async def test_source_summary_metadata_is_exact_and_reads_shared_manifest_once() -> None:
    chunks = [
        _chunk(DOCUMENT_VERSION_IDS[0], 1),
        _chunk(DOCUMENT_VERSION_IDS[0], 2),
        _chunk(DOCUMENT_VERSION_IDS[1], 3),
    ]
    manifest = canonical_json_bytes([chunk.model_dump(mode="json") for chunk in chunks])
    storage = _Storage(manifest)
    service = object.__new__(SourceService)
    service._storage = storage
    generation = DocumentIndexGenerationRecord(
        id=GENERATION_ID,
        project_id=PROJECT_ID,
        build_id=BUILD_ID,
        embedding_model="embedding/model",
        dimensions=3,
        collection_name="project_test",
        generation_key="c" * 64,
        chunk_count=3,
        chunk_manifest_storage_key="indexes/chunks.json",
        chunk_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        source_fingerprint="d" * 64,
        status=IndexGenerationStatus.READY,
        error_summary=None,
        created_at=NOW,
        completed_at=NOW,
    )
    items = [
        _source_summary(
            EXECUTABLE_SOURCE_ID,
            EXECUTABLE_VERSION_ID,
            kind=SourceKind.OPENAPI,
        ),
        _source_summary(
            DOCUMENT_SOURCE_IDS[0],
            DOCUMENT_VERSION_IDS[0],
            kind=SourceKind.DOCUMENTATION,
        ),
        _source_summary(
            DOCUMENT_SOURCE_IDS[1],
            DOCUMENT_VERSION_IDS[1],
            kind=SourceKind.DOCUMENTATION,
        ),
    ]

    enriched = await service._enrich_summary_metadata(
        items,
        build_contexts={BUILD_ID: (_build(), _configuration())},
        snapshots={SNAPSHOT_ID: _snapshot()},
        generations={BUILD_ID: generation},
    )

    assert enriched[0].operation_count == 1
    assert enriched[0].indexed_chunk_count is None
    assert enriched[1].indexed_chunk_count == 2
    assert enriched[2].indexed_chunk_count == 1
    assert {item.metadata_build_id for item in enriched} == {BUILD_ID}
    assert {item.index_generation_id for item in enriched} == {GENERATION_ID}
    assert storage.reads == [("indexes/chunks.json", 10_000)]
