import hashlib
from pathlib import Path

import pytest
from mcp_contracts import MCPManifest, MCPResource

from app.manifest.loader import load_manifest
from app.manifest.schema import validate_manifest


def _fixture_path() -> Path:
    return Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"


def test_manifest_is_bounded_hashed_and_runtime_compatible() -> None:
    path = _fixture_path()
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = load_manifest(
        str(path),
        expected_sha256=expected,
        max_bytes=100_000,
        runtime_version="1.0.0",
    )
    assert manifest.project.slug == "petstore"

    with pytest.raises(ValueError, match="SHA-256 verification failed"):
        load_manifest(str(path), expected_sha256="0" * 64, runtime_version="1.0.0")
    with pytest.raises(ValueError, match="incompatible"):
        load_manifest(str(path), runtime_version="2.0.0")


def test_manifest_loader_uses_inclusive_exact_byte_boundary() -> None:
    path = _fixture_path()
    byte_size = path.stat().st_size

    assert (
        load_manifest(
            str(path),
            max_bytes=byte_size,
            runtime_version="1.0.0",
        ).project.slug
        == "petstore"
    )
    with pytest.raises(ValueError, match="exceeds configured size limit"):
        load_manifest(
            str(path),
            max_bytes=byte_size - 1,
            runtime_version="1.0.0",
        )


def test_ten_thousand_default_chunks_are_rejected_by_runtime_loader(
    tmp_path: Path,
) -> None:
    base = MCPManifest.model_validate_json(_fixture_path().read_bytes())
    chunk_text = "x" * 6_000
    resources = [
        MCPResource(
            uri=f"docs://petstore/source/chunk-{index:05d}",
            name=f"Chunk {index}",
            content=chunk_text,
        )
        for index in range(10_000)
    ]
    manifest_path = tmp_path / "oversized-manifest.json"
    manifest_path.write_bytes(
        base.model_copy(update={"resources": resources}).model_dump_json(by_alias=True).encode()
    )

    assert manifest_path.stat().st_size > 60_000_000
    with pytest.raises(ValueError, match="exceeds configured size limit"):
        load_manifest(
            str(manifest_path),
            max_bytes=10_000_000,
            runtime_version="1.0.0",
        )


def test_manifest_host_allowlist_must_match_server_destinations() -> None:
    manifest = MCPManifest.model_validate_json(_fixture_path().read_bytes())
    security = manifest.security.model_copy(
        update={"allowed_upstream_hosts": ["other.example.com"]}
    )
    changed = manifest.model_copy(update={"security": security})
    with pytest.raises(ValueError, match="allowlist"):
        validate_manifest(changed, runtime_version="1.0.0")


@pytest.mark.parametrize("schema_name", ["input_schema", "output_schema"])
def test_manifest_rejects_remote_json_schema_references(schema_name: str) -> None:
    manifest = MCPManifest.model_validate_json(_fixture_path().read_bytes())
    tool = manifest.tools[0]
    remote_schema = {
        "type": "object",
        "properties": {"payload": {"$ref": "https://schemas.example.com/value.json"}},
    }
    changed_tool = tool.model_copy(update={schema_name: remote_schema})
    changed = manifest.model_copy(update={"tools": [changed_tool, *manifest.tools[1:]]})

    with pytest.raises(ValueError, match="non-local JSON Schema reference"):
        validate_manifest(changed, runtime_version="1.0.0")
