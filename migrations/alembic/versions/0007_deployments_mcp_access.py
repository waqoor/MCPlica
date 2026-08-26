"""Create dynamic deployments and MCP access configuration.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    deployment_status = postgresql.ENUM(
        "pending",
        "deploying",
        "healthcheck",
        "running",
        "unhealthy",
        "stopping",
        "stopped",
        "failed",
        name="deployment_status",
        create_type=False,
    )
    mcp_auth_mode = postgresql.ENUM(
        "static_bearer",
        "external_oauth_oidc",
        "disabled_dev",
        name="mcp_auth_mode",
        create_type=False,
    )
    deployment_status.create(op.get_bind(), checkfirst=True)
    mcp_auth_mode.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", deployment_status, nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("container_name", sa.String(length=255), nullable=False),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("image_ref", sa.Text(), nullable=False),
        sa.Column("image_digest", sa.Text(), nullable=True),
        sa.Column("runtime_version", sa.String(length=64), nullable=False),
        sa.Column("network_name", sa.String(length=255), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("route_priority", sa.Integer(), nullable=False),
        sa.Column(
            "stop_old_first",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("health_status", sa.String(length=64), nullable=True),
        sa.Column("deployed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "route_priority > 0 AND route_priority < 2147482647",
            name="ck_deployments_route_priority_range",
        ),
        sa.CheckConstraint(
            "manifest_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_deployments_manifest_sha256",
        ),
        sa.CheckConstraint(
            "char_length(btrim(hostname)) > 0 "
            "AND char_length(btrim(container_name)) > 0 "
            "AND char_length(btrim(network_name)) > 0 "
            "AND char_length(btrim(image_ref)) > 0 "
            "AND char_length(btrim(runtime_version)) > 0",
            name="ck_deployments_runtime_identity_nonempty",
        ),
        sa.CheckConstraint(
            "status <> 'running'::deployment_status OR ("
            "container_id IS NOT NULL AND image_digest IS NOT NULL "
            "AND started_at IS NOT NULL AND health_status = 'healthy')",
            name="ck_deployments_running_complete",
        ),
        sa.CheckConstraint(
            "status NOT IN ('failed'::deployment_status, 'unhealthy'::deployment_status) "
            "OR (failed_at IS NOT NULL AND error_code IS NOT NULL)",
            name="ck_deployments_failure_complete",
        ),
        sa.CheckConstraint(
            "status <> 'stopped'::deployment_status OR stopped_at IS NOT NULL",
            name="ck_deployments_stopped_complete",
        ),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deployed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("container_id", name="uq_deployments_container_id"),
        sa.UniqueConstraint("container_name", name="uq_deployments_container_name"),
        sa.UniqueConstraint(
            "project_id",
            "route_priority",
            name="uq_deployments_project_route_priority",
        ),
    )
    op.create_index("ix_deployments_build_id", "deployments", ["build_id"])
    op.create_index("ix_deployments_hostname", "deployments", ["hostname"])
    op.create_index("ix_deployments_project_id", "deployments", ["project_id"])
    op.create_index("ix_deployments_status", "deployments", ["status"])
    op.create_index(
        "uq_deployments_one_running_per_project",
        "deployments",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'::deployment_status"),
    )
    op.create_index(
        "uq_deployments_one_in_progress_per_project",
        "deployments",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending'::deployment_status, 'deploying'::deployment_status, "
            "'healthcheck'::deployment_status)"
        ),
    )

    op.create_table(
        "mcp_auth_configs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", mcp_auth_mode, nullable=False),
        sa.Column("issuer_url", sa.Text(), nullable=True),
        sa.Column(
            "audiences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "required_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(audiences) = 'array' "
            "AND jsonb_typeof(required_scopes) = 'array' "
            "AND jsonb_typeof(metadata) = 'object'",
            name="ck_mcp_auth_config_json_shapes",
        ),
        sa.CheckConstraint(
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("project_id"),
    )

    op.create_table(
        "mcp_access_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=71), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "token_hash ~ '^sha256:[a-f0-9]{64}$'",
            name="ck_mcp_access_tokens_sha256",
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) > 0 "
            "AND char_length(token_prefix) >= 4 "
            "AND left(token_prefix, 4) = 'mcp_'",
            name="ck_mcp_access_tokens_identity",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR expires_at IS NOT NULL",
            name="ck_mcp_access_tokens_revocation_expiry",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_mcp_access_tokens_token_hash"),
    )
    op.create_index("ix_mcp_access_tokens_project_id", "mcp_access_tokens", ["project_id"])
    op.create_index(
        "ix_mcp_access_tokens_active",
        "mcp_access_tokens",
        ["project_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.add_column(
        "projects",
        sa.Column("active_build_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("active_deployment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_active_build_id_builds",
        "projects",
        "builds",
        ["active_build_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_projects_active_deployment_id_deployments",
        "projects",
        "deployments",
        ["active_deployment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_projects_active_build_id", "projects", ["active_build_id"])
    op.create_index("ix_projects_active_deployment_id", "projects", ["active_deployment_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_active_deployment_id", table_name="projects")
    op.drop_index("ix_projects_active_build_id", table_name="projects")
    op.drop_constraint(
        "fk_projects_active_deployment_id_deployments",
        "projects",
        type_="foreignkey",
    )
    op.drop_constraint("fk_projects_active_build_id_builds", "projects", type_="foreignkey")
    op.drop_column("projects", "active_deployment_id")
    op.drop_column("projects", "active_build_id")
    op.drop_index("ix_mcp_access_tokens_active", table_name="mcp_access_tokens")
    op.drop_index("ix_mcp_access_tokens_project_id", table_name="mcp_access_tokens")
    op.drop_table("mcp_access_tokens")
    op.drop_table("mcp_auth_configs")
    op.drop_index("uq_deployments_one_in_progress_per_project", table_name="deployments")
    op.drop_index("uq_deployments_one_running_per_project", table_name="deployments")
    op.drop_index("ix_deployments_status", table_name="deployments")
    op.drop_index("ix_deployments_project_id", table_name="deployments")
    op.drop_index("ix_deployments_hostname", table_name="deployments")
    op.drop_index("ix_deployments_build_id", table_name="deployments")
    op.drop_table("deployments")
    postgresql.ENUM(name="mcp_auth_mode").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="deployment_status").drop(op.get_bind(), checkfirst=True)
