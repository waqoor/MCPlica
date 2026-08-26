from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.deployments import DeploymentRecord, DeploymentStatus


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
    health_status: str | None
    created_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_summary: str | None

    @classmethod
    def from_record(cls, record: DeploymentRecord, *, tls: bool) -> "DeploymentRead":
        scheme = "https" if tls else "http"
        return cls(
            **record.model_dump(
                exclude={
                    "route_priority",
                    "stop_old_first",
                    "deployed_by",
                }
            ),
            endpoint_url=f"{scheme}://{record.hostname}/mcp",
        )


class DeploymentListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
