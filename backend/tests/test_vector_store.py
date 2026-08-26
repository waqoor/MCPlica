from typing import Any, cast
from uuid import UUID

import pytest

from app.clients.vector import MilvusVectorClient
from app.core.exceptions import IndexingError
from app.providers.milvus import MilvusVectorStore


class _FakeMilvusClient:
    filter_expression: str | None = None
    result: list[list[dict[str, Any]]]

    def __init__(self) -> None:
        self.result = []

    async def has_collection(self, name: str) -> bool:
        return True

    async def describe_collection(self, name: str) -> dict[str, Any]:
        return {"fields": [{"name": "embedding", "params": {"dim": 2}}]}

    async def search(self, **kwargs: Any) -> list[list[dict[str, Any]]]:
        self.filter_expression = str(kwargs["filter_expression"])
        return self.result

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
