import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from mcp_contracts.json_types import JsonObject

from app.compilers.mcp.compiler import compile_manifest
from app.core.exceptions import CompilationError, SourceParseError
from app.domain.validation import FindingSeverity
from app.parsers.openapi.parser import ExternalOpenApiDocument, parse_openapi
from app.services.sources import (  # pyright: ignore[reportPrivateUsage]
    _inherited_active_server_ref,
)
from app.validators.build import validate_build

FIXTURE_ROOT = Path(__file__).parents[2] / "tests" / "fixtures" / "openapi"


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
    security = manifest.security.model_dump(mode="json")
    assert security["inbound_auth_mode"] is None
    assert security["inbound_auth_boundary"] == "deployment_overlay"


def test_heterogeneous_success_responses_compile_to_truthful_envelope_union() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Response matrix", "version": "1.0"},
        "servers": [{"url": "https://responses.example.com"}],
        "paths": {
            "/matrix": {
                "get": {
                    "operationId": "responseMatrix",
                    "responses": {
                        "200": {
                            "description": "object",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    }
                                }
                            },
                        },
                        "201": {
                            "description": "array",
                            "content": {
                                "application/vnd.example+json": {
                                    "schema": {"type": "array", "items": {"type": "string"}}
                                }
                            },
                        },
                        "2XX": {
                            "description": "scalar",
                            "content": {"text/plain": {"schema": {"type": "string"}}},
                        },
                    },
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"response-matrix").hexdigest(),
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Response matrix",
        project_slug="response-matrix",
        build_id="build-response-matrix",
        created_at=datetime(2026, 8, 27, tzinfo=UTC),
    )

    tool = manifest.tools[0]
    assert [(item.status_code, item.media_type) for item in tool.responses] == [
        ("200", "application/json"),
        ("201", "application/vnd.example+json"),
        ("2XX", "text/plain"),
    ]
    body = cast(dict[str, object], tool.output_schema)["properties"]
    assert isinstance(body, dict)
    body_schema = cast(dict[str, object], body)["body"]
    assert isinstance(body_schema, dict)
    assert len(cast(list[object], body_schema["anyOf"])) == 3


