import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import delete, select

from app.clients.database import DatabaseClient
from app.core.auth import PasswordManager
from app.core.exceptions import InvalidStateError
from app.domain.auth import UserRole
from app.models.audit import AuditEvent
from app.models.auth import AuthSession, User
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.services.users import UserService

pytestmark = pytest.mark.postgres_integration

ADMIN_ONE = UUID(int=820_001)
ADMIN_TWO = UUID(int=820_002)
SESSION_ONE = UUID(int=820_101)
SESSION_TWO = UUID(int=820_102)
USER_IDS = (ADMIN_ONE, ADMIN_TWO)


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id.in_(USER_IDS)))
        await session.execute(delete(User).where(User.id.in_(USER_IDS)))


async def _seed(database: DatabaseClient) -> None:
    now = datetime.now(UTC)
    async with database.session_scope() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"admin-{index}-user-mutation@example.com",
                    display_name=f"Administrator {index}",
                    password_hash="not-used",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
                for index, user_id in enumerate(USER_IDS, start=1)
            ]
        )
        await session.flush()
        session.add_all(
            [
                AuthSession(
                    id=session_id,
                    user_id=user_id,
                    refresh_token_hash=f"{index:064x}",
                    expires_at=now + timedelta(days=1),
                    last_used_at=now,
                    user_agent_hash=None,
                    ip_prefix=None,
                )
                for index, (session_id, user_id) in enumerate(
                    ((SESSION_ONE, ADMIN_ONE), (SESSION_TWO, ADMIN_TWO)),
                    start=1_000,
                )
            ]
        )


def _service(database: DatabaseClient) -> UserService:
    return UserService(
        database,
        UserRepository(),
        AuthSessionRepository(),
        AuditRepository(),
        PasswordManager(),
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_concurrent_admin_demotions_leave_one_admin_and_rollback_loser() -> None:
    database = DatabaseClient(_database_url())
    try:
        await _cleanup(database)
        await _seed(database)
        service = _service(database)

        results = await asyncio.gather(
            service.update(
                ADMIN_ONE,
                display_name=None,
                password=None,
                role=UserRole.BUILDER,
                is_active=None,
                actor_user_id=ADMIN_ONE,
                request_id="request-demote-one",
            ),
            service.update(
                ADMIN_TWO,
                display_name=None,
                password=None,
                role=UserRole.BUILDER,
                is_active=None,
                actor_user_id=ADMIN_ONE,
                request_id="request-demote-two",
            ),
            return_exceptions=True,
        )

        assert sum(isinstance(result, InvalidStateError) for result in results) == 1, results
        assert sum(not isinstance(result, BaseException) for result in results) == 1
        async with database.session_scope() as session:
            roles = {
                user_id: role
                for user_id, role in (
                    await session.execute(select(User.id, User.role).where(User.id.in_(USER_IDS)))
                ).tuples()
            }
            session_states = {
                user_id: revoked_at
                for user_id, revoked_at in (
                    await session.execute(
                        select(AuthSession.user_id, AuthSession.revoked_at).where(
                            AuthSession.user_id.in_(USER_IDS)
                        )
                    )
                ).tuples()
            }

        assert list(roles.values()).count(UserRole.ADMIN) == 1
        assert list(roles.values()).count(UserRole.BUILDER) == 1
        successful_user = next(
            user_id for user_id, role in roles.items() if role is UserRole.BUILDER
        )
        rejected_user = next(user_id for user_id, role in roles.items() if role is UserRole.ADMIN)
        assert session_states[successful_user] is not None
        assert session_states[rejected_user] is None
    finally:
        await _cleanup(database)
        await database.close()
