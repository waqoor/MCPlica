import pytest
from pydantic import SecretStr

from app.cli.ensure_development_admin import (
    _development_admin_credentials,
    _require_development_environment,
)
from app.core.config import Settings


def test_development_admin_credentials_come_from_settings() -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        env="development",
        default_admin_email="admin@admin.com",
        default_admin_password=SecretStr("admin@321"),
    )

    assert _development_admin_credentials(settings) == (
        "admin@admin.com",
        "admin@321",
    )


def test_development_admin_is_production_guarded() -> None:
    _require_development_environment("development")
    with pytest.raises(RuntimeError, match="development-only"):
        _require_development_environment("production")
    with pytest.raises(RuntimeError, match="development-only"):
        _require_development_environment("test")


def test_development_admin_requires_configured_credentials() -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        env="development",
        default_admin_email=None,
        default_admin_password=None,
    )

    with pytest.raises(RuntimeError, match="DEFAULT_ADMIN_EMAIL"):
        _development_admin_credentials(settings)
