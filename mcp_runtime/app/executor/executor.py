from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as validate_json
from mcp_contracts import MCPManifest, MCPTool

from app.auth.upstream import build_auth
from app.clients.api_client import ApiClient, UpstreamResult
from app.executor.request_builder import build_request


class ToolExecutor:
    def __init__(self, manifest: MCPManifest, api_client: ApiClient) -> None:
        self.manifest = manifest
        self.api_client = api_client
        self.tools = {tool.name: tool for tool in manifest.enabled_tools()}
        self.servers = {server.id: server for server in manifest.servers}
        self.auth_profiles = {profile.id: profile for profile in manifest.auth_profiles}

    async def execute(self, tool_name: str, arguments: dict) -> UpstreamResult:
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown or disabled tool: {tool_name}")
        try:
            validate_json(instance=arguments, schema=tool.input_schema)
        except JSONSchemaValidationError as exc:
            raise ValueError(f"Invalid tool arguments: {exc.message}") from exc
        server = self.servers[tool.request_mapping.server_ref]
        profile = self.auth_profiles.get(tool.security_profile_ref) if tool.security_profile_ref else None
        request = build_request(tool, arguments, server, build_auth(profile))
        return await self.api_client.execute(
            request,
            timeout_ms=tool.timeout_ms,
            max_response_bytes=tool.max_response_bytes,
        )
