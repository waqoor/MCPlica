import asyncio
import logging
import secrets
import time
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit
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
from app.core.lifecycle import DispatcherGroup, register_bounded_close
from app.core.logging import configure_logging
from app.core.network_policy import UrlPolicy
from app.core.request_limits import MultipartSpoolLimitMiddleware
from app.observability import observe_http_request, render_metrics
from app.observability.metrics import METRICS_CONTENT_TYPE
from app.providers.ai.openrouter import OpenRouterProvider
from app.providers.milvus import MilvusVectorStore
from app.providers.storage import FilesystemArtifactStorage
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.build_admission import BuildAdmissionRepository
from app.repositories.builds import BuildAIRunRepository, BuildRepository
from app.repositories.canonical import CanonicalRepository
from app.repositories.cleanup import CleanupRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.indexing import IndexGenerationRepository
from app.repositories.mcp_access import MCPAccessRepository
from app.repositories.projects import ProjectRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.repositories.settings import SettingsRepository
from app.repositories.sources import SourceRepository
from app.repositories.users import UserRepository
from app.repositories.validation import ValidationRepository
from app.services.artifacts import ArtifactService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.build_admission import BuildAdmissionDispatcher
from app.services.builds import BuildService
from app.services.builds.configuration_identity import ExecutableConfigurationIdentity
from app.services.canonicalization import CanonicalizationService
from app.services.cleanup import CleanupService, CleanupWorker
from app.services.credentials import CredentialService
from app.services.deployment.command_dispatcher import RuntimeCommandDispatcher
from app.services.deployment.preflight import DeploymentPreflight
from app.services.deployment.service import DeploymentService
from app.services.journey import JourneyService
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
        previous_encoded_keys={
            version: key.get_secret_value()
            for version, key in config.secret_encryption_previous_keys.items()
        },
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


@dataclass(slots=True)
class _AppClients:
    database: DatabaseClient
    redis: RedisClient
    deployment_queue: DeploymentQueueClient
    build_queue: BuildQueueClient
    http: HttpClient
    milvus: MilvusVectorClient
    storage: FilesystemStorageClient
    stack: AsyncExitStack

    async def close(self) -> None:
        await self.stack.aclose()


async def _create_app_clients(config: Settings) -> _AppClients:
    """Acquire clients transactionally and register cleanup immediately."""

    stack = AsyncExitStack()
    await stack.__aenter__()
    try:
        database = DatabaseClient(
            config.database_url,
            pool_size=config.database_pool_size,
            max_overflow=config.database_max_overflow,
            pool_timeout_seconds=config.database_pool_timeout_seconds,
        )
        register_bounded_close(
            stack,
            name="database",
            callback=database.close,
            timeout_seconds=config.shutdown_timeout_seconds,
        )
        redis = RedisClient(
            config.redis_url,
            socket_connect_timeout_seconds=config.redis_socket_connect_timeout_seconds,
            socket_timeout_seconds=config.redis_socket_timeout_seconds,
        )
        register_bounded_close(
            stack,
            name="redis",
            callback=redis.close,
            timeout_seconds=config.shutdown_timeout_seconds,
        )
        deployment_queue = DeploymentQueueClient(
            config.redis_url,
            config.deployment_queue_name,
            job_timeout_seconds=config.deployment_job_timeout_seconds,
            max_attempts=config.deployment_job_max_attempts,
            socket_connect_timeout_seconds=config.redis_socket_connect_timeout_seconds,
            socket_timeout_seconds=config.redis_socket_timeout_seconds,
        )
        register_bounded_close(
            stack,
            name="deployment-queue",
            callback=deployment_queue.close,
            timeout_seconds=config.shutdown_timeout_seconds,
        )
        build_queue = BuildQueueClient(
            config.redis_url,
            config.build_queue_name,
            job_timeout_seconds=config.build_job_timeout_seconds,
            max_attempts=config.build_job_max_attempts,
            socket_connect_timeout_seconds=config.redis_socket_connect_timeout_seconds,
            socket_timeout_seconds=config.redis_socket_timeout_seconds,
        )
        register_bounded_close(
            stack,
            name="build-queue",
            callback=build_queue.close,
            timeout_seconds=config.shutdown_timeout_seconds,
        )
        http = HttpClient(timeout_seconds=config.fetch_timeout_seconds)
        register_bounded_close(
            stack,
            name="http",
            callback=http.close,
            timeout_seconds=config.shutdown_timeout_seconds,
        )
        milvus = MilvusVectorClient(config.milvus_uri, config.milvus_token)
        register_bounded_close(
            stack,
            name="milvus",
            callback=milvus.close,
            timeout_seconds=config.shutdown_timeout_seconds,
        )
        storage = FilesystemStorageClient(config.artifact_root)
        register_bounded_close(
            stack,
            name="storage",
            callback=storage.close,
            timeout_seconds=config.shutdown_timeout_seconds,
        )
    except BaseException:
        await stack.aclose()
        raise
    return _AppClients(
        database=database,
        redis=redis,
        deployment_queue=deployment_queue,
        build_queue=build_queue,
        http=http,
        milvus=milvus,
        storage=storage,
        stack=stack,
    )


