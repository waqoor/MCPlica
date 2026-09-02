import hashlib
import hmac
import json
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class DeploymentIntent(StrEnum):
    NORMAL = "normal"
    SECURITY_REFRESH = "security_refresh"
    ROLLBACK = "rollback"


class DeploymentActivationPhase(StrEnum):
    VERIFIED = "verified"
    RETIRING_PREVIOUS = "retiring_previous"
    RUNNING = "running"
    LEGACY_RUNNING = "legacy_running"
    FAILED = "failed"


def activation_proof_sha256(
    *,
    deployment_id: UUID,
    project_id: UUID,
    build_id: UUID,
    container_id: str,
    image_digest: str,
    hostname: str,
    manifest_sha256: str,
    runtime_version: str,
    verified_at: datetime,
) -> str:
    payload = {
        "build_id": str(build_id),
        "container_id": container_id,
        "deployment_id": str(deployment_id),
        "hostname": hostname,
        "image_digest": image_digest,
        "manifest_sha256": manifest_sha256,
        "project_id": str(project_id),
        "runtime_version": runtime_version,
        "verified_at": verified_at.astimezone(UTC).isoformat(timespec="microseconds"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class DeploymentActivationProof(BaseModel):
    """Content-bound proof of the exact runtime observed through the edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deployment_id: UUID
    project_id: UUID
    build_id: UUID
    container_id: str = Field(min_length=1)
    image_digest: str = Field(min_length=1)
    hostname: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_version: str = Field(min_length=1)
    verified_at: datetime
    proof_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @classmethod
    def verified(
        cls,
        *,
        deployment_id: UUID,
        project_id: UUID,
        build_id: UUID,
        container_id: str,
        image_digest: str,
        hostname: str,
        manifest_sha256: str,
        runtime_version: str,
        verified_at: datetime | None = None,
    ) -> "DeploymentActivationProof":
        observed_at = verified_at or datetime.now(UTC)
        proof_sha256 = activation_proof_sha256(
            deployment_id=deployment_id,
            project_id=project_id,
            build_id=build_id,
            container_id=container_id,
            image_digest=image_digest,
            hostname=hostname,
            manifest_sha256=manifest_sha256,
            runtime_version=runtime_version,
            verified_at=observed_at,
        )
        return cls(
            deployment_id=deployment_id,
            project_id=project_id,
            build_id=build_id,
            container_id=container_id,
            image_digest=image_digest,
            hostname=hostname,
            manifest_sha256=manifest_sha256,
            runtime_version=runtime_version,
            verified_at=observed_at,
            proof_sha256=proof_sha256,
        )

    @model_validator(mode="after")
    def validate_content_binding(self) -> "DeploymentActivationProof":
        if self.verified_at.utcoffset() is None:
            raise ValueError("Activation proof timestamp must be timezone-aware")
        expected = activation_proof_sha256(
            deployment_id=self.deployment_id,
            project_id=self.project_id,
            build_id=self.build_id,
            container_id=self.container_id,
            image_digest=self.image_digest,
            hostname=self.hostname,
            manifest_sha256=self.manifest_sha256,
            runtime_version=self.runtime_version,
            verified_at=self.verified_at,
        )
        if not hmac.compare_digest(expected, self.proof_sha256):
            raise ValueError("Activation proof content binding is invalid")
        return self


class MCPAuthMode(StrEnum):
    STATIC_BEARER = "static_bearer"
    EXTERNAL_OAUTH_OIDC = "external_oauth_oidc"
    DISABLED_DEV = "disabled_dev"


class RuntimeCommandAction(StrEnum):
    DEPLOY = "deploy"
    STOP = "stop"


class RuntimeCommandStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    FAILED = "failed"
    EFFECTIVE = "effective"

    @property
    def terminal(self) -> bool:
        return self in {self.FAILED, self.EFFECTIVE}


class RuntimeCommandLeaseState(StrEnum):
    OWNED = "owned"
    LOST = "lost"


class RuntimeCommandLeaseRenewal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: RuntimeCommandLeaseState
    database_now: datetime
    lease_expires_at: datetime | None = None


class RuntimeEffectState(StrEnum):
    EFFECTIVE = "effective"
    PENDING = "pending"
    FAILED = "failed"


class DeploymentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    build_id: UUID
    intent: DeploymentIntent = DeploymentIntent.NORMAL
    previous_active_deployment_id: UUID | None = None
    status: DeploymentStatus
    hostname: str
    container_name: str
    container_id: str | None
    image_ref: str
    image_digest: str | None
    runtime_version: str
    network_name: str
    manifest_sha256: str
    auth_overlay_sha256: str | None = None
    route_priority: int
    stop_old_first: bool
    health_status: str | None
    deployed_by: UUID
    created_at: datetime
    started_at: datetime | None
    activated_at: datetime | None = None
    activation_phase: DeploymentActivationPhase | None = None
    activation_verified_at: datetime | None = None
    activation_proof_sha256: str | None = None
    stopped_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_summary: str | None


def has_successful_activation(record: DeploymentRecord) -> bool:
    """Verify immutable evidence that this exact runtime was once activated."""

    if (
        record.activated_at is None
        or record.started_at is None
        or record.container_id is None
        or record.image_digest is None
    ):
        return False
    if record.activation_phase is DeploymentActivationPhase.LEGACY_RUNNING:
        return True
    if (
        record.activation_verified_at is None
        or record.activation_verified_at.utcoffset() is None
        or record.activation_proof_sha256 is None
    ):
        return False
    expected = activation_proof_sha256(
        deployment_id=record.id,
        project_id=record.project_id,
        build_id=record.build_id,
        container_id=record.container_id,
        image_digest=record.image_digest,
        hostname=record.hostname,
        manifest_sha256=record.manifest_sha256,
        runtime_version=record.runtime_version,
        verified_at=record.activation_verified_at,
    )
    return hmac.compare_digest(expected, record.activation_proof_sha256)


def is_rollback_eligible(
    record: DeploymentRecord,
    *,
    active_deployment_id: UUID | None,
) -> bool:
    return record.id != active_deployment_id and has_successful_activation(record)


def is_restart_eligible(
    record: DeploymentRecord,
    *,
    active_deployment_id: UUID | None,
) -> bool:
    """Require the exact, proven active runtime for an operational restart."""

    return (
        record.id == active_deployment_id
        and record.status is DeploymentStatus.RUNNING
        and has_successful_activation(record)
    )


class RuntimeCommandRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    sequence: int
    project_id: UUID
    deployment_id: UUID
    build_id: UUID
    transition_id: UUID
    action: RuntimeCommandAction
    status: RuntimeCommandStatus
    reason: str
    subject_type: str | None
    subject_id: UUID | None
    idempotency_key: str
    requested_by: UUID
    request_id: str | None
    attempt_count: int
    retryable: bool
    next_attempt_at: datetime
    dispatched_at: datetime | None
    started_at: datetime | None
    effective_at: datetime | None
    failed_at: datetime | None
    lease_expires_at: datetime | None
    execution_token: UUID | None
    last_error_code: str | None
    last_error_summary: str | None
    created_at: datetime
    updated_at: datetime


class DeployableBuildRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    status: str
    source_binding_metadata_trustworthy: bool = True
    executable_configuration_sha256: str | None = None
    runtime_manifest_max_bytes: int = Field(ge=1_024, le=50_000_000)
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
    runtime_effect_state: RuntimeEffectState = RuntimeEffectState.EFFECTIVE
    runtime_command_id: UUID | None = None
    runtime_error_code: str | None = None


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
    runtime_effect_state: RuntimeEffectState = RuntimeEffectState.EFFECTIVE
    runtime_command_id: UUID | None = None
    runtime_error_code: str | None = None


class MCPAccessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    auth_config: MCPAuthConfigRecord | None
    tokens: list[MCPAccessTokenRecord]


class MCPAccessStatusRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    mode: MCPAuthMode | None
    configured: bool
    remediation: str | None
    runtime_effect_state: RuntimeEffectState
    runtime_command_id: UUID | None = None
    runtime_error_code: str | None = None


class IssuedMCPAccessToken(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token: MCPAccessTokenRecord
    plaintext: str
