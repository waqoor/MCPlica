from typing import Any

import docker

from app.clients.base import AsyncClient


class DockerClient(AsyncClient):
    """Deployment-worker-only Docker integration. Do not instantiate in public API routes."""

    def __init__(self, base_url: str) -> None:
        self.client = docker.DockerClient(base_url=base_url)

    async def health(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def run_container(self, **kwargs: Any) -> Any:
        return self.client.containers.run(**kwargs)

    def get_container(self, name: str) -> Any:
        return self.client.containers.get(name)

    async def close(self) -> None:
        self.client.close()
