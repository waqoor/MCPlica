from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.deployments import (
    DeploymentActivationPhase,
    DeploymentRecord,
    DeploymentStatus,
    is_rollback_eligible,
)


class DeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_id: UUID


class DeploymentRollback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_deployment_id: UUID


class DeploymentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    build_id: UUID
    status: DeploymentStatus
    hostname: str
    endpoint_url: str
    container_name: str
    container_id: str | None
    image_ref: str
    image_digest: str | None
    runtime_version: str
    network_name: str
    manifest_sha256: str
    auth_overlay_sha256: str | None
    health_status: str | None
    created_at: datetime
    started_at: datetime | None
    activated_at: datetime | None
    activation_phase: DeploymentActivationPhase | None
    activation_verified_at: datetime | None
    activation_proof_sha256: str | None
    stopped_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_summary: str | None
    rollback_eligible: bool

    @classmethod
    def from_record(
        cls,
        record: DeploymentRecord,
        *,
        tls: bool,
        active_deployment_id: UUID | None,
    ) -> "DeploymentRead":
        scheme = "https" if tls else "http"
        values = record.model_dump(
            exclude={
                "route_priority",
                "stop_old_first",
                "deployed_by",
                "previous_active_deployment_id",
            }
        )
        return cls(
            **values,
            endpoint_url=f"{scheme}://{record.hostname}/mcp",
            rollback_eligible=is_rollback_eligible(
                record,
                active_deployment_id=active_deployment_id,
            ),
        )


class DeploymentPageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DeploymentRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    has_active: bool


class DeploymentListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
