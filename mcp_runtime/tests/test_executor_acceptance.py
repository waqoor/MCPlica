import base64
import json
from pathlib import Path

import httpx
import pytest
from mcp_contracts import (
    AuthProfile,
    MCPManifest,
    MCPTool,
    MultipartFileMapping,
    ParameterMapping,
    RequestBodyMapping,
    RequestMapping,
    RuntimeSecretBundle,
    ServerDefinition,
    UpstreamCredential,
)
from mcp_contracts.json_types import JsonObject, JsonValue
from mcp_contracts.manifest import HttpMethod, ParameterTarget

from app.auth.upstream import UpstreamAuthManager
from app.clients.api_client import ApiClient
from app.clients.oauth_client import OAuthAccessToken
from app.executor.executor import ToolExecutor
from app.security.url_policy import UpstreamUrlPolicy


class _UnusedOAuth:
    async def fetch_client_credentials(
        self, profile: AuthProfile, credential: UpstreamCredential
    ) -> OAuthAccessToken:
        del profile, credential
        raise AssertionError("OAuth must not be used by unauthenticated fixture tools")

    async def close(self) -> None:
        return None


def _fixture() -> MCPManifest:
    path = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"
    return MCPManifest.model_validate_json(path.read_bytes())


def _tool(
    name: str,
    method: HttpMethod,
    *,
    path: str,
    properties: JsonObject,
    parameters: list[ParameterMapping] | None = None,
    body: RequestBodyMapping | None = None,
) -> MCPTool:
    required: list[JsonValue] = [
        parameter.tool_field for parameter in parameters or [] if parameter.required
    ]
    if body is not None and body.required:
        required.append(body.tool_field)
    input_schema: JsonObject = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    return MCPTool(
        name=name,
        title=name,
        description=f"Acceptance mapping for {method.value}",
        input_schema=input_schema,
        operation_key=f"operation_{name}",
        request_mapping=RequestMapping(
            server_ref="main",
            method=method,
            path=path,
            parameters=parameters or [],
            body=body,
        ),
    )


@pytest.mark.asyncio
async def test_executor_maps_all_required_methods_and_body_encodings() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"method": request.method, "path": request.url.path},
            headers={"content-type": "application/json"},
        )

    tools = [
        _tool(
            "get_item",
            HttpMethod.GET,
            path="/items/{item_id}",
            properties={"item_id": {"type": "string"}, "tag": {"type": "string"}},
            parameters=[
                ParameterMapping(
                    tool_field="item_id",
                    source_name="item_id",
                    target=ParameterTarget.PATH,
                    required=True,
                ),
                ParameterMapping(
                    tool_field="tag",
                    source_name="tag",
                    target=ParameterTarget.QUERY,
                ),
            ],
        ),
        _tool(
            "post_item",
            HttpMethod.POST,
            path="/items",
            properties={"body": {"type": "object"}},
            body=RequestBodyMapping(required=True),
        ),
        _tool(
            "put_form",
            HttpMethod.PUT,
            path="/form",
            properties={"body": {"type": "object"}},
            body=RequestBodyMapping(
                media_type="application/x-www-form-urlencoded",
                required=True,
            ),
        ),
        _tool(
            "patch_file",
            HttpMethod.PATCH,
            path="/files",
            properties={"body": {"type": "object"}},
            body=RequestBodyMapping(
                media_type="multipart/form-data",
                required=True,
                multipart_files=[
                    MultipartFileMapping(
                        part_name="file",
                        content_field="content",
                        filename_field="filename",
                        required=True,
                    )
                ],
            ),
        ),
        _tool(
            "delete_item",
            HttpMethod.DELETE,
            path="/items/{item_id}",
            properties={"item_id": {"type": "string"}, "trace": {"type": "string"}},
            parameters=[
                ParameterMapping(
                    tool_field="item_id",
                    source_name="item_id",
                    target=ParameterTarget.PATH,
                    required=True,
                ),
                ParameterMapping(
                    tool_field="trace",
                    source_name="X-Trace-Id",
                    target=ParameterTarget.HEADER,
                ),
            ],
        ),
    ]
    fixture = _fixture()
    manifest = fixture.model_copy(
        update={
            "servers": [
                ServerDefinition.model_validate({"id": "main", "url": "https://8.8.8.8/api"})
            ],
            "auth_profiles": [],
            "tools": tools,
            "security": fixture.security.model_copy(update={"allowed_upstream_hosts": ["8.8.8.8"]}),
        }
    )
    bundle = RuntimeSecretBundle.model_validate(
        {
            "inbound_auth": {
                "mode": "static_bearer",
                "static_tokens": [{"id": "inbound", "sha256": "3" * 64}],
            }
        }
    )
    policy = UpstreamUrlPolicy(manifest.servers)
    api = ApiClient(policy, transport=httpx.MockTransport(handler))
    auth = UpstreamAuthManager(manifest, bundle, _UnusedOAuth())
    executor = ToolExecutor(manifest, api, auth, policy)
    try:
        await executor.execute("get_item", {"item_id": "a/b", "tag": "new"})
        await executor.execute("post_item", {"body": {"name": "Ada"}})
        await executor.execute("put_form", {"body": {"name": "Ada Lovelace", "active": True}})
        await executor.execute(
            "patch_file",
            {
                "body": {
                    "content": base64.b64encode(b"document").decode("ascii"),
                    "filename": "document.txt",
                }
            },
        )
        await executor.execute("delete_item", {"item_id": "item-1", "trace": "trace-1"})
    finally:
        await executor.close()

    assert [request.method for request in requests] == ["GET", "POST", "PUT", "PATCH", "DELETE"]
    assert str(requests[0].url).endswith("/api/items/a%2Fb?tag=new")
    assert json.loads(requests[1].content) == {"name": "Ada"}
    assert requests[2].headers["content-type"] == "application/x-www-form-urlencoded"
    assert requests[2].content == b"name=Ada+Lovelace&active=true"
    assert requests[3].headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b"document.txt" in requests[3].content
    assert b"document" in requests[3].content
    assert requests[4].headers["x-trace-id"] == "trace-1"
