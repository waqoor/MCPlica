"""Add durable cross-process Build admission leases.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "builds",
        sa.Column("admission_token", postgresql.UUID(as_uuid=True), nullable=True),
    )
    for name in (
        "admission_acquired_at",
        "admission_enqueued_at",
        "admission_heartbeat_at",
        "admission_lease_expires_at",
        "admission_released_at",
    ):
        op.add_column(
            "builds",
            sa.Column(name, sa.DateTime(timezone=True), nullable=True),
        )
    op.add_column(
        "builds",
        sa.Column(
            "admission_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_builds_admission_lease_token",
        "builds",
        "(admission_token IS NULL) = (admission_lease_expires_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_builds_admission_acquired",
        "builds",
        "admission_token IS NULL OR admission_acquired_at IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_builds_admission_attempt_count",
        "builds",
        "admission_attempt_count >= 0",
    )
    op.create_index(
        "ix_builds_admission_active",
        "builds",
        ["admission_lease_expires_at"],
        postgresql_where=sa.text("admission_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_builds_admission_active", table_name="builds")
    op.drop_constraint("ck_builds_admission_attempt_count", "builds", type_="check")
    op.drop_constraint("ck_builds_admission_acquired", "builds", type_="check")
    op.drop_constraint("ck_builds_admission_lease_token", "builds", type_="check")
    op.drop_column("builds", "admission_attempt_count")
    op.drop_column("builds", "admission_released_at")
    op.drop_column("builds", "admission_lease_expires_at")
    op.drop_column("builds", "admission_heartbeat_at")
    op.drop_column("builds", "admission_enqueued_at")
    op.drop_column("builds", "admission_acquired_at")
    op.drop_column("builds", "admission_token")
