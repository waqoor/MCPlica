"""Persist exact source-version findings.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_key", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("pointer", sa.Text(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("column_number", sa.Integer(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('error', 'warning', 'info')",
            name="ck_source_findings_severity",
        ),
        sa.CheckConstraint(
            "char_length(btrim(stage)) > 0 AND char_length(btrim(code)) > 0 "
            "AND char_length(btrim(message)) > 0",
            name="ck_source_findings_required_text",
        ),
        sa.CheckConstraint(
            "finding_key ~ '^[a-f0-9]{64}$'",
            name="ck_source_findings_key",
        ),
        sa.CheckConstraint(
            "(line_number IS NULL OR line_number >= 1) "
            "AND (column_number IS NULL OR column_number >= 1)",
            name="ck_source_findings_position",
        ),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["source_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "build_id",
            "source_version_id",
            "finding_key",
            name="uq_source_findings_build_source_key",
        ),
    )
    op.create_index(
        "ix_source_findings_build",
        "source_findings",
        ["build_id"],
    )
    op.create_index(
        "ix_source_findings_source_created",
        "source_findings",
        ["source_version_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("source_findings")
