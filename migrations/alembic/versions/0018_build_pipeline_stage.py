"""Persist the authoritative Build stage across terminal failure/cancellation.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "builds",
        sa.Column(
            "pipeline_stage",
            postgresql.ENUM(name="build_status", create_type=False),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE builds
        SET pipeline_stage = status
        WHERE status NOT IN ('FAILED'::build_status, 'CANCELLED'::build_status)
        """
    )
    op.create_check_constraint(
        "ck_builds_pipeline_stage",
        "builds",
        "pipeline_stage IS NULL OR pipeline_stage NOT IN "
        "('FAILED'::build_status, 'CANCELLED'::build_status)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_builds_pipeline_stage", "builds", type_="check")
    op.drop_column("builds", "pipeline_stage")
