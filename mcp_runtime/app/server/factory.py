import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import mcp.types as types
from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import INVALID_PARAMS
from mcp_contracts import MCPManifest, RuntimeSecretBundle, ServerDefinition
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.auth.inbound import InboundAuthContext, build_inbound_auth
from app.auth.upstream import UpstreamAuthManager
from app.clients.api_client import ApiClient
from app.clients.oauth_client import OAuthTokenClient
from app.clients.oidc_client import OidcJwksClient
from app.core.config import RuntimeSettings
from app.executor.errors import ArgumentValidationError, RuntimeExecutionError
from app.executor.executor import ToolExecutor
from app.executor.response_mapper import map_runtime_error, map_upstream_result
from app.security.url_policy import UpstreamUrlPolicy
from app.server.resource_registry import ResourceRegistry
from app.server.tool_registry import ToolRegistry

logger = logging.getLogger("mcplica.runtime")
_LIST_PAGE_SIZE = 100


def _page[T](
    values: tuple[T, ...],
    cursor: str | None,
    *,
    namespace: str,
) -> tuple[list[T], str | None]:
    if cursor is None:
        offset = 0
    else:
        prefix = f"{namespace}:"
        raw_offset = cursor.removeprefix(prefix)
        if not cursor.startswith(prefix) or not raw_offset.isdigit() or len(raw_offset) > 10:
            raise MCPError(INVALID_PARAMS, "Invalid pagination cursor")
        offset = int(raw_offset)
        if offset <= 0 or offset >= len(values):
            raise MCPError(INVALID_PARAMS, "Invalid pagination cursor")
    end = min(len(values), offset + _LIST_PAGE_SIZE)
    next_cursor = f"{namespace}:{end}" if end < len(values) else None
    return list(values[offset:end]), next_cursor


