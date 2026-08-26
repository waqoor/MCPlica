from typing import Any

from pymilvus import MilvusClient

from app.clients.base import AsyncClient


class MilvusVectorClient(AsyncClient):
    """Thin infrastructure wrapper. Domain indexing logic belongs in services."""

    def __init__(self, uri: str, token: str | None = None) -> None:
        kwargs: dict[str, Any] = {"uri": uri}
        if token:
            kwargs["token"] = token
        self.client = MilvusClient(**kwargs)

    async def health(self) -> bool:
        try:
            self.client.list_collections()
            return True
        except Exception:
            return False

    def has_collection(self, name: str) -> bool:
        return self.client.has_collection(collection_name=name)

    def create_collection(self, *, name: str, dimension: int) -> None:
        self.client.create_collection(collection_name=name, dimension=dimension)

    def insert(self, *, collection: str, data: list[dict[str, Any]]) -> Any:
        return self.client.insert(collection_name=collection, data=data)

    def search(self, *, collection: str, vectors: list[list[float]], limit: int = 10) -> Any:
        return self.client.search(collection_name=collection, data=vectors, limit=limit)
