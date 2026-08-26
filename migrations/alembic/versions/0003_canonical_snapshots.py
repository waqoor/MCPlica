"""Create immutable canonical snapshots.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("canonical_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "canonical_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "source_version_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_canonical_snapshots_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_canonical_snapshots"),
        sa.CheckConstraint(
            "canonical_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_canonical_snapshots_sha256",
        ),
        sa.CheckConstraint(
            "cardinality(source_version_ids) > 0",
            name="ck_canonical_snapshots_source_versions",
        ),
    )
    op.create_index(
        "ix_canonical_snapshots_project_id",
        "canonical_snapshots",
        ["project_id"],
    )
    op.create_index(
        "ix_canonical_snapshots_canonical_sha256",
        "canonical_snapshots",
        ["canonical_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_snapshots_canonical_sha256",
        table_name="canonical_snapshots",
    )
    op.drop_index("ix_canonical_snapshots_project_id", table_name="canonical_snapshots")
    op.drop_table("canonical_snapshots")
