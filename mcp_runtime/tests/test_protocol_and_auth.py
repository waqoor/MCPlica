import hashlib
from pathlib import Path
from uuid import UUID

import mcp.types as types
import pytest
from mcp import Client
from mcp_contracts import MCPManifest, MCPResource, RuntimeSecretBundle
from starlette.testclient import TestClient

from app.auth.inbound import InboundAuthContext
from app.clients.api_client import UpstreamResult
from app.core.config import RuntimeSettings
from app.executor.executor import ToolExecutor
from app.server.factory import build_app, build_server


def test_environment_proxy_inheritance_is_rejected_in_all_runtime_modes() -> None:
    with pytest.raises(ValueError, match="environment proxies"):
        RuntimeSettings(environment="development", trust_environment_proxy=True)


def _manifest() -> MCPManifest:
    path = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"
    return MCPManifest.model_validate_json(path.read_bytes())


class _FakeExecutor(ToolExecutor):
    def __init__(self) -> None:
        pass

    async def execute(self, tool_name: str, arguments: dict[str, object]) -> UpstreamResult:
        del tool_name
        return UpstreamResult(
            200,
            "application/json",
            {"id": str(arguments["pet_id"]), "name": "Ada"},
        )

    async def close(self) -> None:
        return None


async def test_official_client_lists_calls_and_reads_exact_contract() -> None:
    manifest = _manifest().model_copy(
        update={
            "resources": [
                MCPResource(
                    uri="mcplica://docs/readme",
                    name="README",
                    content="Runtime documentation",
                )
            ]
        }
    )
    server = build_server(
        manifest,
        _FakeExecutor(),
        InboundAuthContext(None, None),
        "1.0.0",
    )
    async with Client(server) as client:
        assert client.protocol_version == "2026-07-28"
        tools = await client.list_tools()
        result = await client.call_tool("get_pet", {"pet_id": "pet-1"})
        resources = await client.list_resources()
        resource = await client.read_resource("mcplica://docs/readme")

    assert [tool.name for tool in tools.tools] == ["get_pet"]
    assert result.structured_content == {
        "status": 200,
        "contentType": "application/json",
        "body": {"id": "pet-1", "name": "Ada"},
    }
    assert [str(item.uri) for item in resources.resources] == ["mcplica://docs/readme"]
    assert isinstance(resource.contents[0], types.TextResourceContents)
    assert resource.contents[0].text == "Runtime documentation"


async def test_official_client_paginates_large_tool_and_resource_sets() -> None:
    manifest = _manifest()
    template = manifest.tools[0]
    manifest = manifest.model_copy(
        update={
            "tools": [
                template.model_copy(
                    update={"name": f"tool_{index}", "operation_key": f"operation_{index}"}
                )
                for index in range(105)
            ],
            "resources": [
                MCPResource(
                    uri=f"mcplica://docs/{index}",
                    name=f"Document {index}",
                    content=f"Page {index}",
                )
                for index in range(105)
            ],
        }
    )
    server = build_server(
        manifest,
        _FakeExecutor(),
        InboundAuthContext(None, None),
        "1.0.0",
    )
    async with Client(server) as client:
        first_tools = await client.list_tools()
        second_tools = await client.list_tools(cursor=first_tools.next_cursor)
        first_resources = await client.list_resources()
        second_resources = await client.list_resources(cursor=first_resources.next_cursor)

    assert len(first_tools.tools) == 100
    assert len(second_tools.tools) == 5
    assert second_tools.next_cursor is None
    assert len(first_resources.resources) == 100
    assert len(second_resources.resources) == 5
    assert second_resources.next_cursor is None


def test_streamable_http_requires_valid_static_bearer_token() -> None:
    token = "test-token-with-at-least-256-bits-of-entropy-1234567890"
    manifest = _manifest()
    bundle = RuntimeSecretBundle.model_validate(
        {
            "upstream_credentials": {"bearer": {"type": "bearer", "token": "upstream-secret"}},
            "inbound_auth": {
                "mode": "static_bearer",
                "static_tokens": [
                    {"id": "token-1", "sha256": hashlib.sha256(token.encode()).hexdigest()}
                ],
            },
        }
    )
    settings = RuntimeSettings(
        environment="test",
        deployment_id=UUID("00000000-0000-0000-0000-000000000123"),
        public_base_url="https://testserver",
        allowed_hosts="testserver",
        allowed_origins="https://testserver",
        require_secure_secret_permissions=False,
    )
    app = build_app(manifest, bundle, settings)
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "runtime-test", "version": "1.0"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Origin": "https://testserver",
    }
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").json()["deployment_id"] == str(settings.deployment_id)
        assert client.post("/mcp", json=initialize, headers=headers).status_code == 401
        authenticated = client.post(
            "/mcp",
            json=initialize,
            headers={**headers, "Authorization": f"Bearer {token}"},
        )
    assert authenticated.status_code == 200, authenticated.text


def test_modern_streamable_http_is_stateless_and_requires_authentication() -> None:
    token = "test-token-with-at-least-256-bits-of-entropy-1234567890"
    manifest = _manifest()
    bundle = RuntimeSecretBundle.model_validate(
        {
            "upstream_credentials": {"bearer": {"type": "bearer", "token": "upstream-secret"}},
            "inbound_auth": {
                "mode": "static_bearer",
                "static_tokens": [
                    {"id": "token-1", "sha256": hashlib.sha256(token.encode()).hexdigest()}
                ],
            },
        }
    )
    settings = RuntimeSettings(
        environment="test",
        deployment_id=UUID("00000000-0000-0000-0000-000000000123"),
        public_base_url="https://testserver",
        allowed_hosts="testserver",
        allowed_origins="https://testserver",
        require_secure_secret_permissions=False,
    )
    app = build_app(manifest, bundle, settings)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "runtime-test",
                    "version": "1.0",
                },
            }
        },
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://testserver",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/list",
    }
    with TestClient(app) as client:
        assert client.post("/mcp", json=request, headers=headers).status_code == 401
        authenticated = client.post(
            "/mcp",
            json=request,
            headers={**headers, "Authorization": f"Bearer {token}"},
        )

    assert authenticated.status_code == 200, authenticated.text
    assert authenticated.json()["result"]["tools"][0]["name"] == "get_pet"
    assert "mcp-session-id" not in authenticated.headers
