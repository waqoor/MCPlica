import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

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
