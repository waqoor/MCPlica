import base64
import hashlib
import re
from collections.abc import Mapping
from typing import TypedDict, cast

from jsonschema import Draft202012Validator
from mcp import Client
from mcp.types import Resource, Tool
from mcp_contracts import (
    AuthProfile,
    MCPManifest,
    MCPTool,
    RuntimeSecretBundle,
    UpstreamCredential,
)
from mcp_contracts.json_types import JsonObject, JsonValue

from app.auth.inbound import InboundAuthContext
from app.auth.upstream import UpstreamAuthManager
from app.clients.api_client import UpstreamResult
from app.clients.oauth_client import OAuthAccessToken
from app.executor.executor import ToolExecutor
from app.executor.request_builder import BuiltRequest
from app.executor.response_contract import compile_response_contract, validate_upstream_response
from app.manifest.schema import validate_manifest
from app.security.url_policy import UpstreamUrlPolicy
from app.server.factory import build_server


class RuntimeCandidateInspection(TypedDict):
    runtime_version: str
    protocol_version: str
    manifest_sha256: str
    tool_count: int
    tools: list[str]
    resource_count: int
    resources: list[str]
    exercised_tool_count: int
    exercised_tools: list[str]
    request_mapping_count: int


class _SyntheticOAuthProvider:
    async def fetch_client_credentials(
        self,
        profile: AuthProfile,
        credential: UpstreamCredential,
    ) -> OAuthAccessToken:
        del profile, credential
        return OAuthAccessToken(value="runtime-validation-token", expires_in_seconds=300)

    async def close(self) -> None:
        return None


class _RecordingApiClient:
    def __init__(self) -> None:
        self.requests: list[BuiltRequest] = []
        self._next_result: UpstreamResult | None = None

    def prepare(self, result: UpstreamResult) -> None:
        if self._next_result is not None:
            raise RuntimeError("runtime validation response was not consumed")
        self._next_result = result

    async def execute(
        self,
        request: BuiltRequest,
        *,
        timeout_ms: int,
        max_request_bytes: int,
        max_response_bytes: int,
    ) -> UpstreamResult:
        del timeout_ms, max_request_bytes, max_response_bytes
        result = self._next_result
        if result is None:
            raise RuntimeError("runtime validation response was not prepared")
        self._next_result = None
        self.requests.append(request)
        return result

    async def close(self) -> None:
        return None


async def inspect_runtime_candidate(
    manifest: MCPManifest,
    *,
    runtime_version: str,
) -> RuntimeCandidateInspection:
    """Load and exercise a candidate through the real pinned runtime implementation."""

    validate_manifest(manifest, runtime_version=runtime_version)
    policy = UpstreamUrlPolicy(manifest.servers)
    api = _RecordingApiClient()
    auth = UpstreamAuthManager(
        manifest,
        _synthetic_secret_bundle(manifest),
        _SyntheticOAuthProvider(),
    )
    executor = ToolExecutor(manifest, api, auth, policy)
    server = build_server(
        manifest,
        executor,
        InboundAuthContext(None, None),
        runtime_version,
    )

    probes: list[tuple[MCPTool, dict[str, object], UpstreamResult]] = []
    missing_arguments: list[str] = []
    missing_responses: list[str] = []
    for tool in manifest.enabled_tools():
        arguments = _representative_arguments(tool)
        if arguments is None:
            missing_arguments.append(tool.name)
            continue
        try:
            response = _representative_response(tool)
        except ValueError:
            missing_responses.append(tool.name)
            continue
        probes.append((tool, arguments, response))
    if missing_arguments:
        raise ValueError(
            "runtime could not synthesize valid representative arguments for enabled tools: "
            f"{', '.join(missing_arguments)}"
        )
    if missing_responses:
        raise ValueError(
            "runtime could not synthesize a valid successful response for enabled tools: "
            f"{', '.join(missing_responses)}"
        )

    exercised: list[str] = []
    failed_calls: list[str] = []
    try:
        async with Client(server, mode="legacy", cache=None) as client:
            tools = await _list_tools(client)
            resources = await _list_resources(client)
            for resource in resources:
                await client.read_resource(str(resource.uri), cache_mode="bypass")
            for tool, arguments, response in probes:
                api.prepare(response)
                result = await client.call_tool(tool.name, arguments)
                if result.is_error:
                    failed_calls.append(tool.name)
                    continue
                exercised.append(tool.name)
            protocol_version = client.protocol_version
    except Exception:
        await executor.close()
        raise

    if failed_calls:
        raise ValueError(
            "runtime representative calls returned errors for enabled tools: "
            f"{', '.join(failed_calls)}"
        )

    enabled = manifest.enabled_tools()
    missing_exercises = [tool.name for tool in enabled if tool.name not in exercised]
    if missing_exercises:
        raise ValueError(
            "runtime could not synthesize and execute a valid representative call for "
            f"enabled tools: {', '.join(missing_exercises)}"
        )
    tool_names = [tool.name for tool in tools]
    expected_tool_names = [tool.name for tool in enabled]
    resource_uris = [str(resource.uri) for resource in resources]
    expected_resource_uris = [str(resource.uri) for resource in manifest.resources]
    if tool_names != expected_tool_names:
        raise ValueError("runtime tool listing differs from the candidate manifest")
    if resource_uris != expected_resource_uris:
        raise ValueError("runtime resource listing differs from the candidate manifest")
    if not protocol_version:
        raise ValueError("runtime did not negotiate an MCP protocol version")
    manifest_bytes = manifest.model_dump_json(by_alias=True).encode("utf-8")
    return {
        "runtime_version": runtime_version,
        "protocol_version": protocol_version,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "tool_count": len(tools),
        "tools": tool_names,
        "resource_count": len(resources),
        "resources": resource_uris,
        "exercised_tool_count": len(exercised),
        "exercised_tools": exercised,
        "request_mapping_count": len(api.requests),
    }


