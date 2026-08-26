import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, cast

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

from app.clients.base import AsyncClient
from app.core.exceptions import DockerOperationError, RuntimeHealthError

_ROUTE_READINESS_PROBE = r"""
import http.client
import json
import socket
import ssl
import sys

edge_host, route_host, expected_build_id, expected_deployment_id, tls_enabled = sys.argv[1:]
port = 443 if tls_enabled == "true" else 80
connection = socket.create_connection((edge_host, port), timeout=3)
try:
    if tls_enabled == "true":
        connection = ssl.create_default_context().wrap_socket(
            connection,
            server_hostname=route_host,
        )
    request = (
        "GET /readyz HTTP/1.1\r\n"
        f"Host: {route_host}\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n\r\n"
    )
    connection.sendall(request.encode("ascii"))
    response = http.client.HTTPResponse(connection)
    response.begin()
    body = response.read(4097)
    payload = json.loads(body) if len(body) <= 4096 else {}
    ready = (
        response.status == 200
        and payload.get("ready") is True
        and payload.get("build_id") == expected_build_id
        and payload.get("deployment_id") == expected_deployment_id
    )
    raise SystemExit(0 if ready else 1)
finally:
    connection.close()
"""


@dataclass(frozen=True, slots=True)
class ContainerMount:
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class RuntimeContainerSpec:
    image: str
    name: str
    network: str
    environment: dict[str, str]
    labels: dict[str, str]
    mounts: tuple[ContainerMount, ...]
    user: str
    memory_limit: int
    nano_cpus: int
    pids_limit: int
    tmpfs_size_bytes: int


@dataclass(frozen=True, slots=True)
class ContainerInfo:
    id: str
    name: str
    status: str
    health: str | None
    image_id: str


