import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import delete, event

from app.clients.database import DatabaseClient
from app.domain.auth import UserRole
from app.domain.sources import SourceKind, SourceOrigin
from app.models.auth import User
from app.models.project import Project
from app.models.source import ProjectSource, SourceVersion
from app.repositories.sources import SourceRepository

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=810_001)
PROJECT_ID = UUID(int=810_002)


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(ProjectSource).where(ProjectSource.project_id == PROJECT_ID))
        await session.execute(delete(Project).where(Project.id == PROJECT_ID))
        await session.execute(delete(User).where(User.id == USER_ID))


async def _seed(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="source-summary-scale@example.test",
                display_name="Source summary scale",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                name="Source summary scale",
                slug="source-summary-scale",
                description=None,
                default_base_url="https://api.example.test",
                active_server_ref=None,
                server_mappings={},
                mcp_hostname="source-summary-scale.mcp.example.test",
                is_enabled=True,
                active_build_id=None,
                active_deployment_id=None,
                created_by=USER_ID,
            )
        )
        await session.flush()
        sources = [
            ProjectSource(
                id=UUID(int=811_000 + index),
                project_id=PROJECT_ID,
                kind=SourceKind.DOCUMENTATION,
                name=f"Document {index:03d}",
                origin_type=SourceOrigin.UPLOAD,
                source_url=None,
                is_primary=False,
            )
            for index in range(100)
        ]
        session.add_all(sources)
        await session.flush()
        # One source intentionally has no version. It must be reported as missing
        # without hiding the other 99 healthy summary rows.
        versions = [
            SourceVersion(
                id=UUID(int=812_000 + index),
                source_id=source.id,
                content_sha256=f"{index + 1:064x}",
                media_type="text/plain",
                storage_key=f"test/source-summary/{index}",
                byte_size=index + 1,
                detected_format="text",
                source_etag=f'"etag-{index}"',
                source_last_modified=None,
                created_by=USER_ID,
            )
            for index, source in enumerate(sources[1:])
        ]
        session.add_all(versions)
        await session.flush()
        observed_at = datetime.now(UTC)
        for source, version in zip(sources[1:], versions, strict=True):
            source.current_version_id = version.id
            source.current_version_selected_at = observed_at
            source.last_observed_at = observed_at
            source.last_observed_etag = version.source_etag


@pytest.mark.asyncio(loop_scope="function")
async def test_source_summary_page_stays_query_bounded_at_one_hundred_sources() -> None:
    database = DatabaseClient(_database_url())
    statements = 0

    def count_statement(*_args: object, **_kwargs: object) -> None:
        nonlocal statements
        statements += 1

    try:
        await _cleanup(database)
        await _seed(database)
        event.listen(database.engine.sync_engine, "before_cursor_execute", count_statement)
        async with database.session_scope() as session:
            items, total = await SourceRepository().list_source_summaries(
                session,
                PROJECT_ID,
                limit=100,
                offset=0,
            )
        event.remove(database.engine.sync_engine, "before_cursor_execute", count_statement)

        assert total == 100
        assert len(items) == 100
        assert items[0].health == "missing"
        assert all(item.health == "pending" for item in items[1:])
        assert sum(item.version_count for item in items) == 99
        assert statements <= 6
    finally:
        if event.contains(database.engine.sync_engine, "before_cursor_execute", count_statement):
            event.remove(database.engine.sync_engine, "before_cursor_execute", count_statement)
        await _cleanup(database)
        await database.close()


@pytest.mark.asyncio(loop_scope="function")
async def test_include_superseded_page_never_splits_a_supersession_group() -> None:
    database = DatabaseClient(_database_url())
    try:
        await _cleanup(database)
        async with database.session_scope() as session:
            session.add(
                User(
                    id=USER_ID,
                    email="source-summary-scale@example.test",
                    display_name="Source summary scale",
                    password_hash="not-used",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )
            await session.flush()
            session.add(
                Project(
                    id=PROJECT_ID,
                    name="Source summary scale",
                    slug="source-summary-scale",
                    description=None,
                    default_base_url="https://api.example.test",
                    active_server_ref=None,
                    server_mappings={},
                    mcp_hostname="source-summary-scale.mcp.example.test",
                    is_enabled=True,
                    active_build_id=None,
                    active_deployment_id=None,
                    created_by=USER_ID,
                )
            )
            await session.flush()
            base = datetime.now(UTC)
            alpha_old_id = UUID(int=820_001)
            alpha_new_id = UUID(int=820_002)
            beta_id = UUID(int=820_003)
            session.add_all(
                [
                    ProjectSource(
                        id=alpha_old_id,
                        project_id=PROJECT_ID,
                        kind=SourceKind.DOCUMENTATION,
                        name="alpha",
                        origin_type=SourceOrigin.UPLOAD,
                        source_url=None,
                        is_primary=False,
                        created_at=base,
                    ),
                    ProjectSource(
                        id=alpha_new_id,
                        project_id=PROJECT_ID,
                        kind=SourceKind.DOCUMENTATION,
                        name="alpha",
                        origin_type=SourceOrigin.UPLOAD,
                        source_url=None,
                        is_primary=False,
                        created_at=base + timedelta(seconds=1),
                    ),
                    ProjectSource(
                        id=beta_id,
                        project_id=PROJECT_ID,
                        kind=SourceKind.DOCUMENTATION,
                        name="beta",
                        origin_type=SourceOrigin.UPLOAD,
                        source_url=None,
                        is_primary=False,
                        created_at=base + timedelta(seconds=2),
                    ),
                ]
            )

        async with database.session_scope() as session:
            items, total = await SourceRepository().list_source_summaries(
                session,
                PROJECT_ID,
                limit=1,
                offset=0,
                include_superseded=True,
            )

        # `alpha` is the first of two distinct sources (groups); a page_size of
        # 1 must still return both of its versions rather than only alpha_new.
        assert total == 2
        assert {item.source.id for item in items} == {alpha_old_id, alpha_new_id}
        by_id = {item.source.id: item for item in items}
        assert by_id[alpha_new_id].is_latest is True
        assert by_id[alpha_old_id].is_latest is False
    finally:
        await _cleanup(database)
        await database.close()