async def _list_tools(client: Client) -> list[Tool]:
    values: list[Tool] = []
    cursor: str | None = None
    while True:
        page = await client.list_tools(cursor=cursor, cache_mode="bypass")
        values.extend(page.tools)
        cursor = page.next_cursor
        if cursor is None:
            return values


async def _list_resources(client: Client) -> list[Resource]:
    values: list[Resource] = []
    cursor: str | None = None
    while True:
        page = await client.list_resources(cursor=cursor, cache_mode="bypass")
        values.extend(page.resources)
        cursor = page.next_cursor
        if cursor is None:
            return values


def _synthetic_secret_bundle(manifest: MCPManifest) -> RuntimeSecretBundle:
    profiles_by_ref: dict[str, list[AuthProfile]] = {}
    for profile in manifest.auth_profiles:
        if profile.type != "none" and profile.credential_ref is not None:
            profiles_by_ref.setdefault(profile.credential_ref, []).append(profile)

    credentials: dict[str, object] = {}
    for reference, profiles in profiles_by_ref.items():
        types = {profile.type for profile in profiles}
        if len(types) != 1:
            raise ValueError("one credential reference cannot satisfy multiple auth types")
        credential_type = profiles[0].type
        if credential_type == "bearer":
            credentials[reference] = {"type": "bearer", "token": "validation-token"}
        elif credential_type == "api_key":
            credentials[reference] = {"type": "api_key", "api_key": "validation-key"}
        elif credential_type == "basic":
            credentials[reference] = {
                "type": "basic",
                "username": "validation-user",
                "password": "validation-password",
            }
        elif credential_type == "oauth2_client_credentials":
            credentials[reference] = {
                "type": "oauth2_client_credentials",
                "client_id": "validation-client",
                "client_secret": "validation-secret",
            }
        elif credential_type == "static_header":
            names = sorted({profile.name for profile in profiles if profile.name is not None})
            credentials[reference] = {
                "type": "static_header",
                "headers": {name: "validation-header" for name in names},
            }
        else:
            raise ValueError("runtime candidate contains an unsupported authentication type")
    return RuntimeSecretBundle.model_validate(
        {
            "upstream_credentials": credentials,
            "inbound_auth": {"mode": "disabled_dev"},
        }
    )


def _representative_arguments(tool: MCPTool) -> dict[str, object] | None:
    schema = tool.input_schema
    try:
        candidate = _sample(schema, schema, include_optional=True)
    except ValueError:
        candidate = None
    if not isinstance(candidate, dict):
        return None
    validator = Draft202012Validator(schema)
    if validator.is_valid(candidate):  # pyright: ignore[reportUnknownMemberType]
        return cast(dict[str, object], candidate)
    required_only = _sample(schema, schema, include_optional=False)
    if isinstance(required_only, dict) and validator.is_valid(  # pyright: ignore[reportUnknownMemberType]
        required_only
    ):
        return cast(dict[str, object], required_only)
    return None


