from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app.parsers.documentation import DocumentChunk


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    chunk: DocumentChunk
    score: float


class VectorStore(ABC):
    @abstractmethod
    def collection_name(self, dimensions: int) -> str: ...

    @abstractmethod
    async def ensure_index(self, *, collection: str, dimensions: int) -> None: ...

    @abstractmethod
    async def upsert_chunks(
        self,
        *,
        collection: str,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        execution_token: UUID,
    ) -> None: ...

    @abstractmethod
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
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    async def delete_generation(
        self,
        *,
        collection: str,
        project_id: UUID,
        generation_id: UUID,
        execution_token: UUID | None = None,
    ) -> None: ...
