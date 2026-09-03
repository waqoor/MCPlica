from pathlib import Path

import pytest
from mcp_contracts import VERSION, MCPManifest
from starlette.testclient import TestClient

from app.validation_harness import inspect_runtime_candidate
from app.validation_main import app


def _manifest() -> MCPManifest:
    path = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"
    return MCPManifest.model_validate_json(path.read_bytes())


async def test_candidate_runs_through_pinned_runtime_and_official_client() -> None:
    manifest = _manifest()
    report = await inspect_runtime_candidate(manifest, runtime_version="1.0.0")

    assert report["protocol_version"] == "2026-07-28"
    assert report["tools"] == ["get_pet"]
    assert report["exercised_tools"] == ["get_pet"]
    assert report["request_mapping_count"] == 1


async def test_runtime_rejected_contract_never_produces_validation_evidence() -> None:
    manifest = _manifest()
    invalid_tool = manifest.tools[0].model_copy(
        update={"output_schema": {"type": "array", "items": {"type": "string"}}}
    )
    invalid = manifest.model_copy(update={"tools": [invalid_tool]})

    with pytest.raises(ValueError, match="output schema must be object-shaped"):
        await inspect_runtime_candidate(invalid, runtime_version="1.0.0")


async def test_candidate_is_rejected_when_any_enabled_tool_cannot_be_exercised() -> None:
    manifest = _manifest()
    unsynthesizable = manifest.tools[0].model_copy(
        update={
            "name": "get_pet_with_strict_code",
            "operation_key": "op_fixture_get_pet_with_strict_code",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pet_id": {"type": "string"},
                    "code": {"type": "string", "pattern": "^Z{50}$"},
                },
                "required": ["pet_id", "code"],
                "additionalProperties": False,
            },
        }
    )
    candidate = manifest.model_copy(update={"tools": [manifest.tools[0], unsynthesizable]})

    with pytest.raises(ValueError, match="get_pet_with_strict_code"):
        await inspect_runtime_candidate(candidate, runtime_version="1.0.0")


async def test_candidate_is_rejected_when_success_output_cannot_be_exercised() -> None:
    manifest = _manifest()
    response = (
        manifest.tools[0]
        .responses[0]
        .model_copy(
            update={
                "schema_": {
                    "type": "object",
                    "properties": {
                        "strict_code": {"type": "string", "pattern": "^Z{50}$"},
                    },
                    "required": ["strict_code"],
                    "additionalProperties": False,
                }
            }
        )
    )
    tool = manifest.tools[0].model_copy(update={"responses": [response]})
    candidate = manifest.model_copy(update={"tools": [tool]})

    with pytest.raises(ValueError, match="valid successful response.*get_pet"):
        await inspect_runtime_candidate(candidate, runtime_version="1.0.0")


def test_validator_http_boundary_is_bounded_and_returns_runtime_evidence() -> None:
    manifest = _manifest()
    with TestClient(app) as client:
        health = client.get("/healthz")
        response = client.post(
            "/validate",
            content=manifest.model_dump_json(by_alias=True),
            headers={"Content-Type": "application/json"},
        )
        wrong_type = client.post(
            "/validate",
            content=b"{}",
            headers={"Content-Type": "text/plain"},
        )

    assert health.json()["runtime_version"] == VERSION
    assert response.status_code == 200
    assert response.json()["request_mapping_count"] == 1
    assert wrong_type.status_code == 415
