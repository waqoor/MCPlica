from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateError
from app.domain.indexing import (
    CachedEmbeddingRecord,
    DocumentIndexGenerationRecord,
    IndexGenerationStatus,
)
from app.models.indexing import DocumentIndexGeneration, EmbeddingVectorCache
from app.repositories.build_execution import require_build_execution_owner
from app.repositories.cleanup import lock_object_reference, lock_vector_reference


def _to_domain(model: DocumentIndexGeneration) -> DocumentIndexGenerationRecord:
    return DocumentIndexGenerationRecord(
        id=model.id,
        project_id=model.project_id,
        build_id=model.build_id,
        embedding_model=model.embedding_model,
        dimensions=model.dimensions,
        collection_name=model.collection_name,
        generation_key=model.generation_key,
        chunk_count=model.chunk_count,
        chunk_manifest_storage_key=model.chunk_manifest_storage_key,
        chunk_manifest_sha256=model.chunk_manifest_sha256,
        source_fingerprint=model.source_fingerprint,
        status=model.status,
        error_summary=model.error_summary,
        execution_token=model.execution_token,
        created_at=model.created_at,
        completed_at=model.completed_at,
    )


def _to_cached_embedding(model: EmbeddingVectorCache) -> CachedEmbeddingRecord:
    return CachedEmbeddingRecord(
        id=model.id,
        project_id=model.project_id,
        model_identity=model.model_identity,
        content_sha256=model.content_sha256,
        resolved_model=model.resolved_model,
        dimensions=model.dimensions,
        vector=model.vector_json,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
    )


