from pathlib import Path

import pytest
from mcp_contracts import MCPManifest

from app.validation_harness import inspect_runtime_candidate

MANIFEST_ROOT = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests"
MATRIX_MANIFESTS = (
    "schema-dialect-3.0-json.json",
    "schema-dialect-3.0-yaml.json",
    "pipeline-matrix-3.1-json.json",
    "pipeline-matrix-3.1-yaml.json",
)


@pytest.mark.parametrize("fixture_name", MATRIX_MANIFESTS)
async def test_every_compiler_golden_lists_and_calls_through_generic_runtime(
    fixture_name: str,
) -> None:
    manifest = MCPManifest.model_validate_json(MANIFEST_ROOT.joinpath(fixture_name).read_bytes())

    report = await inspect_runtime_candidate(manifest, runtime_version="1.0.0")

    expected_tools = [tool.name for tool in manifest.enabled_tools()]
    assert report["tools"] == expected_tools
    assert report["exercised_tools"] == expected_tools
    assert report["request_mapping_count"] == len(expected_tools)
    assert report["protocol_version"] == "2026-07-28"
