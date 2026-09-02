import asyncio
import hashlib
import json
import math
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import structlog
from mcp_contracts import CanonicalApi

from app.clients.database import DatabaseClient
from app.core.async_utils import bounded_map
from app.core.canonical_json import canonical_json_bytes
from app.core.exceptions import IndexingError, MCPlicaError, SourceParseError
from app.domain.builds import BuildConfiguration
from app.domain.cleanup import CleanupJobKind
from app.domain.indexing import (
    DocumentIndexGenerationRecord,
    IndexGenerationStatus,
)
from app.domain.sources import BoundSourceVersionRecord, SourceKind
from app.parsers.documentation import DocumentChunk, chunk_document, parse_document
from app.providers.ai.base import AIProvider, EmbeddingBatch
from app.providers.storage import ArtifactStorage
from app.providers.vector import VectorStore
from app.repositories.build_execution import require_build_execution_owner
from app.repositories.cleanup import CleanupRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.sources import SourceRepository

logger = structlog.get_logger(__name__)


def _documentation_fingerprint(bindings: list[BoundSourceVersionRecord]) -> str:
    digest = hashlib.sha256()
    for binding in sorted(bindings, key=lambda item: str(item.version.id)):
        digest.update(str(binding.version.id).encode())
        digest.update(b"\x00")
        digest.update(binding.version.content_sha256.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _bounded_semantic_text(value: str, max_chars: int) -> list[str]:
    if len(value) <= max_chars:
        return [value]
    parts: list[str] = []
    remaining = value
    while remaining:
        boundary = min(max_chars, len(remaining))
        if boundary < len(remaining):
            candidate = remaining.rfind("\n", 0, boundary + 1)
            if candidate < max_chars // 2:
                candidate = remaining.rfind(" ", 0, boundary + 1)
            if candidate >= max_chars // 2:
                boundary = candidate
        parts.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    return [part for part in parts if part]


def semantic_chunks(
    canonical: CanonicalApi,
    *,
    project_id: UUID,
    generation_id: UUID,
    max_chars: int,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []

    def append(
        *,
        semantic_key: str,
        source_version_id: UUID,
        source_kind: str,
        title: str,
        section_path: list[str],
        operation_keys: list[str],
        payload: object,
    ) -> None:
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        for ordinal, text in enumerate(_bounded_semantic_text(rendered, max_chars)):
            content_sha256 = hashlib.sha256(text.encode()).hexdigest()
            identity = "\x00".join(
                [
                    str(project_id),
                    str(generation_id),
                    str(source_version_id),
                    source_kind,
                    semantic_key,
                    str(ordinal),
                    content_sha256,
                ]
            )
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk_{hashlib.sha256(identity.encode()).hexdigest()}",
                    project_id=project_id,
                    generation_id=generation_id,
                    source_version_id=source_version_id,
                    source_kind=source_kind,
                    title=title,
                    section_path=[*section_path, f"Part {ordinal + 1}"],
                    operation_keys=operation_keys,
                    text=text,
                    content_sha256=content_sha256,
                )
            )

    for operation in sorted(canonical.operations, key=lambda item: item.key):
        scheme_names = sorted(
            {name for requirement in operation.security for name in requirement.scheme_scopes}
        )
        append(
            semantic_key=f"operation:{operation.key}",
            source_version_id=operation.provenance.operation.source_version_id,
            source_kind="operation_semantics",
            title=operation.summary or operation.source_operation_id or operation.key,
            section_path=["Source semantics", "Operations", operation.key],
            operation_keys=[operation.key],
            payload={
                "kind": "operation_semantics",
                "operation_key": operation.key,
                "operation_id": operation.source_operation_id,
                "method": operation.method.value,
                "path": operation.path_template,
                "summary": operation.summary,
                "description": operation.description,
                "tags": operation.tags,
                "parameters": [
                    parameter.model_dump(mode="json", by_alias=True)
                    for parameter in operation.parameters
                ],
                "request_body": (
                    operation.request_body.model_dump(mode="json", by_alias=True)
                    if operation.request_body is not None
                    else None
                ),
                "responses": [
                    response.model_dump(mode="json", by_alias=True)
                    for response in operation.responses
                ],
                "security_requirements": [
                    requirement.model_dump(mode="json") for requirement in operation.security
                ],
                "security_schemes": {
                    name: canonical.security_schemes[name].model_dump(mode="json")
                    for name in scheme_names
                    if name in canonical.security_schemes
                },
                "source_pointer": operation.provenance.operation.pointer,
            },
        )

    operation_payloads = {
        operation.key: json.dumps(
            operation.model_dump(mode="json", by_alias=True),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        for operation in canonical.operations
    }
    for schema_key, schema in sorted(canonical.schemas.items()):
        reference = f"#/components/schemas/{schema_key}"
        operation_keys = sorted(
            key for key, payload in operation_payloads.items() if reference in payload
        )
        append(
            semantic_key=f"schema:{schema_key}",
            source_version_id=schema.source_ref.source_version_id,
            source_kind="schema_semantics",
            title=schema_key,
            section_path=["Source semantics", "Schemas", schema_key],
            operation_keys=operation_keys,
            payload={
                "kind": "schema_semantics",
                "schema_key": schema_key,
                "schema": schema.schema_,
                "source_pointer": schema.source_ref.pointer,
            },
        )

    for scheme_name, scheme in sorted(canonical.security_schemes.items()):
        operation_keys = sorted(
            operation.key
            for operation in canonical.operations
            if any(scheme_name in requirement.scheme_scopes for requirement in operation.security)
        )
        append(
            semantic_key=f"security:{scheme_name}",
            source_version_id=scheme.source_ref.source_version_id,
            source_kind="security_semantics",
            title=scheme_name,
            section_path=["Source semantics", "Security", scheme_name],
            operation_keys=operation_keys,
            payload={
                "kind": "security_semantics",
                "scheme_name": scheme_name,
                "scheme": scheme.model_dump(mode="json"),
                "source_pointer": scheme.source_ref.pointer,
            },
        )
    return chunks


class IndexingService:
    def __init__(
        self,
        database: DatabaseClient,
        sources: SourceRepository,
        generations: IndexGenerationRepository,
        storage: ArtifactStorage,
        ai: AIProvider,
        vector_store: VectorStore,
        cleanup: CleanupRepository | None = None,
    ) -> None:
        self._database = database
        self._sources = sources
        self._generations = generations
        self._storage = storage
        self._ai = ai
        self._vector_store = vector_store
        self._cleanup = cleanup or CleanupRepository()

    async def index(
        self,
        *,
        project_id: UUID,
        build_id: UUID,
        source_bindings: list[BoundSourceVersionRecord],
        canonical: CanonicalApi,
        embedding_model: str | None,
        config: BuildConfiguration,
        admission_token: UUID,
        cancellation_check: Callable[[], Awaitable[None]] | None = None,
    ) -> DocumentIndexGenerationRecord:
        source_version_ids = [binding.version.id for binding in source_bindings]
        if any(binding.source.project_id != project_id for binding in source_bindings):
            raise SourceParseError("Index source versions do not belong to the Project")
        if canonical.project_id != project_id or not set(
            canonical.provenance.source_version_ids
        ).issubset(source_version_ids):
            raise SourceParseError(
                "Canonical source semantics do not belong to the indexed Project generation"
            )
        if cancellation_check is not None:
            await cancellation_check()
        documents = [
            binding
            for binding in source_bindings
            if binding.source.kind is SourceKind.DOCUMENTATION
        ]
        source_fingerprint = hashlib.sha256(
            (
                _documentation_fingerprint(documents)
                + ":"
                + canonical.provenance.source_fingerprint
            ).encode()
        ).hexdigest()
        generation_id = uuid4()
        generation_key = hashlib.sha256(
            f"{project_id}:{build_id}:{embedding_model or 'none'}:{source_fingerprint}".encode()
        ).hexdigest()
        async with self._database.session_scope() as session:
            await require_build_execution_owner(
                session,
                build_id=build_id,
                admission_token=admission_token,
            )
            generation = await self._generations.prepare(
                session,
                generation_id=generation_id,
                project_id=project_id,
                build_id=build_id,
                embedding_model=embedding_model,
                generation_key=generation_key,
                source_fingerprint=source_fingerprint,
                admission_token=admission_token,
            )
        if generation.status is IndexGenerationStatus.READY:
            return generation

        collection: str | None = None
        stored_chunks_key: str | None = None
        try:
            chunks = await self._parse_and_chunk(
                documents,
                project_id=project_id,
                generation_id=generation.id,
                config=config,
                cancellation_check=cancellation_check,
            )
            chunks.extend(
                semantic_chunks(
                    canonical,
                    project_id=project_id,
                    generation_id=generation.id,
                    max_chars=config.documentation_chunk_chars,
                )
            )
            chunks.sort(key=lambda item: item.chunk_id)
            if len(chunks) > config.max_document_chunks:
                raise IndexingError(
                    "Source semantics and documentation exceed the configured chunk limit",
                    details={"chunks": len(chunks), "limit": config.max_document_chunks},
                )
            chunk_manifest = canonical_json_bytes(
                [chunk.model_dump(mode="json", by_alias=True) for chunk in chunks]
            )
            stored_chunks = await self._storage.put_bytes(
                "build-index-chunks",
                chunk_manifest,
                max_bytes=config.artifact_max_bytes,
            )
            stored_chunks_key = stored_chunks.storage_key
            if cancellation_check is not None:
                await cancellation_check()
            if not chunks:
                return await self._complete(
                    generation.id,
                    model=embedding_model,
                    dimensions=0,
                    collection=None,
                    chunk_count=0,
                    chunk_manifest_storage_key=stored_chunks.storage_key,
                    chunk_manifest_sha256=stored_chunks.content_sha256,
                    build_id=build_id,
                    admission_token=admission_token,
                )
            if embedding_model is None:
                raise IndexingError("An embedding model is required when documentation is attached")
            vectors, actual_model, dimension = await self._resolve_embeddings(
                chunks,
                embedding_model,
                project_id=project_id,
                config=config,
                cancellation_check=cancellation_check,
            )
            collection = self._vector_store.collection_name(dimension)
            if cancellation_check is not None:
                await cancellation_check()
            await self._vector_store.ensure_index(
                collection=collection,
                dimensions=dimension,
            )
            if cancellation_check is not None:
                await cancellation_check()
            for offset in range(0, len(chunks), config.embedding_batch_size):
                if cancellation_check is not None:
                    await cancellation_check()
                await self._vector_store.upsert_chunks(
                    collection=collection,
                    chunks=chunks[offset : offset + config.embedding_batch_size],
                    vectors=vectors[offset : offset + config.embedding_batch_size],
                    execution_token=admission_token,
                )
                if cancellation_check is not None:
                    await cancellation_check()
            return await self._complete(
                generation.id,
                model=actual_model,
                dimensions=dimension,
                collection=collection,
                chunk_count=len(chunks),
                chunk_manifest_storage_key=stored_chunks.storage_key,
                chunk_manifest_sha256=stored_chunks.content_sha256,
                build_id=build_id,
                admission_token=admission_token,
            )
        except Exception as exc:
            if collection is not None:
                cleanup_error: Exception | None = None
                try:
                    await self._vector_store.delete_generation(
                        collection=collection,
                        project_id=project_id,
                        generation_id=generation.id,
                        execution_token=admission_token,
                    )
                except Exception as cleanup_exc:
                    cleanup_error = cleanup_exc
                if cleanup_error is not None:
                    logger.warning(
                        "index_generation_cleanup_failed",
                        project_id=str(project_id),
                        generation_id=str(generation.id),
                        error_type=type(cleanup_error).__name__,
                    )
            summary = str(exc) if isinstance(exc, MCPlicaError) else type(exc).__name__
            async with self._database.session_scope() as session:
                await require_build_execution_owner(
                    session,
                    build_id=build_id,
                    admission_token=admission_token,
                    allow_cancellation=True,
                )
                cleanup_job = await self._cleanup.create_job(
                    session,
                    kind=CleanupJobKind.ORPHAN_GUARD,
                    idempotency_key=f"index-failure:{generation.id}",
                    project_id=project_id,
                    requested_by=None,
                    request_id=None,
                )
                if stored_chunks_key is not None:
                    await self._cleanup.add_object_target(
                        session, cleanup_job.id, stored_chunks_key
                    )
                if collection is not None:
                    await self._cleanup.add_vector_target(
                        session,
                        cleanup_job.id,
                        collection_name=collection,
                        project_id=project_id,
                        generation_id=generation.id,
                    )
                await self._cleanup.finalize_empty_job(session, cleanup_job.id)
                await self._generations.fail(
                    session,
                    generation.id,
                    summary,
                    build_id=build_id,
                    admission_token=admission_token,
                )
            raise

    async def _parse_and_chunk(
        self,
        bindings: list[BoundSourceVersionRecord],
        *,
        project_id: UUID,
        generation_id: UUID,
        config: BuildConfiguration,
        cancellation_check: Callable[[], Awaitable[None]] | None,
    ) -> list[DocumentChunk]:
        async def parse(binding: BoundSourceVersionRecord) -> list[DocumentChunk]:
            if cancellation_check is not None:
                await cancellation_check()
            value = await self._storage.get(
                binding.version.storage_key,
                max_bytes=config.document_max_bytes,
            )
            if cancellation_check is not None:
                await cancellation_check()
            document = await asyncio.to_thread(
                parse_document,
                value,
                detected_format=binding.version.detected_format,
                source_version_id=binding.version.id,
                title=binding.source.name,
                pdf_max_pages=config.pdf_max_pages,
                max_text_chars=config.document_max_text_chars,
            )
            return chunk_document(
                document,
                project_id=project_id,
                generation_id=generation_id,
                source_content_sha256=binding.version.content_sha256,
                max_chars=config.documentation_chunk_chars,
                overlap_chars=config.documentation_chunk_overlap_chars,
            )

        results = await bounded_map(
            bindings,
            parse,
            limit=config.max_document_parse_concurrency,
        )
        chunks = [chunk for result in results for chunk in result]
        if len(chunks) > config.max_document_chunks:
            raise IndexingError(
                "Documentation exceeds the configured chunk limit",
                details={"chunks": len(chunks), "limit": config.max_document_chunks},
            )
        return chunks

    async def _embed_chunks(
        self,
        chunks: list[DocumentChunk],
        model: str,
        *,
        config: BuildConfiguration,
        cancellation_check: Callable[[], Awaitable[None]] | None,
    ) -> list[EmbeddingBatch]:
        async def embed(offset: int) -> tuple[int, EmbeddingBatch]:
            batch = chunks[offset : offset + config.embedding_batch_size]
            if cancellation_check is not None:
                await cancellation_check()
            embedded = await self._ai.embed(
                model=model,
                texts=[chunk.text for chunk in batch],
            )
            if cancellation_check is not None:
                await cancellation_check()
            return offset, embedded

        offsets = list(range(0, len(chunks), config.embedding_batch_size))
        completed = await bounded_map(
            offsets,
            embed,
            limit=config.max_embedding_concurrency,
        )
        completed.sort(key=lambda item: item[0])
        return [batch for _, batch in completed]

    async def _resolve_embeddings(
        self,
        chunks: list[DocumentChunk],
        model: str,
        *,
        project_id: UUID,
        config: BuildConfiguration,
        cancellation_check: Callable[[], Awaitable[None]] | None,
    ) -> tuple[list[list[float]], str, int]:
        unique_chunks: dict[str, DocumentChunk] = {}
        for chunk in chunks:
            content_sha256 = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            if content_sha256 != chunk.content_sha256:
                raise IndexingError("Chunk content hash does not match normalized text")
            existing = unique_chunks.get(content_sha256)
            if existing is not None and existing.text != chunk.text:
                raise IndexingError("Chunk content hash collision detected")
            unique_chunks.setdefault(content_sha256, chunk)

        content_sha256s = list(unique_chunks)
        async with self._database.session_scope() as session:
            cached = await self._generations.list_cached_embeddings(
                session,
                project_id=project_id,
                model_identity=model,
                content_sha256s=content_sha256s,
            )
        cached_by_sha256 = {record.content_sha256: record for record in cached}
        if len(cached_by_sha256) != len(cached):
            raise IndexingError("Embedding cache returned duplicate content identities")

        cache_models = {record.resolved_model for record in cached}
        cache_dimensions = {record.dimensions for record in cached}
        cache_is_consistent = len(cache_models) <= 1 and len(cache_dimensions) <= 1
        missing = [
            chunk
            for content_sha256, chunk in unique_chunks.items()
            if content_sha256 not in cached_by_sha256
        ]

        fresh: dict[str, list[float]] = {}
        resolved_model: str
        dimensions: int
        if not cache_is_consistent:
            fresh, resolved_model, dimensions = await self._embed_unique_chunks(
                list(unique_chunks.values()),
                model,
                config=config,
                cancellation_check=cancellation_check,
            )
            cached_by_sha256 = {}
        elif missing:
            fresh, resolved_model, dimensions = await self._embed_unique_chunks(
                missing,
                model,
                config=config,
                cancellation_check=cancellation_check,
            )
            if cached and (cache_models != {resolved_model} or cache_dimensions != {dimensions}):
                fresh, resolved_model, dimensions = await self._embed_unique_chunks(
                    list(unique_chunks.values()),
                    model,
                    config=config,
                    cancellation_check=cancellation_check,
                )
                cached_by_sha256 = {}
        else:
            if not cached:
                raise IndexingError("Embedding resolution received no chunks")
            resolved_model = next(iter(cache_models))
            dimensions = next(iter(cache_dimensions))

        if fresh:
            async with self._database.session_scope() as session:
                await self._generations.upsert_cached_embeddings(
                    session,
                    project_id=project_id,
                    model_identity=model,
                    resolved_model=resolved_model,
                    dimensions=dimensions,
                    vectors_by_sha256=fresh,
                )

        vectors_by_sha256 = {
            content_sha256: record.vector for content_sha256, record in cached_by_sha256.items()
        }
        vectors_by_sha256.update(fresh)
        if set(vectors_by_sha256) != set(content_sha256s):
            raise IndexingError("Embedding cache did not resolve every chunk")
        return (
            [vectors_by_sha256[chunk.content_sha256] for chunk in chunks],
            resolved_model,
            dimensions,
        )

    async def _embed_unique_chunks(
        self,
        chunks: list[DocumentChunk],
        model: str,
        *,
        config: BuildConfiguration,
        cancellation_check: Callable[[], Awaitable[None]] | None,
    ) -> tuple[dict[str, list[float]], str, int]:
        batches = await self._embed_chunks(
            chunks,
            model,
            config=config,
            cancellation_check=cancellation_check,
        )
        actual_models = {batch.model for batch in batches}
        dimensions = {batch.dimensions for batch in batches}
        if len(actual_models) != 1 or len(dimensions) != 1:
            raise IndexingError("Embedding batches returned inconsistent model metadata")
        actual_model = next(iter(actual_models))
        dimension = next(iter(dimensions))
        vectors = [vector for batch in batches for vector in batch.vectors]
        if len(vectors) != len(chunks) or any(
            len(vector) != dimension or not all(math.isfinite(value) for value in vector)
            for vector in vectors
        ):
            raise IndexingError("Embedding vectors do not match chunk metadata")
        return (
            {chunk.content_sha256: vector for chunk, vector in zip(chunks, vectors, strict=True)},
            actual_model,
            dimension,
        )

    async def _complete(
        self,
        generation_id: UUID,
        *,
        model: str | None,
        dimensions: int,
        collection: str | None,
        chunk_count: int,
        chunk_manifest_storage_key: str,
        chunk_manifest_sha256: str,
        build_id: UUID,
        admission_token: UUID,
    ) -> DocumentIndexGenerationRecord:
        async with self._database.session_scope() as session:
            await require_build_execution_owner(
                session,
                build_id=build_id,
                admission_token=admission_token,
            )
            return await self._generations.complete(
                session,
                generation_id,
                embedding_model=model,
                dimensions=dimensions,
                collection_name=collection,
                chunk_count=chunk_count,
                chunk_manifest_storage_key=chunk_manifest_storage_key,
                chunk_manifest_sha256=chunk_manifest_sha256,
                build_id=build_id,
                admission_token=admission_token,
            )
