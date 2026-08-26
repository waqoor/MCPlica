from typing import Any

import pytest

import app.clients.vector as vector_module
from app.clients.vector import MilvusVectorClient


class _AsyncMilvusProbe:
    create_kwargs: dict[str, object]
    search_kwargs: dict[str, object]

    async def create_collection(self, **kwargs: Any) -> None:
        self.create_kwargs = dict(kwargs)

    async def search(self, **kwargs: Any) -> list[list[dict[str, object]]]:
        self.search_kwargs = dict(kwargs)
        return []


@pytest.mark.asyncio
async def test_milvus_build_reads_are_strongly_consistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _AsyncMilvusProbe()

    def client_factory(*, uri: str, token: str, timeout: float) -> _AsyncMilvusProbe:
        return probe

    monkeypatch.setattr(vector_module, "AsyncMilvusClient", client_factory)
    client = MilvusVectorClient("http://milvus:19530")

    await client.create_collection(name="chunks_d8", dimensions=8)
    await client.search(
        collection="chunks_d8",
        vector=[0.5] * 8,
        filter_expression='project_id == "project-1"',
        limit=5,
        output_fields=["chunk_id"],
    )

    assert probe.create_kwargs["consistency_level"] == "Strong"
    assert probe.search_kwargs["consistency_level"] == "Strong"
