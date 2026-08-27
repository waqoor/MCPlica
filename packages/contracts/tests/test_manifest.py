from pathlib import Path

import pytest
from mcp_contracts import MCPManifest, validate_manifest_contract

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_manifest_schema_version_is_fixed() -> None:
    schema = MCPManifest.model_json_schema()
    assert schema["properties"]["schema_version"]["const"] == "mcp-manifest/v1"


def test_ready_manifest_contract_matches_generic_runtime_invariants() -> None:
    manifest = MCPManifest.model_validate_json(
        (REPOSITORY_ROOT / "tests/fixtures/manifests/petstore.json").read_bytes()
    )
    validate_manifest_contract(manifest, runtime_version="1.0.0")

    invalid = manifest.model_copy(deep=True)
    invalid.tools[0].output_schema = {"type": "array", "items": {"type": "string"}}
    with pytest.raises(ValueError, match="output schema must be object-shaped"):
        validate_manifest_contract(invalid, runtime_version="1.0.0")


def test_manifest_contract_rejects_unresolved_nested_schema_references() -> None:
    manifest = MCPManifest.model_validate_json(
        (REPOSITORY_ROOT / "tests/fixtures/manifests/petstore.json").read_bytes()
    )
    invalid_tool = manifest.tools[0].model_copy(
        update={
            "output_schema": {
                "type": "object",
                "properties": {
                    "body": {
                        "$defs": {"Pet": {"type": "object"}},
                        "$ref": "#/$defs/Pet",
                    }
                },
            }
        }
    )
    invalid = manifest.model_copy(update={"tools": [invalid_tool]})

    with pytest.raises(ValueError, match="unresolved local JSON Schema reference"):
        validate_manifest_contract(invalid, runtime_version="1.0.0")
