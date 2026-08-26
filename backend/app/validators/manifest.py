from collections import Counter

from mcp_contracts import MCPManifest

from app.core.exceptions import ValidationError


def validate_manifest(manifest: MCPManifest) -> None:
    server_ids = {server.id for server in manifest.servers}
    auth_ids = {profile.id for profile in manifest.auth_profiles}

    duplicate_names = [
        name for name, count in Counter(t.name for t in manifest.tools).items() if count > 1
    ]
    if duplicate_names:
        raise ValidationError(f"Duplicate MCP tool names: {duplicate_names}")

    for tool in manifest.tools:
        if tool.request_mapping.server_ref not in server_ids:
            raise ValidationError(f"Tool {tool.name} references unknown server")
        if tool.security_profile_ref and tool.security_profile_ref not in auth_ids:
            raise ValidationError(f"Tool {tool.name} references unknown auth profile")
        if not tool.input_schema.get("type") == "object":
            raise ValidationError(f"Tool {tool.name} input schema must be an object")
