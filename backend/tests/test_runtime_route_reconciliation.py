from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DockerOperationError
from app.domain.deployments import (
    DeploymentActivationPhase,
    DeploymentActivationProof,
    DeploymentRecord,
    DeploymentStatus,
)
from app.services.deployment.route_reconciler import reconcile_active_runtime_routes


def _active_deployment(*, hostname: str) -> DeploymentRecord:
    deployment_id = uuid4()
    project_id = uuid4()
    build_id = uuid4()
    verified_at = datetime.now(UTC)
    proof = DeploymentActivationProof.verified(
        deployment_id=deployment_id,
        project_id=project_id,
        build_id=build_id,
        container_id=f"container-{deployment_id.hex}",
        image_digest="sha256:" + "1" * 64,
        hostname=hostname,
        manifest_sha256="2" * 64,
        runtime_version="1.0.0",
        verified_at=verified_at,
    )
    return DeploymentRecord(
        id=deployment_id,
        project_id=project_id,
        build_id=build_id,
        status=DeploymentStatus.RUNNING,
        hostname=hostname,
        container_name=f"mcp-{deployment_id.hex}",
        container_id=proof.container_id,
        image_ref="mcplica/runtime@sha256:" + "1" * 64,
        image_digest=proof.image_digest,
        runtime_version="1.0.0",
        network_name=f"mcp-net-{project_id.hex}",
        manifest_sha256=proof.manifest_sha256,
        route_priority=101,
        stop_old_first=False,
        health_status="healthy",
        deployed_by=uuid4(),
        created_at=verified_at,
        started_at=verified_at,
        activated_at=verified_at,
        activation_phase=DeploymentActivationPhase.RUNNING,
        activation_verified_at=verified_at,
        activation_proof_sha256=proof.proof_sha256,
        stopped_at=None,
        failed_at=None,
        error_code=None,
        error_summary=None,
    )


class _Deployments:
    def __init__(self, values: list[DeploymentRecord]) -> None:
        self.values = values

    async def list_active_for_route_reconciliation(
        self,
        session: AsyncSession,
    ) -> list[DeploymentRecord]:
        return self.values


class _Runtime:
    def __init__(self) -> None:
        self.restored: list[str] = []

    async def restore_edge_route(
        self,
        deployment: DeploymentRecord,
    ) -> DeploymentActivationProof:
        if deployment.hostname == "failed.mcp.localhost":
            raise DockerOperationError("synthetic network failure")
        self.restored.append(deployment.hostname)
        assert deployment.container_id is not None
        assert deployment.image_digest is not None
        assert deployment.activation_verified_at is not None
        return DeploymentActivationProof.verified(
            deployment_id=deployment.id,
            project_id=deployment.project_id,
            build_id=deployment.build_id,
            container_id=deployment.container_id,
            image_digest=deployment.image_digest,
            hostname=deployment.hostname,
            manifest_sha256=deployment.manifest_sha256,
            runtime_version=deployment.runtime_version,
            verified_at=deployment.activation_verified_at,
        )


@pytest.mark.asyncio
async def test_route_reconciliation_restores_only_proven_active_runtimes() -> None:
    healthy = _active_deployment(hostname="healthy.mcp.localhost")
    failed = _active_deployment(hostname="failed.mcp.localhost")
    unproven = _active_deployment(hostname="unproven.mcp.localhost").model_copy(
        update={"activation_proof_sha256": "0" * 64}
    )
    runtime = _Runtime()

    result = await reconcile_active_runtime_routes(
        cast(AsyncSession, object()),
        _Deployments([healthy, failed, unproven]),
        runtime,
    )

    assert result.candidates == 3
    assert result.restored == 1
    assert result.failed == 1
    assert result.skipped == 1
    assert runtime.restored == ["healthy.mcp.localhost"]
