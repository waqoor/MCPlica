import hashlib
from uuid import UUID

from mcp_contracts import CanonicalApi
from mcp_contracts.json_types import JsonObject

from app.parsers.documentation import (
    DocumentSection,
    NormalizedDocument,
    chunk_document,
)
from app.parsers.openapi.parser import parse_openapi
from app.services.indexing.service import semantic_chunks


def _canonical() -> CanonicalApi:
    source: JsonObject = {
        "openapi": "3.1.0",
        "info": {
            "title": "Orders",
            "version": "1",
            "description": "Order lifecycle API",
        },
        "servers": [{"url": "https://orders.example.com"}],
        "components": {
            "securitySchemes": {"ordersBearer": {"type": "http", "scheme": "bearer"}},
            "schemas": {
                "Order": {
                    "type": "object",
                    "description": "A customer order",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Current fulfilment status",
                        }
                    },
                }
            },
        },
        "paths": {
            "/orders/{orderId}": {
                "get": {
                    "operationId": "getOrder",
                    "summary": "Read an order",
                    "description": "Returns one order by identifier",
                    "tags": ["orders"],
                    "security": [{"ordersBearer": []}],
                    "parameters": [
                        {
                            "name": "orderId",
                            "in": "path",
                            "required": True,
                            "description": "Stable order identifier",
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "The order",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Order"}
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    return parse_openapi(
        source,
        project_id=UUID(int=91),
        source_version_id=UUID(int=92),
        content_sha256=hashlib.sha256(b"orders").hexdigest(),
    )


def test_no_documentation_still_produces_complete_source_semantic_chunks() -> None:
    chunks = semantic_chunks(
        _canonical(),
        project_id=UUID(int=91),
        generation_id=UUID(int=93),
        max_chars=6_000,
    )
    kinds = {chunk.source_kind for chunk in chunks}
    assert kinds == {
        "operation_semantics",
        "schema_semantics",
        "security_semantics",
    }
    combined = "\n".join(chunk.text for chunk in chunks)
    for evidence in (
        "Returns one order by identifier",
        "Stable order identifier",
        "Current fulfilment status",
        "ordersBearer",
        "#/paths/~1orders~1{orderId}/get",
    ):
        assert evidence in combined
    operation_chunk = next(chunk for chunk in chunks if chunk.source_kind == "operation_semantics")
    assert operation_chunk.operation_keys == [_canonical().operations[0].key]


def test_mixed_documentation_and_semantics_are_labeled_and_generation_isolated() -> None:
    canonical = _canonical()
    first_generation = UUID(int=93)
    second_generation = UUID(int=94)
    semantic_first = semantic_chunks(
        canonical,
        project_id=canonical.project_id,
        generation_id=first_generation,
        max_chars=6_000,
    )
    semantic_second = semantic_chunks(
        canonical,
        project_id=canonical.project_id,
        generation_id=second_generation,
        max_chars=6_000,
    )
    documentation = chunk_document(
        NormalizedDocument(
            source_version_id=UUID(int=95),
            title="Runbook",
            text="Retry failed orders safely.",
            sections=[
                DocumentSection(
                    path=["Runbook"],
                    heading="Runbook",
                    text="Retry failed orders safely.",
                    ordinal=0,
                )
            ],
        ),
        project_id=canonical.project_id,
        generation_id=first_generation,
        source_content_sha256="a" * 64,
        max_chars=500,
        overlap_chars=0,
    )
    mixed = [*semantic_first, *documentation]
    assert {chunk.source_kind for chunk in mixed} >= {
        "documentation",
        "operation_semantics",
    }
    assert {chunk.generation_id for chunk in mixed} == {first_generation}
    assert {chunk.generation_id for chunk in semantic_second} == {second_generation}
    assert [chunk.chunk_id for chunk in semantic_first] == [
        chunk.chunk_id for chunk in semantic_second
    ]
