from pathlib import Path

from mcp_contracts import MCPManifest


def test_fixture_manifest_loads() -> None:
    path = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"
    manifest = MCPManifest.model_validate_json(path.read_text())
    assert manifest.project.slug == "petstore"
    assert manifest.tools
