"""Cache project-scoped embeddings by model and normalized chunk content.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embedding_vector_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_identity", sa.String(length=300), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("resolved_model", sa.String(length=300), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "vector_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
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
            name="fk_embedding_vector_cache_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_embedding_vector_cache"),
        sa.UniqueConstraint(
            "project_id",
            "model_identity",
            "content_sha256",
            name="uq_embedding_vector_cache_identity",
        ),
        sa.CheckConstraint(
            "char_length(btrim(model_identity)) > 0",
            name="ck_embedding_vector_cache_model_identity_nonempty",
        ),
        sa.CheckConstraint(
            "char_length(btrim(resolved_model)) > 0",
            name="ck_embedding_vector_cache_resolved_model_nonempty",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_embedding_vector_cache_content_sha256",
        ),
        sa.CheckConstraint(
            "dimensions > 0",
            name="ck_embedding_vector_cache_dimensions",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(vector_json) = 'array' AND jsonb_array_length(vector_json) = dimensions",
            name="ck_embedding_vector_cache_shape",
        ),
    )
    op.create_index(
        "ix_embedding_vector_cache_project_id",
        "embedding_vector_cache",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_embedding_vector_cache_project_id",
        table_name="embedding_vector_cache",
    )
    op.drop_table("embedding_vector_cache")
