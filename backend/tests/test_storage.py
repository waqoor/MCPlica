from pathlib import Path

import pytest

from app.clients.storage import BytesReader, FilesystemStorageClient
from app.core.exceptions import PayloadTooLargeError, ValidationError


@pytest.mark.asyncio
async def test_filesystem_storage_is_content_addressed_immutable_and_bounded(
    tmp_path: Path,
) -> None:
    storage = FilesystemStorageClient(str(tmp_path))
    first = await storage.put_content_stream(
        "sources",
        BytesReader(b"hello"),
        max_bytes=5,
    )
    second = await storage.put_content_stream(
        "sources",
        BytesReader(b"hello"),
        max_bytes=5,
    )
    assert first.storage_key == second.storage_key
    assert first.created is True
    assert second.created is False
    assert await storage.read_bytes(first.storage_key) == b"hello"

    with pytest.raises(PayloadTooLargeError):
        await storage.put_content_stream("sources", BytesReader(b"toolarge"), max_bytes=3)
    with pytest.raises(ValidationError):
        await storage.read_bytes("../outside")


@pytest.mark.asyncio
async def test_exact_artifact_write_rejects_content_change(tmp_path: Path) -> None:
    storage = FilesystemStorageClient(str(tmp_path))
    await storage.put_exact("builds/one/manifest.json", b"first")
    await storage.put_exact("builds/one/manifest.json", b"first")
    with pytest.raises(ValidationError, match="different content"):
        await storage.put_exact("builds/one/manifest.json", b"second")


@pytest.mark.asyncio
async def test_staged_upload_is_not_committed_until_validation(tmp_path: Path) -> None:
    storage = FilesystemStorageClient(str(tmp_path))
    staged = await storage.stage_content_stream(
        "sources",
        BytesReader(b"unvalidated"),
        max_bytes=100,
    )
    assert staged.temporary_path.is_file()
    assert await storage.read_staged(staged, max_bytes=100) == b"unvalidated"
    assert not list((tmp_path / "sources").rglob("*"))
    await storage.discard_staged(staged)
    assert not staged.temporary_path.exists()
