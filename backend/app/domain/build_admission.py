from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.builds import BuildStatus


class BuildAdmissionState(StrEnum):
    WAITING = "waiting"
    ADMITTED = "admitted"
    RUNNING = "running"


class BuildLeaseState(StrEnum):
    OWNED = "owned"
    CANCELLATION_REQUESTED = "cancellation_requested"
    LOST = "lost"


class BuildLeaseRenewal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: BuildLeaseState
    lease_expires_at: datetime | None = None


class BuildAdmissionClaim(BaseModel):
    """Internal reservation handed from the durable dispatcher to RQ."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    build_id: UUID
    project_id: UUID
    requested_by: UUID
    status: BuildStatus
    token: UUID
    attempt_count: int = Field(ge=1)
    lease_expires_at: datetime
    cancellation_requested: bool = False


class QueuedBuildAdmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    build_id: UUID
    project_id: UUID
    status: BuildStatus
    state: BuildAdmissionState
    position: int | None = Field(default=None, ge=1)
    admitted_at: datetime | None = None
    lease_expires_at: datetime | None = None


class BuildAdmissionOverview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    configured_concurrency: int = Field(ge=1)
    effective_concurrency: int = Field(ge=0)
    waiting_count: int = Field(ge=0)
    entries: list[QueuedBuildAdmission]
