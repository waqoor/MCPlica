from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.indexing import IndexGenerationStatus
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class DocumentIndexGeneration(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "document_index_generations"
    __table_args__ = (UniqueConstraint("build_id", name="uq_document_index_generations_build_id"),)

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
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
