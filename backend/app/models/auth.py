from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import CITEXT, INET
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.auth import UserRole
from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text(), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=_enum_values),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "auth_sessions"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_prefix: Mapped[str | None] = mapped_column(INET(), nullable=True)
