from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.deployments import DeploymentActivationPhase, DeploymentStatus
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class Deployment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "route_priority",
            name="uq_deployments_project_route_priority",
        ),
        CheckConstraint(
            "route_priority > 0 AND route_priority < 2147482647",
            name="ck_deployments_route_priority_range",
        ),
        CheckConstraint(
            "manifest_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_deployments_manifest_sha256",
        ),
        CheckConstraint(
            "auth_overlay_sha256 IS NULL OR auth_overlay_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_deployments_auth_overlay_sha256",
        ),
        CheckConstraint(
            "char_length(btrim(hostname)) > 0 "
            "AND char_length(btrim(container_name)) > 0 "
            "AND char_length(btrim(network_name)) > 0 "
            "AND char_length(btrim(image_ref)) > 0 "
            "AND char_length(btrim(runtime_version)) > 0",
            name="ck_deployments_runtime_identity_nonempty",
        ),
        CheckConstraint(
            "status <> 'running'::deployment_status OR ("
            "container_id IS NOT NULL AND image_digest IS NOT NULL "
            "AND started_at IS NOT NULL AND activated_at IS NOT NULL "
            "AND activation_phase IN ('running', 'legacy_running') "
            "AND health_status = 'healthy')",
            name="ck_deployments_running_complete",
        ),
        CheckConstraint(
            "activation_phase IS NULL OR activation_phase IN ("
            "'verified', 'retiring_previous', 'running', 'legacy_running', 'failed')",
            name="ck_deployments_activation_phase",
        ),
        CheckConstraint(
            "activation_phase NOT IN ('verified', 'retiring_previous', 'running') OR ("
            "activation_verified_at IS NOT NULL AND activation_proof_sha256 IS NOT NULL "
            "AND activation_proof_sha256 ~ '^[a-f0-9]{64}$')",
            name="ck_deployments_activation_proof",
        ),
        CheckConstraint(
            "activated_at IS NULL OR (started_at IS NOT NULL AND container_id IS NOT NULL "
            "AND image_digest IS NOT NULL AND (activation_phase = 'legacy_running' OR ("
            "activation_verified_at IS NOT NULL AND activation_proof_sha256 IS NOT NULL "
            "AND activation_proof_sha256 ~ '^[a-f0-9]{64}$')))",
            name="ck_deployments_activation_success_evidence",
        ),
        CheckConstraint(
            "status NOT IN ('failed'::deployment_status, 'unhealthy'::deployment_status) "
            "OR (failed_at IS NOT NULL AND error_code IS NOT NULL)",
            name="ck_deployments_failure_complete",
        ),
        CheckConstraint(
            "status <> 'stopped'::deployment_status OR stopped_at IS NOT NULL",
            name="ck_deployments_stopped_complete",
        ),
        Index(
            "uq_deployments_one_running_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'running'::deployment_status"),
        ),
        Index(
            "uq_deployments_one_in_progress_per_project",
            "project_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending'::deployment_status, 'deploying'::deployment_status, "
                "'healthcheck'::deployment_status)"
            ),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    previous_active_deployment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus, name="deployment_status", values_callable=_enum_values),
        nullable=False,
        index=True,
    )
    hostname: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    container_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    image_ref: Mapped[str] = mapped_column(Text(), nullable=False)
    image_digest: Mapped[str | None] = mapped_column(Text(), nullable=True)
    runtime_version: Mapped[str] = mapped_column(String(64), nullable=False)
    network_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    auth_overlay_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    stop_old_first: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)
    health_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deployed_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_phase: Mapped[DeploymentActivationPhase | None] = mapped_column(
        String(32), nullable=True
    )
    activation_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activation_proof_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
