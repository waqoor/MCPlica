from typing import Protocol

from app.clients.storage import (
    AsyncReadable,
    FilesystemStorageClient,
    StagedObject,
    StoredObject,
)


class ArtifactStorage(Protocol):
    async def stage_stream(
        self,
        namespace: str,
        source: AsyncReadable,
        *,
        max_bytes: int,
    ) -> StagedObject: ...

    async def get_staged(self, staged: StagedObject, *, max_bytes: int) -> bytes: ...

    async def commit_staged(self, staged: StagedObject) -> StoredObject: ...

    async def discard_staged(self, staged: StagedObject) -> None: ...

    async def put_stream(
        self,
        namespace: str,
        source: AsyncReadable,
        *,
        max_bytes: int,
    ) -> StoredObject: ...

    async def put_bytes(
        self,
        namespace: str,
        value: bytes,
        *,
        max_bytes: int,
    ) -> StoredObject: ...

    async def put_exact(self, storage_key: str, value: bytes) -> None: ...

    async def get(self, storage_key: str, *, max_bytes: int | None = None) -> bytes: ...

    async def delete(self, storage_key: str) -> None: ...


class FilesystemArtifactStorage:
    def __init__(self, client: FilesystemStorageClient) -> None:
        self._client = client

    async def stage_stream(
        self,
        namespace: str,
        source: AsyncReadable,
        *,
        max_bytes: int,
    ) -> StagedObject:
        return await self._client.stage_content_stream(
            namespace,
            source,
            max_bytes=max_bytes,
        )

    async def get_staged(self, staged: StagedObject, *, max_bytes: int) -> bytes:
        return await self._client.read_staged(staged, max_bytes=max_bytes)

    async def commit_staged(self, staged: StagedObject) -> StoredObject:
        return await self._client.commit_staged(staged)

    async def discard_staged(self, staged: StagedObject) -> None:
        await self._client.discard_staged(staged)

    async def put_stream(
        self,
        namespace: str,
        source: AsyncReadable,
        *,
        max_bytes: int,
    ) -> StoredObject:
        return await self._client.put_content_stream(namespace, source, max_bytes=max_bytes)

    async def put_bytes(
        self,
        namespace: str,
        value: bytes,
        *,
        max_bytes: int,
    ) -> StoredObject:
        return await self._client.put_content_bytes(namespace, value, max_bytes=max_bytes)

    async def put_exact(self, storage_key: str, value: bytes) -> None:
        await self._client.put_exact(storage_key, value)

    async def get(self, storage_key: str, *, max_bytes: int | None = None) -> bytes:
        return await self._client.read_bytes(storage_key, max_bytes=max_bytes)

    async def delete(self, storage_key: str) -> None:
        await self._client.delete(storage_key)
