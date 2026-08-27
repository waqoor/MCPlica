import asyncio
import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from mcp_contracts import RuntimeSecretBundle

from app.clients.base import AsyncClient
from app.core.exceptions import SecretMaterializationError


@dataclass(frozen=True, slots=True)
class RuntimeMounts:
    manifest_path: str
    secret_bundle_path: str
    auth_overlay_sha256: str


class RuntimeFilesClient(AsyncClient):
    """Deployment-worker-only, host-visible runtime mount storage."""

    def __init__(
        self,
        worker_root: str,
        *,
        docker_host_root: str,
        runtime_uid: int,
        runtime_gid: int,
        max_manifest_bytes: int = 10_000_000,
        max_secret_bundle_bytes: int = 1_000_000,
    ) -> None:
        self._root = Path(os.path.abspath(worker_root))
        self._docker_host_root = docker_host_root.rstrip("/\\")
        if not self._docker_host_root or any(
            character in self._docker_host_root for character in "\r\n\x00"
        ):
            raise ValueError("Docker host runtime root is invalid")
        self._runtime_uid = runtime_uid
        self._runtime_gid = runtime_gid
        self._max_manifest_bytes = max_manifest_bytes
        self._max_secret_bundle_bytes = max_secret_bundle_bytes

    async def health(self) -> bool:
        try:
            return await asyncio.to_thread(self._ensure_root)
        except OSError:
            return False

    async def materialize(
        self,
        deployment_id: UUID,
        *,
        manifest_bytes: bytes,
        manifest_sha256: str,
        secret_bundle: RuntimeSecretBundle,
    ) -> RuntimeMounts:
        try:
            return await asyncio.to_thread(
                self._materialize,
                deployment_id,
                manifest_bytes,
                manifest_sha256,
                secret_bundle,
            )
        except SecretMaterializationError:
            raise
        except (OSError, ValueError) as exc:
            raise SecretMaterializationError(
                "Runtime secret material could not be written securely"
            ) from exc

    async def remove(self, deployment_id: UUID) -> None:
        try:
            await asyncio.to_thread(self._remove, deployment_id)
        except OSError as exc:
            raise SecretMaterializationError(
                "Runtime secret material could not be removed"
            ) from exc

    def _ensure_root(self) -> bool:
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root_status = os.lstat(self._root)
        if not stat.S_ISDIR(root_status.st_mode) or stat.S_ISLNK(root_status.st_mode):
            raise SecretMaterializationError("Runtime mount root must be a real directory")
        os.chmod(self._root, 0o700)
        return self._root.is_dir()

    def _deployment_path(self, deployment_id: UUID) -> Path:
        target = self._root / str(deployment_id)
        if target.parent != self._root:
            raise SecretMaterializationError("Runtime mount path escapes configured root")
        return target

    def _materialize(
        self,
        deployment_id: UUID,
        manifest_bytes: bytes,
        manifest_sha256: str,
        secret_bundle: RuntimeSecretBundle,
    ) -> RuntimeMounts:
        if len(manifest_bytes) > self._max_manifest_bytes:
            raise SecretMaterializationError("Runtime manifest exceeds its configured limit")
        secret_bytes = secret_bundle.serialize_for_secret_mount()
        auth_overlay_sha256 = hashlib.sha256(secret_bytes).hexdigest()
        if len(secret_bytes) > self._max_secret_bundle_bytes:
            raise SecretMaterializationError("Runtime secret bundle exceeds its configured limit")
        if hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256:
            raise SecretMaterializationError("Build manifest hash verification failed")
        self._ensure_root()
        directory = self._deployment_path(deployment_id)
        directory.mkdir(mode=0o700, exist_ok=True)
        directory_status = os.lstat(directory)
        if not stat.S_ISDIR(directory_status.st_mode) or stat.S_ISLNK(directory_status.st_mode):
            raise SecretMaterializationError("Runtime deployment mount must be a real directory")
        os.chmod(directory, 0o700)
        self._set_owner(directory)
        manifest_path = directory / "manifest.json"
        secret_path = directory / "runtime-secrets.json"
        self._write_exact(manifest_path, manifest_bytes, mode=0o600)
        self._write_exact(secret_path, secret_bytes, mode=0o600)
        host_directory = f"{self._docker_host_root}/{deployment_id}"
        return RuntimeMounts(
            f"{host_directory}/manifest.json",
            f"{host_directory}/runtime-secrets.json",
            auth_overlay_sha256,
        )

    def _write_exact(self, destination: Path, value: bytes, *, mode: int) -> None:
        if destination.exists():
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(destination, flags)
            with os.fdopen(descriptor, "rb") as handle:
                file_status = os.fstat(handle.fileno())
                existing = handle.read(len(value) + 1)
            if not stat.S_ISREG(file_status.st_mode):
                raise SecretMaterializationError("Runtime mount file is not a regular file")
            if os.name == "posix" and (
                stat.S_IMODE(file_status.st_mode) != mode
                or file_status.st_uid != self._runtime_uid
                or file_status.st_gid != self._runtime_gid
            ):
                raise SecretMaterializationError("Runtime mount file ownership is invalid")
            if existing != value:
                raise SecretMaterializationError(
                    "Immutable runtime mount already contains different content"
                )
            return
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", dir=destination.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            self._set_owner(temporary)
            os.replace(temporary, destination)
            if os.name == "posix":
                directory_descriptor = os.open(
                    destination.parent,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                )
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
        finally:
            temporary.unlink(missing_ok=True)

    def _set_owner(self, path: Path) -> None:
        if os.name == "posix":
            os.chown(path, self._runtime_uid, self._runtime_gid)

    def _remove(self, deployment_id: UUID) -> None:
        directory = self._deployment_path(deployment_id)
        if not directory.exists():
            return
        directory_status = os.lstat(directory)
        if not stat.S_ISDIR(directory_status.st_mode) or stat.S_ISLNK(directory_status.st_mode):
            raise SecretMaterializationError("Runtime deployment mount is not a real directory")
        for name in ("manifest.json", "runtime-secrets.json"):
            (directory / name).unlink(missing_ok=True)
        directory.rmdir()
