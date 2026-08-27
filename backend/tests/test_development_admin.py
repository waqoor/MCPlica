import pytest

from app.cli.ensure_development_admin import (
    DEFAULT_DEVELOPMENT_ADMIN_EMAIL,
    DEFAULT_DEVELOPMENT_ADMIN_PASSWORD,
    _require_development_environment,
)


def test_development_admin_defaults_are_explicit_and_production_guarded() -> None:
    assert DEFAULT_DEVELOPMENT_ADMIN_EMAIL == "admin@admin.com"
    assert DEFAULT_DEVELOPMENT_ADMIN_PASSWORD == "admin@321"
    _require_development_environment("development")
    with pytest.raises(RuntimeError, match="development-only"):
        _require_development_environment("production")
    with pytest.raises(RuntimeError, match="development-only"):
        _require_development_environment("test")
