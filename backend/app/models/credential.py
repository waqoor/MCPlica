from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.credentials import CredentialScheme
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class ProjectCredential(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "project_credentials"

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    scheme_type: Mapped[CredentialScheme] = mapped_column(
        Enum(
            CredentialScheme,
            name="credential_scheme",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary(), nullable=False)
    key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB(), default=dict, nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
