import hashlib
import re
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from app.clients.vector import MilvusVectorClient
from app.core.exceptions import IndexingError
from app.parsers.documentation import DocumentChunk
from app.providers.vector import VectorSearchResult, VectorStore

_NON_NAME = re.compile(r"[^A-Za-z0-9_]+")
_OUTPUT_FIELDS = [
    "chunk_id",
    "project_id",
    "generation_id",
    "source_version_id",
    "source_kind",
    "title",
    "section_path",
    "operation_keys",
    "text",
    "content_sha256",
]


def _field_dimension(description: Mapping[str, object]) -> int | None:
    fields = description.get("fields")
    if not isinstance(fields, list):
        return None
    for field in cast(list[object], fields):
        if not isinstance(field, Mapping):
            continue
        field_mapping = cast(Mapping[object, object], field)
        if field_mapping.get("name") != "embedding":
            continue
        params = field_mapping.get("params")
        raw_dimension = (
            cast(Mapping[object, object], params).get("dim")
            if isinstance(params, Mapping)
            else None
        )
        if isinstance(raw_dimension, int | str) and not isinstance(raw_dimension, bool):
            try:
                return int(raw_dimension)
            except ValueError:
                return None
    return None


class MilvusVectorStore(VectorStore):
    def __init__(self, client: MilvusVectorClient, base_collection: str) -> None:
        normalized = _NON_NAME.sub("_", base_collection).strip("_").lower()
        if not normalized:
            raise ValueError("Milvus collection base name is invalid")
        digest = hashlib.sha256(base_collection.encode()).hexdigest()[:8]
        self._base_collection = f"{normalized[:180]}_{digest}"
        self._client = client

    def collection_name(self, dimensions: int) -> str:
        if dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")
        return f"{self._base_collection}_d{dimensions}"

    async def ensure_index(self, *, collection: str, dimensions: int) -> None:
        if not await self._client.has_collection(collection):
            await self._client.create_collection(name=collection, dimensions=dimensions)
            return
        actual = _field_dimension(await self._client.describe_collection(collection))
        if actual is not None and actual != dimensions:
            raise IndexingError(
                "Milvus collection embedding dimension mismatch",
                details={"expected": dimensions, "actual": actual},
            )

    async def upsert_chunks(
        self,
        *,
        collection: str,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise IndexingError("Chunk and embedding counts do not match")
        rows: list[dict[str, Any]] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            rows.append(
                {
                    **chunk.model_dump(mode="json"),
                    "embedding": vector,
                }
            )
        await self._client.upsert(collection=collection, data=rows)

    async def search(
        self,
        *,
        collection: str,
        project_id: UUID,
        generation_id: UUID,
        vector: list[float],
        limit: int,
        include_documentation: bool = True,
    ) -> list[VectorSearchResult]:
        if not 1 <= limit <= 100:
            raise ValueError("Vector search limit must be between 1 and 100")
        expression = f'project_id == "{project_id}" and generation_id == "{generation_id}"'
        if not include_documentation:
            expression += ' and source_kind != "documentation"'
        raw = await self._client.search(
            collection=collection,
            vector=vector,
            filter_expression=expression,
            limit=limit,
            output_fields=_OUTPUT_FIELDS,
        )
        matches = raw[0] if raw else []
        results: list[VectorSearchResult] = []
        for match in matches:
            entity = match.get("entity")
            if not isinstance(entity, dict):
                continue
            try:
                chunk = DocumentChunk.model_validate(entity)
                score = float(match.get("distance", match.get("score", 0)))
            except (TypeError, ValueError) as exc:
                raise IndexingError("Milvus returned malformed chunk metadata") from exc
            if chunk.project_id != project_id or chunk.generation_id != generation_id:
                raise IndexingError("Milvus returned cross-project or cross-generation data")
            results.append(VectorSearchResult(chunk=chunk, score=score))
        return results

    async def delete_generation(
        self,
        *,
        collection: str,
        project_id: UUID,
        generation_id: UUID,
    ) -> None:
        expression = f'project_id == "{project_id}" and generation_id == "{generation_id}"'
        await self._client.delete(collection=collection, filter_expression=expression)
