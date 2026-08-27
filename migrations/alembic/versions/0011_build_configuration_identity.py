"""Backfill immutable executable configuration identity on builds.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-27
"""

import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _fingerprint(
    *,
    source_version_ids: list[str],
    default_base_url: str | None,
    active_server_ref: str | None,
    server_mappings: dict[str, str],
) -> str:
    value = json.dumps(
        {
            "source_version_ids": sorted(source_version_ids),
            "default_base_url": default_base_url,
            "active_server_ref": active_server_ref,
            "server_mappings": dict(sorted(server_mappings.items())),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT
                builds.id,
                builds.build_config_json,
                COALESCE(
                    array_agg(build_source_versions.source_version_id::text
                              ORDER BY build_source_versions.source_version_id::text)
                    FILTER (WHERE build_source_versions.source_version_id IS NOT NULL),
                    ARRAY[]::text[]
                ) AS source_version_ids
            FROM builds
            LEFT JOIN build_source_versions
              ON build_source_versions.build_id = builds.id
            GROUP BY builds.id, builds.build_config_json
            """
        )
    ).mappings()
    for row in rows:
        config = dict(row["build_config_json"])
        config["executable_configuration_sha256"] = _fingerprint(
            source_version_ids=list(row["source_version_ids"]),
            default_base_url=config.get("default_base_url"),
            active_server_ref=config.get("active_server_ref"),
            server_mappings=dict(config.get("server_mappings") or {}),
        )
        connection.execute(
            sa.text(
                """
                UPDATE builds
                SET build_config_json = CAST(:config AS jsonb)
                WHERE id = :build_id
                """
            ),
            {"build_id": row["id"], "config": json.dumps(config)},
        )


def downgrade() -> None:
    op.execute(
        """
        UPDATE builds
        SET build_config_json = build_config_json - 'executable_configuration_sha256'
        """
    )
