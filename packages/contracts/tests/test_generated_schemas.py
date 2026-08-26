import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mcp_contracts import ApiInventory, MCPManifest
from pydantic import BaseModel

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("model", "relative_path"),
    [
        (MCPManifest, "packages/contracts/schemas/mcp-manifest-v1.schema.json"),
        (
            ApiInventory,
            "backend/app/parsers/api_inventory/schema/api-inventory-v1.schema.json",
        ),
    ],
)
def test_committed_json_schema_matches_authoritative_contract(
    model: type[BaseModel],
    relative_path: str,
) -> None:
    schema = json.loads((REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema == model.model_json_schema(by_alias=True)
