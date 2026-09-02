import asyncio
from collections.abc import Awaitable

from fastapi import APIRouter, Request, Response, status
from mcp_contracts import VERSION

from app.schemas.health import HealthRead, ReadinessDependenciesRead, ReadinessRead

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthRead)
async def health() -> HealthRead:
    return HealthRead(status="ok", service="mcplica-api", version=VERSION)


async def _bounded_health(check: Awaitable[bool], timeout_seconds: float) -> bool:
    try:
        return await asyncio.wait_for(check, timeout=timeout_seconds)
    except Exception:
        return False


@router.get("/ready", response_model=ReadinessRead)
async def ready(request: Request, response: Response) -> ReadinessRead:
    timeout = request.app.state.settings.readiness_timeout_seconds
    (
        database_ok,
        redis_ok,
        storage_ok,
        queue_ok,
        milvus_ok,
        openrouter_ok,
    ) = await asyncio.gather(
        _bounded_health(request.app.state.database.health(), timeout),
        _bounded_health(request.app.state.redis.health(), timeout),
        _bounded_health(request.app.state.storage.health(), timeout),
        _bounded_health(request.app.state.build_queue.health(), timeout),
        _bounded_health(request.app.state.milvus.health(), timeout),
        _bounded_health(request.app.state.openrouter.health(), timeout),
    )
    # OpenRouter and Milvus are builder dependencies; their outage must not disable
    # control-plane access to existing projects or already-deployed runtimes.
    ready_value = database_ok and redis_ok and storage_ok and queue_ok
    if not ready_value:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessRead(
        ready=ready_value,
        dependencies=ReadinessDependenciesRead(
            postgres=database_ok,
            redis=redis_ok,
            artifact_storage=storage_ok,
            build_queue=queue_ok,
            milvus=milvus_ok,
            openrouter=openrouter_ok,
        ),
    )
