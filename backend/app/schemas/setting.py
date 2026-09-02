from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.core.hostname import normalize_dns_hostname


class SystemSettingsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    builders_can_deploy: bool
    mcp_base_domain: str
    build_concurrency: int
    source_retention_days: int | None
    build_retention_count: int | None
    max_upload_bytes: int
    max_operations_per_project: int
    max_document_chunks_per_project: int
    environment: Literal["development", "production", "test"]


class SystemSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # These fields are omissible for PATCH but explicit null has no persisted
    # meaning. A non-optional annotation with a None default expresses that
    # distinction in both Pydantic validation and the generated OpenAPI schema.
    builders_can_deploy: bool = Field(default=cast(bool, None))
    mcp_base_domain: str = Field(default=cast(str, None), min_length=1, max_length=253)
    build_concurrency: int = Field(default=cast(int, None), ge=1, le=32)
    source_retention_days: int | None = Field(default=None, ge=1, le=3650)
    build_retention_count: int | None = Field(default=None, ge=1, le=10_000)
    max_upload_bytes: int = Field(default=cast(int, None), ge=1024, le=100_000_000)
    max_operations_per_project: int = Field(default=cast(int, None), ge=1, le=100_000)
    max_document_chunks_per_project: int = Field(default=cast(int, None), ge=1, le=100_000)
    environment: Literal["development", "production", "test"] = Field(
        default=cast(Literal["development", "production", "test"], None)
    )

    @field_validator("mcp_base_domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        try:
            return normalize_dns_hostname(value)
        except ValueError as exc:
            raise ValueError("mcp_base_domain must be a DNS hostname") from exc


class ModelSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_model: str | None = Field(default=None, max_length=300)
    validation_model: str | None = Field(default=None, max_length=300)
    embedding_model: str | None = Field(default=None, max_length=300)
    include_documentation_in_analysis: bool = False

    @field_validator("analysis_model", "validation_model", "embedding_model")
    @classmethod
    def normalize_model(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None


class ModelSettingsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openrouter_configured: bool
    analysis_model: str | None
    validation_model: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    include_documentation_in_analysis: bool
    updated_at: datetime | None


class OpenRouterSecretUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr = Field(min_length=10, max_length=500)


class ModelCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    context_length: int | None = None
    supports_structured_outputs: bool
    supports_embeddings: bool


class OpenRouterTestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str
