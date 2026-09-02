import hashlib
import os
import stat
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from mcp_contracts import RuntimeSecretBundle

from app.clients.docker import (
    _ROUTE_READINESS_PROBE,  # pyright: ignore[reportPrivateUsage]
    ContainerInfo,
    ContainerMount,
    DockerClient,
    RuntimeContainerSpec,
)
from app.clients.runtime_files import RuntimeFilesClient, RuntimeMounts
from app.core.config import Settings
from app.core.exceptions import (
    DockerOperationError,
    RuntimeHealthError,
    SecretMaterializationError,
)
from app.domain.deployments import DeploymentRecord, DeploymentStatus
from app.services.deployment.runtime_manager import RuntimeManager
from app.services.deployment.service import is_retryable_deployment_error


def _deployment() -> DeploymentRecord:
    return DeploymentRecord(
        id=uuid4(),
        project_id=uuid4(),
        build_id=uuid4(),
        status=DeploymentStatus.HEALTHCHECK,
        hostname="inventory.mcp.example.com",
        container_name=f"mcp-{uuid4().hex}",
        container_id=None,
        image_ref="mcplica/runtime@sha256:" + "1" * 64,
        image_digest=None,
        runtime_version="1.0.0",
        network_name=f"mcp-net-{uuid4().hex}",
        manifest_sha256="2" * 64,
        route_priority=101,
        stop_old_first=False,
        health_status="starting",
        deployed_by=uuid4(),
        created_at=datetime.now(UTC),
        started_at=None,
        stopped_at=None,
        failed_at=None,
        error_code=None,
        error_summary=None,
    )


def _secret_bundle() -> RuntimeSecretBundle:
    return RuntimeSecretBundle.model_validate(
        {
            "inbound_auth": {
                "mode": "static_bearer",
                "static_tokens": [{"id": "token-1", "sha256": "a" * 64}],
            }
        }
    )


def test_embedded_route_readiness_probe_is_valid_python() -> None:
    compile(_ROUTE_READINESS_PROBE, "<route-readiness-probe>", "exec")


@pytest.mark.asyncio
async def test_runtime_files_are_bounded_immutable_and_host_mapped(tmp_path: Path) -> None:
    worker_root = tmp_path / "runtime"
    uid_reader = cast(Callable[[], int], getattr(os, "getuid", lambda: 10_001))
    gid_reader = cast(Callable[[], int], getattr(os, "getgid", lambda: 10_001))
    runtime_uid = uid_reader()
    runtime_gid = gid_reader()
    client = RuntimeFilesClient(
        str(worker_root),
        docker_host_root="/srv/mcplica/runtime",
        runtime_uid=runtime_uid,
        runtime_gid=runtime_gid,
        max_manifest_bytes=1_024,
        max_secret_bundle_bytes=1_024,
    )
    deployment_id = uuid4()
    manifest = b'{"schema_version":"mcp-manifest/v1"}'
    digest = hashlib.sha256(manifest).hexdigest()

    mounts = await client.materialize(
        deployment_id,
        manifest_bytes=manifest,
        manifest_sha256=digest,
        secret_bundle=_secret_bundle(),
    )
    assert mounts == RuntimeMounts(
        f"/srv/mcplica/runtime/{deployment_id}/manifest.json",
        f"/srv/mcplica/runtime/{deployment_id}/runtime-secrets.json",
        hashlib.sha256(_secret_bundle().serialize_for_secret_mount()).hexdigest(),
    )
    manifest_path = worker_root / str(deployment_id) / "manifest.json"
    secret_path = worker_root / str(deployment_id) / "runtime-secrets.json"
    assert manifest_path.read_bytes() == manifest
    assert b"token-1" in secret_path.read_bytes()
    if os.name == "posix":
        assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600

    assert (
        await client.materialize(
            deployment_id,
            manifest_bytes=manifest,
            manifest_sha256=digest,
            secret_bundle=_secret_bundle(),
        )
        == mounts
    )
    changed = b'{"schema_version":"changed"}'
    with pytest.raises(SecretMaterializationError, match="different content"):
        await client.materialize(
            deployment_id,
            manifest_bytes=changed,
            manifest_sha256=hashlib.sha256(changed).hexdigest(),
            secret_bundle=_secret_bundle(),
        )
    with pytest.raises(SecretMaterializationError, match="configured limit"):
        await RuntimeFilesClient(
            str(tmp_path / "bounded"),
            docker_host_root="/srv/mcplica/bounded",
            runtime_uid=runtime_uid,
            runtime_gid=runtime_gid,
            max_manifest_bytes=4,
        ).materialize(
            uuid4(),
            manifest_bytes=b"12345",
            manifest_sha256=hashlib.sha256(b"12345").hexdigest(),
            secret_bundle=_secret_bundle(),
        )

    await client.remove(deployment_id)
    assert not manifest_path.parent.exists()


