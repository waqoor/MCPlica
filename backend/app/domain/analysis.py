from typing import Literal

from mcp_contracts import SemanticProvenance
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OperationEnrichmentResult(BaseModel):
    """Strict AI response. It intentionally contains no executable transport fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_key: str = Field(min_length=1, max_length=160)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4_000)
    category: str | None = Field(default=None, max_length=160)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    documentation_chunk_ids: list[str] = Field(default_factory=list, max_length=20)
    relationship_hints: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("keywords", "documentation_chunk_ids", "relationship_hints", "warnings")
    @classmethod
    def normalize_unique_text(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized


class OperationEnrichment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_key: str
    title: str | None
    description: str | None
    category: str | None
    keywords: list[str]
    documentation_chunk_ids: list[str]
    relationship_hints: list[str]
    confidence: float
    warnings: list[str]
    provenance: SemanticProvenance


class EnrichmentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["semantic-enrichment/v1"] = "semantic-enrichment/v1"
    operations: dict[str, OperationEnrichment]


class SemanticReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    severity: Literal["warning", "info"]
    operation_key: str | None = Field(default=None, max_length=160)
    message: str = Field(min_length=1, max_length=2_000)


class SemanticReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    findings: list[SemanticReviewFinding] = Field(
        default_factory=lambda: list[SemanticReviewFinding](),
        max_length=200,
    )
