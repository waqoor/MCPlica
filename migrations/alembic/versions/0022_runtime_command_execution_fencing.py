"""Fence runtime command execution ownership.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runtime_lifecycle_commands",
        sa.Column("execution_token", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # An in-flight pre-fencing command has no identity that can be trusted. Requeue it
    # instead of fabricating ownership; the durable dispatcher will issue a fresh token.
    op.execute(
        sa.text(
            """
            UPDATE runtime_lifecycle_commands
            SET status = 'pending'::runtime_command_status,
                lease_expires_at = NULL,
                next_attempt_at = clock_timestamp(),
                failed_at = NULL,
                retryable = TRUE
            WHERE status IN (
                'dispatched'::runtime_command_status,
                'running'::runtime_command_status
            )
            """
        )
    )
    op.create_check_constraint(
        "ck_runtime_lifecycle_commands_execution_owner_shape",
        "runtime_lifecycle_commands",
        "(status IN ('dispatched'::runtime_command_status, "
        "'running'::runtime_command_status) AND execution_token IS NOT NULL "
        "AND lease_expires_at IS NOT NULL) OR "
        "(status IN ('pending'::runtime_command_status, "
        "'failed'::runtime_command_status, 'effective'::runtime_command_status) "
        "AND execution_token IS NULL AND lease_expires_at IS NULL)",
    )


def downgrade() -> None:
    # Do not let a token-bearing process survive a downgrade into the unfenced
    # execution contract. Requeue all live attempts for an old-version worker.
    op.execute(
        sa.text(
            """
            UPDATE runtime_lifecycle_commands
            SET status = 'pending'::runtime_command_status,
                execution_token = NULL,
                lease_expires_at = NULL,
                next_attempt_at = clock_timestamp(),
                failed_at = NULL,
                retryable = TRUE
            WHERE status IN (
                'dispatched'::runtime_command_status,
                'running'::runtime_command_status
            )
            """
        )
    )
    op.drop_constraint(
        "ck_runtime_lifecycle_commands_execution_owner_shape",
        "runtime_lifecycle_commands",
        type_="check",
    )
    op.drop_column("runtime_lifecycle_commands", "execution_token")
