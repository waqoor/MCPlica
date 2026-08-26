"""Create rebuildable document index generation metadata.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "building",
        "ready",
        "failed",
        name="document_index_status",
        create_type=False,
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "document_index_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_model", sa.String(length=300), nullable=True),
        sa.Column("dimensions", sa.Integer(), nullable=True),
        sa.Column("collection_name", sa.String(length=255), nullable=True),
        sa.Column("generation_key", sa.String(length=64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chunk_manifest_storage_key", sa.Text(), nullable=True),
        sa.Column("chunk_manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_document_index_generations_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_index_generations"),
        sa.UniqueConstraint("build_id", name="uq_document_index_generations_build_id"),
        sa.UniqueConstraint(
            "generation_key",
            name="uq_document_index_generations_generation_key",
        ),
        sa.CheckConstraint(
            "dimensions IS NULL OR dimensions >= 0",
            name="ck_document_index_generations_dimensions",
        ),
        sa.CheckConstraint(
            "chunk_count >= 0",
            name="ck_document_index_generations_chunk_count",
        ),
        sa.CheckConstraint(
            "source_fingerprint ~ '^[a-f0-9]{64}$'",
            name="ck_document_index_generations_source_fingerprint",
        ),
    )
    op.create_index(
        "ix_document_index_generations_project_id",
        "document_index_generations",
        ["project_id"],
    )
    op.create_index(
        "ix_document_index_generations_build_id",
        "document_index_generations",
        ["build_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_index_generations_build_id",
        table_name="document_index_generations",
    )
    op.drop_index(
        "ix_document_index_generations_project_id",
        table_name="document_index_generations",
    )
    op.drop_table("document_index_generations")
    postgresql.ENUM(name="document_index_status").drop(op.get_bind(), checkfirst=True)
