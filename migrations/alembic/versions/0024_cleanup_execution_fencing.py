"""Fence cleanup execution and normalize pre-fencing leases.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cleanup_targets",
        sa.Column("execution_token", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE cleanup_targets
            SET status = 'retrying'::cleanup_target_status,
                execution_token = NULL,
                lease_expires_at = NULL,
                next_attempt_at = clock_timestamp()
            WHERE status = 'running'::cleanup_target_status
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE cleanup_targets
            SET execution_token = NULL,
                lease_expires_at = NULL
            WHERE status <> 'running'::cleanup_target_status
            """
        )
    )
    op.create_check_constraint(
        "ck_cleanup_targets_execution_owner_shape",
        "cleanup_targets",
        "(status = 'running'::cleanup_target_status AND execution_token IS NOT NULL "
        "AND lease_expires_at IS NOT NULL) OR "
        "(status <> 'running'::cleanup_target_status AND execution_token IS NULL "
        "AND lease_expires_at IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_cleanup_targets_execution_owner_shape",
        "cleanup_targets",
        type_="check",
    )
    op.drop_column("cleanup_targets", "execution_token")
