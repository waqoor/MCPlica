import logging
import secrets
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import SecretStr
from starlette.middleware.base import RequestResponseEndpoint

from app.api.router import router
from app.clients.ai import OpenRouterClient
from app.clients.build_queue import BuildQueueClient
from app.clients.cache import RedisClient
from app.clients.database import DatabaseClient
from app.clients.http import HttpClient
from app.clients.queue import DeploymentQueueClient
from app.clients.storage import FilesystemStorageClient
from app.clients.vector import MilvusVectorClient
from app.container import ServiceContainer
from app.core.auth import PasswordManager, TokenManager, constant_time_equal
from app.core.config import Settings, get_settings
from app.core.crypto import AesGcmSecretCipher, configured_secret_cipher
from app.core.exceptions import AuthenticationError, MCPlicaError
from app.core.logging import configure_logging
from app.core.network_policy import UrlPolicy
from app.observability import observe_http_request, render_metrics
from app.observability.metrics import METRICS_CONTENT_TYPE
from app.providers.ai.openrouter import OpenRouterProvider
from app.providers.storage import FilesystemArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.builds import BuildAIRunRepository, BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.mcp_access import MCPAccessRepository
from app.repositories.projects import ProjectRepository
from app.repositories.settings import SettingsRepository
from app.repositories.sources import SourceRepository
from app.repositories.users import UserRepository
from app.repositories.validation import ValidationRepository
from app.services.artifacts import ArtifactService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.builds import BuildService
from app.services.credentials import CredentialService
from app.services.deployment.service import DeploymentService
from app.services.mcp_access import MCPAccessService
from app.services.projects import ProjectService
from app.services.settings import SettingsService
from app.services.sources import SourceService
from app.services.users import UserService


def _secret_or_ephemeral(value: SecretStr | None, *, bytes_count: int = 48) -> str:
    return value.get_secret_value() if value is not None else secrets.token_urlsafe(bytes_count)


def _cipher(config: Settings) -> AesGcmSecretCipher:
    return configured_secret_cipher(
        (
            config.secret_encryption_key.get_secret_value()
            if config.secret_encryption_key is not None
            else None
        ),
        config.secret_encryption_key_version,
        allow_ephemeral=config.env == "test",
    )


def _validate_api_security(config: Settings) -> None:
    if not config.is_production:
        return
    if not config.frontend_origin.startswith("https://"):
        raise ValueError("production API requires an HTTPS frontend_origin")
    if config.api_domain.endswith(".localhost"):
        raise ValueError("production API requires an explicit non-localhost API domain")
    token = config.metrics_bearer_token
    if token is None or len(token.get_secret_value()) < 32:
        raise ValueError("production API requires a metrics_bearer_token of at least 32 characters")


