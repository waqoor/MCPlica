import hashlib
from datetime import UTC, datetime
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from mcp_contracts.json_types import JsonObject

from app.compilers.mcp.compiler import compile_manifest
from app.core.exceptions import ReferenceResolutionError
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


def test_inventory_materialization_preserves_instance_valued_annotations() -> None:
    literal = {"$ref": "literal-value", "$defs": {"still": "data"}}
    document: JsonObject = {
        "schema": "api-inventory/v1",
        "name": "Inventory",
        "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
        "operations": [
            {
                "operation_id": "createProduct",
                "method": "POST",
                "path": "/products",
                "request_body": {
                    "content_type": "application/json",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "payload": {
                                "type": "object",
                                "default": literal,
                                "examples": [literal],
                                "const": literal,
                                "enum": [literal],
                            }
                        },
                    },
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
    body = canonical.operations[0].request_body
    assert body is not None
    payload = body.content[0].schema_["properties"]["payload"]  # type: ignore[index]
    assert payload["default"] == literal  # type: ignore[index]
    assert payload["examples"] == [literal]  # type: ignore[index]
    assert payload["const"] == literal  # type: ignore[index]
    assert payload["enum"] == [literal]  # type: ignore[index]


def test_inventory_json_pointer_resolves_array_and_escaped_tokens() -> None:
    document: JsonObject = {
        "schema": "api-inventory/v1",
        "name": "Inventory",
        "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
        "schemas": {
            "Coordinates Set": {
                "$defs": {"coordinate/value": {"type": "number", "minimum": 0}},
                "prefixItems": [
                    {"type": "string"},
                    {"$ref": "#/$defs/coordinate~1value"},
                ],
            }
        },
        "operations": [
            {
                "operation_id": "setCoordinate",
                "method": "POST",
                "path": "/coordinates",
                "request_body": {
                    "content_type": "application/json",
                    "schema": {"$ref": "#/schemas/Coordinates%20Set/prefixItems/1"},
                },
                "responses": {"204": {"description": "Updated"}},
            }
        ],
    }
    canonical = parse_api_inventory(
        document,
        project_id=UUID(int=10),
        source_version_id=UUID(int=11),
        content_sha256=hashlib.sha256(b"inventory").hexdigest(),
    )
    body = canonical.operations[0].request_body
    assert body is not None
    schema = body.content[0].schema_
    Draft202012Validator(schema).validate(3)
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(schema).validate(-1)


@pytest.mark.parametrize("index", ["-1", "x", "2", "01"])
def test_inventory_json_pointer_rejects_invalid_array_indices(index: str) -> None:
    document: JsonObject = {
        "schema": "api-inventory/v1",
        "name": "Inventory",
        "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
        "schemas": {"Values": {"prefixItems": [{"type": "string"}]}},
        "operations": [
            {
                "method": "POST",
                "path": "/values",
                "request_body": {
                    "content_type": "application/json",
                    "schema": {"$ref": f"#/schemas/Values/prefixItems/{index}"},
                },
                "responses": {"204": {"description": "Updated"}},
            }
        ],
    }
    with pytest.raises(ReferenceResolutionError, match="Unresolved API Inventory"):
        parse_api_inventory(
            document,
            project_id=UUID(int=10),
            source_version_id=UUID(int=11),
            content_sha256=hashlib.sha256(b"inventory").hexdigest(),
        )