class DockerClient(AsyncClient):
    """Deployment-worker-only Docker SDK boundary; SDK objects never escape it."""

    def __init__(self, base_url: str) -> None:
        self._client = docker.DockerClient(base_url=base_url)

    @classmethod
    async def connect(cls, base_url: str) -> "DockerClient":
        return await asyncio.to_thread(cls, base_url)

    async def health(self) -> bool:
        try:
            return await asyncio.to_thread(self._ping)
        except DockerException:
            return False

    def _ping(self) -> bool:
        return bool(self._client.ping())  # pyright: ignore[reportUnknownMemberType]

    async def ensure_image(
        self,
        image_ref: str,
        *,
        pull_policy: str,
    ) -> str:
        if pull_policy not in {"never", "missing", "always"}:
            raise ValueError("Unsupported runtime image pull policy")
        return await asyncio.to_thread(self._ensure_image, image_ref, pull_policy)

    def _ensure_image(self, image_ref: str, pull_policy: str) -> str:
        try:
            if pull_policy == "always":
                image = self._client.images.pull(image_ref)
            else:
                try:
                    image = self._client.images.get(image_ref)
                except ImageNotFound:
                    if pull_policy == "never":
                        raise DockerOperationError(
                            "Configured runtime image is not present"
                        ) from None
                    image = self._client.images.pull(image_ref)
            attrs = cast(dict[str, object], image.attrs)
            repo_digests = attrs.get("RepoDigests")
            if isinstance(repo_digests, list):
                raw_digests = cast(list[object], repo_digests)
                digests = [str(value) for value in raw_digests if isinstance(value, str)]
                if digests:
                    return sorted(digests)[0]
            image_id = attrs.get("Id")
            if isinstance(image_id, str) and image_id:
                return image_id
            raise DockerOperationError("Runtime image has no verifiable identity")
        except ImageNotFound as exc:
            raise DockerOperationError("Configured runtime image could not be pulled") from exc
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Runtime image inspection failed") from exc

    async def ensure_network(
        self,
        name: str,
        *,
        project_id: str,
        edge_container_name: str,
    ) -> None:
        await asyncio.to_thread(
            self._ensure_network,
            name,
            project_id,
            edge_container_name,
        )

    def _ensure_network(
        self,
        name: str,
        project_id: str,
        edge_container_name: str,
    ) -> None:
        try:
            network = self._client.networks.get(name)
            network.reload()
            self._assert_network_identity(
                network,
                project_id=project_id,
                edge_container_name=edge_container_name,
            )
        except NotFound:
            try:
                self._client.networks.create(
                    name,
                    driver="bridge",
                    internal=False,
                    attachable=False,
                    labels={
                        "com.mcplica.managed": "true",
                        "com.mcplica.project_id": project_id,
                    },
                    check_duplicate=True,
                )
            except (APIError, DockerException) as exc:
                raise DockerOperationError("Project runtime network creation failed") from exc
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Project runtime network inspection failed") from exc

    async def connect_edge_container_to_network(
        self, network_name: str, container_name: str
    ) -> None:
        await asyncio.to_thread(
            self._connect_edge_container_to_network,
            network_name,
            container_name,
        )

    def _connect_edge_container_to_network(self, network_name: str, container_name: str) -> None:
        try:
            network = self._client.networks.get(network_name)
            network.reload()
            containers = cast(dict[str, object], network.attrs.get("Containers") or {})
            container = self._client.containers.get(container_name)
            container.reload()
            self._assert_edge_container(container)
            if container.id not in containers:
                network.connect(container)  # pyright: ignore[reportUnknownMemberType]
        except (NotFound, APIError, DockerException) as exc:
            raise DockerOperationError("Container network attachment failed") from exc

    async def create_runtime_container(self, spec: RuntimeContainerSpec) -> ContainerInfo:
        return await asyncio.to_thread(self._create_runtime_container, spec)

    def _create_runtime_container(self, spec: RuntimeContainerSpec) -> ContainerInfo:
        try:
            try:
                existing = self._client.containers.get(spec.name)
            except NotFound:
                existing = None
            if existing is not None:
                existing.reload()
                labels = cast(
                    dict[str, str],
                    existing.labels or {},  # pyright: ignore[reportUnknownMemberType]
                )
                expected = spec.labels.get("com.mcplica.deployment_id")
                if labels.get("com.mcplica.deployment_id") != expected:
                    raise DockerOperationError("Runtime container name is already in use")
                self._assert_existing_container(existing, spec)
                return self._container_info(existing)

            volumes = {mount.source: {"bind": mount.target, "mode": "ro"} for mount in spec.mounts}
            create_options: dict[str, object] = {
                "name": spec.name,
                "detach": True,
                "environment": spec.environment,
                "labels": spec.labels,
                "network": spec.network,
                "volumes": volumes,
                "read_only": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "tmpfs": {"/tmp": f"rw,noexec,nosuid,nodev,size={spec.tmpfs_size_bytes},mode=1777"},
                "mem_limit": spec.memory_limit,
                "memswap_limit": spec.memory_limit,
                "nano_cpus": spec.nano_cpus,
                "pids_limit": spec.pids_limit,
                "user": spec.user,
                "privileged": False,
                "init": True,
                "restart_policy": {"Name": "unless-stopped"},
                "log_config": {
                    "type": "json-file",
                    "config": {"max-size": "10m", "max-file": "3"},
                },
                "healthcheck": {
                    "test": [
                        "CMD",
                        "python",
                        "-c",
                        (
                            "import urllib.request;"
                            "urllib.request.urlopen('http://127.0.0.1:8000/readyz',"
                            "timeout=3).read()"
                        ),
                    ],
                    "interval": 5_000_000_000,
                    "timeout": 3_000_000_000,
                    "retries": 6,
                    "start_period": 5_000_000_000,
                },
            }
            create_container = cast(Callable[..., Any], self._client.containers.create)
            container: Any = create_container(spec.image, **create_options)
            return self._container_info(container)
        except DockerOperationError:
            raise
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Runtime container creation failed") from exc

    async def start_container(self, name: str) -> ContainerInfo:
        return await asyncio.to_thread(self._start_container, name)

    def _start_container(self, name: str) -> ContainerInfo:
        try:
            container = self._client.containers.get(name)
            container.reload()
            if container.status != "running":
                container.start()
                container.reload()
            return self._container_info(container)
        except (NotFound, APIError, DockerException) as exc:
            raise DockerOperationError("Runtime container start failed") from exc

    async def inspect_container(self, name: str) -> ContainerInfo | None:
        return await asyncio.to_thread(self._inspect_container, name)

    def _inspect_container(self, name: str) -> ContainerInfo | None:
        try:
            container = self._client.containers.get(name)
            container.reload()
            return self._container_info(container)
        except NotFound:
            return None
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Runtime container inspection failed") from exc

    async def wait_until_healthy(
        self,
        name: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float = 1.0,
    ) -> ContainerInfo:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            info = await self.inspect_container(name)
            if info is None:
                raise RuntimeHealthError("Runtime container disappeared during startup")
            if info.health == "healthy":
                return info
            if info.health == "unhealthy" or info.status in {"dead", "exited"}:
                raise RuntimeHealthError("Runtime failed its startup health check")
            await asyncio.sleep(poll_interval_seconds)
        raise RuntimeHealthError("Runtime startup health check timed out")

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
        """Wait until Traefik routes the hostname to this exact immutable build."""

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            info = await self.inspect_container(name)
            if info is None:
                raise RuntimeHealthError("Runtime container disappeared during route setup")
            if info.health == "unhealthy" or info.status in {"dead", "exited"}:
                raise RuntimeHealthError("Runtime failed while its edge route was being prepared")
            if await asyncio.to_thread(
                self._probe_route,
                name,
                edge_container_name,
                hostname,
                expected_build_id,
                expected_deployment_id,
                tls,
            ):
                return
            await asyncio.sleep(poll_interval_seconds)
        raise RuntimeHealthError("Runtime edge route readiness check timed out")

    def _probe_route(
        self,
        name: str,
        edge_container_name: str,
        hostname: str,
        expected_build_id: str,
        expected_deployment_id: str,
        tls: bool,
    ) -> bool:
        try:
            container = self._client.containers.get(name)
            result = container.exec_run(
                [
                    "python",
                    "-c",
                    _ROUTE_READINESS_PROBE,
                    edge_container_name,
                    hostname,
                    expected_build_id,
                    expected_deployment_id,
                    "true" if tls else "false",
                ]
            )
            return bool(result.exit_code == 0)
        except NotFound as exc:
            raise RuntimeHealthError("Runtime container disappeared during route setup") from exc
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Runtime edge route probe failed") from exc

    async def stop_container(self, name: str, *, timeout_seconds: int) -> None:
        await asyncio.to_thread(self._stop_container, name, timeout_seconds)

    def _stop_container(self, name: str, timeout_seconds: int) -> None:
        try:
            container = self._client.containers.get(name)
            container.reload()
            if container.status == "running":
                container.stop(timeout=timeout_seconds)
        except NotFound:
            return
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Runtime container stop failed") from exc

    async def remove_container(self, name: str, *, force: bool = False) -> None:
        await asyncio.to_thread(self._remove_container, name, force)

    def _remove_container(self, name: str, force: bool) -> None:
        try:
            container = self._client.containers.get(name)
            container.remove(force=force, v=True)
        except NotFound:
            return
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Runtime container removal failed") from exc

    async def remove_network_if_unused(
        self,
        name: str,
        *,
        project_id: str,
        keep_container: str,
    ) -> bool:
        return await asyncio.to_thread(
            self._remove_network_if_unused,
            name,
            project_id,
            keep_container,
        )

    def _remove_network_if_unused(self, name: str, project_id: str, keep_container: str) -> bool:
        try:
            network = self._client.networks.get(name)
            network.reload()
            self._assert_network_identity(
                network,
                project_id=project_id,
                edge_container_name=keep_container,
            )
            containers = cast(dict[str, dict[str, Any]], network.attrs.get("Containers") or {})
            names = {
                str(value.get("Name"))
                for value in containers.values()
                if value.get("Name") is not None
            }
            if names - {keep_container}:
                return False
            if keep_container in names:
                with suppress(NotFound):
                    network.disconnect(keep_container)
            network.remove()
            return True
        except NotFound:
            return True
        except (APIError, DockerException) as exc:
            raise DockerOperationError("Project runtime network cleanup failed") from exc

    def _assert_network_identity(
        self,
        network: Any,
        *,
        project_id: str,
        edge_container_name: str,
    ) -> None:
        attrs = cast(dict[str, object], network.attrs)
        labels = cast(dict[str, str], attrs.get("Labels") or {})
        if (
            labels.get("com.mcplica.managed") != "true"
            or labels.get("com.mcplica.project_id") != project_id
            or attrs.get("Driver") != "bridge"
            or attrs.get("Internal") is not False
            or attrs.get("Attachable") is not False
        ):
            raise DockerOperationError("Docker network identity conflicts with deployment")
        containers = cast(dict[str, object], attrs.get("Containers") or {})
        for container_id, raw_attachment in containers.items():
            attachment = cast(dict[str, object], raw_attachment)
            name = attachment.get("Name")
            if name == edge_container_name:
                try:
                    edge = self._client.containers.get(container_id)
                except NotFound as exc:
                    raise DockerOperationError(
                        "Docker network contains an unknown edge container"
                    ) from exc
                self._assert_edge_container(edge)
                continue
            try:
                container = self._client.containers.get(container_id)
            except NotFound as exc:
                raise DockerOperationError("Docker network contains an unknown container") from exc
            container_labels = cast(
                dict[str, str],
                container.labels or {},  # pyright: ignore[reportUnknownMemberType]
            )
            if (
                container_labels.get("com.mcplica.managed") != "true"
                or container_labels.get("com.mcplica.project_id") != project_id
                or not container_labels.get("com.mcplica.deployment_id")
            ):
                raise DockerOperationError("Docker network contains an unauthorized container")

    @staticmethod
    def _assert_edge_container(container: Any) -> None:
        labels = cast(
            dict[str, str],
            container.labels or {},  # pyright: ignore[reportUnknownMemberType]
        )
        if labels.get("com.mcplica.edge") != "true":
            raise DockerOperationError("Configured edge container is not MCPlica Traefik")

    @staticmethod
    def _assert_existing_container(container: Any, spec: RuntimeContainerSpec) -> None:
        attrs = cast(dict[str, object], container.attrs)
        config = cast(dict[str, object], attrs.get("Config") or {})
        host = cast(dict[str, object], attrs.get("HostConfig") or {})
        network_settings = cast(dict[str, object], attrs.get("NetworkSettings") or {})
        networks = cast(dict[str, object], network_settings.get("Networks") or {})
        labels = cast(dict[str, str], config.get("Labels") or {})
        environment = cast(list[object], config.get("Env") or [])
        configured_environment = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in environment
            if isinstance(item, str) and "=" in item
        }
        expected_mounts = {
            (DockerClient._normalized_mount_path(mount.source), mount.target)
            for mount in spec.mounts
        }
        raw_mounts = cast(list[object], attrs.get("Mounts") or [])
        actual_mounts: set[tuple[str, str]] = set()
        all_mounts_read_only = True
        for raw_mount in raw_mounts:
            mount = cast(dict[str, object], raw_mount)
            source = mount.get("Source")
            destination = mount.get("Destination")
            if isinstance(source, str) and isinstance(destination, str):
                actual_mounts.add((DockerClient._normalized_mount_path(source), destination))
            if mount.get("RW") is not False:
                all_mounts_read_only = False
        managed_label_prefixes = ("com.mcplica.", "traefik.")
        actual_managed_labels = {
            key: value for key, value in labels.items() if key.startswith(managed_label_prefixes)
        }
        expected_managed_labels = {
            key: value
            for key, value in spec.labels.items()
            if key.startswith(managed_label_prefixes)
        }
        security_environment_names = {
            key
            for key in configured_environment
            if key.startswith("MCP_")
            or key.casefold() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
        }
        expected_environment_names = set(spec.environment)
        actual_security_environment = {
            key: configured_environment[key] for key in security_environment_names
        }
        expected_security_environment = {
            key: spec.environment[key] for key in expected_environment_names
        }
        cap_drop = cast(list[object], host.get("CapDrop") or [])
        security_options = cast(list[object], host.get("SecurityOpt") or [])
        restart_policy = cast(dict[str, object], host.get("RestartPolicy") or {})
        log_config = cast(dict[str, object], host.get("LogConfig") or {})
        log_options = cast(dict[str, str], log_config.get("Config") or {})
        healthcheck = cast(dict[str, object], config.get("Healthcheck") or {})
        tmpfs = cast(dict[str, str], host.get("Tmpfs") or {})
        expected_health_test = [
            "CMD",
            "python",
            "-c",
            (
                "import urllib.request;"
                "urllib.request.urlopen('http://127.0.0.1:8000/readyz',"
                "timeout=3).read()"
            ),
        ]
        tmpfs_options = set((tmpfs.get("/tmp") or "").split(","))
        identity_matches = (
            config.get("Image") == spec.image
            and config.get("User") == spec.user
            and actual_managed_labels == expected_managed_labels
            and actual_security_environment == expected_security_environment
            and set(networks) == {spec.network}
            and host.get("NetworkMode") == spec.network
            and expected_mounts == actual_mounts
            and all_mounts_read_only
            and host.get("ReadonlyRootfs") is True
            and host.get("Privileged") is False
            and "ALL" in cap_drop
            and any(str(value).startswith("no-new-privileges") for value in security_options)
            and host.get("Memory") == spec.memory_limit
            and host.get("MemorySwap") == spec.memory_limit
            and host.get("NanoCpus") == spec.nano_cpus
            and host.get("PidsLimit") == spec.pids_limit
            and host.get("Init") is True
            and restart_policy.get("Name") == "unless-stopped"
            and log_config.get("Type") == "json-file"
            and log_options == {"max-size": "10m", "max-file": "3"}
            and not host.get("PortBindings")
            and healthcheck.get("Test") == expected_health_test
            and healthcheck.get("Interval") == 5_000_000_000
            and healthcheck.get("Timeout") == 3_000_000_000
            and healthcheck.get("Retries") == 6
            and healthcheck.get("StartPeriod") == 5_000_000_000
            and {"rw", "noexec", "nosuid", "nodev", "mode=1777"} <= tmpfs_options
            and f"size={spec.tmpfs_size_bytes}" in tmpfs_options
        )
        if not identity_matches:
            raise DockerOperationError("Existing runtime container does not match deployment spec")

    @staticmethod
    def _normalized_mount_path(value: str) -> str:
        return value.replace("\\", "/").rstrip("/").casefold()

    @staticmethod
    def _container_info(container: Any) -> ContainerInfo:
        attrs = cast(dict[str, object], container.attrs)
        state = cast(dict[str, object], attrs.get("State") or {})
        health_data = cast(dict[str, object], state.get("Health") or {})
        health = health_data.get("Status")
        image_id = attrs.get("Image")
        return ContainerInfo(
            id=str(container.id),
            name=str(container.name),
            status=str(state.get("Status") or container.status),
            health=str(health) if health is not None else None,
            image_id=str(image_id or ""),
        )

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