def _representative_response(tool: MCPTool) -> UpstreamResult:
    candidates = sorted(
        tool.responses,
        key=lambda item: (
            0 if item.status_code.isdigit() and item.status_code.startswith("2") else 1,
            0 if item.status_code == "2XX" else 1,
            0 if item.status_code == "default" else 1,
            item.status_code,
            item.media_type or "",
        ),
    )
    contract = compile_response_contract(tool)
    for response in candidates:
        status = (
            int(response.status_code)
            if response.status_code.isdigit() and response.status_code.startswith("2")
            else 200
            if response.status_code in {"2XX", "default"}
            else None
        )
        if status is None:
            continue
        if response.media_type is None:
            results = [UpstreamResult(status, "application/octet-stream", None)]
        else:
            media_type = _concrete_media_type(response.media_type)
            samples: list[JsonValue] = []
            for include_optional in (True, False):
                try:
                    data = (
                        _sample(
                            response.schema_,
                            response.schema_,
                            include_optional=include_optional,
                        )
                        if response.schema_ is not None
                        else None
                    )
                except ValueError:
                    continue
                if data not in samples:
                    samples.append(data)
            results = [UpstreamResult(status, media_type, data) for data in samples]
        for result in results:
            try:
                validate_upstream_response(contract, result)
            except Exception:
                continue
            return result
    raise ValueError(
        f"runtime could not synthesize a valid successful response for enabled tool: {tool.name}"
    )


def _concrete_media_type(value: str) -> str:
    if value == "*/*":
        return "application/json"
    if value.endswith("/*"):
        return f"{value[:-1]}json"
    if "*+" in value:
        return value.replace("*+", "validation+")
    return value


def _sample(
    raw_schema: Mapping[str, JsonValue] | None,
    root: Mapping[str, JsonValue] | None,
    *,
    include_optional: bool,
    depth: int = 0,
) -> JsonValue:
    if raw_schema is None or not raw_schema:
        return None
    if depth > 20:
        raise ValueError("schema nesting exceeds runtime validation sample limits")
    schema_root = root or raw_schema
    schema = _dereference(raw_schema, schema_root)
    for key in ("const", "default", "example"):
        if key in schema:
            return schema[key]
    examples = schema.get("examples")
    if isinstance(examples, list) and examples:
        return examples[0]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    for key in ("oneOf", "anyOf"):
        branches = schema.get(key)
        if isinstance(branches, list):
            for branch in branches:
                if not isinstance(branch, dict):
                    continue
                try:
                    candidate = _sample(
                        branch,
                        schema_root,
                        include_optional=include_optional,
                        depth=depth + 1,
                    )
                except ValueError:
                    continue
                if _sample_is_valid(schema, schema_root, candidate):
                    return candidate

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        merged: JsonObject = {}
        for branch in all_of:
            if not isinstance(branch, dict):
                continue
            branch_value = _sample(
                branch,
                schema_root,
                include_optional=include_optional,
                depth=depth + 1,
            )
            if isinstance(branch_value, dict):
                merged.update(branch_value)
        if _sample_is_valid(schema, schema_root, merged):
            return merged

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        types = [value for value in schema_type if isinstance(value, str) and value != "null"]
        schema_type = types[0] if types else "null"
    if schema_type is None:
        if isinstance(schema.get("properties"), dict):
            schema_type = "object"
        elif isinstance(schema.get("items"), dict):
            schema_type = "array"

    if schema_type == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError("object schema properties are invalid")
        raw_required = schema.get("required", [])
        required: set[str] = (
            {item for item in raw_required if isinstance(item, str)}
            if isinstance(raw_required, list)
            else set()
        )
        value: JsonObject = {}
        for name, property_schema in properties.items():
            if not isinstance(property_schema, dict):
                continue
            if not include_optional and name not in required:
                continue
            try:
                value[name] = _sample(
                    property_schema,
                    root,
                    include_optional=include_optional,
                    depth=depth + 1,
                )
            except ValueError:
                if name in required:
                    raise
        return value
    if schema_type == "array":
        minimum = max(0, _integer_keyword(schema.get("minItems"), default=0))
        maximum = _integer_keyword(schema.get("maxItems"), default=max(1, minimum))
        count = min(maximum, max(1, minimum))
        if maximum == 0:
            return []
        items = schema.get("items")
        if not isinstance(items, dict):
            return [None for _ in range(count)]
        return [
            _sample(
                items,
                root,
                include_optional=include_optional,
                depth=depth + 1,
            )
            for _ in range(count)
        ]
    if schema_type == "string":
        return _sample_string(schema)
    if schema_type == "integer":
        return int(_sample_number(schema, integer=True))
    if schema_type == "number":
        return _sample_number(schema, integer=False)
    if schema_type == "boolean":
        return True
    if schema_type == "null":
        return None
    return None


