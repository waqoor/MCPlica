from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.builds import BuildStatus
from app.domain.deployments import (
    DeploymentStatus,
    MCPAuthMode,
    RuntimeEffectState,
)
from app.domain.sources import SourceKind
from app.domain.validation import ValidationStatus


class JourneyStepState(StrEnum):
    COMPLETE = "complete"
    CURRENT = "current"
    STALE = "stale"
    LOCKED = "locked"


class JourneyStepRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    number: int = Field(ge=1, le=10)
    state: JourneyStepState
    authorized: bool
    reason_code: str | None = None
    message: str | None = None
    remediation: str | None = None


class JourneySourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    version_id: UUID
    kind: SourceKind
    name: str
    is_primary: bool


class ProjectJourneyRecord(BaseModel):
    """Role-safe, server-derived setup state; URL parameters are never truth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    requested_build_id: UUID | None
    selected_build_id: UUID | None
    active_build_id: UUID | None
    active_deployment_id: UUID | None
    resume_step: int = Field(ge=1, le=10)
    steps: list[JourneyStepRecord] = Field(min_length=10, max_length=10)
    sources: list[JourneySourceRecord]
    source_version_ids: list[UUID]
    routing_complete: bool
    credential_mapping_required: bool
    credential_mapping_complete: bool
    bound_security_schemes: list[str]
    access_mode: MCPAuthMode | None
    access_configured: bool
    access_runtime_effect_state: RuntimeEffectState
    access_remediation: str | None
    build_status: BuildStatus | None
    build_stale: bool
    validation_status: ValidationStatus | None
    validation_complete: bool
    active_deployment_status: DeploymentStatus | None
    deployment_transition_in_progress: bool
    preflight_ready: bool
    deployable: bool
    deployability_reason_code: str | None
    deployability_remediation: str | None
    can_manage_credentials: bool
    can_manage_mcp_access: bool
    can_deploy: bool
