import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DockerOperationError, RuntimeHealthError
from app.domain.deployments import (
    DeploymentActivationProof,
    DeploymentRecord,
    is_restart_eligible,
)

logger = logging.getLogger("mcplica.deployment.route_reconciler")


class ActiveDeploymentSource(Protocol):
    async def list_active_for_route_reconciliation(
        self,
        session: AsyncSession,
    ) -> list[DeploymentRecord]: ...


class EdgeRouteRestorer(Protocol):
    async def restore_edge_route(
        self,
        deployment: DeploymentRecord,
    ) -> DeploymentActivationProof: ...


@dataclass(frozen=True, slots=True)
class RouteReconciliationResult:
    candidates: int
    restored: int
    skipped: int
    failed: int


async def reconcile_active_runtime_routes(
    session: AsyncSession,
    deployments: ActiveDeploymentSource,
    runtime: EdgeRouteRestorer,
) -> RouteReconciliationResult:
    """Restore proxy links for exact, proven active runtimes and skip unsafe rows."""

    candidates = await deployments.list_active_for_route_reconciliation(session)
    restored = 0
    skipped = 0
    failed = 0
    for deployment in candidates:
        if not is_restart_eligible(deployment, active_deployment_id=deployment.id):
            skipped += 1
            logger.warning(
                "runtime_route_reconciliation_skipped",
                extra={
                    "project_id": str(deployment.project_id),
                    "deployment_id": str(deployment.id),
                },
            )
            continue
        try:
            await runtime.restore_edge_route(deployment)
        except (DockerOperationError, RuntimeHealthError):
            failed += 1
            logger.exception(
                "runtime_route_reconciliation_failed",
                extra={
                    "project_id": str(deployment.project_id),
                    "deployment_id": str(deployment.id),
                },
            )
            continue
        restored += 1
        logger.info(
            "runtime_route_reconciliation_restored",
            extra={
                "project_id": str(deployment.project_id),
                "deployment_id": str(deployment.id),
            },
        )
    return RouteReconciliationResult(
        candidates=len(candidates),
        restored=restored,
        skipped=skipped,
        failed=failed,
    )
