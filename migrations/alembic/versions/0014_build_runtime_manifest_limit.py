"""Freeze the generic-runtime manifest limit into every build.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-27
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_HISTORICAL_RUNTIME_MANIFEST_LIMIT = 10_000_000


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE builds
        SET build_config_json = jsonb_set(
            build_config_json,
            '{{runtime_manifest_max_bytes}}',
            to_jsonb({_HISTORICAL_RUNTIME_MANIFEST_LIMIT}),
            true
        )
        WHERE NOT (build_config_json ? 'runtime_manifest_max_bytes')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE builds
        SET build_config_json = build_config_json - 'runtime_manifest_max_bytes'
        """
    )
