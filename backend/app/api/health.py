from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mcplica-api"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    database_ok = await request.app.state.database.health()
    redis_ok = await request.app.state.redis.health()
    # Milvus/OpenRouter are build-time dependencies and are reported but do not prevent API liveness.
    milvus_ok = await request.app.state.milvus.health()
    openrouter_ok = await request.app.state.openrouter.health()
    ready_value = database_ok and redis_ok
    return {
        "ready": ready_value,
        "dependencies": {
            "postgres": database_ok,
            "redis": redis_ok,
            "milvus": milvus_ok,
            "openrouter": openrouter_ok,
        },
    }
