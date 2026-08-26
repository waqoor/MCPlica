"""Create immutable Build core, source bindings, and AI audit runs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_STATUSES = (
    "QUEUED",
    "INGESTING",
    "PARSING",
    "INDEXING",
    "ANALYZING",
    "COMPILING",
    "VALIDATING",
    "PACKAGING",
    "READY",
    "FAILED",
    "CANCELLED",
)


def upgrade() -> None:
    build_status = postgresql.ENUM(*_STATUSES, name="build_status", create_type=False)
    build_trigger = postgresql.ENUM(
        "initial",
        "source_change",
        "manual_review",
        "manual_rebuild",
        name="build_trigger",
        create_type=False,
    )
    build_status.create(op.get_bind(), checkfirst=True)
    build_trigger.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "builds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", build_status, nullable=False),
        sa.Column("trigger", build_trigger, nullable=False),
        sa.Column("canonical_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_build_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("manifest_schema_version", sa.String(length=80), nullable=False),
        sa.Column("runtime_compatibility", sa.String(length=80), nullable=False),
        sa.Column("analysis_model", sa.String(length=300), nullable=True),
        sa.Column("validation_model", sa.String(length=300), nullable=True),
        sa.Column("embedding_model", sa.String(length=300), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("prompt_bundle_version", sa.String(length=64), nullable=True),
        sa.Column("build_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enrichment_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enrichment_sha256", sa.String(length=64), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("manifest_storage_key", sa.Text(), nullable=True),
        sa.Column("artifact_storage_key", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["canonical_snapshot_id"],
            ["canonical_snapshots.id"],
            name="fk_builds_canonical_snapshot_id_canonical_snapshots",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_build_id"],
            ["builds.id"],
            name="fk_builds_previous_build_id_builds",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_builds_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_builds_requested_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_builds"),
        sa.UniqueConstraint("project_id", "sequence", name="uq_builds_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_builds_sequence_positive"),
        sa.CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions >= 0",
            name="ck_builds_embedding_dimensions",
        ),
    )
    op.create_index("ix_builds_project_id", "builds", ["project_id"])
    op.create_index("ix_builds_status", "builds", ["status"])
    op.create_index(
        "uq_builds_one_active_per_project",
        "builds",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text(
            "status NOT IN ('READY'::build_status, 'FAILED'::build_status, "
            "'CANCELLED'::build_status)"
        ),
    )

    op.create_table(
        "build_source_versions",
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["build_id"],
            ["builds.id"],
            name="fk_build_source_versions_build_id_builds",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["source_versions.id"],
            name="fk_build_source_versions_source_version_id_source_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "build_id",
            "source_version_id",
            name="pk_build_source_versions",
        ),
    )
    op.create_index(
        "ix_build_source_versions_source_version_id",
        "build_source_versions",
        ["source_version_id"],
    )

    op.create_table(
        "build_ai_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_key", sa.String(length=160), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("operation_key", sa.String(length=160), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=300), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=160), nullable=False),
        sa.Column("prompt_template_version", sa.String(length=64), nullable=False),
        sa.Column("input_context_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "retrieved_chunk_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("response_schema_id", sa.String(length=160), nullable=False),
        sa.Column("response_sha256", sa.String(length=64), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cost_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["build_id"],
            ["builds.id"],
            name="fk_build_ai_runs_build_id_builds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_build_ai_runs"),
        sa.UniqueConstraint(
            "build_id",
            "run_key",
            name="uq_build_ai_runs_build_run_key",
        ),
    )
    op.create_index("ix_build_ai_runs_build_id", "build_ai_runs", ["build_id"])
    op.create_foreign_key(
        "fk_document_index_generations_build_id_builds",
        "document_index_generations",
        "builds",
        ["build_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_document_index_generations_build_id_builds",
        "document_index_generations",
        type_="foreignkey",
    )
    op.drop_index("ix_build_ai_runs_build_id", table_name="build_ai_runs")
    op.drop_table("build_ai_runs")
    op.drop_index(
        "ix_build_source_versions_source_version_id",
        table_name="build_source_versions",
    )
    op.drop_table("build_source_versions")
    op.drop_index("uq_builds_one_active_per_project", table_name="builds")
    op.drop_index("ix_builds_status", table_name="builds")
    op.drop_index("ix_builds_project_id", table_name="builds")
    op.drop_table("builds")
    postgresql.ENUM(name="build_trigger").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="build_status").drop(op.get_bind(), checkfirst=True)
