from pathlib import Path

from mcp_contracts import MCPManifest


def load_manifest(path: str) -> MCPManifest:
    payload = Path(path).read_text(encoding="utf-8")
    return MCPManifest.model_validate_json(payload)
