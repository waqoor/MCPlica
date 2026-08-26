from pathlib import Path

from app.clients.base import AsyncClient


class FilesystemStorageClient(AsyncClient):
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def health(self) -> bool:
        return self.root.exists() and self.root.is_dir()

    def _safe_path(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError("artifact path escapes configured root")
        return target

    def write_bytes(self, relative_path: str, data: bytes) -> Path:
        target = self._safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def read_bytes(self, relative_path: str) -> bytes:
        return self._safe_path(relative_path).read_bytes()
