import time
from typing import Any, cast

from pymilvus import AsyncMilvusClient
from pymilvus.exceptions import MilvusException

from app.clients.base import AsyncClient
from app.core.exceptions import ClientResponseError, ClientUnavailableError
from app.observability import observe_milvus_operation


class MilvusVectorClient(AsyncClient):
    """Owns all pymilvus SDK interaction and translates transport failures."""

    def __init__(self, uri: str, token: str | None = None, *, timeout_seconds: float = 30) -> None:
        self._client = AsyncMilvusClient(
            uri=uri,
            token=token or "",
            timeout=timeout_seconds,
        )

    async def health(self) -> bool:
        started = time.perf_counter()
        outcome = "error"
        try:
            await self._client.list_collections()  # pyright: ignore[reportUnknownMemberType]
            outcome = "succeeded"
            return True
        except MilvusException:
            return False
        finally:
            observe_milvus_operation("health", outcome, time.perf_counter() - started)

    async def has_collection(self, name: str) -> bool:
        started = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.has_collection(  # pyright: ignore[reportUnknownMemberType]
                collection_name=name
            )
            outcome = "succeeded"
            return result
        except MilvusException as exc:
            raise ClientUnavailableError("Milvus collection lookup failed") from exc
        finally:
            observe_milvus_operation("has_collection", outcome, time.perf_counter() - started)

    async def create_collection(self, *, name: str, dimensions: int) -> None:
        started = time.perf_counter()
        outcome = "error"
        try:
            await self._client.create_collection(  # pyright: ignore[reportUnknownMemberType]
                collection_name=name,
                dimension=dimensions,
                primary_field_name="chunk_id",
                id_type="string",
                vector_field_name="embedding",
                metric_type="COSINE",
                auto_id=False,
                max_length=80,
                enable_dynamic_field=True,
                # A build searches the generation immediately after indexing it.
                # Bounded consistency can silently return an empty result here.
                consistency_level="Strong",
            )
            outcome = "succeeded"
        except MilvusException as exc:
            raise ClientUnavailableError("Milvus collection creation failed") from exc
        finally:
            observe_milvus_operation("create_collection", outcome, time.perf_counter() - started)

    async def describe_collection(self, name: str) -> dict[str, Any]:
        started = time.perf_counter()
        outcome = "error"
        try:
            raw = cast(
                object,
                await self._client.describe_collection(  # pyright: ignore[reportUnknownMemberType]
                    collection_name=name
                ),
            )
            if not isinstance(raw, dict):
                raise ClientResponseError("Milvus returned malformed collection metadata")
            outcome = "succeeded"
            return cast(dict[str, Any], raw)
        except MilvusException as exc:
            raise ClientUnavailableError("Milvus collection inspection failed") from exc
        finally:
            observe_milvus_operation(
                "describe_collection",
                outcome,
                time.perf_counter() - started,
            )

    async def upsert(self, *, collection: str, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        started = time.perf_counter()
        outcome = "error"
        try:
            await self._client.upsert(  # pyright: ignore[reportUnknownMemberType]
                collection_name=collection,
                data=data,
            )
            outcome = "succeeded"
        except MilvusException as exc:
            raise ClientUnavailableError("Milvus upsert failed") from exc
        finally:
            observe_milvus_operation("upsert", outcome, time.perf_counter() - started)

    async def search(
        self,
        *,
        collection: str,
        vector: list[float],
        filter_expression: str,
        limit: int,
        output_fields: list[str],
    ) -> list[list[dict[str, Any]]]:
        started = time.perf_counter()
        outcome = "error"
        try:
            raw = cast(
                object,
                await self._client.search(  # pyright: ignore[reportUnknownMemberType]
                    collection_name=collection,
                    data=[vector],
                    filter=filter_expression,
                    limit=limit,
                    output_fields=output_fields,
                    anns_field="embedding",
                    search_params={"metric_type": "COSINE", "params": {}},
                    # Preserve read-your-writes when a generation is queried directly
                    # after upsert, including collections created before this setting.
                    consistency_level="Strong",
                ),
            )
            if not isinstance(raw, list):
                raise ClientResponseError("Milvus returned malformed search results")
            outcome = "succeeded"
            return cast(list[list[dict[str, Any]]], raw)
        except MilvusException as exc:
            raise ClientUnavailableError("Milvus search failed") from exc
        finally:
            observe_milvus_operation("search", outcome, time.perf_counter() - started)

    async def delete(self, *, collection: str, filter_expression: str) -> None:
        started = time.perf_counter()
        outcome = "error"
        try:
            await self._client.delete(  # pyright: ignore[reportUnknownMemberType]
                collection_name=collection,
                filter=filter_expression,
            )
            outcome = "succeeded"
        except MilvusException as exc:
            raise ClientUnavailableError("Milvus generation deletion failed") from exc
        finally:
            observe_milvus_operation("delete", outcome, time.perf_counter() - started)

    async def close(self) -> None:
        await self._client.close()
