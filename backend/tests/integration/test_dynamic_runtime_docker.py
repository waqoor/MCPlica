import hashlib
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from mcp_contracts import MCPManifest, RuntimeSecretBundle

from app.clients.docker import DockerClient
from app.clients.runtime_files import RuntimeFilesClient
from app.core.config import Settings
from app.domain.deployments import DeploymentRecord, DeploymentStatus
from app.services.deployment.runtime_manager import RuntimeManager


def _deployment(
    *,
    deployment_id: UUID,
    project_id: UUID,
    build_id: UUID,
    hostname: str,
    image: str,
    manifest_sha256: str,
    priority: int,
) -> DeploymentRecord:
    return DeploymentRecord(
        id=deployment_id,
        project_id=project_id,
        build_id=build_id,
        status=DeploymentStatus.HEALTHCHECK,
        hostname=hostname,
        container_name=f"mcp-{project_id.hex}-{deployment_id.hex}",
        container_id=None,
        image_ref=image,
        image_digest=None,
        runtime_version="1.0.0",
        network_name=f"mcp-net-{project_id.hex}",
        manifest_sha256=manifest_sha256,
        route_priority=priority,
        stop_old_first=False,
        health_status="starting",
        deployed_by=UUID(int=1),
        created_at=datetime.now(UTC),
        started_at=None,
        stopped_at=None,
        failed_at=None,
        error_code=None,
        error_summary=None,
    )


@pytest.mark.asyncio
async def test_two_projects_replacement_and_rollback_remain_isolated() -> None:
    """Exercise real Docker only when the CI/host explicitly supplies its mount mapping."""

    if os.getenv("MCP_LICA_RUN_DOCKER_INTEGRATION") != "1":
        pytest.skip("set MCP_LICA_RUN_DOCKER_INTEGRATION=1 to run Docker acceptance")
    image = os.getenv("MCP_LICA_TEST_RUNTIME_IMAGE")
    worker_base = os.getenv("MCP_LICA_TEST_RUNTIME_WORKER_ROOT")
    host_base = os.getenv("MCP_LICA_TEST_RUNTIME_HOST_ROOT")
    if not image or not worker_base or not host_base:
        pytest.fail("Docker acceptance requires MCP_LICA_TEST_RUNTIME_IMAGE and both runtime roots")

    suffix = f"pytest-{uuid4().hex}"
    worker_root = Path(worker_base).resolve() / suffix
    host_root = f"{host_base.rstrip('/\\')}/{suffix}"
    raw_pull_policy = os.getenv("MCP_LICA_TEST_RUNTIME_PULL_POLICY", "never")
    if raw_pull_policy not in {"never", "missing", "always"}:
        pytest.fail("MCP_LICA_TEST_RUNTIME_PULL_POLICY is invalid")
    pull_policy = cast(Literal["never", "missing", "always"], raw_pull_policy)
    uid_reader = cast(Callable[[], int], getattr(os, "getuid", lambda: 10_001))
    gid_reader = cast(Callable[[], int], getattr(os, "getgid", lambda: 10_001))
    runtime_uid = uid_reader()
    runtime_gid = gid_reader()
    settings = Settings(
        env="test",
        docker_base_url=os.getenv("MCP_LICA_DOCKER_BASE_URL", "unix:///var/run/docker.sock"),
        mcp_runtime_image=image,
        mcp_runtime_pull_policy=pull_policy,
        runtime_worker_root=str(worker_root),
        runtime_host_root=host_root,
        runtime_uid=runtime_uid,
        runtime_gid=runtime_gid,
        traefik_container_name=os.getenv("MCP_LICA_TRAEFIK_CONTAINER_NAME", "mcplica-traefik-1"),
    )
    runtime_files = RuntimeFilesClient(
        str(worker_root),
        docker_host_root=host_root,
        runtime_uid=runtime_uid,
        runtime_gid=runtime_gid,
    )
    docker = await DockerClient.connect(settings.docker_base_url)
    manager = RuntimeManager(docker, settings)
    fixture_path = Path(__file__).parents[3] / "tests" / "fixtures" / "manifests" / "petstore.json"
    manifest = MCPManifest.model_validate_json(fixture_path.read_bytes())
    fixture_build_id = uuid4()
    manifest = manifest.model_copy(
        update={"build": manifest.build.model_copy(update={"build_id": str(fixture_build_id)})}
    )
    manifest_bytes = manifest.model_dump_json(by_alias=True).encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    bundle = RuntimeSecretBundle.model_validate(
        {
            "upstream_credentials": {"bearer": {"type": "bearer", "token": "integration-not-used"}},
            "inbound_auth": {
                "mode": "static_bearer",
                "static_tokens": [{"id": "integration", "sha256": "a" * 64}],
            },
        }
    )
    project_one = uuid4()
    project_two = uuid4()
    deployments = [
        _deployment(
            deployment_id=uuid4(),
            project_id=project_one,
            build_id=fixture_build_id,
            hostname="project-one.mcp.localhost",
            image=image,
            manifest_sha256=manifest_sha256,
            priority=100,
        ),
        _deployment(
            deployment_id=uuid4(),
            project_id=project_two,
            build_id=fixture_build_id,
            hostname="project-two.mcp.localhost",
            image=image,
            manifest_sha256=manifest_sha256,
            priority=100,
        ),
        _deployment(
            deployment_id=uuid4(),
            project_id=project_one,
            build_id=fixture_build_id,
            hostname="project-one.mcp.localhost",
            image=image,
            manifest_sha256=manifest_sha256,
            priority=101,
        ),
        _deployment(
            deployment_id=uuid4(),
            project_id=project_one,
            build_id=fixture_build_id,
            hostname="project-one.mcp.localhost",
            image=image,
            manifest_sha256=manifest_sha256,
            priority=102,
        ),
    ]
    materialized: set[UUID] = set()
    try:
        assert await docker.health()
        for deployment in deployments[:2]:
            mounts = await runtime_files.materialize(
                deployment.id,
                manifest_bytes=manifest_bytes,
                manifest_sha256=manifest_sha256,
                secret_bundle=bundle,
            )
            materialized.add(deployment.id)
            assert (await manager.provision(deployment, mounts)).health_status == "healthy"

        replacement = deployments[2]
        replacement_mounts = await runtime_files.materialize(
            replacement.id,
            manifest_bytes=manifest_bytes,
            manifest_sha256=manifest_sha256,
            secret_bundle=bundle,
        )
        materialized.add(replacement.id)
        assert (await manager.provision(replacement, replacement_mounts)).health_status == "healthy"
        await manager.stop(deployments[0], remove=True)
        await runtime_files.remove(deployments[0].id)
        materialized.remove(deployments[0].id)
        assert await docker.inspect_container(deployments[1].container_name) is not None

        rollback = deployments[3]
        rollback_mounts = await runtime_files.materialize(
            rollback.id,
            manifest_bytes=manifest_bytes,
            manifest_sha256=manifest_sha256,
            secret_bundle=bundle,
        )
        materialized.add(rollback.id)
        assert (await manager.provision(rollback, rollback_mounts)).health_status == "healthy"
        await manager.stop(replacement, remove=True)
        await runtime_files.remove(replacement.id)
        materialized.remove(replacement.id)
        assert await docker.inspect_container(deployments[1].container_name) is not None
    finally:
        for deployment in reversed(deployments):
            await manager.cleanup_failed(deployment)
            if deployment.id in materialized:
                await runtime_files.remove(deployment.id)
        for deployment in reversed(deployments):
            await manager.cleanup_network_if_unused(deployment)
        await docker.close()
        worker_root.rmdir()