def test_binary_success_response_is_blocked_before_ready() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Binary", "version": "1.0"},
        "servers": [{"url": "https://responses.example.com"}],
        "paths": {
            "/report": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "PDF",
                            "content": {
                                "application/pdf": {
                                    "schema": {"type": "string", "format": "binary"}
                                }
                            },
                        }
                    }
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"binary-response").hexdigest(),
    )
    with pytest.raises(CompilationError, match="successful response media type"):
        compile_manifest(
            canonical,
            project_id=str(UUID(int=1)),
            project_name="Binary",
            project_slug="binary",
            build_id="build-binary",
            created_at=datetime(2026, 8, 27, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    "method",
    ["get", "post", "put", "patch", "delete", "head", "options", "trace"],
)
def test_every_standard_openapi_method_survives_parse_compile_and_coverage(
    method: str,
) -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Method matrix", "version": "1.0"},
        "servers": [{"url": "https://methods.example.com"}],
        "paths": {
            f"/{method}": {
                method: {
                    "operationId": f"{method}Operation",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(method.encode()).hexdigest(),
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Method matrix",
        project_slug="method-matrix",
        build_id=f"build-{method}",
        created_at=datetime(2026, 8, 27, tzinfo=UTC),
    )

    assert len(canonical.operations) == 1
    assert canonical.operations[0].method.value == method.upper()
    assert len(manifest.tools) == 1
    assert manifest.tools[0].operation_key == canonical.operations[0].key
    assert manifest.tools[0].request_mapping.method.value == method.upper()
    findings = validate_build(
        canonical,
        manifest,
        excluded_operation_keys=frozenset(),
        canonical_sha256=manifest.build.canonical_sha256,
        runtime_version="1.0.0",
    )
    assert not [finding for finding in findings if finding.severity is FindingSeverity.ERROR]


@pytest.mark.parametrize(
    ("fixture_name", "loader"),
    [
        ("schema-dialect-3.0.json", json.loads),
        ("schema-dialect-3.0.yaml", yaml.safe_load),
    ],
)
def test_openapi_30_schema_dialect_is_normalized_and_runtime_executable(
    fixture_name: str,
    loader: object,
) -> None:
    raw = FIXTURE_ROOT.joinpath(fixture_name).read_text(encoding="utf-8")
    assert callable(loader)
    source = loader(raw)
    assert isinstance(source, dict)
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(raw.encode()).hexdigest(),
    )

    component = next(iter(canonical.schemas.values())).schema_
    properties = component["properties"]
    assert isinstance(properties, dict)
    assert component["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "nullable" not in str(component)
    assert properties["score"] == {
        "type": "number",
        "exclusiveMinimum": 0,
        "maximum": 10,
    }
    dialect = canonical.provenance.schema_dialect
    assert dialect is not None
    assert dialect.source == "openapi-3.0-schema-object"
    assert dialect.target == "https://json-schema.org/draft/2020-12/schema"
    assert {item.transformation for item in dialect.transformations} >= {
        "nullable",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }

    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Schema dialect matrix",
        project_slug="schema-dialect",
        build_id="build-schema-dialect",
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    input_validator = Draft202012Validator(manifest.tools[0].input_schema)
    valid = {
        "body": {
            "nickname": None,
            "score": 0.1,
            "state": None,
            "labels": [None, "stable"],
            "attributes": {"attempts": None},
            "choice": None,
        }
    }
    input_validator.validate(valid)  # pyright: ignore[reportUnknownMemberType]
    with pytest.raises(JsonSchemaValidationError):
        input_validator.validate(  # pyright: ignore[reportUnknownMemberType]
            {**valid, "body": {**valid["body"], "score": 0}}
        )


@pytest.mark.parametrize(
    ("dialect_location", "expected_pointer"),
    [
        ("document", "#/jsonSchemaDialect"),
        ("schema", "#/components/schemas/Pet"),
    ],
)
def test_openapi_31_unknown_schema_dialects_fail_closed(
    dialect_location: str,
    expected_pointer: str,
) -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Dialect", "version": "1.0"},
        "servers": [{"url": "https://api.example.com"}],
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                }
            }
        },
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}
                            },
                        }
                    }
                }
            }
        },
    }
    if dialect_location == "document":
        source["jsonSchemaDialect"] = "https://example.com/unsupported-dialect"
    else:
        components = cast(dict[str, object], source["components"])
        schemas = cast(dict[str, object], components["schemas"])
        pet = cast(dict[str, object], schemas["Pet"])
        pet["$schema"] = "https://example.com/unsupported-dialect"

    with pytest.raises(SourceParseError) as error:
        parse_openapi(
            source,
            project_id=UUID(int=1),
            source_version_id=UUID(int=2),
            content_sha256="a" * 64,
        )

    assert error.value.details["source_pointer"] == expected_pointer


def test_openapi_31_nested_response_schema_dialect_reports_exact_pointer() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Nested dialect", "version": "1.0"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$schema": "https://example.com/unsupported-dialect",
                                            "type": "string",
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        },
    }

    with pytest.raises(SourceParseError) as error:
        parse_openapi(
            source,
            project_id=UUID(int=1),
            source_version_id=UUID(int=2),
            content_sha256="a" * 64,
        )

    assert error.value.details["source_pointer"] == (
        "#/paths/~1pets/get/responses/200/content/application~1json/schema/items"
    )


def test_openapi_31_literal_schema_properties_in_examples_are_not_dialects() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Example payload", "version": "1.0"},
        "servers": [{"url": "https://api.example.com"}],
        "components": {
            "schemas": {
                "Payload": {
                    "type": "object",
                    "example": {"$schema": "https://example.com/payload-value"},
                }
            },
            "examples": {
                "Literal": {"value": {"schema": {"$schema": "https://example.com/payload-value"}}}
            },
        },
        "paths": {
            "/payload": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Payload"},
                                    "example": {
                                        "schema": {"$schema": "https://example.com/payload-value"}
                                    },
                                }
                            },
                        }
                    }
                }
            }
        },
    }

    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256="a" * 64,
    )

    assert len(canonical.operations) == 1


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


