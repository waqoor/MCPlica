"""Fence vector rows to the accepted build execution owner.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_index_generations",
        sa.Column("execution_token", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_index_generations", "execution_token")
