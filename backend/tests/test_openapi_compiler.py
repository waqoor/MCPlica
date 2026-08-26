from app.compilers.mcp.compiler import compile_manifest
from app.parsers.openapi.parser import parse_openapi


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
    canonical = parse_openapi(source)
    manifest = compile_manifest(
        canonical,
        project_id="project-1",
        project_name="Inventory",
        project_slug="inventory",
        source_digest="abc123",
        build_id="build-1",
    )
    assert manifest.tools[0].name == "get_product"
    assert manifest.tools[0].request_mapping.path == "/products/{product_id}"
    assert "product_id" in manifest.tools[0].input_schema["required"]
