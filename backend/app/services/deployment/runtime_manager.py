from dataclasses import dataclass
from typing import Protocol

from app.clients.docker import (
    ContainerInfo,
    ContainerMount,
    RuntimeContainerSpec,
)
from app.clients.runtime_files import RuntimeMounts
from app.core.config import Settings
from app.domain.deployments import DeploymentRecord


@dataclass(frozen=True, slots=True)
class ProvisionedRuntime:
    container_id: str
    image_digest: str
    health_status: str


class RuntimeDockerClient(Protocol):
    async def ensure_network(
        self,
        name: str,
        *,
        project_id: str,
        edge_container_name: str,
    ) -> None: ...

    async def connect_edge_container_to_network(
        self, network_name: str, container_name: str
    ) -> None: ...

    async def ensure_image(self, image_ref: str, *, pull_policy: str) -> str: ...

    async def create_runtime_container(self, spec: RuntimeContainerSpec) -> ContainerInfo: ...

    async def start_container(self, name: str) -> ContainerInfo: ...

    async def wait_until_healthy(
        self,
        name: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float = 1.0,
    ) -> ContainerInfo: ...

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
    ) -> None: ...

    async def stop_container(self, name: str, *, timeout_seconds: int) -> None: ...

    async def remove_container(self, name: str, *, force: bool = False) -> None: ...

    async def remove_network_if_unused(
        self,
        name: str,
        *,
        project_id: str,
        keep_container: str,
    ) -> bool: ...


class RuntimeManager:
    """Worker-only runtime lifecycle; all Docker operations stay in DockerClient."""

    def __init__(self, docker_client: RuntimeDockerClient, settings: Settings) -> None:
        self._docker = docker_client
        self._settings = settings

    async def provision(
        self, deployment: DeploymentRecord, mounts: RuntimeMounts
    ) -> ProvisionedRuntime:
        project_fragment = deployment.project_id.hex
        deployment_fragment = deployment.id.hex
        router = f"mcp-{project_fragment}-{deployment_fragment}"
        service = router
        labels = {
            "com.mcplica.managed": "true",
            "com.mcplica.project_id": str(deployment.project_id),
            "com.mcplica.deployment_id": str(deployment.id),
            "com.mcplica.build_id": str(deployment.build_id),
            "traefik.enable": "true",
            "traefik.docker.network": deployment.network_name,
            f"traefik.http.routers.{router}.rule": f"Host(`{deployment.hostname}`)",
            f"traefik.http.routers.{router}.entrypoints": self._settings.traefik_entrypoint,
            f"traefik.http.routers.{router}.priority": str(deployment.route_priority),
            f"traefik.http.routers.{router}.service": service,
            f"traefik.http.services.{service}.loadbalancer.server.port": "8000",
            f"traefik.http.services.{service}.loadbalancer.healthcheck.path": "/readyz",
            f"traefik.http.services.{service}.loadbalancer.healthcheck.hostname": (
                deployment.hostname
            ),
            f"traefik.http.services.{service}.loadbalancer.healthcheck.interval": "5s",
            f"traefik.http.services.{service}.loadbalancer.healthcheck.timeout": "3s",
        }
        if self._settings.traefik_tls:
            labels[f"traefik.http.routers.{router}.tls"] = "true"
            if self._settings.traefik_cert_resolver:
                labels[f"traefik.http.routers.{router}.tls.certresolver"] = (
                    self._settings.traefik_cert_resolver
                )

        await self._docker.ensure_network(
            deployment.network_name,
            project_id=str(deployment.project_id),
            edge_container_name=self._settings.traefik_container_name,
        )
        await self._docker.connect_edge_container_to_network(
            deployment.network_name,
            self._settings.traefik_container_name,
        )
        image_digest = await self._docker.ensure_image(
            deployment.image_ref,
            pull_policy=self._settings.mcp_runtime_pull_policy,
        )
        scheme = "https" if self._settings.traefik_tls else "http"
        public_base_url = f"{scheme}://{deployment.hostname}"
        spec = RuntimeContainerSpec(
            image=deployment.image_ref,
            name=deployment.container_name,
            network=deployment.network_name,
            environment={
                "MCP_ENVIRONMENT": self._settings.env,
                "MCP_RUNTIME_VERSION": deployment.runtime_version,
                "MCP_DEPLOYMENT_ID": str(deployment.id),
                "MCP_MANIFEST_PATH": "/runtime/manifest.json",
                "MCP_MANIFEST_SHA256": deployment.manifest_sha256,
                "MCP_SECRET_BUNDLE_PATH": "/run/secrets/mcplica-runtime.json",
                "MCP_PUBLIC_BASE_URL": public_base_url,
                "MCP_ALLOWED_HOSTS": (
                    f"{deployment.hostname},127.0.0.1,127.0.0.1:8000,localhost,localhost:8000"
                ),
                "MCP_ALLOWED_ORIGINS": public_base_url,
                "MCP_REQUIRE_SECURE_SECRET_PERMISSIONS": "true",
                "MCP_MAX_MANIFEST_BYTES": str(self._settings.runtime_manifest_max_bytes),
                "MCP_MAX_SECRET_BUNDLE_BYTES": str(self._settings.runtime_secret_bundle_max_bytes),
                "MCP_TRUST_ENVIRONMENT_PROXY": "false",
                "MCP_TLS_VERIFY": "true",
            },
            labels=labels,
            mounts=(
                ContainerMount(mounts.manifest_path, "/runtime/manifest.json"),
                ContainerMount(
                    mounts.secret_bundle_path,
                    "/run/secrets/mcplica-runtime.json",
                ),
            ),
            user=f"{self._settings.runtime_uid}:{self._settings.runtime_gid}",
            memory_limit=self._settings.runtime_memory_bytes,
            nano_cpus=self._settings.runtime_nano_cpus,
            pids_limit=self._settings.runtime_pids_limit,
            tmpfs_size_bytes=self._settings.runtime_tmpfs_bytes,
        )
        created = await self._docker.create_runtime_container(spec)
        started = await self._docker.start_container(created.name)
        healthy = await self._docker.wait_until_healthy(
            started.name,
            timeout_seconds=self._settings.runtime_health_timeout_seconds,
            poll_interval_seconds=self._settings.runtime_health_poll_seconds,
        )
        await self._docker.wait_until_route_ready(
            healthy.name,
            edge_container_name=self._settings.traefik_container_name,
            hostname=deployment.hostname,
            expected_build_id=str(deployment.build_id),
            expected_deployment_id=str(deployment.id),
            tls=self._settings.traefik_tls,
            timeout_seconds=self._settings.runtime_health_timeout_seconds,
            poll_interval_seconds=self._settings.runtime_health_poll_seconds,
        )
        return ProvisionedRuntime(
            healthy.id,
            healthy.image_id or image_digest,
            healthy.health or "healthy",
        )

    async def stop(self, deployment: DeploymentRecord, *, remove: bool) -> None:
        await self._docker.stop_container(
            deployment.container_name,
            timeout_seconds=self._settings.runtime_stop_timeout_seconds,
        )
        if remove:
            await self._docker.remove_container(deployment.container_name)

    async def cleanup_failed(self, deployment: DeploymentRecord) -> None:
        await self._docker.remove_container(deployment.container_name, force=True)

    async def cleanup_network_if_unused(self, deployment: DeploymentRecord) -> bool:
        return await self._docker.remove_network_if_unused(
            deployment.network_name,
            project_id=str(deployment.project_id),
            keep_container=self._settings.traefik_container_name,
        )
