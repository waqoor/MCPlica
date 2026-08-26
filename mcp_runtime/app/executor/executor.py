from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from mcp_contracts import MCPManifest

from app.auth.upstream import UpstreamAuthManager
from app.clients.api_client import ApiClient, UpstreamResult
from app.executor.errors import ArgumentValidationError, RuntimeConfigurationError
from app.executor.request_builder import build_request
from app.security.url_policy import UpstreamUrlPolicy


class ToolExecutor:
    def __init__(
        self,
        manifest: MCPManifest,
        api_client: ApiClient,
        auth_manager: UpstreamAuthManager,
        url_policy: UpstreamUrlPolicy,
    ) -> None:
        self._api_client = api_client
        self._auth_manager = auth_manager
        self._url_policy = url_policy
        self._tools = {tool.name: tool for tool in manifest.enabled_tools()}
        self._validators: dict[str, Draft202012Validator] = {}
        for name, tool in self._tools.items():
            try:
                Draft202012Validator.check_schema(tool.input_schema)
            except SchemaError as exc:
                raise RuntimeConfigurationError(
                    f"Tool {name!r} has an invalid input schema"
                ) from exc
            self._validators[name] = Draft202012Validator(tool.input_schema)

    async def execute(self, tool_name: str, arguments: dict[str, object]) -> UpstreamResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ArgumentValidationError(f"Unknown or disabled tool: {tool_name}")
        try:
            # jsonschema's public validator is typed as a partially unknown overload.
            self._validators[tool_name].validate(arguments)  # pyright: ignore[reportUnknownMemberType]
        except JSONSchemaValidationError as exc:
            path = ".".join(str(part) for part in exc.absolute_path)
            location = f" at {path}" if path else ""
            raise ArgumentValidationError(f"Invalid tool arguments{location}") from exc
        auth = await self._auth_manager.injection_for(tool.security_profile_ref)
        request = build_request(tool, arguments, self._url_policy, auth)
        return await self._api_client.execute(
            request,
            timeout_ms=tool.timeout_ms,
            max_request_bytes=tool.max_request_bytes,
            max_response_bytes=tool.max_response_bytes,
        )

    async def close(self) -> None:
        await self._api_client.close()
        await self._auth_manager.close()