class IndexGenerationRepository:
    async def list_cached_embeddings(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        model_identity: str,
        content_sha256s: list[str],
    ) -> list[CachedEmbeddingRecord]:
        if not content_sha256s:
            return []
        now = datetime.now(UTC)
        models = list(
            await session.scalars(
                select(EmbeddingVectorCache).where(
                    EmbeddingVectorCache.project_id == project_id,
                    EmbeddingVectorCache.model_identity == model_identity,
                    EmbeddingVectorCache.content_sha256.in_(content_sha256s),
                )
            )
        )
        if models:
            await session.execute(
                update(EmbeddingVectorCache)
                .where(EmbeddingVectorCache.id.in_([model.id for model in models]))
                .values(last_used_at=now)
            )
        return [
            _to_cached_embedding(model).model_copy(update={"last_used_at": now}) for model in models
        ]

    async def upsert_cached_embeddings(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        model_identity: str,
        resolved_model: str,
        dimensions: int,
        vectors_by_sha256: dict[str, list[float]],
    ) -> None:
        if not vectors_by_sha256:
            return
        now = datetime.now(UTC)
        values = [
            {
                "id": uuid4(),
                "project_id": project_id,
                "model_identity": model_identity,
                "content_sha256": content_sha256,
                "resolved_model": resolved_model,
                "dimensions": dimensions,
                "vector_json": vector,
                "created_at": now,
                "last_used_at": now,
            }
            for content_sha256, vector in vectors_by_sha256.items()
        ]
        statement = insert(EmbeddingVectorCache).values(values)
        await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_embedding_vector_cache_identity",
                set_={
                    "resolved_model": statement.excluded.resolved_model,
                    "dimensions": statement.excluded.dimensions,
                    "vector_json": statement.excluded.vector_json,
                    "last_used_at": statement.excluded.last_used_at,
                },
            )
        )

    async def prepare(
        self,
        session: AsyncSession,
        *,
        generation_id: UUID,
        project_id: UUID,
        build_id: UUID,
        embedding_model: str | None,
        generation_key: str,
        source_fingerprint: str,
        admission_token: UUID,
    ) -> DocumentIndexGenerationRecord:
        await require_build_execution_owner(
            session,
            build_id=build_id,
            admission_token=admission_token,
        )
        existing = await self.get_for_build(session, build_id)
        if existing is None:
            return await self.create(
                session,
                generation_id=generation_id,
                project_id=project_id,
                build_id=build_id,
                embedding_model=embedding_model,
                generation_key=generation_key,
                source_fingerprint=source_fingerprint,
            )
        if (
            existing.project_id != project_id
            or existing.generation_key != generation_key
            or existing.source_fingerprint != source_fingerprint
        ):
            raise InvalidStateError("Build index generation inputs changed after binding")
        if existing.status is IndexGenerationStatus.FAILED:
            await session.execute(
                update(DocumentIndexGeneration)
                .where(DocumentIndexGeneration.id == existing.id)
                .values(
                    status=IndexGenerationStatus.BUILDING,
                    error_summary=None,
                    completed_at=None,
                    embedding_model=embedding_model,
                    dimensions=None,
                    collection_name=None,
                    chunk_count=0,
                    chunk_manifest_storage_key=None,
                    chunk_manifest_sha256=None,
                    execution_token=None,
                )
            )
            model = await session.get(DocumentIndexGeneration, existing.id)
            assert model is not None
            return _to_domain(model)
        return existing

    async def create(
        self,
        session: AsyncSession,
        *,
        generation_id: UUID,
        project_id: UUID,
        build_id: UUID,
        embedding_model: str | None,
        generation_key: str,
        source_fingerprint: str,
    ) -> DocumentIndexGenerationRecord:
        model = DocumentIndexGeneration(
            id=generation_id,
            project_id=project_id,
            build_id=build_id,
            embedding_model=embedding_model,
            generation_key=generation_key,
            chunk_count=0,
            source_fingerprint=source_fingerprint,
            status=IndexGenerationStatus.BUILDING,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def complete(
        self,
        session: AsyncSession,
        generation_id: UUID,
        *,
        embedding_model: str | None,
        dimensions: int,
        collection_name: str | None,
        chunk_count: int,
        chunk_manifest_storage_key: str,
        chunk_manifest_sha256: str,
        build_id: UUID,
        admission_token: UUID,
    ) -> DocumentIndexGenerationRecord:
        await require_build_execution_owner(
            session,
            build_id=build_id,
            admission_token=admission_token,
        )
        await lock_object_reference(session, chunk_manifest_storage_key)
        if collection_name is not None:
            await lock_vector_reference(
                session,
                collection_name=collection_name,
                project_id=(await self._project_id(session, generation_id)),
                generation_id=generation_id,
            )
        now = datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(DocumentIndexGeneration)
                .where(
                    DocumentIndexGeneration.id == generation_id,
                    DocumentIndexGeneration.status == IndexGenerationStatus.BUILDING,
                )
                .values(
                    embedding_model=embedding_model,
                    dimensions=dimensions,
                    collection_name=collection_name,
                    chunk_count=chunk_count,
                    chunk_manifest_storage_key=chunk_manifest_storage_key,
                    chunk_manifest_sha256=chunk_manifest_sha256,
                    execution_token=admission_token,
                    status=IndexGenerationStatus.READY,
                    completed_at=now,
                )
            ),
        )
        if result.rowcount != 1:
            raise InvalidStateError("Index generation is no longer building")
        model = await session.get(DocumentIndexGeneration, generation_id)
        assert model is not None
        return _to_domain(model)

    async def _project_id(self, session: AsyncSession, generation_id: UUID) -> UUID:
        project_id = await session.scalar(
            select(DocumentIndexGeneration.project_id).where(
                DocumentIndexGeneration.id == generation_id
            )
        )
        if project_id is None:
            raise InvalidStateError("Index generation is unavailable")
        return project_id

    async def fail(
        self,
        session: AsyncSession,
        generation_id: UUID,
        error_summary: str,
        *,
        build_id: UUID,
        admission_token: UUID,
    ) -> None:
        await require_build_execution_owner(
            session,
            build_id=build_id,
            admission_token=admission_token,
            allow_cancellation=True,
        )
        await session.execute(
            update(DocumentIndexGeneration)
            .where(
                DocumentIndexGeneration.id == generation_id,
                DocumentIndexGeneration.status == IndexGenerationStatus.BUILDING,
            )
            .values(
                status=IndexGenerationStatus.FAILED,
                error_summary=error_summary[:1000],
                completed_at=datetime.now(UTC),
            )
        )

    async def get_for_build(
        self,
        session: AsyncSession,
        build_id: UUID,
    ) -> DocumentIndexGenerationRecord | None:
        model = await session.scalar(
            select(DocumentIndexGeneration).where(DocumentIndexGeneration.build_id == build_id)
        )
        return _to_domain(model) if model else None

    async def get_for_builds(
        self,
        session: AsyncSession,
        build_ids: list[UUID],
    ) -> dict[UUID, DocumentIndexGenerationRecord]:
        if not build_ids:
            return {}
        models = list(
            await session.scalars(
                select(DocumentIndexGeneration).where(
                    DocumentIndexGeneration.build_id.in_(set(build_ids))
                )
            )
        )
        return {model.build_id: _to_domain(model) for model in models}
