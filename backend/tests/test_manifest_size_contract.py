from datetime import UTC, datetime
from uuid import UUID

from mcp_contracts import MCPResource

from app.compilers.mcp.compiler import compile_manifest
from app.core.canonical_json import canonical_json_bytes
from app.parsers.openapi.parser import parse_openapi
from app.validators.build import validate_runtime_manifest_size


def test_ten_thousand_default_chunks_are_rejected_before_ready() -> None:
    project_id = UUID(int=901)
    source_version_id = UUID(int=902)
    canonical = parse_openapi(
        {
            "openapi": "3.1.0",
            "info": {"title": "Manifest size", "version": "1"},
            "servers": [{"url": "https://api.example.test"}],
            "paths": {
                "/health": {
                    "get": {
                        "operationId": "health",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        },
        project_id=project_id,
        source_version_id=source_version_id,
        content_sha256="1" * 64,
    )
    chunk_text = "x" * 6_000
    resources = [
        MCPResource(
            uri=f"docs://manifest-size/{source_version_id}/chunk-{index:05d}",
            name=f"Chunk {index}",
            content=chunk_text,
            provenance={
                "source_version_id": str(source_version_id),
                "chunk_id": f"chunk-{index:05d}",
            },
        )
        for index in range(10_000)
    ]

    manifest = compile_manifest(
        canonical,
        project_id=str(project_id),
        project_name="Manifest size",
        project_slug="manifest-size",
        build_id=str(UUID(int=903)),
        created_at=datetime.now(UTC),
        resources=resources,
    )
    manifest_bytes = canonical_json_bytes(manifest)
    findings = validate_runtime_manifest_size(
        manifest_bytes,
        maximum_bytes=10_000_000,
    )

    assert len(manifest.resources) == 10_000
    assert len(manifest_bytes) > 60_000_000
    assert [finding.code for finding in findings] == ["MANIFEST_RUNTIME_SIZE_LIMIT_EXCEEDED"]
    assert findings[0].details["actual_bytes"] == len(manifest_bytes)
