import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_control_plane_processes_share_interpolated_configuration() -> None:
    services = yaml.safe_load((ROOT / "infra/compose.yaml").read_text())["services"]
    expected = services["api"]["environment"]
    for name in ("migrate", "builder-worker", "deployment-worker"):
        assert services[name]["environment"] == expected
    for name in ("DATABASE_URL", "BUILD_QUEUE_NAME", "DEPLOYMENT_QUEUE_NAME", "RUNTIME_HOST_ROOT"):
        assert expected[name].startswith("${" + name + ":")


def test_runtime_mount_destination_matches_process_configuration() -> None:
    services = yaml.safe_load((ROOT / "infra/compose.yaml").read_text())["services"]
    for name in ("runtime-init", "deployment-worker"):
        service = services[name]
        mount = next(value for value in service["volumes"] if isinstance(value, dict))
        assert mount["target"] == service["environment"]["RUNTIME_WORKER_ROOT"]
    assert services["runtime-init"]["env_file"] == []
    assert set(services["runtime-init"]["environment"]) == {
        "RUNTIME_UID",
        "RUNTIME_GID",
        "RUNTIME_WORKER_ROOT",
    }


def test_workers_consume_the_same_queues_as_the_control_plane() -> None:
    services = yaml.safe_load((ROOT / "infra/compose.yaml").read_text())["services"]
    for service, queue in (
        ("builder-worker", "BUILD_QUEUE_NAME"),
        ("deployment-worker", "DEPLOYMENT_QUEUE_NAME"),
    ):
        assert services[service]["command"][-1] == services["api"]["environment"][queue]


def test_control_plane_waits_for_migrations_and_runtime_permissions() -> None:
    services = yaml.safe_load((ROOT / "infra/compose.yaml").read_text())["services"]
    for name in ("api", "builder-worker", "deployment-worker"):
        assert services[name]["depends_on"]["migrate"]["condition"] == (
            "service_completed_successfully"
        )
    assert services["deployment-worker"]["depends_on"]["runtime-init"]["condition"] == (
        "service_completed_successfully"
    )
    for name in ("postgres", "redis", "milvus", "etcd", "minio"):
        assert not services[name].get("ports")


def test_edge_routing_uses_the_configured_network() -> None:
    model = yaml.safe_load((ROOT / "infra/compose.yaml").read_text())
    network = "${TRAEFIK_NETWORK:-mcplica-edge}"
    assert model["networks"]["edge"]["name"] == network
    for name in ("api", "frontend"):
        assert model["services"][name]["labels"]["traefik.docker.network"] == network


def test_make_commands_use_the_same_absolute_python_environments() -> None:
    result = subprocess.run(
        ["make", "--no-print-directory", "-n", "install-python", "test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    commands = [line for line in result.stdout.splitlines() if "UV_PROJECT_ENVIRONMENT=" in line]
    assert len(commands) == 4
    for component in ("backend", "mcp_runtime"):
        setting = f'UV_PROJECT_ENVIRONMENT="{ROOT / component / ".venv"}"'
        assert sum(setting in command for command in commands) == 2
    assert all("--frozen --extra dev" in command for command in commands)
