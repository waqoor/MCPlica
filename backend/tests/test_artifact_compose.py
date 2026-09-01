import yaml

from app.services.artifacts import _compose_example


def test_export_compose_supplies_required_production_runtime_inputs() -> None:
    example = yaml.safe_load(_compose_example("example", "a" * 64))
    service = example["services"]["example-mcp"]
    environment = service["environment"]
    assert environment["MCP_ENVIRONMENT"] == "production"
    assert environment["MCP_MANIFEST_SHA256"] == "a" * 64
    assert environment["MCP_AUTH_OVERLAY_SHA256"].startswith("${MCP_AUTH_OVERLAY_SHA256:?")
    assert environment["MCP_ALLOWED_ORIGINS"] == environment["MCP_PUBLIC_BASE_URL"]
    assert "ports" not in service
