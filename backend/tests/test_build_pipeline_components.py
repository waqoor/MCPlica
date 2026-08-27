import hashlib
import io
import zipfile
from datetime import UTC, datetime
from uuid import UUID

import httpx2
import pytest
import yaml
from mcp_contracts import MCPManifest

from app.clients.mcp import MCPValidationClient
from app.compilers.mcp.compiler import compile_manifest
from app.core.exceptions import CompilationError
from app.domain.analysis import OperationEnrichmentResult
from app.domain.builds import (
    BuildConfiguration,
    BuildCredentialSnapshot,
    BuildRecord,
    BuildStatus,
    BuildTrigger,
)
from app.domain.credentials import CredentialScheme
from app.domain.validation import ValidationReportRecord, ValidationStatus
from app.parsers.openapi.parser import parse_openapi
from app.services.artifacts import ArtifactService
from app.services.builds.credential_mapping import map_credentials
from app.services.builds.diff import diff_builds


def _canonical(*, summary: str = "Get product", secured: bool = False):
    operation: dict[str, object] = {
        "operationId": "getProduct",
        "summary": summary,
        "responses": {"200": {"description": "OK"}},
    }
    source: dict[str, object] = {
        "openapi": "3.1.0",
        "info": {"title": "Inventory", "version": "1.0"},
        "servers": [{"url": "https://inventory.example.com"}],
        "paths": {"/products": {"get": operation}},
    }
    if secured:
        source["components"] = {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
            }
        }
        operation["security"] = [{"bearerAuth": []}]
    return parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(summary.encode()).hexdigest(),
    )


def test_credential_mapping_fails_closed_on_ambiguity_and_honors_explicit_binding() -> None:
    canonical = _canonical(secured=True)
    credentials = [
        BuildCredentialSnapshot(
            id=UUID(int=10),
            scheme_type=CredentialScheme.BEARER,
            metadata={},
        ),
        BuildCredentialSnapshot(
            id=UUID(int=11),
            scheme_type=CredentialScheme.BEARER,
            metadata={},
        ),
    ]
    with pytest.raises(CompilationError, match="ambiguous"):
        map_credentials(canonical, credentials)
    selected = credentials[0].model_copy(update={"metadata": {"security_scheme": "bearerAuth"}})
    mapped = map_credentials(canonical, [selected, credentials[1]])
    selection = mapped[canonical.operations[0].key]
    assert selection.scheme_name == "bearerAuth"
    assert selection.credential_ref == str(selected.id)
    assert (
        map_credentials(
            canonical,
            [],
            excluded_operation_keys=frozenset({canonical.operations[0].key}),
        )
        == {}
    )


