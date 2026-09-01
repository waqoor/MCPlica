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
