from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_json: Mapped[object] = mapped_column(JSONB(), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SystemSecret(CreatedAtMixin, Base):
    __tablename__ = "system_secrets"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary(), nullable=False)
    key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
