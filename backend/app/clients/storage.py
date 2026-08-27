import asyncio
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.clients.base import AsyncClient
from app.core.exceptions import NotFoundError, PayloadTooLargeError, ValidationError


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class AsyncReadable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StoredObject:
    storage_key: str
    content_sha256: str
    byte_size: int
    created: bool


@dataclass(frozen=True, slots=True)
class StagedObject:
    namespace: str
    temporary_path: Path
    content_sha256: str
    byte_size: int


class BytesReader:
    def __init__(self, value: bytes) -> None:
        self._value = value
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        if self._offset >= len(self._value):
            return b""
        if size < 0:
            size = len(self._value) - self._offset
        chunk = self._value[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class FilesystemStorageClient(AsyncClient):
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._temporary = self.root / ".tmp"
        self._temporary.mkdir(parents=True, exist_ok=True)

    async def health(self) -> bool:
        return await asyncio.to_thread(lambda: self.root.exists() and self.root.is_dir())

    def _safe_path(self, relative_path: str) -> Path:
        pure_path = PurePosixPath(relative_path)
        if pure_path.is_absolute() or ".." in pure_path.parts or not pure_path.parts:
            raise ValidationError("Storage key is invalid")
        target = self.root.joinpath(*pure_path.parts).resolve()
        if self.root not in target.parents:
            raise ValidationError("Storage key escapes configured root")
        return target

    @staticmethod
    def _namespace(value: str) -> PurePosixPath:
        namespace = PurePosixPath(value)
        if namespace.is_absolute() or ".." in namespace.parts or not namespace.parts:
            raise ValidationError("Storage namespace is invalid")
        return namespace

    def _staged_path(self, staged: StagedObject) -> Path:
        temporary_path = staged.temporary_path.resolve()
        if temporary_path.parent != self._temporary or not temporary_path.is_file():
            raise ValidationError("Staged storage object is unavailable")
        return temporary_path

    def storage_key_for_staged(self, staged: StagedObject) -> str:
        namespace = self._namespace(staged.namespace)
        return str(namespace / staged.content_sha256[:2] / staged.content_sha256).replace("\\", "/")

    async def stage_content_stream(
        self,
        namespace: str,
        source: AsyncReadable,
        *,
        max_bytes: int,
        chunk_size: int = 64 * 1024,
    ) -> StagedObject:
        normalized_namespace = self._namespace(namespace)
        if max_bytes <= 0 or chunk_size <= 0:
            raise ValueError("Storage byte and chunk limits must be positive")
        file_descriptor, temporary_name = await asyncio.to_thread(
            tempfile.mkstemp,
            prefix="upload-",
            dir=self._temporary,
        )
        temporary_path = Path(temporary_name)
        digest = hashlib.sha256()
        total = 0
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                while True:
                    chunk = await source.read(chunk_size)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise PayloadTooLargeError("Upload exceeds configured byte limit")
                    digest.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
                await asyncio.to_thread(handle.flush)
                await asyncio.to_thread(os.fsync, handle.fileno())
            return StagedObject(
                namespace=str(normalized_namespace).replace("\\", "/"),
                temporary_path=temporary_path,
                content_sha256=digest.hexdigest(),
                byte_size=total,
            )
        except BaseException:
            await asyncio.to_thread(temporary_path.unlink, missing_ok=True)
            raise

    async def read_staged(self, staged: StagedObject, *, max_bytes: int) -> bytes:
        temporary_path = self._staged_path(staged)
        if staged.byte_size > max_bytes:
            raise PayloadTooLargeError("Staged object exceeds configured byte limit")
        value = await asyncio.to_thread(temporary_path.read_bytes)
        if len(value) != staged.byte_size:
            raise ValidationError("Staged object size changed before commit")
        if hashlib.sha256(value).hexdigest() != staged.content_sha256:
            raise ValidationError("Staged object hash changed before commit")
        return value

    async def commit_staged(self, staged: StagedObject) -> StoredObject:
        temporary_path = self._staged_path(staged)
        storage_key = self.storage_key_for_staged(staged)
        destination = self._safe_path(storage_key)
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        if await asyncio.to_thread(destination.exists):
            existing_size = (await asyncio.to_thread(destination.stat)).st_size
            existing_hash = await asyncio.to_thread(_file_sha256, destination)
            if existing_size != staged.byte_size or existing_hash != staged.content_sha256:
                raise ValidationError("Content-addressed object does not match its digest")
            await asyncio.to_thread(temporary_path.unlink, missing_ok=True)
            created = False
        else:
            await asyncio.to_thread(os.replace, temporary_path, destination)
            created = True
        return StoredObject(
            storage_key=storage_key,
            content_sha256=staged.content_sha256,
            byte_size=staged.byte_size,
            created=created,
        )

    async def discard_staged(self, staged: StagedObject) -> None:
        temporary_path = staged.temporary_path.resolve()
        if temporary_path.parent != self._temporary:
            raise ValidationError("Staged storage object path is invalid")
        await asyncio.to_thread(temporary_path.unlink, missing_ok=True)

    async def put_content_stream(
        self,
        namespace: str,
        source: AsyncReadable,
        *,
        max_bytes: int,
        chunk_size: int = 64 * 1024,
    ) -> StoredObject:
        staged = await self.stage_content_stream(
            namespace,
            source,
            max_bytes=max_bytes,
            chunk_size=chunk_size,
        )
        try:
            return await self.commit_staged(staged)
        except BaseException:
            await self.discard_staged(staged)
            raise

    async def put_content_bytes(
        self, namespace: str, value: bytes, *, max_bytes: int
    ) -> StoredObject:
        return await self.put_content_stream(
            namespace,
            BytesReader(value),
            max_bytes=max_bytes,
        )

    async def put_exact(self, storage_key: str, value: bytes, *, overwrite: bool = False) -> None:
        destination = self._safe_path(storage_key)
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        if not overwrite and await asyncio.to_thread(destination.exists):
            existing = await asyncio.to_thread(destination.read_bytes)
            if existing != value:
                raise ValidationError("Immutable storage key already contains different content")
            return
        file_descriptor, temporary_name = await asyncio.to_thread(
            tempfile.mkstemp,
            prefix="artifact-",
            dir=destination.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                await asyncio.to_thread(handle.write, value)
                await asyncio.to_thread(handle.flush)
                await asyncio.to_thread(os.fsync, handle.fileno())
            await asyncio.to_thread(os.replace, temporary_path, destination)
        except BaseException:
            await asyncio.to_thread(temporary_path.unlink, missing_ok=True)
            raise

    async def read_bytes(self, storage_key: str, *, max_bytes: int | None = None) -> bytes:
        source = self._safe_path(storage_key)
        if not await asyncio.to_thread(source.is_file):
            raise NotFoundError("Stored object was not found")
        if max_bytes is not None:
            size = (await asyncio.to_thread(source.stat)).st_size
            if size > max_bytes:
                raise PayloadTooLargeError("Stored object exceeds configured byte limit")
        return await asyncio.to_thread(source.read_bytes)

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(self._safe_path(storage_key).unlink, missing_ok=True)
