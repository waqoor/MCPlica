import json
import logging
import sys

import httpx
import pytest
from pydantic import SecretStr
from pydantic import ValidationError as PydanticValidationError

from app.core.config import Settings
from app.core.logging import JsonLogFormatter
from app.main import create_app
from app.observability import observe_http_request, observe_openrouter_usage, render_metrics


def _production_settings() -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        env="production",
        frontend_origin="https://ui.example.com",
        api_domain="api.example.com",
        mcp_domain="mcp.example.com",
        metrics_bearer_token=SecretStr("m" * 32),
        secret_encryption_key=SecretStr("encryption-key"),
        auth_signing_key=SecretStr("signing-key"),
        refresh_token_pepper=SecretStr("refresh-pepper"),
        default_admin_email=None,
        default_admin_password=None,
        traefik_tls=True,
        mcp_runtime_image="mcplica/runtime@sha256:" + "a" * 64,
    )


def test_production_settings_fail_closed_for_local_domains_and_metrics_auth() -> None:
    values = _production_settings().model_dump()
    values["api_domain"] = "api.localhost"
    with pytest.raises(ValueError, match="non-localhost"):
        create_app(Settings.model_validate(values))

    values = _production_settings().model_dump()
    values["metrics_bearer_token"] = None
    with pytest.raises(ValueError, match="metrics_bearer_token"):
        create_app(Settings.model_validate(values))

    with pytest.raises(PydanticValidationError, match="non-localhost MCP domain"):
        Settings.model_validate(
            {
                **_production_settings().model_dump(),
                "mcp_domain": "mcp.localhost",
            }
        )


def test_blank_optional_secrets_from_example_environment_are_unconfigured() -> None:
    settings = Settings.model_validate(
        {
            "env": "test",
            "metrics_bearer_token": "",
            "openrouter_api_key": "",
            "secret_encryption_key": "",
            "auth_signing_key": "",
            "refresh_token_pepper": "",
            "bootstrap_secret": "",
        }
    )
    assert settings.metrics_bearer_token is None
    assert settings.openrouter_api_key is None
    assert settings.secret_encryption_key is None


async def test_production_host_policy_and_authenticated_metrics_endpoint() -> None:
    app = create_app(_production_settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.example.com") as client:
        assert (await client.get("/api/v1/health")).status_code == 200
        rejected = await client.get("/api/v1/health", headers={"Host": "evil.example"})
        assert rejected.status_code == 400
        assert (await client.get("/metrics")).status_code == 401
        response = await client.get(
            "/metrics",
            headers={"Authorization": f"Bearer {'m' * 32}"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "mcplica_http_requests_total" in response.text

    loopback_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=loopback_transport,
        base_url="http://127.0.0.1",
    ) as loopback:
        assert (await loopback.get("/api/v1/health")).status_code == 200


def test_json_logs_and_metrics_use_bounded_labels() -> None:
    record = logging.LogRecord(
        name="mcplica.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request.completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-1"
    record.route = "/api/v1/builds/{build_id}"
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["message"] == "request.completed"
    assert payload["request_id"] == "request-1"
    assert payload["route"] == "/api/v1/builds/{build_id}"

    observe_http_request("GET", "/api/v1/builds/{build_id}", 200, 0.01)
    observe_openrouter_usage(
        {
            "prompt_tokens": 2,
            "completion_tokens": 1,
            "total_tokens": 3,
            "cost": 0.001,
            "ignored": "not-a-number",
        }
    )
    rendered = render_metrics().decode()
    assert 'route="/api/v1/builds/{build_id}"' in rendered
    assert "mcplica_openrouter_usage_total" in rendered


def test_json_logs_preserve_safe_lifecycle_context_and_omit_sensitive_content() -> None:
    sentinel = "SENTINEL-secret-value"
    try:
        try:
            raise ValueError(f"password={sentinel}")
        except ValueError as cause:
            raise RuntimeError(f"Bearer {sentinel}") from cause
    except RuntimeError:
        record = logging.LogRecord(
            name="mcplica.worker",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg=f"request failed?api_key={sentinel}",
            args=(),
            exc_info=sys.exc_info(),
        )
    record.cleanup_target_id = "00000000-0000-0000-0000-000000000001"
    record.cleanup_job_id = "00000000-0000-0000-0000-000000000002"
    record.runtime_command_id = "00000000-0000-0000-0000-000000000003"
    record.admission_attempt = 4
    record.retryable = True
    record.route = f"/api/v1/source?api_key={sentinel}"
    record.password = sentinel

    rendered = JsonLogFormatter().format(record)
    payload = json.loads(rendered)

    assert sentinel not in rendered
    assert payload["message"] == "log.message_omitted"
    assert payload["exception"] == {
        "type": "RuntimeError",
        "chain": ["RuntimeError", "ValueError"],
    }
    assert payload["cleanup_target_id"].endswith("1")
    assert payload["cleanup_job_id"].endswith("2")
    assert payload["runtime_command_id"].endswith("3")
    assert payload["admission_attempt"] == 4
    assert payload["retryable"] is True
    assert payload["route"] == "/api/v1/source"
    assert "password" not in payload


async def test_production_same_origin_ui_proxy_host_is_allowed() -> None:
    app = create_app(_production_settings())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://ui.example.com"
    ) as client:
        assert (await client.get("/api/v1/health")).status_code == 200
        rejected = await client.get("/api/v1/health", headers={"Host": "unrelated.example.com"})
        assert rejected.status_code == 400
