"""Persist current source selection and immutable build source bindings.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_source_versions_source_id_id",
        "source_versions",
        ["source_id", "id"],
    )
    op.add_column(
        "project_sources",
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "project_sources",
        sa.Column("current_version_selected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_sources",
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_sources",
        sa.Column("last_observed_etag", sa.Text(), nullable=True),
    )
    op.add_column(
        "project_sources",
        sa.Column("last_observed_last_modified", sa.Text(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            WITH selected AS (
                SELECT DISTINCT ON (source_id)
                    source_id,
                    id AS version_id,
                    created_at,
                    source_etag,
                    source_last_modified
                FROM source_versions
                ORDER BY source_id, created_at DESC, id DESC
            )
            UPDATE project_sources AS source
            SET current_version_id = selected.version_id,
                current_version_selected_at = selected.created_at,
                last_observed_at = selected.created_at,
                last_observed_etag = selected.source_etag,
                last_observed_last_modified = selected.source_last_modified
            FROM selected
            WHERE source.id = selected.source_id
            """
        )
    )
    op.create_foreign_key(
        "fk_project_sources_current_version_same_source",
        "project_sources",
        "source_versions",
        ["id", "current_version_id"],
        ["source_id", "id"],
        deferrable=True,
        initially="DEFERRED",
        use_alter=True,
    )
    op.create_index(
        "ix_project_sources_current_version_id",
        "project_sources",
        ["current_version_id"],
    )
    op.create_check_constraint(
        "ck_project_sources_current_selection_shape",
        "project_sources",
        "(current_version_id IS NULL AND current_version_selected_at IS NULL "
        "AND last_observed_at IS NULL AND last_observed_etag IS NULL "
        "AND last_observed_last_modified IS NULL) OR "
        "(current_version_id IS NOT NULL AND current_version_selected_at IS NOT NULL "
        "AND last_observed_at IS NOT NULL)",
    )

    op.add_column(
        "build_source_versions",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "build_source_versions",
        sa.Column(
            "source_kind",
            postgresql.ENUM(name="source_kind", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "build_source_versions",
        sa.Column("source_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "build_source_versions",
        sa.Column(
            "source_origin_type",
            postgresql.ENUM(name="source_origin", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("build_source_versions", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column(
        "build_source_versions",
        sa.Column("source_is_primary", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "build_source_versions",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "build_source_versions",
        sa.Column(
            "dependency_aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "build_source_versions",
        sa.Column(
            "binding_metadata_trustworthy",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE build_source_versions AS binding
            SET source_id = source.id,
                source_kind = source.kind,
                source_name = source.name,
                source_origin_type = source.origin_type,
                source_url = source.source_url,
                source_is_primary = source.is_primary,
                source_created_at = source.created_at,
                dependency_aliases = CASE
                    WHEN source.source_url IS NULL THEN jsonb_build_array(source.name)
                    ELSE jsonb_build_array(source.name, source.source_url)
                END
            FROM source_versions AS version
            JOIN project_sources AS source ON source.id = version.source_id
            WHERE binding.source_version_id = version.id
            """
        )
    )
    for column in (
        "source_id",
        "source_kind",
        "source_name",
        "source_origin_type",
        "source_is_primary",
        "source_created_at",
        "dependency_aliases",
    ):
        op.alter_column("build_source_versions", column, nullable=False)
    op.create_foreign_key(
        "fk_build_source_versions_source_id_project_sources",
        "build_source_versions",
        "project_sources",
        ["source_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_build_source_versions_version_same_source",
        "build_source_versions",
        "source_versions",
        ["source_id", "source_version_id"],
        ["source_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_build_source_versions_name_nonempty",
        "build_source_versions",
        "char_length(btrim(source_name)) > 0",
    )
    op.create_check_constraint(
        "ck_build_source_versions_aliases_array",
        "build_source_versions",
        "jsonb_typeof(dependency_aliases) = 'array' AND jsonb_array_length(dependency_aliases) > 0",
    )
    op.create_index(
        "ix_build_source_versions_source_id",
        "build_source_versions",
        ["source_id"],
    )
    op.create_index(
        "uq_build_source_versions_primary_executable",
        "build_source_versions",
        ["build_id"],
        unique=True,
        postgresql_where=sa.text(
            "binding_metadata_trustworthy AND source_is_primary "
            "AND source_kind IN ('openapi'::source_kind, 'api_inventory'::source_kind)"
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    changed_selection = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM project_sources AS source
                JOIN source_versions AS current ON current.id = source.current_version_id
                JOIN LATERAL (
                    SELECT version.id, version.created_at, version.source_etag,
                           version.source_last_modified
                    FROM source_versions AS version
                    WHERE version.source_id = source.id
                    ORDER BY version.created_at DESC, version.id DESC
                    LIMIT 1
                ) AS latest ON TRUE
                WHERE current.id <> latest.id
                   OR source.current_version_selected_at <> latest.created_at
                   OR source.last_observed_at <> latest.created_at
                   OR source.last_observed_etag IS DISTINCT FROM latest.source_etag
                   OR source.last_observed_last_modified
                      IS DISTINCT FROM latest.source_last_modified
            )
            """
        )
    ).scalar_one()
    if changed_selection:
        raise RuntimeError(
            "Downgrade would discard accepted source-selection history; restore the "
            "pre-0021 selection state or retain revision 0021."
        )

    op.drop_index(
        "uq_build_source_versions_primary_executable",
        table_name="build_source_versions",
    )
    op.drop_index("ix_build_source_versions_source_id", table_name="build_source_versions")
    op.drop_constraint(
        "ck_build_source_versions_aliases_array",
        "build_source_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_build_source_versions_name_nonempty",
        "build_source_versions",
        type_="check",
    )
    op.drop_constraint(
        "fk_build_source_versions_version_same_source",
        "build_source_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_build_source_versions_source_id_project_sources",
        "build_source_versions",
        type_="foreignkey",
    )
    for column in (
        "binding_metadata_trustworthy",
        "dependency_aliases",
        "source_created_at",
        "source_is_primary",
        "source_url",
        "source_origin_type",
        "source_name",
        "source_kind",
        "source_id",
    ):
        op.drop_column("build_source_versions", column)

    op.drop_constraint(
        "ck_project_sources_current_selection_shape",
        "project_sources",
        type_="check",
    )
    op.drop_index("ix_project_sources_current_version_id", table_name="project_sources")
    op.drop_constraint(
        "fk_project_sources_current_version_same_source",
        "project_sources",
        type_="foreignkey",
    )
    for column in (
        "last_observed_last_modified",
        "last_observed_etag",
        "last_observed_at",
        "current_version_selected_at",
        "current_version_id",
    ):
        op.drop_column("project_sources", column)
    op.drop_constraint(
        "uq_source_versions_source_id_id",
        "source_versions",
        type_="unique",
    )