def build_server(
    manifest: MCPManifest,
    executor: ToolExecutor,
    inbound_auth: InboundAuthContext,
    runtime_version: str,
) -> Server[Any]:
    tools = ToolRegistry(manifest)
    resources = ResourceRegistry(manifest)
    runtime_logger = logging.LoggerAdapter(
        logger,
        {
            "project_id": manifest.project.id,
            "build_id": manifest.build.build_id,
        },
    )

    async def list_tools(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        del ctx
        page, next_cursor = _page(
            tools.list(),
            params.cursor if params is not None else None,
            namespace="tools",
        )
        return types.ListToolsResult(
            next_cursor=next_cursor,
            tools=[
                types.Tool(
                    name=tool.name,
                    title=tool.title,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    output_schema=(
                        tool.output_schema
                        if tool.output_schema and tool.output_schema.get("type") == "object"
                        else None
                    ),
                    _meta={"operationKey": tool.operation_key},
                )
                for tool in page
            ],
        )

    async def call_tool(
        ctx: ServerRequestContext[Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        del ctx
        if tools.get(params.name) is None:
            raise MCPError(INVALID_PARAMS, f"Unknown tool: {params.name}")
        try:
            arguments = cast(dict[str, object], dict(params.arguments or {}))
            result = await executor.execute(params.name, arguments)
        except ArgumentValidationError as exc:
            raise MCPError(INVALID_PARAMS, exc.safe_message) from exc
        except RuntimeExecutionError as exc:
            runtime_logger.warning(
                "tool_call_failed",
                extra={"tool_name": params.name, "error_code": exc.code},
            )
            return map_runtime_error(exc)
        except Exception:
            runtime_logger.error(
                "tool_call_failed",
                extra={"tool_name": params.name, "error_code": "internal_runtime_error"},
            )
            return map_runtime_error(
                RuntimeExecutionError(
                    "internal_runtime_error",
                    "The runtime could not complete the tool call",
                )
            )
        return map_upstream_result(result)

    async def list_resources(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListResourcesResult:
        del ctx
        page, next_cursor = _page(
            resources.list(),
            params.cursor if params is not None else None,
            namespace="resources",
        )
        return types.ListResourcesResult(
            next_cursor=next_cursor,
            resources=[
                types.Resource(
                    uri=resource.uri,
                    name=resource.name,
                    description=resource.description,
                    mime_type=resource.mime_type,
                    size=len(resource.content.encode("utf-8")),
                )
                for resource in page
            ],
        )

    async def read_resource(
        ctx: ServerRequestContext[Any], params: types.ReadResourceRequestParams
    ) -> types.ReadResourceResult:
        del ctx
        resource = resources.get(str(params.uri))
        if resource is None:
            raise MCPError(INVALID_PARAMS, "Unknown resource URI")
        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=resource.uri,
                    mime_type=resource.mime_type,
                    text=resource.content,
                )
            ]
        )

    @asynccontextmanager
    async def lifespan(_: Server[Any]) -> AsyncGenerator[dict[str, object]]:
        try:
            yield {}
        finally:
            await executor.close()
            await inbound_auth.close()

    return Server(
        f"MCPlica:{manifest.project.slug}",
        version=runtime_version,
        description=f"MCPlica-generated MCP server for {manifest.project.name}",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        on_list_resources=list_resources,
        on_read_resource=read_resource,
        lifespan=lifespan,
    )


def build_app(
    manifest: MCPManifest,
    secret_bundle: RuntimeSecretBundle,
    settings: RuntimeSettings,
) -> Starlette:
    network = secret_bundle.network_policy
    api_policy = UpstreamUrlPolicy(
        manifest.servers,
        allowed_private_hosts=network.allowed_private_hosts,
        allowed_development_hosts=network.allowed_development_hosts,
        development_mode=settings.is_development,
    )
    oauth_servers = list(manifest.servers)
    for profile in manifest.auth_profiles:
        if profile.type == "oauth2_client_credentials" and profile.token_url:
            oauth_servers.append(
                ServerDefinition(id=f"oauth-token-{profile.id}", url=profile.token_url)
            )
    oauth_policy = UpstreamUrlPolicy(
        oauth_servers,
        allowed_private_hosts=network.allowed_private_hosts,
        allowed_development_hosts=network.allowed_development_hosts,
        development_mode=settings.is_development,
    )
    api_client = ApiClient(
        api_policy,
        max_connections=settings.http_max_connections,
        max_keepalive_connections=settings.http_max_keepalive_connections,
        keepalive_expiry_seconds=settings.http_keepalive_expiry_seconds,
        connect_timeout_seconds=settings.http_connect_timeout_seconds,
        read_timeout_seconds=settings.http_read_timeout_seconds,
        write_timeout_seconds=settings.http_write_timeout_seconds,
        pool_timeout_seconds=settings.http_pool_timeout_seconds,
        max_request_bytes=settings.max_upstream_request_bytes,
        tls_verify=settings.tls_verify,
        trust_env=settings.trust_environment_proxy,
    )
    oauth_client = OAuthTokenClient(
        oauth_policy,
        tls_verify=settings.tls_verify,
        trust_env=settings.trust_environment_proxy,
    )
    auth_manager = UpstreamAuthManager(manifest, secret_bundle, oauth_client)
    oidc_client: OidcJwksClient | None = None
    if secret_bundle.inbound_auth.mode == "external_oauth_oidc":
        assert secret_bundle.inbound_auth.issuer_url is not None
        oidc_client = OidcJwksClient(
            issuer_url=str(secret_bundle.inbound_auth.issuer_url),
            configured_jwks_url=(
                str(secret_bundle.inbound_auth.jwks_url)
                if secret_bundle.inbound_auth.jwks_url is not None
                else None
            ),
            policy=api_policy,
            tls_verify=settings.tls_verify,
            trust_env=settings.trust_environment_proxy,
        )
    inbound_auth = build_inbound_auth(
        secret_bundle,
        settings,
        oidc_client=oidc_client,
    )
    executor = ToolExecutor(manifest, api_client, auth_manager, api_policy)
    server = build_server(manifest, executor, inbound_auth, settings.runtime_version)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "mcplica-runtime",
                "project": manifest.project.slug,
            }
        )

    async def ready(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "ready": True,
                "manifest_id": manifest.manifest_id,
                "build_id": manifest.build.build_id,
                "deployment_id": (
                    str(settings.deployment_id) if settings.deployment_id is not None else None
                ),
                "runtime_version": settings.runtime_version,
            }
        )

    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.allowed_host_list,
        allowed_origins=settings.allowed_origin_list,
    )
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        max_request_body_size=settings.max_mcp_request_bytes,
        transport_security=transport_security,
        auth=inbound_auth.settings,
        token_verifier=inbound_auth.verifier,
        custom_starlette_routes=[
            Route("/healthz", endpoint=health, methods=["GET"]),
            Route("/readyz", endpoint=ready, methods=["GET"]),
        ],
    )
    app.state.manifest = manifest
    app.state.secret_bundle_loaded = True
    return app