class _RecordingDocker:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.spec: RuntimeContainerSpec | None = None
        self.network_cleanup: tuple[str, str, str] | None = None
        self.route_probe: tuple[str, str, str, str, str, bool] | None = None
        self.inspect_result: ContainerInfo | None = ContainerInfo(
            "container-1", "runtime", "running", "healthy", "sha256:runtime"
        )

    async def ensure_network(self, name: str, *, project_id: str, edge_container_name: str) -> None:
        self.events.append("network")

    async def connect_edge_container_to_network(
        self, network_name: str, container_name: str
    ) -> None:
        self.events.append("edge")

    async def ensure_image(self, image_ref: str, *, pull_policy: str) -> str:
        self.events.append(f"image:{pull_policy}")
        return image_ref.split("@", 1)[1]

    async def create_runtime_container(self, spec: RuntimeContainerSpec) -> ContainerInfo:
        self.events.append("create")
        self.spec = spec
        return ContainerInfo("container-1", spec.name, "created", None, "")

    async def start_container(self, name: str) -> ContainerInfo:
        self.events.append("start")
        return ContainerInfo("container-1", name, "running", "starting", "")

    async def inspect_container(self, name: str) -> ContainerInfo | None:
        result = self.inspect_result
        if result is None:
            return None
        return ContainerInfo(result.id, name, result.status, result.health, result.image_id)

    async def wait_until_healthy(
        self,
        name: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float = 1.0,
    ) -> ContainerInfo:
        self.events.append("healthy")
        return ContainerInfo("container-1", name, "running", "healthy", "sha256:runtime")

    async def wait_until_route_ready(
        self,
        name: str,
        *,
        edge_container_name: str,
        hostname: str,
        expected_build_id: str,
        expected_deployment_id: str,
        tls: bool,
        timeout_seconds: float,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.events.append("route")
        self.route_probe = (
            name,
            edge_container_name,
            hostname,
            expected_build_id,
            expected_deployment_id,
            tls,
        )

    async def stop_container(self, name: str, *, timeout_seconds: int) -> None:
        self.events.append("stop")

    async def remove_container(self, name: str, *, force: bool = False) -> None:
        self.events.append(f"remove:{force}")

    async def remove_network_if_unused(
        self,
        name: str,
        *,
        project_id: str,
        keep_container: str,
    ) -> bool:
        self.network_cleanup = (name, project_id, keep_container)
        return True


@pytest.mark.asyncio
async def test_runtime_manager_builds_hardened_project_scoped_spec_and_waits_for_health() -> None:
    docker = _RecordingDocker()
    settings = Settings(
        env="test",
        runtime_host_root="/srv/mcplica/runtime",
        runtime_worker_root="/runtime-host",
        mcp_runtime_pull_policy="never",
    )
    manager = RuntimeManager(docker, settings)
    deployment = _deployment()
    provisioned = await manager.provision(
        deployment,
        RuntimeMounts("/host/manifest.json", "/host/runtime-secrets.json", "3" * 64),
    )

    assert docker.events == [
        "network",
        "edge",
        "image:never",
        "create",
        "start",
        "healthy",
        "route",
    ]
    assert provisioned.health_status == "healthy"
    assert provisioned.image_digest == "sha256:runtime"
    assert provisioned.activation_proof.container_id == provisioned.container_id
    assert provisioned.activation_proof.image_digest == provisioned.image_digest
    assert provisioned.activation_proof.deployment_id == deployment.id
    assert docker.spec is not None
    assert docker.spec.network == deployment.network_name
    assert docker.spec.user == f"{settings.runtime_uid}:{settings.runtime_gid}"
    assert docker.spec.mounts == (
        ContainerMount("/host/manifest.json", "/runtime/manifest.json"),
        ContainerMount("/host/runtime-secrets.json", "/run/secrets/mcplica-runtime.json"),
    )
    assert docker.spec.environment["MCP_MANIFEST_SHA256"] == deployment.manifest_sha256
    assert docker.spec.environment["MCP_TRUST_ENVIRONMENT_PROXY"] == "false"
    assert "127.0.0.1:8000" in docker.spec.environment["MCP_ALLOWED_HOSTS"]
    assert docker.spec.labels["com.mcplica.project_id"] == str(deployment.project_id)
    assert docker.spec.labels["traefik.enable"] == "true"
    assert docker.route_probe == (
        deployment.container_name,
        settings.traefik_container_name,
        deployment.hostname,
        str(deployment.build_id),
        str(deployment.id),
        settings.traefik_tls,
    )
    assert any(
        key.endswith(".loadbalancer.healthcheck.hostname") and value == deployment.hostname
        for key, value in docker.spec.labels.items()
    )
    assert any(
        key.startswith(f"traefik.http.routers.mcp-{deployment.project_id.hex}-")
        for key in docker.spec.labels
    )

    assert await manager.cleanup_network_if_unused(deployment)
    assert docker.network_cleanup == (
        deployment.network_name,
        str(deployment.project_id),
        settings.traefik_container_name,
    )


@pytest.mark.asyncio
async def test_activation_retry_revalidates_exact_candidate_before_cleanup() -> None:
    docker = _RecordingDocker()
    settings = Settings(env="test")
    manager = RuntimeManager(docker, settings)
    deployment = _deployment().model_copy(
        update={"container_id": "container-1", "image_digest": "sha256:runtime"}
    )

    proof = await manager.revalidate_activation_candidate(deployment)
    assert proof.deployment_id == deployment.id
    assert proof.container_id == "container-1"
    assert docker.route_probe is not None
    assert docker.route_probe[3:5] == (str(deployment.build_id), str(deployment.id))

    docker.inspect_result = ContainerInfo(
        "replacement-container", "runtime", "running", "healthy", "sha256:runtime"
    )
    with pytest.raises(RuntimeHealthError, match="identity changed"):
        await manager.revalidate_activation_candidate(deployment)

    docker.inspect_result = None
    with pytest.raises(RuntimeHealthError, match="no longer exists"):
        await manager.revalidate_activation_candidate(deployment)


@pytest.mark.asyncio
async def test_activation_predecessor_is_restarted_and_edge_proved_before_restore() -> None:
    docker = _RecordingDocker()
    docker.inspect_result = ContainerInfo(
        "container-1", "runtime", "exited", None, "sha256:runtime"
    )
    manager = RuntimeManager(docker, Settings(env="test"))
    deployment = _deployment().model_copy(
        update={"container_id": "container-1", "image_digest": "sha256:runtime"}
    )

    proof = await manager.restore_activation_predecessor(deployment)

    assert proof.deployment_id == deployment.id
    assert docker.events == ["start", "healthy", "route"]
    assert docker.route_probe is not None
    assert docker.route_probe[3:5] == (str(deployment.build_id), str(deployment.id))


@pytest.mark.asyncio
async def test_stop_targets_the_exact_recorded_container_identity() -> None:
    docker = _RecordingDocker()
    manager = RuntimeManager(docker, Settings(env="test"))
    deployment = _deployment().model_copy(update={"container_id": "container-1"})

    await manager.stop(deployment, remove=True)

    assert docker.events == ["stop", "remove:False"]

    docker.events.clear()
    docker.inspect_result = ContainerInfo(
        "replacement-container", "runtime", "running", "healthy", "sha256:runtime"
    )
    with pytest.raises(RuntimeHealthError, match="identity changed before stop"):
        await manager.stop(deployment, remove=True)
    assert docker.events == []


def _existing_container_attrs(spec: RuntimeContainerSpec) -> dict[str, object]:
    health_test = [
        "CMD",
        "python",
        "-c",
        (
            "import urllib.request;"
            "urllib.request.urlopen('http://127.0.0.1:8000/readyz',timeout=3).read()"
        ),
    ]
    return {
        "Config": {
            "Image": spec.image,
            "User": spec.user,
            "Labels": dict(spec.labels),
            "Env": [f"{key}={value}" for key, value in spec.environment.items()],
            "Healthcheck": {
                "Test": health_test,
                "Interval": 5_000_000_000,
                "Timeout": 3_000_000_000,
                "Retries": 6,
                "StartPeriod": 5_000_000_000,
            },
        },
        "HostConfig": {
            "NetworkMode": spec.network,
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Memory": spec.memory_limit,
            "MemorySwap": spec.memory_limit,
            "NanoCpus": spec.nano_cpus,
            "PidsLimit": spec.pids_limit,
            "Init": True,
            "RestartPolicy": {"Name": "unless-stopped"},
            "LogConfig": {
                "Type": "json-file",
                "Config": {"max-size": "10m", "max-file": "3"},
            },
            "PortBindings": {},
            "Tmpfs": {"/tmp": (f"rw,noexec,nosuid,nodev,size={spec.tmpfs_size_bytes},mode=1777")},
        },
        "NetworkSettings": {"Networks": {spec.network: {}}},
        "Mounts": [
            {"Source": mount.source, "Destination": mount.target, "RW": False}
            for mount in spec.mounts
        ],
    }


def test_existing_container_reuse_requires_exact_security_identity() -> None:
    spec = RuntimeContainerSpec(
        image="mcplica/runtime@sha256:" + "1" * 64,
        name="runtime",
        network="project-network",
        environment={"MCP_ENVIRONMENT": "production", "MCP_TLS_VERIFY": "true"},
        labels={
            "com.mcplica.managed": "true",
            "com.mcplica.project_id": str(UUID(int=1)),
            "com.mcplica.deployment_id": str(UUID(int=2)),
            "traefik.enable": "true",
        },
        mounts=(ContainerMount("/host/manifest", "/runtime/manifest.json"),),
        user="10001:10001",
        memory_limit=536_870_912,
        nano_cpus=1_000_000_000,
        pids_limit=256,
        tmpfs_size_bytes=67_108_864,
    )
    attrs = _existing_container_attrs(spec)
    DockerClient._assert_existing_container(  # pyright: ignore[reportPrivateUsage]
        SimpleNamespace(attrs=attrs), spec
    )

    config = attrs["Config"]
    assert isinstance(config, dict)
    environment = cast(list[object], config["Env"])
    environment.append("MCP_UNEXPECTED_SECRET=bad")
    with pytest.raises(DockerOperationError, match="does not match"):
        DockerClient._assert_existing_container(  # pyright: ignore[reportPrivateUsage]
            SimpleNamespace(attrs=attrs), spec
        )


def test_edge_container_attachment_requires_managed_identity() -> None:
    DockerClient._assert_edge_container(  # pyright: ignore[reportPrivateUsage]
        SimpleNamespace(labels={"com.mcplica.edge": "true"})
    )
    with pytest.raises(DockerOperationError, match="not MCPlica Traefik"):
        DockerClient._assert_edge_container(  # pyright: ignore[reportPrivateUsage]
            SimpleNamespace(labels={})
        )


def test_only_transient_deployment_errors_are_retried() -> None:
    assert is_retryable_deployment_error(DockerOperationError("daemon unavailable"))
    assert not is_retryable_deployment_error(
        SecretMaterializationError("invalid immutable material")
    )
