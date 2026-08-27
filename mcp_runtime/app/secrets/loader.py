import hashlib
import hmac
import os
import stat
from pathlib import Path

from mcp_contracts import RuntimeSecretBundle


def load_secret_bundle(
    path: str,
    *,
    max_bytes: int = 1_000_000,
    require_secure_permissions: bool = True,
    expected_sha256: str | None = None,
) -> RuntimeSecretBundle:
    bundle_path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(bundle_path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        file_status = os.fstat(handle.fileno())
        if not stat.S_ISREG(file_status.st_mode):
            raise ValueError("runtime secret bundle must be a regular file")
        if require_secure_permissions and os.name == "posix":
            mode = stat.S_IMODE(file_status.st_mode)
            if mode & 0o077:
                raise ValueError("runtime secret bundle permissions are too broad")
            if file_status.st_uid != os.geteuid():
                raise ValueError("runtime secret bundle must be owned by the runtime user")
        payload = handle.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("runtime secret bundle exceeds configured size limit")
    if expected_sha256 is not None:
        expected = expected_sha256.removeprefix("sha256:").lower()
        if not expected or not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), expected):
            raise ValueError("runtime deployment authentication overlay hash mismatch")
    return RuntimeSecretBundle.model_validate_json(payload)
