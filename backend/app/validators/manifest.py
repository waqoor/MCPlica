from mcp_contracts import MCPManifest, validate_manifest_contract

from app.core.exceptions import ValidationError


def validate_manifest(manifest: MCPManifest, *, runtime_version: str) -> None:
    try:
        validate_manifest_contract(manifest, runtime_version=runtime_version)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
