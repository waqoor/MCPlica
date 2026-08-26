import hashlib
from datetime import UTC, datetime
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from mcp_contracts.json_types import JsonObject

from app.compilers.mcp.compiler import compile_manifest
from app.core.exceptions import CompilationError, SourceParseError
from app.parsers.openapi.parser import ExternalOpenApiDocument, parse_openapi


def test_openapi_compiles_to_manifest() -> None:
    source = {
        "openapi": "3.1.0",
        "info": {"title": "Inventory", "version": "1.0"},
        "servers": [{"url": "https://inventory.example.com"}],
        "paths": {
            "/products/{product_id}": {
                "get": {
                    "operationId": "getProduct",
                    "summary": "Get product",
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
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"inventory-source").hexdigest(),
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Inventory",
        project_slug="inventory",
        build_id="build-1",
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    assert manifest.tools[0].name == "get_product"
    assert manifest.tools[0].request_mapping.path == "/products/{product_id}"
    required = manifest.tools[0].input_schema["required"]
    assert isinstance(required, list)
    assert "product_id" in required


def test_external_schema_refs_compile_to_self_contained_tool_schema() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Inventory", "version": "1.0"},
        "servers": [{"url": "https://inventory.example.com"}],
        "paths": {"/products": {"$ref": "shared.yaml#/paths/~1products"}},
    }
    shared: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Shared", "version": "1.0"},
        "paths": {
            "/products": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Product"}}
                        },
                    },
                    "responses": {"201": {"description": "Created"}},
                }
            }
        },
        "components": {
            "schemas": {
                "Product": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "parent": {"$ref": "#/components/schemas/Product"},
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"inventory-source").hexdigest(),
        external_documents={
            "shared.yaml": ExternalOpenApiDocument(shared, UUID(int=3)),
        },
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Inventory",
        project_slug="inventory",
        build_id="build-1",
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    input_schema = manifest.tools[0].input_schema
    assert canonical.operations[0].provenance.operation.source_version_id == UUID(int=3)
    assert "$defs" in input_schema
    assert "#/components/" not in str(input_schema)
    validator = Draft202012Validator(input_schema)
    validator.validate(  # pyright: ignore[reportUnknownMemberType]
        {"body": {"id": "product-1", "parent": {"id": "parent-1"}}}
    )
    with pytest.raises(JsonSchemaValidationError):
        validator.validate({"body": {}})  # pyright: ignore[reportUnknownMemberType]


def test_openapi_spec_validation_rejects_unresolved_path_parameter() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Inventory", "version": "1.0"},
        "servers": [{"url": "https://inventory.example.com"}],
        "paths": {"/products/{product_id}": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }
    with pytest.raises(SourceParseError, match="specification validation failed"):
        parse_openapi(
            source,
            project_id=UUID(int=1),
            source_version_id=UUID(int=2),
            content_sha256=hashlib.sha256(b"invalid-source").hexdigest(),
        )


def test_unsupported_parameter_content_fails_compilation_visibly() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Inventory", "version": "1.0"},
        "servers": [{"url": "https://inventory.example.com"}],
        "paths": {
            "/products": {
                "get": {
                    "parameters": [
                        {
                            "name": "filter",
                            "in": "query",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"unsupported-source").hexdigest(),
    )
    with pytest.raises(CompilationError, match="parameter-content"):
        compile_manifest(
            canonical,
            project_id=str(UUID(int=1)),
            project_name="Inventory",
            project_slug="inventory",
            build_id="build-1",
            created_at=datetime(2026, 8, 26, tzinfo=UTC),
        )


def test_explicit_exclusion_removes_unsupported_operation_and_its_auth_dependencies() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Inventory", "version": "1.0"},
        "servers": [{"url": "https://inventory.example.com"}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
            }
        },
        "paths": {
            "/products": {
                "get": {
                    "operationId": "listProducts",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/legacy": {
                "get": {
                    "operationId": "legacyCookieOperation",
                    "servers": [{"url": "https://legacy.example.com"}],
                    "parameters": [
                        {
                            "name": "legacy_session",
                            "in": "cookie",
                            "schema": {"type": "string"},
                        }
                    ],
                    "security": [{"bearerAuth": []}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"excluded-source").hexdigest(),
    )
    excluded_key = next(
        operation.key for operation in canonical.operations if operation.path_template == "/legacy"
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Inventory",
        project_slug="inventory",
        build_id="build-1",
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
        excluded_operation_keys=frozenset({excluded_key}),
    )
    assert [tool.operation_key for tool in manifest.tools] == [
        next(
            operation.key
            for operation in canonical.operations
            if operation.path_template == "/products"
        )
    ]
    assert manifest.auth_profiles == []
    assert [str(server.url) for server in manifest.servers] == ["https://inventory.example.com/"]
    assert manifest.security.allowed_upstream_hosts == ["inventory.example.com"]
