from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class CanonicalSnapshot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "canonical_snapshots"
    __table_args__ = (
        CheckConstraint(
            "canonical_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_canonical_snapshots_sha256",
        ),
        CheckConstraint(
            "cardinality(source_version_ids) > 0",
            name="ck_canonical_snapshots_source_versions",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    canonical_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonical_json: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False)
    source_version_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        nullable=False,
    )
