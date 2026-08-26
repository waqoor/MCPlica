from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateError
from app.domain.indexing import DocumentIndexGenerationRecord, IndexGenerationStatus
from app.models.indexing import DocumentIndexGeneration


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
        created_at=model.created_at,
        completed_at=model.completed_at,
    )


class IndexGenerationRepository:
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
    ) -> DocumentIndexGenerationRecord:
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
    ) -> DocumentIndexGenerationRecord:
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

    async def fail(
        self,
        session: AsyncSession,
        generation_id: UUID,
        error_summary: str,
    ) -> None:
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
