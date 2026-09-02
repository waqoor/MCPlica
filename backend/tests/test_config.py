import re
from pathlib import Path

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


class _ComposeLoader(yaml.SafeLoader):
    """Parse Compose override tags without applying merge semantics in unit tests."""


_ComposeLoader.add_constructor("!reset", lambda _loader, _node: None)
_ComposeLoader.add_constructor("!override", yaml.SafeLoader.construct_sequence)


def test_default_admin_credentials_must_be_configured_as_a_pair() -> None:
    with pytest.raises(ValidationError, match="must be configured together"):
        Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue]
            env="development",
            default_admin_email="admin@admin.com",
            default_admin_password=None,
        )


def test_default_admin_credentials_are_development_only_and_masked() -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        env="development",
        default_admin_email="admin@admin.com",
        default_admin_password=SecretStr("admin@321"),
    )
    assert "admin@321" not in repr(settings)

    with pytest.raises(ValidationError, match="development-only"):
        Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue]
            env="production",
            default_admin_email="admin@admin.com",
            default_admin_password=SecretStr("admin@321"),
        )


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

    assert settings.multipart_spool_capacity_bytes >= 2 * (upload_limit + 1_048_576)
    assert tmpfs_capacity > settings.multipart_spool_capacity_bytes

    nginx = (compose_path.parent / "docker" / "nginx.conf").read_text(encoding="utf-8")
    assert "client_max_body_size 101m;" in nginx


def test_compose_application_services_wait_for_schema_migrations() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((root / "infra" / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert services["migrate"]["command"] == [
        "alembic",
        "-c",
        "../migrations/alembic.ini",
        "upgrade",
        "head",
    ]
    assert services["migrate"]["restart"] == "no"
    for service_name in ("api", "builder-worker", "deployment-worker"):
        assert services[service_name]["depends_on"]["migrate"] == {
            "condition": "service_completed_successfully"
        }

    production = yaml.load(
        (root / "infra" / "compose.production.yaml").read_text(encoding="utf-8"),
        Loader=_ComposeLoader,
    )
    assert production["services"]["traefik"]["ports"] == ["80:80", "443:443"]
    assert production["services"]["migrate"].get("build") is None
    assert production["services"]["migrate"]["image"].startswith("${BACKEND_IMAGE:")
    for service_name in ("api", "runtime-validator", "frontend"):
        assert production["services"][service_name]["build"] is None


@pytest.mark.parametrize("field", ["source_retention_days", "build_retention_count"])
def test_blank_optional_retention_disables_retention(field: str) -> None:
    settings = Settings.model_validate({field: ""})
    assert getattr(settings, field) is None
    with pytest.raises(ValidationError):
        Settings.model_validate({field: 0})


def test_redis_socket_timeouts_must_fit_inside_readiness_deadline() -> None:
    settings = Settings(
        readiness_timeout_seconds=5,
        redis_socket_connect_timeout_seconds=2,
        redis_socket_timeout_seconds=4,
    )
    assert settings.redis_socket_timeout_seconds == 4

    with pytest.raises(ValidationError, match="cannot exceed the readiness timeout"):
        Settings(
            readiness_timeout_seconds=1,
            redis_socket_connect_timeout_seconds=2,
        )


def test_example_environment_has_unique_keys_and_loads() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / ".env.example"
    keys = [
        line.split("=", 1)[0]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    ]
    assert len(keys) == len(set(keys))
    settings = Settings(_env_file=path)  # pyright: ignore[reportCallIssue]
    assert settings.source_retention_days is None


def test_compose_recovery_and_isolation_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    services = yaml.safe_load((root / "infra/compose.yaml").read_text())["services"]
    oneshot = {"migrate", "runtime-init"}
    for name, service in services.items():
        if name in oneshot:
            assert service["restart"] == "no"
        else:
            assert service["restart"] == "unless-stopped"
            assert "healthcheck" in service
            assert service["logging"]["options"]["max-size"]
    for name in ("postgres", "redis", "milvus", "minio", "etcd"):
        assert services[name]["networks"] == ["builder"]
        assert not services[name].get("ports")
    for name in ("api", "builder-worker"):
        assert not any("docker.sock" in str(item) for item in services[name].get("volumes", []))
    assert "milvus" not in services["api"]["depends_on"]
    assert services["builder-worker"]["depends_on"]["runtime-validator"]["condition"] == (
        "service_healthy"
    )
    assert services["deployment-worker"]["depends_on"]["runtime-init"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["api"]["image"] == services["migrate"]["image"]
    assert services["api"]["build"] == services["migrate"]["build"]


def test_all_production_application_images_disable_local_builds() -> None:
    root = Path(__file__).resolve().parents[2]
    services = yaml.load(
        (root / "infra/compose.production.yaml").read_text(), Loader=_ComposeLoader
    )["services"]
    for name in (
        "migrate",
        "runtime-init",
        "api",
        "builder-worker",
        "deployment-worker",
        "runtime-validator",
        "frontend",
    ):
        assert "build" in services[name]
        assert services[name]["build"] is None
        assert ":?" in services[name]["image"]
