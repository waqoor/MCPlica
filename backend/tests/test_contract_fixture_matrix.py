import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from app.compilers.mcp.compiler import compile_manifest
from app.core.exceptions import CompilationError, ReferenceResolutionError
from app.domain.validation import FindingSeverity
from app.parsers.openapi.parser import parse_openapi
from app.validators.build import validate_build
from scripts.generate_contract_matrix import CASES, OPENAPI_ROOT, MatrixCase, compile_case

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_fixture_has_exact_canonical_and_manifest_goldens(case: MatrixCase) -> None:
    canonical, manifest = compile_case(case)
    name = case.name
    canonical_golden = json.loads(
        ROOT.joinpath("tests", "fixtures", "canonical", f"{name}.json").read_text(encoding="utf-8")
    )
    manifest_golden = json.loads(
        ROOT.joinpath("tests", "fixtures", "manifests", f"{name}.json").read_text(encoding="utf-8")
    )

    assert canonical.model_dump(mode="json", by_alias=True) == canonical_golden
    assert manifest.model_dump(mode="json", by_alias=True) == manifest_golden
    repeated_canonical, repeated_manifest = compile_case(case)
    assert repeated_canonical == canonical
    assert repeated_manifest == manifest
    assert hashlib.sha256(manifest.model_dump_json(by_alias=True).encode()).digest() == (
        hashlib.sha256(repeated_manifest.model_dump_json(by_alias=True).encode()).digest()
    )
    findings = validate_build(
        canonical,
        manifest,
        excluded_operation_keys=frozenset(),
        canonical_sha256=manifest.build.canonical_sha256,
        runtime_version="1.0.0",
    )
    assert not [item for item in findings if item.severity is FindingSeverity.ERROR]


def test_comprehensive_fixture_covers_risk_matrix_semantics() -> None:
    case = next(case for case in CASES if case.name == "pipeline-matrix-3.1-json")
    canonical, manifest = compile_case(case)

    assert len(canonical.servers) == 3
    assert len(canonical.operations) == len(manifest.enabled_tools()) == 7
    assert {profile.type for profile in manifest.auth_profiles} == {
        "bearer",
        "basic",
        "api_key",
        "oauth2_client_credentials",
    }
    assert {
        profile.location for profile in manifest.auth_profiles if profile.type == "api_key"
    } == {"header", "query"}
    assert {tool.request_mapping.method.value for tool in manifest.tools} >= {
        "GET",
        "POST",
    }
    assert {
        tool.request_mapping.body.media_type
        for tool in manifest.tools
        if tool.request_mapping.body is not None
    } == {
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }
    upload = next(tool for tool in manifest.tools if tool.name == "upload_matrix_file")
    assert upload.request_mapping.body is not None
    assert [item.part_name for item in upload.request_mapping.body.multipart_files] == ["file"]
    assert "$defs" in next(
        tool.input_schema for tool in manifest.tools if tool.name == "create_matrix_item"
    )
    get_item = next(tool for tool in manifest.tools if tool.name == "get_matrix_item")
    assert {parameter.target.value for parameter in get_item.request_mapping.parameters} == {
        "path",
        "query",
        "header",
    }


def test_malformed_and_unsupported_fixtures_fail_closed_at_the_origin() -> None:
    malformed_path = OPENAPI_ROOT / "malformed-ref-3.1.json"
    malformed_raw = malformed_path.read_bytes()
    with pytest.raises(ReferenceResolutionError, match="immutable source dependency"):
        parse_openapi(
            json.loads(malformed_raw),
            project_id=UUID(int=1),
            source_version_id=UUID(int=2),
            content_sha256=hashlib.sha256(malformed_raw).hexdigest(),
        )

    unsupported_path = OPENAPI_ROOT / "unsupported-cookie-3.1.yaml"
    unsupported_raw = unsupported_path.read_bytes()
    source = yaml.safe_load(unsupported_raw)
    assert isinstance(source, dict)
    canonical = parse_openapi(
        source,
        project_id=UUID(int=1),
        source_version_id=UUID(int=2),
        content_sha256=hashlib.sha256(unsupported_raw).hexdigest(),
    )
    with pytest.raises(CompilationError, match="cookie parameters are not supported"):
        compile_manifest(
            canonical,
            project_id=str(UUID(int=1)),
            project_name="Unsupported cookie parameter",
            project_slug="unsupported-cookie",
            build_id="fixture-unsupported-cookie",
            created_at=datetime(2026, 8, 27, tzinfo=UTC),
        )
