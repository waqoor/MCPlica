import json
from pathlib import Path

from app.openapi_artifact import render_openapi_artifact


def test_tracked_openapi_artifact_matches_live_fastapi_schema() -> None:
    artifact = Path(__file__).parents[2] / "openapi.json"

    assert artifact.read_bytes() == render_openapi_artifact()


def test_manifest_and_ai_evidence_have_authoritative_response_contracts() -> None:
    document = json.loads(render_openapi_artifact())

    manifest = document["paths"]["/api/v1/builds/{build_id}/manifest"]["get"]
    manifest_schema = manifest["responses"]["200"]["content"]["application/json"]["schema"]
    ai_runs = document["paths"]["/api/v1/builds/{build_id}/ai-runs"]["get"]
    ai_schema = ai_runs["responses"]["200"]["content"]["application/json"]["schema"]

    assert manifest_schema == {"$ref": "#/components/schemas/MCPManifest"}
    assert ai_schema == {"$ref": "#/components/schemas/Page_BuildAIRunRead_"}
    page_schema = document["components"]["schemas"]["Page_BuildAIRunRead_"]
    assert page_schema["properties"]["items"]["items"] == {
        "$ref": "#/components/schemas/BuildAIRunRead"
    }
    assert {"items", "total", "page", "page_size"} == set(page_schema["required"])


def test_source_findings_expose_exact_structured_attribution() -> None:
    document = json.loads(render_openapi_artifact())

    schema = document["components"]["schemas"]["SourceIssueRead"]

    assert {
        "source_version_id",
        "stage",
        "code",
        "severity",
        "message",
        "details",
    }.issubset(schema["required"])
    assert {"pointer", "line", "column"}.issubset(schema["properties"])
    assert "location" not in schema["properties"]
