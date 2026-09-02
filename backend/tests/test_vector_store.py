from typing import Any, cast
from uuid import UUID

import pytest

from app.clients.vector import MilvusVectorClient
from app.core.exceptions import IndexingError
from app.parsers.documentation import DocumentChunk
from app.providers.milvus import MilvusVectorStore


class _FakeMilvusClient:
    filter_expression: str | None = None
    result: list[list[dict[str, Any]]]
    upserted: list[dict[str, Any]]

    def __init__(self) -> None:
        self.result = []
        self.upserted = []

    async def has_collection(self, name: str) -> bool:
        return True

    async def describe_collection(self, name: str) -> dict[str, Any]:
        return {"fields": [{"name": "embedding", "params": {"dim": 2}}]}

    async def search(self, **kwargs: Any) -> list[list[dict[str, Any]]]:
        self.filter_expression = str(kwargs["filter_expression"])
        return self.result

    async def upsert(self, **kwargs: Any) -> None:
        self.upserted = list(kwargs["data"])

    async def delete(self, **kwargs: Any) -> None:
        self.filter_expression = str(kwargs["filter_expression"])


async def test_vector_search_is_always_project_and_generation_scoped() -> None:
    client = _FakeMilvusClient()
    store = MilvusVectorStore(cast(MilvusVectorClient, client), "document-chunks")
    await store.search(
        collection=store.collection_name(2),
        project_id=UUID(int=30),
        generation_id=UUID(int=31),
        vector=[0.1, 0.2],
        limit=5,
    )
    assert client.filter_expression is not None
    assert "project_id" in client.filter_expression
    assert "generation_id" in client.filter_expression

    await store.search(
        collection=store.collection_name(2),
        project_id=UUID(int=30),
        generation_id=UUID(int=31),
        vector=[0.1, 0.2],
        limit=5,
        include_documentation=False,
    )
    assert client.filter_expression is not None
    assert 'source_kind != "documentation"' in client.filter_expression


async def test_vector_store_rejects_cross_project_result_even_if_backend_misbehaves() -> None:
    client = _FakeMilvusClient()
    client.result = [
        [
            {
                "distance": 0.9,
                "entity": {
                    "chunk_id": "chunk_" + "1" * 64,
                    "project_id": str(UUID(int=99)),
                    "generation_id": str(UUID(int=31)),
                    "source_version_id": str(UUID(int=32)),
                    "source_kind": "documentation",
                    "title": "Docs",
                    "section_path": ["Docs"],
                    "operation_keys": [],
                    "text": "text",
                    "content_sha256": "2" * 64,
                },
            }
        ]
    ]
    store = MilvusVectorStore(cast(MilvusVectorClient, client), "document-chunks")
    with pytest.raises(IndexingError, match="cross-project"):
        await store.search(
            collection=store.collection_name(2),
            project_id=UUID(int=30),
            generation_id=UUID(int=31),
            vector=[0.1, 0.2],
            limit=5,
        )


async def test_vector_rows_and_queries_are_fenced_to_the_execution_owner() -> None:
    client = _FakeMilvusClient()
    store = MilvusVectorStore(cast(MilvusVectorClient, client), "document-chunks")
    project_id = UUID(int=40)
    generation_id = UUID(int=41)
    source_version_id = UUID(int=42)
    first_token = UUID(int=43)
    accepted_token = UUID(int=44)
    chunk = DocumentChunk(
        chunk_id="chunk_" + "3" * 64,
        project_id=project_id,
        generation_id=generation_id,
        source_version_id=source_version_id,
        section_path=["Docs"],
        text="bounded evidence",
        content_sha256="4" * 64,
    )

    await store.upsert_chunks(
        collection=store.collection_name(2),
        chunks=[chunk],
        vectors=[[0.1, 0.2]],
        execution_token=first_token,
    )
    first_row_id = client.upserted[0]["chunk_id"]
    await store.upsert_chunks(
        collection=store.collection_name(2),
        chunks=[chunk],
        vectors=[[0.3, 0.4]],
        execution_token=accepted_token,
    )

    assert first_row_id != client.upserted[0]["chunk_id"]
    assert client.upserted[0]["document_chunk_id"] == chunk.chunk_id
    assert client.upserted[0]["execution_token"] == str(accepted_token)

    client.result = [
        [
            {
                "distance": 0.8,
                "entity": {
                    **chunk.model_dump(mode="json"),
                    "chunk_id": client.upserted[0]["chunk_id"],
                    "document_chunk_id": chunk.chunk_id,
                },
            }
        ]
    ]
    results = await store.search(
        collection=store.collection_name(2),
        project_id=project_id,
        generation_id=generation_id,
        execution_token=accepted_token,
        vector=[0.3, 0.4],
        limit=5,
    )

    assert client.filter_expression is not None
    assert f'execution_token == "{accepted_token}"' in client.filter_expression
    assert results[0].chunk.chunk_id == chunk.chunk_id

    await store.delete_generation(
        collection=store.collection_name(2),
        project_id=project_id,
        generation_id=generation_id,
        execution_token=first_token,
    )
    assert client.filter_expression is not None
    assert f'execution_token == "{first_token}"' in client.filter_expression