def test_ambiguous_servers_require_applicable_operation_mapping() -> None:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {"title": "Multi environment", "version": "1.0"},
        "servers": [
            {"url": "https://production.example.com", "description": "Production"},
            {"url": "https://staging.example.com", "description": "Staging"},
        ],
        "paths": {
            "/root": {
                "get": {
                    "operationId": "rootOperation",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/scoped": {
                "servers": [{"url": "https://scoped.example.com/v1"}],
                "get": {
                    "operationId": "scopedOperation",
                    "responses": {"200": {"description": "OK"}},
                },
            },
        },
    }
    unresolved = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"multi-server").hexdigest(),
    )
    root = next(
        item for item in unresolved.operations if item.source_operation_id == "rootOperation"
    )
    scoped = next(
        item for item in unresolved.operations if item.source_operation_id == "scopedOperation"
    )
    assert root.server_ref is None
    assert len(root.server_candidates) == 2
    assert scoped.server_ref is not None
    with pytest.raises(CompilationError, match="server selection is unresolved"):
        compile_manifest(
            unresolved,
            project_id=str(UUID(int=1)),
            project_name="Multi environment",
            project_slug="multi-environment",
            build_id="build-multi",
            created_at=datetime(2026, 8, 27, tzinfo=UTC),
        )

    staging = next(
        server.key for server in unresolved.servers if "staging.example.com" in str(server.url)
    )
    assert (
        _inherited_active_server_ref(
            root.server_candidates,
            unresolved.servers,
            source_format=unresolved.source_format,
            active_server_ref=staging,
        )
        == staging
    )
    assert (
        _inherited_active_server_ref(
            scoped.server_candidates,
            unresolved.servers,
            source_format=unresolved.source_format,
            active_server_ref=staging,
        )
        is None
    )
    selected = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"multi-server").hexdigest(),
        active_server_ref=staging,
    )
    selected_root = next(
        item for item in selected.operations if item.source_operation_id == "rootOperation"
    )
    selected_scoped = next(
        item for item in selected.operations if item.source_operation_id == "scopedOperation"
    )
    assert selected_root.server_ref == staging
    assert selected_scoped.server_ref == scoped.server_ref
    with pytest.raises(SourceParseError, match="not applicable"):
        parse_openapi(
            source,
            project_id=UUID(int=1),
            source_version_id=UUID(int=2),
            content_sha256=hashlib.sha256(b"multi-server").hexdigest(),
            server_mappings={root.key: scoped.server_ref or ""},
        )


def test_relative_server_and_oauth_urls_resolve_against_project_base() -> None:
    source: JsonObject = {
        "openapi": "3.0.3",
        "info": {"title": "Relative API", "version": "1.0"},
        "servers": [{"url": "/v1"}],
        "components": {
            "securitySchemes": {
                "oauth": {
                    "type": "oauth2",
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "oauth/token",
                            "scopes": {},
                        }
                    },
                }
            }
        },
        "paths": {
            "/items": {
                "get": {
                    "security": [{"oauth": []}],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"relative-api").hexdigest(),
        default_base_url="https://gateway.example.com/platform",
    )
    assert str(canonical.servers[0].url) == "https://gateway.example.com/v1"
    assert str(canonical.security_schemes["oauth"].token_url) == (
        "https://gateway.example.com/platform/oauth/token"
    )
    with pytest.raises(SourceParseError, match="requires the Project default base URL"):
        parse_openapi(
            source,
            project_id=UUID(int=1),
            source_version_id=UUID(int=2),
            content_sha256=hashlib.sha256(b"relative-api").hexdigest(),
        )