def create_app(settings_override: Settings | None = None) -> FastAPI:
    config = settings_override or get_settings()
    _validate_api_security(config)
    configure_logging(config.log_level, json_logs=config.is_production)
    request_logger = logging.getLogger("mcplica.api")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        clients = await _create_app_clients(config)
        database = clients.database
        redis = clients.redis
        deployment_queue = clients.deployment_queue
        build_queue = clients.build_queue
        http = clients.http
        milvus = clients.milvus

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
        storage = clients.storage
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
        runtime_commands = RuntimeCommandRepository()
        cleanup_repository = CleanupRepository()
        build_admission_repository = BuildAdmissionRepository()
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
        runtime_command_dispatcher = RuntimeCommandDispatcher(
            database,
            runtime_commands,
            deployment_queue,
            interval_seconds=config.runtime_command_dispatch_interval_seconds,
            lease_seconds=config.runtime_command_dispatch_lease_seconds,
        )
        cleanup_worker = CleanupWorker(
            database,
            cleanup_repository,
            audit,
            artifact_storage,
            MilvusVectorStore(milvus, config.milvus_collection),
            settings_service,
            interval_seconds=config.cleanup_dispatch_interval_seconds,
            lease_seconds=config.cleanup_lease_seconds,
            max_attempts=config.cleanup_max_attempts,
            retention_interval_seconds=config.cleanup_retention_interval_seconds,
        )
        cleanup_service = CleanupService(
            database,
            cleanup_repository,
            audit,
            orphan_guard_delay_seconds=config.cleanup_orphan_guard_delay_seconds,
            notify=cleanup_worker.wake,
        )
        build_admission = BuildAdmissionDispatcher(
            database,
            build_admission_repository,
            build_queue,
            settings_service,
            audit,
            interval_seconds=config.build_admission_dispatch_interval_seconds,
            lease_seconds=config.build_admission_lease_seconds,
        )
        deployment_preflight = DeploymentPreflight(
            mcp_access,
            credentials,
            ExecutableConfigurationIdentity(projects, sources),
            artifact_storage,
            config,
            manifest_max_bytes=config.runtime_manifest_max_bytes,
        )
        deployment_service = DeploymentService(
            database,
            deployments,
            runtime_commands,
            audit,
            runtime_command_dispatcher,
            deployment_preflight,
            config,
        )
        canonicalization = CanonicalizationService(
            database,
            projects,
            sources,
            snapshots,
            artifact_storage,
        )
        source_service = SourceService(
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
            canonicalization=canonicalization,
            document_max_bytes=config.document_max_bytes,
            fetch_max_bytes=config.fetch_max_bytes,
            fetch_max_redirects=config.fetch_max_redirects,
            fetch_max_attempts=config.fetch_max_attempts,
            cleanup=cleanup_service,
        )
        mcp_access_service = MCPAccessService(
            database,
            mcp_access,
            deployments,
            runtime_commands,
            audit,
            deployment_service,
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
                runtime_commands,
                deployment_service,
                settings_service,
                cleanup_service,
            ),
            sources=source_service,
            credentials=CredentialService(
                database,
                credentials,
                projects,
                runtime_commands,
                audit,
                secret_cipher,
                deployment_service,
                source_configuration=source_service,
            ),
            audit=AuditService(database, audit),
            deployments=deployment_service,
            journey=JourneyService(
                database,
                projects,
                sources,
                builds,
                validation,
                credentials,
                deployments,
                source_service,
                mcp_access_service,
                deployment_preflight,
                settings_service,
                config,
            ),
            mcp_access=mcp_access_service,
            settings=settings_service,
            ai=ai,
            build_admission=build_admission,
            builds=BuildService(
                database,
                builds,
                ai_runs,
                snapshots,
                sources,
                source_service,
                projects,
                credentials,
                validation,
                audit,
                settings_service,
                build_queue,
                config,
                ArtifactService(artifact_storage),
                cleanup_service,
                build_admission,
            ),
            cleanup=cleanup_service,
        )
        dispatchers = DispatcherGroup(timeout_seconds=config.shutdown_timeout_seconds)
        runtime_command_stop = asyncio.Event()
        runtime_command_task = asyncio.create_task(
            runtime_command_dispatcher.run(runtime_command_stop),
            name="runtime-command-dispatcher",
        )
        dispatchers.add(
            name="runtime-command-dispatcher",
            task=runtime_command_task,
            stop_event=runtime_command_stop,
            wake=runtime_command_dispatcher.wake,
        )
        runtime_command_dispatcher.wake()
        cleanup_stop = asyncio.Event()
        cleanup_task = asyncio.create_task(
            cleanup_worker.run(cleanup_stop),
            name="cleanup-dispatcher",
        )
        dispatchers.add(
            name="cleanup-dispatcher",
            task=cleanup_task,
            stop_event=cleanup_stop,
            wake=cleanup_worker.wake,
        )
        cleanup_worker.wake()
        build_admission_stop = asyncio.Event()
        build_admission_task = asyncio.create_task(
            build_admission.run(build_admission_stop),
            name="build-admission-dispatcher",
        )
        dispatchers.add(
            name="build-admission-dispatcher",
            task=build_admission_task,
            stop_event=build_admission_stop,
            wake=build_admission.wake,
        )
        build_admission.wake()
        try:
            yield
        finally:
            await dispatchers.shutdown()
            await clients.close()

    app = FastAPI(
        title="MCPlica API",
        version="0.1.0",
        description="Self-hosted API-to-MCP builder/control plane",
        lifespan=lifespan,
    )
    app.state.settings = config
    app.add_middleware(
        MultipartSpoolLimitMiddleware,
        request_max_bytes=config.upload_max_bytes + 1_048_576,
        capacity_bytes=config.multipart_spool_capacity_bytes,
    )
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
            allowed_hosts=[
                config.api_domain,
                urlsplit(config.frontend_origin).hostname or config.api_domain,
                "127.0.0.1",
                "localhost",
            ],
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
