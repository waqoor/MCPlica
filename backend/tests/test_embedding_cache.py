import hashlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.clients.storage import StoredObject
from app.domain.builds import BuildConfiguration
from app.domain.indexing import (
    CachedEmbeddingRecord,
    DocumentIndexGenerationRecord,
    IndexGenerationStatus,
)
from app.domain.sources import (
    BoundSourceVersionRecord,
    ProjectSourceRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionRecord,
)
from app.parsers.documentation import DocumentChunk
from app.parsers.openapi.parser import parse_openapi
from app.providers.ai.base import AIProvider, EmbeddingBatch
from app.providers.vector import VectorStore
from app.repositories.indexing import IndexGenerationRepository
from app.services.indexing import service as indexing_service_module
from app.services.indexing.service import IndexingService


def _config() -> BuildConfiguration:
    return BuildConfiguration(
        include_documentation_in_analysis=True,
        max_operations=1_000,
        max_context_chars=120_000,
        max_ai_concurrency=4,
        retrieval_top_k=5,
        source_max_bytes=1_000_000,
        document_max_bytes=1_000_000,
        document_max_text_chars=100_000,
        pdf_max_pages=100,
        documentation_chunk_chars=2_000,
        documentation_chunk_overlap_chars=200,
        max_document_chunks=1_000,
        embedding_batch_size=32,
        max_embedding_concurrency=4,
        runtime_timeout_ms=30_000,
        runtime_max_request_bytes=10_000,
        runtime_max_response_bytes=10_000,
        runtime_manifest_max_bytes=10_000,
        artifact_max_bytes=1_000_000,
    )


def _chunk(*, project_id: UUID, generation_id: UUID, text: str, ordinal: int) -> DocumentChunk:
    content_sha256 = hashlib.sha256(text.encode()).hexdigest()
    identity = hashlib.sha256(f"{generation_id}:{ordinal}:{content_sha256}".encode()).hexdigest()
    return DocumentChunk(
        chunk_id=f"chunk_{identity}",
        project_id=project_id,
        generation_id=generation_id,
        source_version_id=UUID(int=100 + ordinal),
        title="Documentation",
        section_path=["Documentation"],
        text=text,
        content_sha256=content_sha256,
    )


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[object]:
        yield object()


class _CacheRepository:
    def __init__(self) -> None:
        self.values: dict[tuple[UUID, str, str], CachedEmbeddingRecord] = {}
        self.lookups: list[tuple[UUID, str, list[str]]] = []

    async def list_cached_embeddings(
        self,
        _session: object,
        *,
        project_id: UUID,
        model_identity: str,
        content_sha256s: list[str],
    ) -> list[CachedEmbeddingRecord]:
        self.lookups.append((project_id, model_identity, content_sha256s))
        return [
            self.values[(project_id, model_identity, content_sha256)]
            for content_sha256 in content_sha256s
            if (project_id, model_identity, content_sha256) in self.values
        ]

    async def upsert_cached_embeddings(
        self,
        _session: object,
        *,
        project_id: UUID,
        model_identity: str,
        resolved_model: str,
        dimensions: int,
        vectors_by_sha256: dict[str, list[float]],
    ) -> None:
        now = datetime.now(UTC)
        for content_sha256, vector in vectors_by_sha256.items():
            self.values[(project_id, model_identity, content_sha256)] = CachedEmbeddingRecord(
                id=uuid4(),
                project_id=project_id,
                model_identity=model_identity,
                content_sha256=content_sha256,
                resolved_model=resolved_model,
                dimensions=dimensions,
                vector=vector,
                created_at=now,
                last_used_at=now,
            )