def test_oauth_profiles_preserve_exact_operation_scopes_method_and_optional_auth() -> None:
    source: dict[str, object] = {
        "openapi": "3.0.3",
        "info": {"title": "Scoped API", "version": "1.0"},
        "servers": [{"url": "https://api.example.com/v1"}],
        "components": {
            "securitySchemes": {
                "oauth": {
                    "type": "oauth2",
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "/oauth/token",
                            "scopes": {"read": "Read", "write": "Write"},
                        }
                    },
                }
            }
        },
        "paths": {
            "/read": {
                "get": {
                    "operationId": "read",
                    "security": [{"oauth": ["read"]}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/write": {
                "post": {
                    "operationId": "write",
                    "security": [{"oauth": ["write"]}],
                    "responses": {"204": {"description": "Done"}},
                }
            },
            "/optional": {
                "get": {
                    "operationId": "optional",
                    "security": [{}, {"oauth": ["write"]}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(b"scoped-api").hexdigest(),
    )
    credential = BuildCredentialSnapshot(
        id=UUID(int=20),
        scheme_type=CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
        metadata={
            "security_scheme": "oauth",
            "scope": "read write",
            "token_auth_method": "client_secret_post",
        },
    )
    selections = map_credentials(canonical, [credential])
    assert len(selections) == 2
    assert {tuple(selection.scopes) for selection in selections.values()} == {
        ("read",),
        ("write",),
    }
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Scoped API",
        project_slug="scoped-api",
        build_id="build-scoped-api",
        created_at=datetime(2026, 8, 27, tzinfo=UTC),
        security_selections=selections,
    )
    assert {tuple(profile.scopes) for profile in manifest.auth_profiles} == {
        ("read",),
        ("write",),
    }
    assert {profile.token_auth_method for profile in manifest.auth_profiles} == {
        "client_secret_post"
    }
    assert {str(profile.token_url) for profile in manifest.auth_profiles} == {
        "https://api.example.com/oauth/token"
    }
    optional = next(
        tool
        for tool in manifest.tools
        if next(
            operation for operation in canonical.operations if operation.key == tool.operation_key
        ).source_operation_id
        == "optional"
    )
    assert optional.security_profile_ref is None


def test_ai_enrichment_schema_has_no_executable_write_surface() -> None:
    with pytest.raises(ValueError):
        OperationEnrichmentResult.model_validate(
            {
                "operation_key": "get_products",
                "title": "Products",
                "description": "List products",
                "category": "inventory",
                "keywords": [],
                "documentation_chunk_ids": [],
                "relationship_hints": [],
                "confidence": 0.9,
                "warnings": [],
                "method": "DELETE",
            }
        )


def test_build_diff_is_structural_and_stable() -> None:
    previous = _canonical(summary="Get product")
    current = _canonical(summary="Retrieve product")
    result = diff_builds(current, previous)
    assert result.added_operations == []
    assert result.removed_operations == []
    assert result.changed_operations[0].operation_key == current.operations[0].key
    assert result.changed_operations[0].changes == ["source_semantics"]


class _MemoryStorage:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    async def put_bytes(self, namespace: str, value: bytes, *, max_bytes: int):
        from app.clients.storage import StoredObject

        assert len(value) <= max_bytes
        digest = hashlib.sha256(value).hexdigest()
        key = f"{namespace}/{digest}"
        self.values[key] = value
        return StoredObject(key, digest, len(value), True)


async def test_export_is_deterministic_protocol_compatible_and_contains_required_files() -> None:
    from typing import cast

    from app.providers.storage import ArtifactStorage

    canonical = _canonical()
    created_at = datetime(2026, 8, 26, tzinfo=UTC)
    build = BuildRecord(
        id=UUID(int=20),
        project_id=UUID(int=1),
        sequence=1,
        status=BuildStatus.PACKAGING,
        trigger=BuildTrigger.INITIAL,
        canonical_snapshot_id=UUID(int=21),
        previous_build_id=None,
        compiler_version="1.0.0",
        manifest_schema_version="mcp-manifest/v1",
        runtime_compatibility=">=1.0,<2.0",
        analysis_model="analysis/model",
        validation_model="validation/model",
        embedding_model=None,
        embedding_dimensions=0,
        prompt_bundle_version="1.0.0",
        enrichment_sha256="1" * 64,
        manifest_sha256=None,
        artifact_sha256=None,
        manifest_storage_key=None,
        artifact_storage_key=None,
        error_code=None,
        error_summary=None,
        requested_by=UUID(int=22),
        created_at=created_at,
        started_at=created_at,
        completed_at=None,
    )
    config = BuildConfiguration(
        inbound_auth_mode="static_bearer",
        include_documentation_in_analysis=False,
        max_operations=1000,
        max_context_chars=120_000,
        max_ai_concurrency=4,
        retrieval_top_k=5,
        source_max_bytes=100_000,
        document_max_bytes=100_000,
        document_max_text_chars=100_000,
        pdf_max_pages=100,
        documentation_chunk_chars=2_000,
        documentation_chunk_overlap_chars=200,
        max_document_chunks=1_000,
        embedding_batch_size=64,
        max_embedding_concurrency=4,
        runtime_timeout_ms=30_000,
        runtime_max_request_bytes=10_000_000,
        runtime_max_response_bytes=2_000_000,
        runtime_manifest_max_bytes=10_000_000,
        artifact_max_bytes=10_000_000,
    )
    manifest = compile_manifest(
        canonical,
        project_id=str(UUID(int=1)),
        project_name="Inventory",
        project_slug="inventory",
        build_id=str(build.id),
        created_at=created_at,
    )
    report = ValidationReportRecord(
        id=UUID(int=23),
        build_id=build.id,
        overall_status=ValidationStatus.PASS,
        operation_source_count=1,
        operation_excluded_count=0,
        operation_expected_count=1,
        operation_generated_count=1,
        coverage_percent=100,
        blocking_error_count=0,
        warning_count=0,
        findings=[],
        created_at=created_at,
    )
    storage = _MemoryStorage()
    artifacts = ArtifactService(cast(ArtifactStorage, storage))
    first = await artifacts.package(
        build=build,
        config=config,
        manifest=manifest,
        validation=report,
        project_name="Inventory",
        project_slug="inventory",
        source_version_ids=[str(UUID(int=2))],
    )
    second = await artifacts.package(
        build=build,
        config=config,
        manifest=manifest,
        validation=report,
        project_name="Inventory",
        project_slug="inventory",
        source_version_ids=[str(UUID(int=2))],
    )
    assert first.sha256 == second.sha256
    value = storage.values[first.storage_key]
    assert b"plaintext-secret-marker" not in value
    with zipfile.ZipFile(io.BytesIO(value)) as archive:
        assert archive.namelist() == [
            "README.md",
            "build-metadata.json",
            "compose.example.yaml",
            "manifest.json",
            "validation-report.json",
        ]
        compose = archive.read("compose.example.yaml").decode()
        assert "RUNTIME_IMAGE" in compose
        assert "SECRET_BUNDLE_HOST_PATH" in compose
        assert "plaintext-secret-marker" not in compose
        parsed_compose = yaml.safe_load(compose)
        service = parsed_compose["services"]["inventory-mcp"]
        assert service["read_only"] is True
        assert service["user"] == "10001:10001"
        assert service["cap_drop"] == ["ALL"]
        assert service["pids_limit"] == 256
        assert service["security_opt"] == ["no-new-privileges:true"]

    async def runtime_validator(request: httpx2.Request) -> httpx2.Response:
        payload = await request.aread()
        candidate = MCPManifest.model_validate_json(payload)
        tools = [tool.name for tool in candidate.enabled_tools()]
        resources = [str(resource.uri) for resource in candidate.resources]
        return httpx2.Response(
            200,
            json={
                "runtime_version": "1.0.0",
                "protocol_version": "2025-11-25",
                "manifest_sha256": hashlib.sha256(payload).hexdigest(),
                "tool_count": len(tools),
                "tools": tools,
                "resource_count": len(resources),
                "resources": resources,
                "exercised_tool_count": len(tools),
                "exercised_tools": tools,
                "request_mapping_count": len(tools),
            },
        )

    inspected = await MCPValidationClient(
        validator_endpoint="http://runtime-validator:8090/validate",
        validator_transport=httpx2.MockTransport(runtime_validator),
    ).inspect_manifest(manifest, runtime_version="1.0.0")
    assert inspected["tool_count"] == 1
