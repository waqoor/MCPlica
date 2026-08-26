"""Create immutable validation reports and persistent operation exclusions.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    validation_status = postgresql.ENUM(
        "pass",
        "fail",
        name="validation_status",
        create_type=False,
    )
    validation_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "validation_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overall_status", validation_status, nullable=False),
        sa.Column("operation_source_count", sa.Integer(), nullable=False),
        sa.Column("operation_excluded_count", sa.Integer(), nullable=False),
        sa.Column("operation_expected_count", sa.Integer(), nullable=False),
        sa.Column("operation_generated_count", sa.Integer(), nullable=False),
        sa.Column("coverage_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("blocking_error_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["build_id"],
            ["builds.id"],
            name="fk_validation_reports_build_id_builds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_validation_reports"),
        sa.UniqueConstraint("build_id", name="uq_validation_reports_build_id"),
        sa.CheckConstraint(
            "operation_source_count >= 0 AND operation_excluded_count >= 0 AND "
            "operation_expected_count >= 0 AND operation_generated_count >= 0",
            name="ck_validation_reports_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "coverage_percent >= 0 AND coverage_percent <= 100",
            name="ck_validation_reports_coverage_range",
        ),
        sa.CheckConstraint(
            "blocking_error_count >= 0 AND warning_count >= 0",
            name="ck_validation_reports_findings_nonnegative",
        ),
    )

    op.create_table(
        "operation_exclusions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_key", sa.String(length=160), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_user_requested", sa.Boolean(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["build_id"],
            ["builds.id"],
            name="fk_operation_exclusions_build_id_builds",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_operation_exclusions_created_by_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_operation_exclusions_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_operation_exclusions"),
        sa.UniqueConstraint(
            "project_id",
            "operation_key",
            name="uq_operation_exclusions_project_operation",
        ),
        sa.CheckConstraint(
            "char_length(btrim(reason)) > 0",
            name="ck_operation_exclusions_reason_nonempty",
        ),
    )
    op.create_index(
        "ix_operation_exclusions_project_id",
        "operation_exclusions",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_operation_exclusions_project_id", table_name="operation_exclusions")
    op.drop_table("operation_exclusions")
    op.drop_table("validation_reports")
    postgresql.ENUM(name="validation_status").drop(op.get_bind(), checkfirst=True)
