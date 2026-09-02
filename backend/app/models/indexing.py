from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.indexing import IndexGenerationStatus
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class DocumentIndexGeneration(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "document_index_generations"
    __table_args__ = (
        UniqueConstraint("build_id", name="uq_document_index_generations_build_id"),
        CheckConstraint(
            "generation_key ~ '^[a-f0-9]{64}$'",
            name="ck_document_index_generation_key_sha256",
        ),
        CheckConstraint(
            "chunk_manifest_sha256 IS NULL OR chunk_manifest_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_document_index_chunk_manifest_sha256",
        ),
        CheckConstraint(
            "chunk_count >= 0",
            name="ck_document_index_generations_chunk_count",
        ),
        CheckConstraint(
            "dimensions IS NULL OR dimensions >= 0",
            name="ck_document_index_generations_dimensions",
        ),
        CheckConstraint(
            "source_fingerprint ~ '^[a-f0-9]{64}$'",
            name="ck_document_index_generations_source_fingerprint",
        ),
        CheckConstraint(
            "status <> 'ready'::document_index_status OR ("
            "completed_at IS NOT NULL AND dimensions IS NOT NULL AND "
            "chunk_manifest_storage_key IS NOT NULL AND chunk_manifest_sha256 IS NOT NULL "
            "AND ((chunk_count = 0 AND dimensions = 0 AND collection_name IS NULL) OR "
            "(chunk_count > 0 AND dimensions > 0 AND embedding_model IS NOT NULL "
            "AND collection_name IS NOT NULL)))",
            name="ck_document_index_ready_complete",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_model: Mapped[str | None] = mapped_column(String(300), nullable=True)
    dimensions: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    collection_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    chunk_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    chunk_manifest_storage_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    chunk_manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[IndexGenerationStatus] = mapped_column(
        Enum(
            IndexGenerationStatus,
            name="document_index_status",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    execution_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmbeddingVectorCache(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "embedding_vector_cache"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "model_identity",
            "content_sha256",
            name="uq_embedding_vector_cache_identity",
        ),
        CheckConstraint(
            "char_length(btrim(model_identity)) > 0",
            name="ck_embedding_vector_cache_model_identity_nonempty",
        ),
        CheckConstraint(
            "char_length(btrim(resolved_model)) > 0",
            name="ck_embedding_vector_cache_resolved_model_nonempty",
        ),
        CheckConstraint(
            "content_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_embedding_vector_cache_content_sha256",
        ),
        CheckConstraint(
            "dimensions > 0",
            name="ck_embedding_vector_cache_dimensions",
        ),
        CheckConstraint(
            "jsonb_typeof(vector_json) = 'array' AND jsonb_array_length(vector_json) = dimensions",
            name="ck_embedding_vector_cache_shape",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_identity: Mapped[str] = mapped_column(String(300), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_model: Mapped[str] = mapped_column(String(300), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer(), nullable=False)
    vector_json: Mapped[list[float]] = mapped_column(JSONB(), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
