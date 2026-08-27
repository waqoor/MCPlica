import hashlib
import os
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import delete, select

from app.clients.cache import RedisClient
from app.clients.database import DatabaseClient
from app.core.auth import PasswordManager, TokenManager
from app.core.exceptions import AuthenticationError
from app.domain.auth import UserRole
from app.models.audit import AuditEvent
from app.models.auth import User
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.services.auth import AuthService

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=801)
REQUEST_ID = "failed-login-postgres-1"
EMAIL = "audit-login@example.com"
PASSWORD = "correct horse battery staple"


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


class _Cache:
    async def rate_limit_exceeded(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> bool:
        return False


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(AuditEvent).where(AuditEvent.request_id == REQUEST_ID))
        await session.execute(delete(User).where(User.id == USER_ID))


async def test_failed_login_401_commits_one_sanitized_audit_event() -> None:
    database = DatabaseClient(_database_url(), pool_size=2, max_overflow=0)
    passwords = PasswordManager()
    try:
        await _cleanup(database)
        async with database.session_scope() as session:
            session.add(
                User(
                    id=USER_ID,
                    email=EMAIL,
                    display_name="Audit login",
                    password_hash=passwords.hash(PASSWORD),
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )

        service = AuthService(
            database,
            cast(RedisClient, _Cache()),
            UserRepository(),
            AuthSessionRepository(),
            AuditRepository(),
            passwords,
            TokenManager(
                signing_key="s" * 32,
                refresh_pepper="p" * 32,
                access_ttl_seconds=900,
            ),
            refresh_ttl_seconds=86_400,
            rate_limit_attempts=5,
            rate_limit_window_seconds=60,
        )

        with pytest.raises(AuthenticationError) as denied:
            await service.login(
                email=EMAIL,
                password="definitely-not-the-password",
                user_agent="MCPlica audit regression",
                remote_ip="203.0.113.27",
                request_id=REQUEST_ID,
            )
        assert denied.value.status_code == 401

        async with database.session_scope() as session:
            events = list(
                await session.scalars(select(AuditEvent).where(AuditEvent.request_id == REQUEST_ID))
            )
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "auth.login_failed"
        assert event.actor_user_id == USER_ID
        assert event.metadata_json == {
            "reason": "invalid_credentials",
            "email_sha256": hashlib.sha256(EMAIL.encode()).hexdigest(),
            "ip_prefix": "203.0.113.0/24",
            "user_agent_sha256": hashlib.sha256(b"MCPlica audit regression").hexdigest(),
        }
        serialized = str(event.metadata_json)
        assert PASSWORD not in serialized
        assert "definitely-not-the-password" not in serialized
        assert EMAIL not in serialized
    finally:
        await _cleanup(database)
        await database.close()
