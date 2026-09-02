"""Persist deployment lifecycle intent.

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    intent = postgresql.ENUM(
        "normal",
        "security_refresh",
        "rollback",
        name="deployment_intent",
    )
    intent.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "deployments",
        sa.Column(
            "intent",
            postgresql.ENUM(name="deployment_intent", create_type=False),
            nullable=False,
            server_default="normal",
        ),
    )
    op.alter_column("deployments", "intent", server_default=None)


def downgrade() -> None:
    op.drop_column("deployments", "intent")
    postgresql.ENUM(name="deployment_intent").drop(op.get_bind(), checkfirst=True)
