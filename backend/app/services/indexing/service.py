import asyncio
import hashlib
from uuid import UUID, uuid4

import structlog

from app.clients.database import DatabaseClient
from app.core.async_utils import bounded_map
from app.core.canonical_json import canonical_json_bytes
from app.core.exceptions import IndexingError, MCPlicaError, SourceParseError
from app.domain.builds import BuildConfiguration
from app.domain.indexing import (
    DocumentIndexGenerationRecord,
    IndexGenerationStatus,
)
from app.domain.sources import BoundSourceVersionRecord, SourceKind
from app.parsers.documentation import DocumentChunk, chunk_document, parse_document
from app.providers.ai.base import AIProvider, EmbeddingBatch
from app.providers.storage import ArtifactStorage
from app.providers.vector import VectorStore
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


class IndexingService:
    def __init__(
        self,
        database: DatabaseClient,
        sources: SourceRepository,
        generations: IndexGenerationRepository,
        storage: ArtifactStorage,
        ai: AIProvider,
        vector_store: VectorStore,
    ) -> None:
        self._database = database
        self._sources = sources
        self._generations = generations
        self._storage = storage
        self._ai = ai
        self._vector_store = vector_store

    async def index(
        self,
        *,
        project_id: UUID,
        build_id: UUID,
        source_version_ids: list[UUID],
        embedding_model: str | None,
        config: BuildConfiguration,
    ) -> DocumentIndexGenerationRecord:
        async with self._database.session_scope() as session:
            bindings = await self._sources.list_bound_versions(
                session,
                project_id,
                source_version_ids,
            )
        if len(bindings) != len(source_version_ids):
            raise SourceParseError("Index source versions do not belong to the Project")
        documents = [
            binding for binding in bindings if binding.source.kind is SourceKind.DOCUMENTATION
        ]
        source_fingerprint = _documentation_fingerprint(documents)
        generation_id = uuid4()
        generation_key = hashlib.sha256(
            f"{project_id}:{build_id}:{embedding_model or 'none'}:{source_fingerprint}".encode()
        ).hexdigest()
        async with self._database.session_scope() as session:
            generation = await self._generations.prepare(
                session,
                generation_id=generation_id,
                project_id=project_id,
                build_id=build_id,
                embedding_model=embedding_model,
                generation_key=generation_key,
                source_fingerprint=source_fingerprint,
            )
        if generation.status is IndexGenerationStatus.READY:
            return generation

        collection: str | None = None
        try:
            chunks = await self._parse_and_chunk(
                documents,
                project_id=project_id,
                generation_id=generation.id,
                config=config,
            )
            chunk_manifest = canonical_json_bytes(
                [chunk.model_dump(mode="json", by_alias=True) for chunk in chunks]
            )
            stored_chunks = await self._storage.put_bytes(
                "build-index-chunks",
                chunk_manifest,
                max_bytes=config.artifact_max_bytes,
            )
            if not chunks:
                return await self._complete(
                    generation.id,
                    model=embedding_model,
                    dimensions=0,
                    collection=None,
                    chunk_count=0,
                    chunk_manifest_storage_key=stored_chunks.storage_key,
                    chunk_manifest_sha256=stored_chunks.content_sha256,
                )
            if embedding_model is None:
                raise IndexingError("An embedding model is required when documentation is attached")
            batches = await self._embed_chunks(chunks, embedding_model, config=config)
            actual_models = {batch.model for batch in batches}
            dimensions = {batch.dimensions for batch in batches}
            if len(actual_models) != 1 or len(dimensions) != 1:
                raise IndexingError("Embedding batches returned inconsistent model metadata")
            actual_model = next(iter(actual_models))
            dimension = next(iter(dimensions))
            vectors = [vector for batch in batches for vector in batch.vectors]
            if len(vectors) != len(chunks):
                raise IndexingError("Embedding count does not match documentation chunks")
            collection = self._vector_store.collection_name(dimension)
            await self._vector_store.ensure_index(
                collection=collection,
                dimensions=dimension,
            )
            for offset in range(0, len(chunks), config.embedding_batch_size):
                await self._vector_store.upsert_chunks(
                    collection=collection,
                    chunks=chunks[offset : offset + config.embedding_batch_size],
                    vectors=vectors[offset : offset + config.embedding_batch_size],
                )
            return await self._complete(
                generation.id,
                model=actual_model,
                dimensions=dimension,
                collection=collection,
                chunk_count=len(chunks),
                chunk_manifest_storage_key=stored_chunks.storage_key,
                chunk_manifest_sha256=stored_chunks.content_sha256,
            )
        except Exception as exc:
            if collection is not None:
                cleanup_error: Exception | None = None
                try:
                    await self._vector_store.delete_generation(
                        collection=collection,
                        project_id=project_id,
                        generation_id=generation.id,
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
                await self._generations.fail(session, generation.id, summary)
            raise

    async def _parse_and_chunk(
        self,
        bindings: list[BoundSourceVersionRecord],
        *,
        project_id: UUID,
        generation_id: UUID,
        config: BuildConfiguration,
    ) -> list[DocumentChunk]:
        async def parse(binding: BoundSourceVersionRecord) -> list[DocumentChunk]:
            value = await self._storage.get(
                binding.version.storage_key,
                max_bytes=config.document_max_bytes,
            )
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
    ) -> list[EmbeddingBatch]:
        async def embed(offset: int) -> tuple[int, EmbeddingBatch]:
            batch = chunks[offset : offset + config.embedding_batch_size]
            return offset, await self._ai.embed(
                model=model,
                texts=[chunk.text for chunk in batch],
            )

        offsets = list(range(0, len(chunks), config.embedding_batch_size))
        completed = await bounded_map(
            offsets,
            embed,
            limit=config.max_embedding_concurrency,
        )
        completed.sort(key=lambda item: item[0])
        return [batch for _, batch in completed]

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
    ) -> DocumentIndexGenerationRecord:
        async with self._database.session_scope() as session:
            return await self._generations.complete(
                session,
                generation_id,
                embedding_model=model,
                dimensions=dimensions,
                collection_name=collection,
                chunk_count=chunk_count,
                chunk_manifest_storage_key=chunk_manifest_storage_key,
                chunk_manifest_sha256=chunk_manifest_sha256,
            )
