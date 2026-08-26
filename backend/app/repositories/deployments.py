from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.deployments import (
    DeployableBuildRecord,
    DeploymentRecord,
    DeploymentStatus,
)
from app.models.build import Build
from app.models.deployment import Deployment
from app.models.project import Project


@dataclass(frozen=True, slots=True)
class LockedProjectDeploymentState:
    id: UUID
    hostname: str
    is_enabled: bool
    active_build_id: UUID | None
    active_deployment_id: UUID | None


def _to_domain(model: Deployment) -> DeploymentRecord:
    return DeploymentRecord(
        id=model.id,
        project_id=model.project_id,
        build_id=model.build_id,
        status=model.status,
        hostname=model.hostname,
        container_name=model.container_name,
        container_id=model.container_id,
        image_ref=model.image_ref,
        image_digest=model.image_digest,
        runtime_version=model.runtime_version,
        network_name=model.network_name,
        manifest_sha256=model.manifest_sha256,
        route_priority=model.route_priority,
        stop_old_first=model.stop_old_first,
        health_status=model.health_status,
        deployed_by=model.deployed_by,
        created_at=model.created_at,
        started_at=model.started_at,
        stopped_at=model.stopped_at,
        failed_at=model.failed_at,
        error_code=model.error_code,
        error_summary=model.error_summary,
    )


