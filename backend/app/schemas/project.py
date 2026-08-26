import re
from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=3, max_length=63)
    description: str | None = Field(default=None, max_length=10_000)
    default_base_url: AnyHttpUrl | None = None

    @field_validator("slug")
    @classmethod
    def slug_is_dns_safe(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not SLUG_RE.fullmatch(normalized):
            raise ValueError("slug must be DNS-label safe: lowercase alphanumeric and hyphen")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=10_000)
    default_base_url: AnyHttpUrl | None = None
    active_server_ref: str | None = Field(default=None, min_length=1, max_length=120)
    is_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    default_base_url: str | None
    active_server_ref: str | None
    mcp_hostname: str
    is_enabled: bool
    active_build_id: UUID | None
    active_deployment_id: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
