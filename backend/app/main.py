from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.clients.ai import OpenRouterClient
from app.clients.cache import RedisClient
from app.clients.database import DatabaseClient
from app.clients.storage import FilesystemStorageClient
from app.clients.vector import MilvusVectorClient
from app.core.config import get_settings
from app.core.exceptions import MCPlicaError
from app.core.logging import configure_logging
from app.repositories.projects import ProjectRepository
from app.services.projects import ProjectService

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.database = DatabaseClient(settings.database_url)
    app.state.redis = RedisClient(settings.redis_url)
    app.state.milvus = MilvusVectorClient(settings.milvus_uri, settings.milvus_token)
    app.state.openrouter = OpenRouterClient(
        settings.openrouter_api_key,
        settings.openrouter_base_url,
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
    )
    app.state.storage = FilesystemStorageClient(settings.artifact_root)
    app.state.project_service = ProjectService(ProjectRepository())
    try:
        yield
    finally:
        await app.state.database.close()
        await app.state.redis.close()
        await app.state.openrouter.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="MCPlica API",
        version="0.1.0",
        description="Self-hosted API-to-MCP builder/control plane",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(MCPlicaError)
    async def handle_domain_error(request: Request, exc: MCPlicaError) -> JSONResponse:
        status_code = 404 if exc.code == "NOT_FOUND" else 409 if exc.code == "CONFLICT" else 400
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "details": {},
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    app.include_router(router)
    return app


app = create_app()
