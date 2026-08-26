from mcp_contracts import MCPManifest


def test_manifest_schema_version_is_fixed() -> None:
    schema = MCPManifest.model_json_schema()
    assert schema["properties"]["schema_version"]["const"] == "mcp-manifest/v1"
