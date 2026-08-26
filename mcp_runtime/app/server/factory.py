import json
from contextlib import asynccontextmanager
from typing import Any

import mcp.types as types
from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import INVALID_PARAMS
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_contracts import MCPManifest

from app.clients.api_client import ApiClient
from app.core.config import RuntimeSettings
from app.executor.executor import ToolExecutor
from app.server.auth_middleware import StaticBearerMiddleware


def build_server(manifest: MCPManifest, api_client: ApiClient) -> Server[Any]:
    executor = ToolExecutor(manifest, api_client)
    tools_by_name = {tool.name: tool for tool in manifest.enabled_tools()}

    async def list_tools(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.name,
                    title=tool.title,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    # MCP structured output is object-shaped. Preserve non-object
                    # response schemas in the manifest, but do not advertise them as
                    # structuredContent contracts.
                    output_schema=(
                        tool.output_schema
                        if tool.output_schema and tool.output_schema.get("type") == "object"
                        else None
                    ),
                )
                for tool in tools_by_name.values()
            ]
        )

    async def call_tool(
        ctx: ServerRequestContext[Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        if params.name not in tools_by_name:
            raise MCPError(INVALID_PARAMS, f"Unknown tool: {params.name}")
        try:
            result = await executor.execute(params.name, dict(params.arguments or {}))
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except Exception as exc:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Upstream execution failed: {type(exc).__name__}")],
                is_error=True,
            )

        if isinstance(result.data, dict):
            text = json.dumps(result.data, ensure_ascii=False)
            structured = result.data
        else:
            text = str(result.data)
            structured = None
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
            structured_content=structured,
            is_error=result.is_error,
            _meta={"httpStatus": result.status_code, "contentType": result.content_type},
        )

    @asynccontextmanager
    async def lifespan(_: Server[Any]):
        try:
            yield {}
        finally:
            await api_client.close()

    return Server(
        f"MCPlica:{manifest.project.slug}",
        version="0.1.0",
        description=f"MCPlica-generated MCP server for {manifest.project.name}",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        lifespan=lifespan,
    )


def build_app(manifest: MCPManifest, settings: RuntimeSettings):
    api_client = ApiClient()
    server = build_server(manifest, api_client)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "mcplica-runtime", "project": manifest.project.slug})

    async def ready(_: Request) -> JSONResponse:
        return JSONResponse({"ready": True, "manifest_id": manifest.manifest_id})

    transport_security = TransportSecuritySettings(
        allowed_hosts=settings.allowed_host_list,
        allowed_origins=settings.allowed_origin_list,
    )
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=transport_security,
        custom_starlette_routes=[
            Route("/healthz", endpoint=health, methods=["GET"]),
            Route("/readyz", endpoint=ready, methods=["GET"]),
        ],
    )
    auth_required = manifest.security.inbound_auth_mode == "static_bearer"
    app.add_middleware(
        StaticBearerMiddleware,
        token=settings.inbound_bearer_token,
        auth_required=auth_required,
    )
    app.state.api_client = api_client
    return app
