import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.engine import make_url
from sqlalchemy.sql.elements import conv

pytestmark = pytest.mark.postgres_integration


def _run_alembic(
    *,
    root: Path,
    environment: dict[str, str],
    arguments: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "migrations/alembic.ini",
            *arguments,
        ],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_blank_database_upgrades_to_head_with_clean_orm_metadata() -> None:
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    source_url = make_url(raw_url)
    database_name = f"mcplica_schema_{uuid4().hex[:12]}"
    assert database_name.startswith("mcplica_schema_")
    admin_url = source_url.set(drivername="postgresql", database="postgres")
    migration_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    root = Path(__file__).resolve().parents[3]
    environment = {**os.environ, "DATABASE_URL": migration_url}

    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        upgrade = _run_alembic(
            root=root,
            environment=environment,
            arguments=["upgrade", "head"],
        )
        assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr
        check = _run_alembic(
            root=root,
            environment=environment,
            arguments=["check"],
        )
        assert check.returncode == 0, check.stdout + check.stderr
        assert "No new upgrade operations detected" in check.stdout + check.stderr
        assert "unresolvable cycles" not in check.stdout + check.stderr
    finally:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def test_legacy_0008_check_constraint_name_upgrades_to_head() -> None:
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    source_url = make_url(raw_url)
    database_name = f"mcplica_legacy_{uuid4().hex[:12]}"
    assert database_name.startswith("mcplica_legacy_")
    admin_url = source_url.set(drivername="postgresql", database="postgres")
    migration_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    direct_url = source_url.set(drivername="postgresql", database=database_name).render_as_string(
        hide_password=False
    )
    root = Path(__file__).resolve().parents[3]
    environment = {**os.environ, "DATABASE_URL": migration_url}

    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        upgrade_0008 = _run_alembic(
            root=root,
            environment=environment,
            arguments=["upgrade", "0008"],
        )
        assert upgrade_0008.returncode == 0, upgrade_0008.stdout + upgrade_0008.stderr

        legacy_names: list[tuple[str, str, str]] = []
        preparer = postgresql_dialect().identifier_preparer
        with psycopg.connect(direct_url) as connection:
            constraints = connection.execute(
                "SELECT relation.relname, constraint_record.conname "
                "FROM pg_constraint AS constraint_record "
                "JOIN pg_class AS relation ON relation.oid = constraint_record.conrelid "
                "JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
                "WHERE namespace.nspname = 'public' AND constraint_record.contype = 'c' "
                "ORDER BY relation.relname, constraint_record.conname"
            ).fetchall()
            for table_name, canonical_name in constraints:
                legacy_name = preparer.truncate_and_render_constraint_name(
                    conv(f"ck_{table_name}_{canonical_name}"),
                    _alembic_quote=False,
                )
                connection.execute(
                    sql.SQL("ALTER TABLE {} RENAME CONSTRAINT {} TO {}").format(
                        sql.Identifier(table_name),
                        sql.Identifier(canonical_name),
                        sql.Identifier(legacy_name),
                    )
                )
                legacy_names.append((table_name, canonical_name, legacy_name))

        upgrade_head = _run_alembic(
            root=root,
            environment=environment,
            arguments=["upgrade", "head"],
        )
        assert upgrade_head.returncode == 0, upgrade_head.stdout + upgrade_head.stderr

        check = _run_alembic(
            root=root,
            environment=environment,
            arguments=["check"],
        )
        assert check.returncode == 0, check.stdout + check.stderr

        with psycopg.connect(direct_url) as connection:
            head_names = set(
                connection.execute(
                    "SELECT relation.relname, constraint_record.conname "
                    "FROM pg_constraint AS constraint_record "
                    "JOIN pg_class AS relation ON relation.oid = constraint_record.conrelid "
                    "JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
                    "WHERE namespace.nspname = 'public' AND constraint_record.contype = 'c'"
                ).fetchall()
            )
        for table_name, canonical_name, legacy_name in legacy_names:
            assert (table_name, canonical_name) in head_names
            assert (table_name, legacy_name) not in head_names
    finally:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def test_foundation_migrations_round_trip_without_new_runtime_state() -> None:
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    source_url = make_url(raw_url)
    database_name = f"mcplica_roundtrip_{uuid4().hex[:12]}"
    assert database_name.startswith("mcplica_roundtrip_")
    admin_url = source_url.set(drivername="postgresql", database="postgres")
    migration_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    root = Path(__file__).resolve().parents[3]
    environment = {**os.environ, "DATABASE_URL": migration_url}

    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        for arguments in (["upgrade", "head"], ["downgrade", "0020"], ["upgrade", "head"]):
            result = _run_alembic(
                root=root,
                environment=environment,
                arguments=arguments,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        check = _run_alembic(
            root=root,
            environment=environment,
            arguments=["check"],
        )
        assert check.returncode == 0, check.stdout + check.stderr
    finally:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def test_0021_downgrade_refuses_to_discard_restored_source_selection() -> None:
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    source_url = make_url(raw_url)
    database_name = f"mcplica_selection_{uuid4().hex[:12]}"
    assert database_name.startswith("mcplica_selection_")
    admin_url = source_url.set(drivername="postgresql", database="postgres")
    migration_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    direct_url = source_url.set(drivername="postgresql", database=database_name).render_as_string(
        hide_password=False
    )
    root = Path(__file__).resolve().parents[3]
    environment = {**os.environ, "DATABASE_URL": migration_url}
    user_id = UUID(int=91_001)
    project_id = UUID(int=91_002)
    source_id = UUID(int=91_003)
    version_a = UUID(int=91_004)
    version_b = UUID(int=91_005)

    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        upgrade_0020 = _run_alembic(
            root=root,
            environment=environment,
            arguments=["upgrade", "0020"],
        )
        assert upgrade_0020.returncode == 0, upgrade_0020.stdout + upgrade_0020.stderr
        with psycopg.connect(direct_url) as connection:
            connection.execute(
                "INSERT INTO users (id, email, display_name, password_hash, role) "
                "VALUES (%s, %s, %s, %s, 'admin')",
                (user_id, "migration@example.com", "Migration", "not-a-live-password-hash"),
            )
            connection.execute(
                "INSERT INTO projects (id, name, slug, mcp_hostname, created_by) "
                "VALUES (%s, %s, %s, %s, %s)",
                (project_id, "Migration", "migration", "migration.mcp.local", user_id),
            )
            connection.execute(
                "INSERT INTO project_sources "
                "(id, project_id, kind, name, origin_type, source_url, is_primary) "
                "VALUES (%s, %s, 'openapi', %s, 'upload', NULL, TRUE)",
                (source_id, project_id, "Restorable API"),
            )
            connection.execute(
                "INSERT INTO source_versions "
                "(id, source_id, content_sha256, media_type, storage_key, byte_size, "
                "detected_format, created_by, created_at) VALUES "
                "(%s, %s, %s, 'application/json', %s, 1, 'json', %s, "
                "clock_timestamp() - interval '2 minutes'), "
                "(%s, %s, %s, 'application/json', %s, 1, 'json', %s, "
                "clock_timestamp() - interval '1 minute')",
                (
                    version_a,
                    source_id,
                    "a" * 64,
                    "migration/a.json",
                    user_id,
                    version_b,
                    source_id,
                    "b" * 64,
                    "migration/b.json",
                    user_id,
                ),
            )

        upgrade_0021 = _run_alembic(
            root=root,
            environment=environment,
            arguments=["upgrade", "0021"],
        )
        assert upgrade_0021.returncode == 0, upgrade_0021.stdout + upgrade_0021.stderr
        with psycopg.connect(direct_url) as connection:
            connection.execute(
                "UPDATE project_sources SET current_version_id = %s, "
                "current_version_selected_at = clock_timestamp(), "
                "last_observed_at = clock_timestamp(), last_observed_etag = %s "
                "WHERE id = %s",
                (version_a, '"restored-a"', source_id),
            )

        downgrade = _run_alembic(
            root=root,
            environment=environment,
            arguments=["downgrade", "0020"],
        )
        output = downgrade.stdout + downgrade.stderr
        assert downgrade.returncode != 0
        assert "Downgrade would discard accepted source-selection history" in output
    finally:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )
