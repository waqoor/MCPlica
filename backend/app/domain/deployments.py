from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    HEALTHCHECK = "healthcheck"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in {self.UNHEALTHY, self.STOPPED, self.FAILED}


class MCPAuthMode(StrEnum):
    STATIC_BEARER = "static_bearer"
    EXTERNAL_OAUTH_OIDC = "external_oauth_oidc"
    DISABLED_DEV = "disabled_dev"


class DeploymentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    build_id: UUID
    status: DeploymentStatus
    hostname: str
    container_name: str
    container_id: str | None
    image_ref: str
    image_digest: str | None
    runtime_version: str
    network_name: str
    manifest_sha256: str
    route_priority: int
    stop_old_first: bool
    health_status: str | None
    deployed_by: UUID
    created_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_summary: str | None


class DeployableBuildRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    status: str
    manifest_sha256: str | None
    manifest_storage_key: str | None


class MCPAuthConfigRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    mode: MCPAuthMode
    issuer_url: str | None
    audiences: list[str]
    required_scopes: list[str]
    metadata: dict[str, object]
    updated_by: UUID
    updated_at: datetime


class MCPAccessTokenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    name: str
    token_prefix: str
    created_by: UUID
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class MCPAccessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    auth_config: MCPAuthConfigRecord | None
    tokens: list[MCPAccessTokenRecord]


class IssuedMCPAccessToken(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token: MCPAccessTokenRecord
    plaintext: str
