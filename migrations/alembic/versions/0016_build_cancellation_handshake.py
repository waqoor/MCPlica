"""Add durable cooperative Build cancellation handshake.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "builds",
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "builds",
        sa.Column(
            "cancellation_requested_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "builds",
        sa.Column(
            "cancellation_acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_builds_cancellation_requested_by_users",
        "builds",
        "users",
        ["cancellation_requested_by"],
        ["id"],
        ondelete="SET NULL",
    )
    # Preserve validity and history for Builds cancelled by the pre-handshake API.
    op.execute(
        """
        UPDATE builds
        SET cancellation_requested_at = completed_at,
            cancellation_requested_by = requested_by,
            cancellation_acknowledged_at = completed_at
        WHERE status = 'CANCELLED'::build_status
        """
    )
    op.create_check_constraint(
        "ck_builds_cancellation_acknowledgement",
        "builds",
        "cancellation_acknowledged_at IS NULL OR "
        "(cancellation_requested_at IS NOT NULL AND status = 'CANCELLED'::build_status)",
    )
    op.create_check_constraint(
        "ck_builds_cancelled_acknowledged",
        "builds",
        "status <> 'CANCELLED'::build_status OR cancellation_acknowledged_at IS NOT NULL",
    )
    op.create_index(
        "ix_builds_cancellation_requested",
        "builds",
        ["cancellation_requested_at"],
        postgresql_where=sa.text(
            "cancellation_requested_at IS NOT NULL AND cancellation_acknowledged_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_builds_cancellation_requested", table_name="builds")
    op.drop_constraint("ck_builds_cancelled_acknowledged", "builds", type_="check")
    op.drop_constraint("ck_builds_cancellation_acknowledgement", "builds", type_="check")
    op.drop_constraint("fk_builds_cancellation_requested_by_users", "builds", type_="foreignkey")
    op.drop_column("builds", "cancellation_acknowledged_at")
    op.drop_column("builds", "cancellation_requested_by")
    op.drop_column("builds", "cancellation_requested_at")
