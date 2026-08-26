import hashlib
from datetime import UTC, datetime
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from mcp_contracts.json_types import JsonObject

from app.compilers.mcp.compiler import compile_manifest
from app.parsers.api_inventory import parse_api_inventory


def test_inventory_normalizes_into_canonical_model() -> None:
    canonical = parse_api_inventory(
        {
            "schema": "api-inventory/v1",
            "name": "Inventory",
            "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
            "operations": [
                {
                    "operation_id": "getProduct",
                    "method": "GET",
                    "path": "/products/{product_id}",
                    "parameters": [
                        {
                            "name": "product_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "content_type": "application/json",
                            "schema": {"type": "object"},
                        }
                    },
                }
            ],
        },
        project_id=UUID(int=10),
        source_version_id=UUID(int=11),
        content_sha256=hashlib.sha256(b"inventory").hexdigest(),
    )

    assert canonical.source_format == "api-inventory/v1"
    assert canonical.operations[0].tool_name_seed == "get_product"
    assert canonical.operations[0].provenance.operation.pointer == "#/operations/0"


def test_inventory_schema_refs_compile_to_self_contained_tool_schema() -> None:
    document: JsonObject = {
        "schema": "api-inventory/v1",
        "name": "Inventory",
        "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
        "schemas": {
            "Product": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
            }
        },
        "operations": [
            {
                "operation_id": "createProduct",
                "method": "POST",
                "path": "/products",
                "request_body": {
                    "required": True,
                    "content_type": "application/json",
                    "schema": {"$ref": "#/schemas/Product"},
                },
                "responses": {"201": {"description": "Created"}},
            }
        ],
    }
    canonical = parse_api_inventory(
        document,
        project_id=UUID(int=10),
        source_version_id=UUID(int=11),
        content_sha256=hashlib.sha256(b"inventory").hexdigest(),
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=10)),
        project_name="Inventory",
        project_slug="inventory",
        build_id="build-1",
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    input_schema = manifest.tools[0].input_schema
    assert "$defs" in input_schema
    assert "#/schemas/" not in str(input_schema)
    validator = Draft202012Validator(input_schema)
    validator.validate(  # pyright: ignore[reportUnknownMemberType]
        {"body": {"id": "product-1"}}
    )
    with pytest.raises(JsonSchemaValidationError):
        validator.validate({"body": {}})  # pyright: ignore[reportUnknownMemberType]
