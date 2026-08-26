from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from app.domain.deployments import MCPAuthMode


class MCPAuthConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: MCPAuthMode
    issuer_url: AnyHttpUrl | None = None
    audiences: list[str] = Field(default_factory=list, max_length=50)
    required_scopes: list[str] = Field(default_factory=list, max_length=100)
    jwks_url: AnyHttpUrl | None = None
    allowed_algorithms: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def exact_mode_fields(self) -> "MCPAuthConfigUpdate":
        if self.mode == MCPAuthMode.EXTERNAL_OAUTH_OIDC:
            if self.issuer_url is None or not self.audiences:
                raise ValueError("OIDC mode requires issuer_url and at least one audience")
        elif (
            self.issuer_url is not None
            or self.audiences
            or self.required_scopes
            or self.jwks_url is not None
            or self.allowed_algorithms
        ):
            raise ValueError("OIDC verifier fields are valid only in OIDC mode")
        return self

    def metadata(self) -> dict[str, object]:
        result: dict[str, object] = {}
        if self.jwks_url is not None:
            result["jwks_url"] = str(self.jwks_url)
        if self.allowed_algorithms:
            result["allowed_algorithms"] = list(self.allowed_algorithms)
        return result


class MCPAuthConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    mode: MCPAuthMode
    issuer_url: str | None
    audiences: list[str]
    required_scopes: list[str]
    metadata: dict[str, object]
    updated_by: UUID
    updated_at: datetime


class MCPAccessTokenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    expires_at: datetime | None = None


class MCPAccessTokenRotate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overlap_seconds: int = Field(default=300, ge=0, le=900)


class MCPAccessTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    token_prefix: str
    created_by: UUID
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class MCPAccessTokenIssued(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: MCPAccessTokenRead
    plaintext: str


class MCPAccessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_config: MCPAuthConfigRead | None
    tokens: list[MCPAccessTokenRead]