class _AI(AIProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.resolved_suffix = "stable"

    async def embed(self, *, model: str, texts: list[str]) -> EmbeddingBatch:
        self.calls.append((model, texts))
        return EmbeddingBatch(
            vectors=[[float(len(text)), float(sum(text.encode()) % 997)] for text in texts],
            model=f"{model}:{self.resolved_suffix}",
            dimensions=2,
            usage=None,
        )

    async def structured_generate(self, **_kwargs: Any) -> Any:
        raise AssertionError("structured generation is not used for embedding resolution")

    async def list_models(self) -> list[Any]:
        return []


def _service(repository: _CacheRepository, ai: _AI) -> IndexingService:
    return IndexingService(
        cast(Any, _Database()),
        cast(Any, object()),
        cast(IndexGenerationRepository, repository),
        cast(Any, object()),
        ai,
        cast(Any, object()),
    )


async def test_embedding_cache_reuses_only_same_project_model_and_normalized_content() -> None:
    repository = _CacheRepository()
    ai = _AI()
    service = _service(repository, ai)
    project_a = UUID(int=1)
    project_b = UUID(int=2)
    first = _chunk(project_id=project_a, generation_id=UUID(int=10), text="same", ordinal=1)
    duplicate = _chunk(
        project_id=project_a,
        generation_id=UUID(int=10),
        text="same",
        ordinal=2,
    )

    vectors, resolved, dimensions = await service._resolve_embeddings(
        [first, duplicate],
        "embed/v1",
        project_id=project_a,
        config=_config(),
        cancellation_check=None,
    )
    assert len(ai.calls) == 1
    assert ai.calls[0] == ("embed/v1", ["same"])
    assert vectors[0] == vectors[1]
    assert resolved == "embed/v1:stable"
    assert dimensions == 2

    rebuilt = _chunk(
        project_id=project_a,
        generation_id=UUID(int=11),
        text="same",
        ordinal=1,
    )
    await service._resolve_embeddings(
        [rebuilt],
        "embed/v1",
        project_id=project_a,
        config=_config(),
        cancellation_check=None,
    )
    assert len(ai.calls) == 1

    other_project = _chunk(
        project_id=project_b,
        generation_id=UUID(int=12),
        text="same",
        ordinal=1,
    )
    await service._resolve_embeddings(
        [other_project],
        "embed/v1",
        project_id=project_b,
        config=_config(),
        cancellation_check=None,
    )
    assert len(ai.calls) == 2

    changed_content = _chunk(
        project_id=project_a,
        generation_id=UUID(int=13),
        text="changed",
        ordinal=1,
    )
    await service._resolve_embeddings(
        [changed_content],
        "embed/v1",
        project_id=project_a,
        config=_config(),
        cancellation_check=None,
    )
    assert len(ai.calls) == 3

    await service._resolve_embeddings(
        [rebuilt],
        "embed/v2",
        project_id=project_a,
        config=_config(),
        cancellation_check=None,
    )
    assert len(ai.calls) == 4
    assert all(
        lookup_project in {project_a, project_b} and lookup_model in {"embed/v1", "embed/v2"}
        for lookup_project, lookup_model, _hashes in repository.lookups
    )


async def test_embedding_cache_refreshes_all_vectors_when_resolved_model_drifts() -> None:
    repository = _CacheRepository()
    ai = _AI()
    service = _service(repository, ai)
    project_id = UUID(int=1)
    first = _chunk(project_id=project_id, generation_id=UUID(int=20), text="first", ordinal=1)
    await service._resolve_embeddings(
        [first],
        "embed/alias",
        project_id=project_id,
        config=_config(),
        cancellation_check=None,
    )

    ai.resolved_suffix = "replacement"
    second = _chunk(
        project_id=project_id,
        generation_id=UUID(int=21),
        text="second",
        ordinal=2,
    )
    _vectors, resolved, dimensions = await service._resolve_embeddings(
        [first.model_copy(update={"generation_id": UUID(int=21)}), second],
        "embed/alias",
        project_id=project_id,
        config=_config(),
        cancellation_check=None,
    )
    assert ai.calls[-2:] == [
        ("embed/alias", ["second"]),
        ("embed/alias", ["first", "second"]),
    ]
    assert resolved == "embed/alias:replacement"
    assert dimensions == 2
    assert {
        record.resolved_model
        for key, record in repository.values.items()
        if key[0] == project_id and key[1] == "embed/alias"
    } == {"embed/alias:replacement"}


class _GenerationRepository(_CacheRepository):
    def __init__(self) -> None:
        super().__init__()
        self.completed_embedding_models: list[str | None] = []

    async def prepare(
        self,
        _session: object,
        *,
        generation_id: UUID,
        project_id: UUID,
        build_id: UUID,
        embedding_model: str | None,
        generation_key: str,
        source_fingerprint: str,
        admission_token: UUID,
    ) -> DocumentIndexGenerationRecord:
        return DocumentIndexGenerationRecord(
            id=generation_id,
            project_id=project_id,
            build_id=build_id,
            embedding_model=embedding_model,
            dimensions=None,
            collection_name=None,
            generation_key=generation_key,
            chunk_count=0,
            chunk_manifest_storage_key=None,
            chunk_manifest_sha256=None,
            source_fingerprint=source_fingerprint,
            status=IndexGenerationStatus.BUILDING,
            error_summary=None,
            created_at=datetime.now(UTC),
            completed_at=None,
        )

    async def complete(
        self,
        _session: object,
        generation_id: UUID,
        *,
        embedding_model: str | None,
        dimensions: int,
        collection_name: str | None,
        chunk_count: int,
        chunk_manifest_storage_key: str | None,
        chunk_manifest_sha256: str | None,
        build_id: UUID,
        admission_token: UUID,
    ) -> DocumentIndexGenerationRecord:
        self.completed_embedding_models.append(embedding_model)
        return DocumentIndexGenerationRecord(
            id=generation_id,
            project_id=UUID(int=0),
            build_id=build_id,
            embedding_model=embedding_model,
            dimensions=dimensions,
            collection_name=collection_name,
            generation_key="unused",
            chunk_count=chunk_count,
            chunk_manifest_storage_key=chunk_manifest_storage_key,
            chunk_manifest_sha256=chunk_manifest_sha256,
            source_fingerprint="a" * 64,
            status=IndexGenerationStatus.READY,
            error_summary=None,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )


class _Storage:
    async def put_bytes(self, _namespace: str, value: bytes, *, max_bytes: int) -> StoredObject:
        return StoredObject(
            storage_key="build-index-chunks/stub",
            content_sha256=hashlib.sha256(value).hexdigest(),
            byte_size=len(value),
            created=True,
        )


class _VectorStore(VectorStore):
    def collection_name(self, dimensions: int) -> str:
        return f"collection_{dimensions}"

    async def ensure_index(self, *, collection: str, dimensions: int) -> None:
        return None

    async def upsert_chunks(
        self,
        *,
        collection: str,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        execution_token: UUID,
    ) -> None:
        return None

    async def search(
        self,
        *,
        collection: str,
        project_id: UUID,
        generation_id: UUID,
        execution_token: UUID | None = None,
        vector: list[float],
        limit: int,
        include_documentation: bool = True,
    ) -> list[Any]:
        return []

    async def delete_generation(
        self,
        *,
        collection: str,
        project_id: UUID,
        generation_id: UUID,
        execution_token: UUID | None = None,
    ) -> None:
        return None


def _openapi_canonical(source_version_id: UUID, project_id: UUID) -> Any:
    document = {
        "openapi": "3.0.3",
        "info": {"title": "Widgets", "version": "1"},
        "servers": [{"url": "https://widgets.example.com"}],
        "paths": {
            "/widgets": {
                "get": {
                    "operationId": "listWidgets",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    return parse_openapi(
        document,
        project_id=project_id,
        source_version_id=source_version_id,
        content_sha256=hashlib.sha256(b"widgets").hexdigest(),
    )


async def test_index_persists_the_configured_embedding_model_not_the_provider_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        indexing_service_module,
        "require_build_execution_owner",
        _no_op_require_build_execution_owner,
    )
    project_id = uuid4()
    build_id = uuid4()
    source_id = uuid4()
    source_version_id = uuid4()
    canonical = _openapi_canonical(source_version_id, project_id)
    source_bindings = [
        BoundSourceVersionRecord(
            source=ProjectSourceRecord(
                id=source_id,
                project_id=project_id,
                kind=SourceKind.OPENAPI,
                name="Primary API specification",
                origin_type=SourceOrigin.UPLOAD,
                source_url=None,
                is_primary=True,
                created_at=datetime.now(UTC),
                current_version_id=source_version_id,
            ),
            version=SourceVersionRecord(
                id=source_version_id,
                source_id=source_id,
                content_sha256=hashlib.sha256(b"widgets").hexdigest(),
                media_type="application/json",
                storage_key="sources/widgets.json",
                byte_size=100,
                detected_format="openapi-3.0",
                source_etag=None,
                source_last_modified=None,
                created_by=uuid4(),
                created_at=datetime.now(UTC),
            ),
        )
    ]
    repository = _GenerationRepository()
    ai = _AI()
    service = IndexingService(
        cast(Any, _Database()),
        cast(Any, object()),
        cast(IndexGenerationRepository, repository),
        cast(Any, _Storage()),
        ai,
        cast(Any, _VectorStore()),
    )

    result = await service.index(
        project_id=project_id,
        build_id=build_id,
        source_bindings=source_bindings,
        canonical=canonical,
        embedding_model="nvidia/nemotron-3-embed-1b:free",
        config=_config(),
        admission_token=uuid4(),
    )

    assert any(call[0] == "nvidia/nemotron-3-embed-1b:free" for call in ai.calls)
    assert repository.completed_embedding_models == ["nvidia/nemotron-3-embed-1b:free"]
    assert result.embedding_model == "nvidia/nemotron-3-embed-1b:free"


async def _no_op_require_build_execution_owner(
    _session: object,
    *,
    build_id: UUID,
    admission_token: UUID,
) -> None:
    return None
