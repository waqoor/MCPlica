import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete

from app.clients.database import DatabaseClient
from app.core.exceptions import ValidationError
from app.domain.auth import UserRole
from app.models.audit import AuditEvent
from app.models.auth import User
from app.repositories.audit import AuditRepository
from app.services.audit import AuditService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=11_001)
PROJECT_ID = UUID(int=11_002)


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(AuditEvent).where(AuditEvent.project_id == PROJECT_ID))
        await session.execute(delete(User).where(User.id == USER_ID))


async def test_audit_filters_use_actor_and_exclusive_offset_aware_upper_bound() -> None:
    database = DatabaseClient(_database_url(), pool_size=3, max_overflow=0)
    service = AuditService(database, AuditRepository())
    try:
        await _cleanup(database)
        async with database.session_scope() as session:
            session.add(
                User(
                    id=USER_ID,
                    email="audit-filter@example.com",
                    display_name="Audit Filter",
                    password_hash="unused",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )
            await session.flush()
            session.add_all(
                AuditEvent(
                    actor_user_id=USER_ID,
                    event_type="test.audit_filter",
                    entity_type="test",
                    entity_id=None,
                    project_id=PROJECT_ID,
                    request_id=f"audit-filter-{index}",
                    metadata_json={},
                    created_at=created_at,
                )
                for index, created_at in enumerate(
                    (
                        datetime(2026, 8, 1, 0, 0, tzinfo=UTC),
                        datetime(2026, 8, 1, 23, 59, 59, tzinfo=UTC),
                        datetime(2026, 8, 2, 0, 0, tzinfo=UTC),
                    )
                )
            )

        items, total = await service.list(
            actor="audit-filter@example.com",
            project_id=PROJECT_ID,
            created_from=datetime(2026, 8, 1, 0, 0, tzinfo=UTC),
            created_to=datetime(2026, 8, 2, 0, 0, tzinfo=UTC),
        )
        assert total == len(items) == 2
        assert {item.request_id for item in items} == {
            "audit-filter-0",
            "audit-filter-1",
        }

        empty, empty_total = await service.list(
            project_id=PROJECT_ID,
            created_from=datetime(2026, 8, 2, 0, 0, tzinfo=UTC),
            created_to=datetime(2026, 8, 2, 0, 0, tzinfo=UTC),
        )
        assert empty == []
        assert empty_total == 0
        with pytest.raises(ValidationError, match="UTC offset"):
            await service.list(created_from=datetime(2026, 8, 1))
    finally:
        await _cleanup(database)
        await database.close()