def create_app(settings_override: Settings | None = None) -> FastAPI:
    config = settings_override or get_settings()
    _validate_api_security(config)
    configure_logging(config.log_level, json_logs=config.is_production)
    request_logger = logging.getLogger("mcplica.api")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        database = DatabaseClient(
            config.database_url,
            pool_size=config.database_pool_size,
            max_overflow=config.database_max_overflow,
            pool_timeout_seconds=config.database_pool_timeout_seconds,
        )
        redis = RedisClient(config.redis_url)
        deployment_queue = DeploymentQueueClient(
            config.redis_url,
            config.deployment_queue_name,
            job_timeout_seconds=config.deployment_job_timeout_seconds,
            max_attempts=config.deployment_job_max_attempts,
        )
        build_queue = BuildQueueClient(
            config.redis_url,
            config.build_queue_name,
            job_timeout_seconds=config.build_job_timeout_seconds,
            max_attempts=config.build_job_max_attempts,
        )
        http = HttpClient(timeout_seconds=config.fetch_timeout_seconds)
        milvus = MilvusVectorClient(config.milvus_uri, config.milvus_token)

        audit = AuditRepository()
        settings_repository = SettingsRepository()
        secret_cipher = _cipher(config)
        settings_service = SettingsService(
            database,
            settings_repository,
            audit,
            secret_cipher,
            config,
        )

        async def resolve_openrouter_key() -> str | None:
            return await settings_service.resolve_openrouter_api_key()

        openrouter = OpenRouterClient(
            http,
            resolve_openrouter_key,
            config.openrouter_base_url,
            site_url=config.openrouter_site_url,
            app_name=config.openrouter_app_name,
            max_attempts=config.openrouter_max_attempts,
            timeout_seconds=config.openrouter_timeout_seconds,
        )
        ai = OpenRouterProvider(
            openrouter,
            structured_attempts=config.openrouter_structured_max_attempts,
        )
        storage = FilesystemStorageClient(config.artifact_root)
        artifact_storage = FilesystemArtifactStorage(storage)
        url_policy = UrlPolicy(
            allow_http=config.allow_http_source_urls,
            allowed_private_hosts=config.source_allowed_hosts,
            allowed_private_cidrs=config.source_allowed_private_cidrs,
            allow_special_use=config.env in {"development", "test"},
        )

        users = UserRepository()
        sessions = AuthSessionRepository()
        projects = ProjectRepository()
        sources = SourceRepository()
        builds = BuildRepository()
        ai_runs = BuildAIRunRepository()
        snapshots = CanonicalRepository()
        generations = IndexGenerationRepository()
        credentials = CredentialRepository()
        validation = ValidationRepository()
        deployments = DeploymentRepository()
        mcp_access = MCPAccessRepository()
        passwords = PasswordManager()
        tokens = TokenManager(
            signing_key=_secret_or_ephemeral(config.auth_signing_key),
            refresh_pepper=_secret_or_ephemeral(config.refresh_token_pepper),
            access_ttl_seconds=config.access_token_ttl_seconds,
        )

        app.state.settings = config
        app.state.database = database
        app.state.redis = redis
        app.state.deployment_queue = deployment_queue
        app.state.build_queue = build_queue
        app.state.http = http
        app.state.milvus = milvus
        app.state.openrouter = openrouter
        app.state.storage = storage
        deployment_service = DeploymentService(
            database,
            deployments,
            audit,
            deployment_queue,
            config,
        )
        app.state.services = ServiceContainer(
            auth=AuthService(
                database,
                redis,
                users,
                sessions,
                audit,
                passwords,
                tokens,
                refresh_ttl_seconds=config.refresh_token_ttl_seconds,
                rate_limit_attempts=config.login_rate_limit_attempts,
                rate_limit_window_seconds=config.login_rate_limit_window_seconds,
            ),
            users=UserService(database, users, sessions, audit, passwords),
            projects=ProjectService(
                database,
                projects,
                audit,
                deployment_service,
                settings_service,
            ),
            sources=SourceService(
                database,
                sources,
                projects,
                builds,
                snapshots,
                generations,
                audit,
                artifact_storage,
                http,
                url_policy,
                settings_service,
                document_max_bytes=config.document_max_bytes,
                fetch_max_bytes=config.fetch_max_bytes,
                fetch_max_redirects=config.fetch_max_redirects,
                fetch_max_attempts=config.fetch_max_attempts,
            ),
            credentials=CredentialService(
                database,
                credentials,
                projects,
                audit,
                secret_cipher,
                deployment_service,
            ),
            audit=AuditService(database, audit),
            deployments=deployment_service,
            mcp_access=MCPAccessService(
                database,
                mcp_access,
                deployments,
                audit,
                deployment_service,
                config,
            ),
            settings=settings_service,
            ai=ai,
            builds=BuildService(
                database,
                builds,
                ai_runs,
                snapshots,
                sources,
                projects,
                credentials,
                mcp_access,
                validation,
                audit,
                settings_service,
                build_queue,
                config,
                ArtifactService(artifact_storage),
            ),
        )
        try:
            yield
        finally:
            await database.close()
            await redis.close()
            await deployment_queue.close()
            await build_queue.close()
            await http.close()
            await milvus.close()
            await openrouter.close()
            await storage.close()

    app = FastAPI(
        title="MCPlica API",
        version="0.1.0",
        description="Self-hosted API-to-MCP builder/control plane",
        lifespan=lifespan,
    )
    app.state.settings = config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )
    if config.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[config.api_domain, "127.0.0.1", "localhost"],
        )

    async def request_context_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id[:120]
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request.state.request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
            return response
        finally:
            duration = time.perf_counter() - started
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", "unmatched")
            if not isinstance(route, str):
                route = "unmatched"
            observe_http_request(request.method, route, status_code, duration)
            principal = getattr(request.state, "principal", None)
            actor_id = str(principal.user.id) if principal is not None else None
            request_logger.info(
                "request.completed",
                extra={
                    "service": "mcplica-api",
                    "component": "http",
                    "request_id": request.state.request_id,
                    "actor_id": actor_id,
                    "method": request.method,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1_000, 3),
                },
            )

    app.middleware("http")(request_context_middleware)

    async def handle_domain_error(request: Request, exc: MCPlicaError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "details": exc.details,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    app.exception_handler(MCPlicaError)(handle_domain_error)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        expected = config.metrics_bearer_token
        if expected is not None:
            authorization = request.headers.get("Authorization", "")
            supplied = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
            if not supplied or not constant_time_equal(
                supplied,
                expected.get_secret_value(),
            ):
                raise AuthenticationError("Metrics authentication is required")
        return Response(content=render_metrics(), media_type=METRICS_CONTENT_TYPE)

    app.include_router(router)
    return app


app = create_app()
