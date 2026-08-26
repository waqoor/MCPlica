"""Create projects, immutable sources, and encrypted credentials.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source_kind = postgresql.ENUM(
        "openapi", "api_inventory", "documentation", name="source_kind", create_type=False
    )
    source_origin = postgresql.ENUM("upload", "url", name="source_origin", create_type=False)
    credential_scheme = postgresql.ENUM(
        "bearer",
        "api_key_header",
        "api_key_query",
        "basic",
        "oauth2_client_credentials",
        "static_headers",
        name="credential_scheme",
        create_type=False,
    )
    source_kind.create(op.get_bind(), checkfirst=True)
    source_origin.create(op.get_bind(), checkfirst=True)
    credential_scheme.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_base_url", sa.Text(), nullable=True),
        sa.Column("active_server_ref", sa.String(length=120), nullable=True),
        sa.Column("mcp_hostname", sa.String(length=253), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_projects_created_by_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("mcp_hostname", name="uq_projects_mcp_hostname"),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )
    op.create_index("ix_projects_mcp_hostname", "projects", ["mcp_hostname"], unique=True)
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)

    op.create_table(
        "project_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", source_kind, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("origin_type", source_origin, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_sources_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_sources"),
        sa.CheckConstraint(
            "(origin_type = 'url' AND source_url IS NOT NULL) OR "
            "(origin_type = 'upload' AND source_url IS NULL)",
            name="ck_project_sources_origin_url",
        ),
    )
    op.create_index("ix_project_sources_project_id", "project_sources", ["project_id"])
    op.create_index(
        "uq_project_sources_primary_executable",
        "project_sources",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_primary AND kind IN ('openapi'::source_kind, 'api_inventory'::source_kind)"
        ),
    )

    op.create_table(
        "source_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("detected_format", sa.String(length=80), nullable=False),
        sa.Column("source_etag", sa.Text(), nullable=True),
        sa.Column("source_last_modified", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_source_versions_created_by_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["project_sources.id"],
            name="fk_source_versions_source_id_project_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_versions"),
        sa.UniqueConstraint("source_id", "content_sha256", name="uq_source_versions_source_hash"),
        sa.CheckConstraint("byte_size >= 0", name="ck_source_versions_byte_size"),
    )
    op.create_index("ix_source_versions_source_id", "source_versions", ["source_id"])

    op.create_table(
        "project_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("scheme_type", credential_scheme, nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.String(length=64), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_project_credentials_created_by_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_credentials_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_credentials"),
    )
    op.create_index("ix_project_credentials_project_id", "project_credentials", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_credentials_project_id", table_name="project_credentials")
    op.drop_table("project_credentials")
    op.drop_index("ix_source_versions_source_id", table_name="source_versions")
    op.drop_table("source_versions")
    op.drop_index("uq_project_sources_primary_executable", table_name="project_sources")
    op.drop_index("ix_project_sources_project_id", table_name="project_sources")
    op.drop_table("project_sources")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_index("ix_projects_mcp_hostname", table_name="projects")
    op.drop_table("projects")
    postgresql.ENUM(name="credential_scheme").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="source_origin").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="source_kind").drop(op.get_bind(), checkfirst=True)
