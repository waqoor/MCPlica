"""Regenerate the committed parser/compiler/runtime contract-matrix goldens.

This script is intentionally not part of the test command. Tests compare live
compiler output with the committed files so semantic changes require an
explicit, reviewable golden update.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import yaml

from app.compilers.mcp.compiler import compile_manifest
from app.domain.builds import BuildCredentialSnapshot
from app.domain.credentials import CredentialScheme
from app.parsers.identifiers import server_key
from app.parsers.openapi.parser import parse_openapi
from app.services.builds.credential_mapping import map_credentials

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ROOT = ROOT / "tests" / "fixtures" / "openapi"
CANONICAL_ROOT = ROOT / "tests" / "fixtures" / "canonical"
MANIFEST_ROOT = ROOT / "tests" / "fixtures" / "manifests"
PROJECT_ID = UUID(int=1)
SOURCE_VERSION_ID = UUID(int=2)
CREATED_AT = datetime(2026, 8, 27, tzinfo=UTC)


@dataclass(frozen=True)
class MatrixCase:
    name: str
    source_name: str
    active_server_url: str | None = None


CASES = (
    MatrixCase("schema-dialect-3.0-json", "schema-dialect-3.0.json"),
    MatrixCase("schema-dialect-3.0-yaml", "schema-dialect-3.0.yaml"),
    MatrixCase(
        "pipeline-matrix-3.1-json",
        "pipeline-matrix-3.1.json",
        "https://api.example.com/v1",
    ),
    MatrixCase("pipeline-matrix-3.1-yaml", "pipeline-matrix-3.1.yaml"),
)


def load_case(case: MatrixCase) -> tuple[bytes, dict[str, object]]:
    raw = OPENAPI_ROOT.joinpath(case.source_name).read_bytes()
    parsed = yaml.safe_load(raw) if case.source_name.endswith(".yaml") else json.loads(raw)
    if not isinstance(parsed, dict):
        raise TypeError(f"{case.source_name} must contain an object")
    return raw, cast(dict[str, object], parsed)


def compile_case(case: MatrixCase):
    raw, source = load_case(case)
    canonical = parse_openapi(
        source,
        project_id=PROJECT_ID,
        source_version_id=SOURCE_VERSION_ID,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        active_server_ref=(server_key(case.active_server_url) if case.active_server_url else None),
    )
    selections = map_credentials(canonical, _matrix_credentials())
    manifest = compile_manifest(
        canonical,
        project_id=str(PROJECT_ID),
        project_name=canonical.title,
        project_slug=case.name,
        build_id=f"fixture-{case.name}",
        created_at=CREATED_AT,
        security_selections=selections,
    )
    return canonical, manifest


def _matrix_credentials() -> list[BuildCredentialSnapshot]:
    return [
        BuildCredentialSnapshot(
            id=UUID(int=101),
            scheme_type=CredentialScheme.BEARER,
            metadata={"security_scheme": "bearerAuth"},
        ),
        BuildCredentialSnapshot(
            id=UUID(int=102),
            scheme_type=CredentialScheme.BASIC,
            metadata={"security_scheme": "basicAuth"},
        ),
        BuildCredentialSnapshot(
            id=UUID(int=103),
            scheme_type=CredentialScheme.API_KEY_HEADER,
            metadata={"security_scheme": "headerKey", "name": "X-API-Key"},
        ),
        BuildCredentialSnapshot(
            id=UUID(int=104),
            scheme_type=CredentialScheme.API_KEY_QUERY,
            metadata={"security_scheme": "queryKey", "name": "api_key"},
        ),
        BuildCredentialSnapshot(
            id=UUID(int=105),
            scheme_type=CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
            metadata={"security_scheme": "oauthAuth", "scope": "read"},
        ),
    ]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    for case in CASES:
        canonical, manifest = compile_case(case)
        _write_json(
            CANONICAL_ROOT / f"{case.name}.json",
            canonical.model_dump(mode="json", by_alias=True),
        )
        _write_json(
            MANIFEST_ROOT / f"{case.name}.json",
            manifest.model_dump(mode="json", by_alias=True),
        )


if __name__ == "__main__":
    main()
