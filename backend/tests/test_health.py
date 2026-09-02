from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request, Response

from app.api.health import health, ready


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    assert (await health()).model_dump() == {
        "status": "ok",
        "service": "mcplica-api",
        "version": "1.0.0",
    }


class _Dependency:
    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy

    async def health(self) -> bool:
        return self._healthy


def _request(*, storage: bool = True, openrouter: bool = False) -> Request:
    state = SimpleNamespace(
        settings=SimpleNamespace(readiness_timeout_seconds=0.1),
        database=_Dependency(True),
        redis=_Dependency(True),
        storage=_Dependency(storage),
        build_queue=_Dependency(True),
        milvus=_Dependency(False),
        openrouter=_Dependency(openrouter),
    )
    return cast(Request, SimpleNamespace(app=SimpleNamespace(state=state)))


async def test_ready_is_bounded_to_essential_control_plane_dependencies() -> None:
    response = Response()
    result = await ready(_request(), response)
    assert result.ready is True
    assert result.dependencies.model_dump() == {
        "postgres": True,
        "redis": True,
        "artifact_storage": True,
        "build_queue": True,
        "milvus": False,
        "openrouter": False,
    }
    assert response.status_code == 200

    unavailable = Response()
    assert (await ready(_request(storage=False), unavailable)).ready is False
    assert unavailable.status_code == 503
