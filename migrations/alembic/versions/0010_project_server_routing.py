"""Persist explicit per-operation upstream server routing.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "server_mappings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_projects_server_mappings_object",
        "projects",
        "jsonb_typeof(server_mappings) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_server_mappings_object", "projects", type_="check")
    op.drop_column("projects", "server_mappings")
