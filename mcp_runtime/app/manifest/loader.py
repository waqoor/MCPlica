import hashlib
import hmac
import os
import stat
from pathlib import Path

from mcp_contracts import MCPManifest

from app.manifest.schema import validate_manifest


def _read_bounded(path: Path, max_bytes: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("manifest path must reference a regular file")
        payload = handle.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("manifest exceeds configured size limit")
    return payload


def load_manifest(
    path: str,
    *,
    expected_sha256: str | None = None,
    max_bytes: int = 10_000_000,
    runtime_version: str = "1.0.0",
) -> MCPManifest:
    payload = _read_bounded(Path(path), max_bytes)
    if expected_sha256 is not None:
        normalized = expected_sha256.removeprefix("sha256:").lower()
        if not re_fullmatch_sha256(normalized):
            raise ValueError("configured manifest SHA-256 is invalid")
        actual = hashlib.sha256(payload).hexdigest()
        if not hmac.compare_digest(actual, normalized):
            raise ValueError("manifest SHA-256 verification failed")
    manifest = MCPManifest.model_validate_json(payload)
    validate_manifest(manifest, runtime_version=runtime_version)
    return manifest


def re_fullmatch_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
