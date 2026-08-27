"""Add durable reference-aware cleanup jobs and targets.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


cleanup_job_kind = postgresql.ENUM(
    "project_delete",
    "source_delete",
    "retention",
    "orphan_guard",
    name="cleanup_job_kind",
    create_type=False,
)
cleanup_job_status = postgresql.ENUM(
    "pending",
    "running",
    "retrying",
    "completed",
    "failed",
    name="cleanup_job_status",
    create_type=False,
)
cleanup_target_type = postgresql.ENUM(
    "object",
    "vector_generation",
    name="cleanup_target_type",
    create_type=False,
)
cleanup_target_status = postgresql.ENUM(
    "pending",
    "running",
    "retrying",
    "completed",
    "skipped_referenced",
    "failed",
    name="cleanup_target_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    cleanup_job_kind.create(bind, checkfirst=True)
    cleanup_job_status.create(bind, checkfirst=True)
    cleanup_target_type.create(bind, checkfirst=True)
    cleanup_target_status.create(bind, checkfirst=True)

    op.create_table(
        "cleanup_jobs",
        sa.Column("kind", cleanup_job_kind, nullable=False),
        sa.Column(
            "status",
            cleanup_job_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("total_targets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_targets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_targets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_targets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(idempotency_key)) > 0",
            name="ck_cleanup_jobs_idempotency_key_nonempty",
        ),
        sa.CheckConstraint(
            "total_targets >= 0 AND completed_targets >= 0 AND skipped_targets >= 0 "
            "AND failed_targets >= 0 AND completed_targets + skipped_targets + "
            "failed_targets <= total_targets",
            name="ck_cleanup_jobs_progress",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_cleanup_jobs_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_cleanup_jobs_idempotency_key"),
    )
    op.create_index(
        "ix_cleanup_jobs_project_created",
        "cleanup_jobs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_cleanup_jobs_status_created",
        "cleanup_jobs",
        ["status", "created_at"],
    )

    op.create_table(
        "cleanup_targets",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_key", sa.String(length=64), nullable=False),
        sa.Column("target_type", cleanup_target_type, nullable=False),
        sa.Column(
            "status",
            cleanup_target_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("collection_name", sa.String(length=255), nullable=True),
        sa.Column("vector_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_cleanup_targets_attempt_count"),
        sa.CheckConstraint(
            "(target_type = 'object'::cleanup_target_type AND storage_key IS NOT NULL "
            "AND collection_name IS NULL AND vector_project_id IS NULL "
            "AND generation_id IS NULL) OR "
            "(target_type = 'vector_generation'::cleanup_target_type "
            "AND storage_key IS NULL AND collection_name IS NOT NULL "
            "AND vector_project_id IS NOT NULL AND generation_id IS NOT NULL)",
            name="ck_cleanup_targets_shape",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["cleanup_jobs.id"],
            name="fk_cleanup_targets_job_id_cleanup_jobs",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "job_id",
            "target_key",
            name="uq_cleanup_targets_job_target_key",
        ),
    )
    op.create_index(
        "ix_cleanup_targets_due",
        "cleanup_targets",
        ["next_attempt_at", "created_at"],
        postgresql_where=sa.text(
            "status IN ('pending'::cleanup_target_status, "
            "'running'::cleanup_target_status, 'retrying'::cleanup_target_status)"
        ),
    )
    op.create_index(
        "ix_cleanup_targets_job_status",
        "cleanup_targets",
        ["job_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_cleanup_targets_job_status", table_name="cleanup_targets")
    op.drop_index("ix_cleanup_targets_due", table_name="cleanup_targets")
    op.drop_table("cleanup_targets")
    op.drop_index("ix_cleanup_jobs_status_created", table_name="cleanup_jobs")
    op.drop_index("ix_cleanup_jobs_project_created", table_name="cleanup_jobs")
    op.drop_table("cleanup_jobs")
    bind = op.get_bind()
    cleanup_target_status.drop(bind, checkfirst=True)
    cleanup_target_type.drop(bind, checkfirst=True)
    cleanup_job_status.drop(bind, checkfirst=True)
    cleanup_job_kind.drop(bind, checkfirst=True)
