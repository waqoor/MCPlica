import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=63)
    description: str | None = Field(default=None, max_length=10_000)

    @field_validator("slug")
    @classmethod
    def slug_is_dns_safe(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not SLUG_RE.fullmatch(normalized):
            raise ValueError("slug must be DNS-label safe: lowercase alphanumeric and hyphen")
        return normalized


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=10_000)
    enabled: bool | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