class DeploymentRepository:
    async def get_project(
        self, session: AsyncSession, project_id: UUID
    ) -> LockedProjectDeploymentState | None:
        project = await session.get(Project, project_id)
        return self._project_state(project)

    async def lock_project(
        self, session: AsyncSession, project_id: UUID
    ) -> LockedProjectDeploymentState | None:
        project = await session.scalar(
            select(Project).where(Project.id == project_id).with_for_update()
        )
        return self._project_state(project)

    @staticmethod
    def _project_state(project: Project | None) -> LockedProjectDeploymentState | None:
        if project is None:
            return None
        return LockedProjectDeploymentState(
            id=project.id,
            hostname=project.mcp_hostname,
            is_enabled=project.is_enabled,
            active_build_id=project.active_build_id,
            active_deployment_id=project.active_deployment_id,
        )

    async def get(self, session: AsyncSession, deployment_id: UUID) -> DeploymentRecord | None:
        model = await session.get(Deployment, deployment_id)
        return _to_domain(model) if model else None

    async def get_for_update(
        self, session: AsyncSession, deployment_id: UUID
    ) -> DeploymentRecord | None:
        model = await session.scalar(
            select(Deployment).where(Deployment.id == deployment_id).with_for_update()
        )
        return _to_domain(model) if model else None

    async def list_for_project(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DeploymentRecord]:
        result = await session.scalars(
            select(Deployment)
            .where(Deployment.project_id == project_id)
            .order_by(Deployment.created_at.desc())
            .limit(min(limit, 500))
            .offset(offset)
        )
        return [_to_domain(model) for model in result]

    async def get_build(
        self, session: AsyncSession, build_id: UUID
    ) -> DeployableBuildRecord | None:
        model = await session.get(Build, build_id)
        if model is None:
            return None
        return DeployableBuildRecord(
            id=model.id,
            project_id=model.project_id,
            status=model.status.value,
            manifest_sha256=model.manifest_sha256,
            manifest_storage_key=model.manifest_storage_key,
        )

    async def has_in_progress(self, session: AsyncSession, project_id: UUID) -> bool:
        deployment_id = await session.scalar(
            select(Deployment.id)
            .where(
                Deployment.project_id == project_id,
                Deployment.status.in_(
                    {
                        DeploymentStatus.PENDING,
                        DeploymentStatus.DEPLOYING,
                        DeploymentStatus.HEALTHCHECK,
                    }
                ),
            )
            .limit(1)
        )
        return deployment_id is not None

    async def list_stoppable_for_project(
        self, session: AsyncSession, project_id: UUID
    ) -> list[DeploymentRecord]:
        result = await session.scalars(
            select(Deployment)
            .where(
                Deployment.project_id == project_id,
                Deployment.status.in_(
                    {
                        DeploymentStatus.PENDING,
                        DeploymentStatus.DEPLOYING,
                        DeploymentStatus.HEALTHCHECK,
                        DeploymentStatus.RUNNING,
                        DeploymentStatus.UNHEALTHY,
                        DeploymentStatus.STOPPING,
                    }
                ),
            )
            .order_by(Deployment.created_at.desc())
            .limit(500)
        )
        return [_to_domain(model) for model in result]

    async def next_route_priority(self, session: AsyncSession, project_id: UUID) -> int:
        current = await session.scalar(
            select(func.max(Deployment.route_priority)).where(Deployment.project_id == project_id)
        )
        return max(100, int(current or 99) + 1)

    async def create(
        self,
        session: AsyncSession,
        *,
        deployment_id: UUID,
        project_id: UUID,
        build_id: UUID,
        hostname: str,
        container_name: str,
        image_ref: str,
        runtime_version: str,
        network_name: str,
        manifest_sha256: str,
        route_priority: int,
        stop_old_first: bool,
        deployed_by: UUID,
    ) -> DeploymentRecord:
        model = Deployment(
            id=deployment_id,
            project_id=project_id,
            build_id=build_id,
            status=DeploymentStatus.PENDING,
            hostname=hostname,
            container_name=container_name,
            image_ref=image_ref,
            runtime_version=runtime_version,
            network_name=network_name,
            manifest_sha256=manifest_sha256,
            route_priority=route_priority,
            stop_old_first=stop_old_first,
            deployed_by=deployed_by,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def transition(
        self,
        session: AsyncSession,
        deployment_id: UUID,
        *,
        expected: set[DeploymentStatus],
        status: DeploymentStatus,
        values: dict[str, object] | None = None,
    ) -> DeploymentRecord | None:
        changes = dict(values or {})
        changes["status"] = status
        updated_id = await session.scalar(
            update(Deployment)
            .where(Deployment.id == deployment_id, Deployment.status.in_(expected))
            .values(**changes)
            .returning(Deployment.id)
        )
        if updated_id is None:
            return None
        return await self.get(session, deployment_id)

    async def begin_activation(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> bool:
        deployment = await self.get_for_update(session, deployment_id)
        if deployment is None:
            return False
        if deployment.status not in {
            DeploymentStatus.DEPLOYING,
            DeploymentStatus.HEALTHCHECK,
        }:
            return False
        project = await session.scalar(
            select(Project).where(Project.id == deployment.project_id).with_for_update()
        )
        if project is None or not project.is_enabled:
            return False
        if project.active_deployment_id and project.active_deployment_id != deployment_id:
            old = await self.get_for_update(session, project.active_deployment_id)
            if old is not None and old.status == DeploymentStatus.RUNNING:
                await session.execute(
                    update(Deployment)
                    .where(Deployment.id == old.id)
                    .values(status=DeploymentStatus.STOPPING)
                )
        await session.execute(
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.status.in_({DeploymentStatus.DEPLOYING, DeploymentStatus.HEALTHCHECK}),
            )
            .values(
                status=DeploymentStatus.HEALTHCHECK,
                health_status="activating",
                error_code=None,
                error_summary=None,
            )
        )
        project.active_build_id = deployment.build_id
        project.active_deployment_id = deployment.id
        await session.flush()
        return True

    async def complete_activation(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> DeploymentRecord | None:
        deployment = await self.get_for_update(session, deployment_id)
        if deployment is None or deployment.status != DeploymentStatus.HEALTHCHECK:
            return None
        project = await session.scalar(
            select(Project).where(Project.id == deployment.project_id).with_for_update()
        )
        if (
            project is None
            or not project.is_enabled
            or project.active_deployment_id != deployment_id
        ):
            return None
        superseded_id = await session.scalar(
            select(Deployment.id)
            .where(
                Deployment.project_id == deployment.project_id,
                Deployment.id != deployment_id,
                Deployment.status.in_({DeploymentStatus.RUNNING, DeploymentStatus.STOPPING}),
            )
            .limit(1)
        )
        if superseded_id is not None:
            return None
        now = datetime.now(UTC)
        updated_id = await session.scalar(
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.status == DeploymentStatus.HEALTHCHECK,
            )
            .values(
                status=DeploymentStatus.RUNNING,
                health_status="healthy",
                started_at=func.coalesce(Deployment.started_at, now),
                error_code=None,
                error_summary=None,
            )
            .returning(Deployment.id)
        )
        if updated_id is None:
            return None
        return await self.get(session, deployment_id)

    async def clear_active(
        self, session: AsyncSession, project_id: UUID, deployment_id: UUID
    ) -> None:
        await session.execute(
            update(Project)
            .where(
                Project.id == project_id,
                Project.active_deployment_id == deployment_id,
            )
            .values(active_deployment_id=None)
        )

    async def mark_stopped(
        self, session: AsyncSession, deployment_id: UUID
    ) -> DeploymentRecord | None:
        now = datetime.now(UTC)
        await session.execute(
            update(Deployment)
            .where(Deployment.id == deployment_id)
            .values(
                status=DeploymentStatus.STOPPED,
                health_status="stopped",
                stopped_at=now,
            )
        )
        return await self.get(session, deployment_id)

    async def mark_failed(
        self,
        session: AsyncSession,
        deployment_id: UUID,
        *,
        error_code: str,
        error_summary: str,
        unhealthy: bool = False,
    ) -> DeploymentRecord | None:
        now = datetime.now(UTC)
        updated_id = await session.scalar(
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.status.in_(
                    {
                        DeploymentStatus.PENDING,
                        DeploymentStatus.DEPLOYING,
                        DeploymentStatus.HEALTHCHECK,
                    }
                ),
            )
            .values(
                status=(DeploymentStatus.UNHEALTHY if unhealthy else DeploymentStatus.FAILED),
                health_status="unhealthy" if unhealthy else "failed",
                failed_at=now,
                error_code=error_code[:128],
                error_summary=error_summary[:2_000],
            )
            .returning(Deployment.id)
        )
        if updated_id is None:
            return None
        return await self.get(session, deployment_id)

    async def reset_for_retry(
        self,
        session: AsyncSession,
        deployment_id: UUID,
    ) -> DeploymentRecord | None:
        updated_id = await session.scalar(
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.status.in_({DeploymentStatus.DEPLOYING, DeploymentStatus.HEALTHCHECK}),
            )
            .values(
                status=DeploymentStatus.PENDING,
                container_id=None,
                image_digest=None,
                health_status=None,
                started_at=None,
                failed_at=None,
                error_code=None,
                error_summary=None,
            )
            .returning(Deployment.id)
        )
        if updated_id is None:
            return None
        return await self.get(session, deployment_id)

    async def find_superseded_running(
        self, session: AsyncSession, active: DeploymentRecord
    ) -> list[DeploymentRecord]:
        result = await session.scalars(
            select(Deployment).where(
                Deployment.project_id == active.project_id,
                Deployment.id != active.id,
                Deployment.status.in_({DeploymentStatus.RUNNING, DeploymentStatus.STOPPING}),
            )
        )
        return [_to_domain(model) for model in result]

    async def list_pending(self, session: AsyncSession, *, limit: int = 100) -> list[UUID]:
        result = await session.scalars(
            select(Deployment.id)
            .where(Deployment.status == DeploymentStatus.PENDING)
            .order_by(Deployment.created_at.asc())
            .limit(min(limit, 500))
        )
        return list(result)