def _sample_is_valid(
    schema: Mapping[str, JsonValue],
    root: Mapping[str, JsonValue],
    candidate: JsonValue,
) -> bool:
    validation_schema: JsonObject = dict(schema)
    root_definitions = root.get("$defs")
    if "$defs" not in validation_schema and isinstance(root_definitions, dict):
        validation_schema["$defs"] = cast(JsonObject, root_definitions)
    return Draft202012Validator(validation_schema).is_valid(  # pyright: ignore[reportUnknownMemberType]
        candidate
    )


def _dereference(
    schema: Mapping[str, JsonValue],
    root: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    if not reference.startswith("#/"):
        raise ValueError("runtime validation supports only local schema references")
    value: JsonValue | Mapping[str, JsonValue] = root
    for component in reference[2:].split("/"):
        key = component.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or key not in value:
            raise ValueError("runtime validation schema reference cannot be resolved")
        value = value[key]
    if not isinstance(value, dict):
        raise ValueError("runtime validation schema reference is not an object")
    return value


def _sample_string(schema: Mapping[str, JsonValue]) -> str:
    formats = {
        "date-time": "2026-01-01T00:00:00Z",
        "date": "2026-01-01",
        "time": "00:00:00Z",
        "email": "validation@example.com",
        "hostname": "validation.example.com",
        "ipv4": "8.8.8.8",
        "ipv6": "2001:4860:4860::8888",
        "uri": "https://validation.example.com/value",
        "uri-reference": "/validation",
        "uuid": "00000000-0000-4000-8000-000000000001",
        "byte": base64.b64encode(b"validation").decode("ascii"),
        "binary": base64.b64encode(b"validation").decode("ascii"),
    }
    minimum = max(0, _integer_keyword(schema.get("minLength"), default=0))
    maximum = _integer_keyword(schema.get("maxLength"), default=max(32, minimum))
    if maximum < minimum:
        raise ValueError("string schema has inconsistent length bounds")
    candidates = [
        formats.get(str(schema.get("format"))),
        "validation",
        "value",
        "a",
        "1",
        "",
    ]
    pattern = schema.get("pattern")
    for raw in candidates:
        if raw is None:
            continue
        candidate = raw
        if len(candidate) < minimum:
            candidate += "a" * (minimum - len(candidate))
        candidate = candidate[:maximum]
        if isinstance(pattern, str) and re.search(pattern, candidate) is None:
            continue
        return candidate
    raise ValueError("runtime validation could not synthesize a patterned string")


def _sample_number(schema: Mapping[str, JsonValue], *, integer: bool) -> int | float:
    minimum = schema.get("minimum", schema.get("exclusiveMinimum", 0))
    maximum = schema.get("maximum", schema.get("exclusiveMaximum"))
    value = float(minimum) if isinstance(minimum, int | float) else 0.0
    if isinstance(schema.get("exclusiveMinimum"), int | float):
        value += 1.0 if integer else 0.5
    multiple = schema.get("multipleOf")
    if isinstance(multiple, int | float) and multiple > 0:
        value = max(multiple, ((value // multiple) + (value % multiple > 0)) * multiple)
    if isinstance(maximum, int | float) and value > float(maximum):
        raise ValueError("number schema has inconsistent bounds")
    if isinstance(schema.get("exclusiveMaximum"), int | float) and value >= float(
        cast(int | float, schema["exclusiveMaximum"])
    ):
        raise ValueError("number schema has inconsistent exclusive bounds")
    return int(value) if integer else value


def _integer_keyword(value: object, *, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default
