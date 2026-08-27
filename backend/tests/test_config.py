import re
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings


def test_csv_environment_settings_accept_operator_friendly_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SOURCE_ALLOWED_HOSTS",
        "api.example.com, docs.example.com",
    )
    monkeypatch.setenv(
        "SOURCE_ALLOWED_PRIVATE_CIDRS",
        "10.20.0.0/16,192.168.4.0/24",
    )
    monkeypatch.setenv(
        "RUNTIME_ALLOWED_DEVELOPMENT_HOSTS",
        "host.docker.internal, localhost",
    )

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.source_allowed_hosts == ["api.example.com", "docs.example.com"]
    assert settings.source_allowed_private_cidrs == ["10.20.0.0/16", "192.168.4.0/24"]
    assert settings.runtime_allowed_development_hosts == [
        "host.docker.internal",
        "localhost",
    ]


def test_default_upload_and_document_limits_are_100_mb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UPLOAD_MAX_BYTES", raising=False)
    monkeypatch.delenv("DOCUMENT_MAX_BYTES", raising=False)

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.upload_max_bytes == 100_000_000
    assert settings.document_max_bytes == 100_000_000


def test_compose_api_tmpfs_can_spool_the_default_upload_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UPLOAD_MAX_BYTES", raising=False)
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    upload_limit = settings.upload_max_bytes
    compose_path = Path(__file__).resolve().parents[2] / "infra" / "compose.yaml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    tmpfs_entries = compose["services"]["api"]["tmpfs"]
    tmp_entry = next(entry for entry in tmpfs_entries if entry.startswith("/tmp:"))
    match = re.search(r"(?:^|[:,])size=(\d+)([kmg])(?:,|$)", tmp_entry, re.IGNORECASE)
    assert match is not None
    units = {"k": 1024, "m": 1024**2, "g": 1024**3}
    tmpfs_capacity = int(match.group(1)) * units[match.group(2).lower()]

    assert tmpfs_capacity > upload_limit
