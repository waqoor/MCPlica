from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.deployments import RuntimeEffectState


class ProjectRoutingConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    default_base_url: str | None = None
    active_server_ref: str | None = None
    server_mappings: dict[str, str] = Field(default_factory=dict)


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    default_base_url: str | None
    active_server_ref: str | None
    server_mappings: dict[str, str]
    mcp_hostname: str
    is_enabled: bool
    active_build_id: UUID | None
    active_deployment_id: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    runtime_effect_state: RuntimeEffectState = RuntimeEffectState.EFFECTIVE
    runtime_command_id: UUID | None = None
    runtime_error_code: str | None = None
