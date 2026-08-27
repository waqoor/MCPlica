from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.deployments import MCPAuthMode
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [value.value for value in enum_type]


class MCPAuthConfig(Base):
    __tablename__ = "mcp_auth_configs"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(audiences) = 'array' "
            "AND jsonb_typeof(required_scopes) = 'array' "
            "AND jsonb_typeof(metadata) = 'object'",
            name="ck_mcp_auth_config_json_shapes",
        ),
        CheckConstraint(
            "(mode = 'external_oauth_oidc'::mcp_auth_mode "
            "AND issuer_url IS NOT NULL AND char_length(issuer_url) <= 2048 "
            "AND jsonb_array_length(audiences) > 0 "
            "AND metadata ? 'allowed_algorithms' "
            "AND jsonb_typeof(metadata -> 'allowed_algorithms') = 'array' "
            "AND jsonb_array_length(metadata -> 'allowed_algorithms') > 0) "
            "OR (mode <> 'external_oauth_oidc'::mcp_auth_mode "
            "AND issuer_url IS NULL AND audiences = '[]'::jsonb "
            "AND required_scopes = '[]'::jsonb AND metadata = '{}'::jsonb)",
            name="ck_mcp_auth_config_mode_shape",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mode: Mapped[MCPAuthMode] = mapped_column(
        Enum(MCPAuthMode, name="mcp_auth_mode", values_callable=_enum_values),
        nullable=False,
    )
    issuer_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    audiences: Mapped[list[str]] = mapped_column(JSONB(), default=list, nullable=False)
    required_scopes: Mapped[list[str]] = mapped_column(JSONB(), default=list, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB(), default=dict, nullable=False
    )
    updated_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MCPAccessToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "mcp_access_tokens"
    __table_args__ = (
        CheckConstraint(
            "token_hash ~ '^sha256:[a-f0-9]{64}$'",
            name="ck_mcp_access_tokens_sha256",
        ),
        CheckConstraint(
            "char_length(btrim(name)) > 0 "
            "AND char_length(token_prefix) >= 4 "
            "AND left(token_prefix, 4) = 'mcp_'",
            name="ck_mcp_access_tokens_identity",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR expires_at IS NOT NULL",
            name="ck_mcp_access_tokens_revocation_expiry",
        ),
        Index(
            "ix_mcp_access_tokens_active",
            "project_id",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
