import pytest

from app.core.config import Settings


def test_csv_environment_settings_accept_operator_friendly_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MCP_LICA_SOURCE_ALLOWED_HOSTS",
        "api.example.com, docs.example.com",
    )
    monkeypatch.setenv(
        "MCP_LICA_SOURCE_ALLOWED_PRIVATE_CIDRS",
        "10.20.0.0/16,192.168.4.0/24",
    )
    monkeypatch.setenv(
        "MCP_LICA_RUNTIME_ALLOWED_DEVELOPMENT_HOSTS",
        "host.docker.internal, localhost",
    )

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.source_allowed_hosts == ["api.example.com", "docs.example.com"]
    assert settings.source_allowed_private_cidrs == ["10.20.0.0/16", "192.168.4.0/24"]
    assert settings.runtime_allowed_development_hosts == [
        "host.docker.internal",
        "localhost",
    ]
