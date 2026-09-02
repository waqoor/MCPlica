from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp_contracts import CanonicalOperation

from app.core.exceptions import IndexingError
from app.domain.indexing import DocumentIndexGenerationRecord, IndexGenerationStatus
from app.parsers.documentation import DocumentChunk
from app.providers.ai.base import AIProvider
from app.providers.vector import VectorStore


@dataclass(frozen=True, slots=True)
class RetrievalContext:
    chunks: list[DocumentChunk]
    embedding_usage: dict[str, Any] | None


class RetrievalService:
    def __init__(self, ai: AIProvider, vector_store: VectorStore) -> None:
        self._ai = ai
        self._vector_store = vector_store

    async def retrieve(
        self,
        operation: CanonicalOperation,
        *,
        generation: DocumentIndexGenerationRecord,
        include_documentation: bool,
        limit: int,
        max_context_chars: int,
        cancellation_check: Callable[[], Awaitable[None]] | None = None,
    ) -> RetrievalContext:
        if (
            generation.status is not IndexGenerationStatus.READY
            or generation.chunk_count == 0
            or generation.collection_name is None
            or generation.embedding_model is None
            or not generation.dimensions
        ):
            return RetrievalContext([], None)
        query = _query(operation)
        if cancellation_check is not None:
            await cancellation_check()
        embedded = await self._ai.embed(
            model=generation.embedding_model,
            texts=[query],
        )
        if cancellation_check is not None:
            await cancellation_check()
        if embedded.dimensions != generation.dimensions:
            raise IndexingError(
                "Retrieval embedding dimensions do not match the indexed generation"
            )
        results = await self._vector_store.search(
            collection=generation.collection_name,
            project_id=generation.project_id,
            generation_id=generation.id,
            execution_token=generation.execution_token,
            vector=embedded.vectors[0],
            limit=limit,
            include_documentation=include_documentation,
        )
        chunks: list[DocumentChunk] = []
        consumed = 0
        for result in results:
            size = len(result.chunk.text)
            if chunks and consumed + size > max_context_chars:
                break
            chunks.append(result.chunk)
            consumed += size
        return RetrievalContext(chunks, embedded.usage)


def _query(operation: CanonicalOperation) -> str:
    parameter_names = ", ".join(
        f"{parameter.location.value}:{parameter.name}" for parameter in operation.parameters
    )
    values = [
        operation.source_operation_id or "",
        operation.method.value,
        operation.path_template,
        operation.summary or "",
        operation.description or "",
        " ".join(operation.tags),
        parameter_names,
    ]
    return "\n".join(value for value in values if value)[:8_000]
