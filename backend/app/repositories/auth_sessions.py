from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth import AuthSessionRecord
from app.models.auth import AuthSession


def _to_domain(model: AuthSession) -> AuthSessionRecord:
    return AuthSessionRecord(
        id=model.id,
        user_id=model.user_id,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
    )


class AuthSessionRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent_hash: str | None,
        ip_prefix: str | None,
        now: datetime,
    ) -> AuthSessionRecord:
        model = AuthSession(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            last_used_at=now,
            user_agent_hash=user_agent_hash,
            ip_prefix=ip_prefix,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def get(self, session: AsyncSession, session_id: UUID) -> AuthSessionRecord | None:
        model = await session.get(AuthSession, session_id)
        return _to_domain(model) if model else None

    async def get_by_refresh_hash(
        self, session: AsyncSession, refresh_hash: str
    ) -> AuthSessionRecord | None:
        model = await session.scalar(
            select(AuthSession).where(AuthSession.refresh_token_hash == refresh_hash)
        )
        return _to_domain(model) if model else None

    async def rotate_refresh_token(
        self,
        session: AsyncSession,
        session_id: UUID,
        *,
        old_hash: str,
        new_hash: str,
        now: datetime,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(AuthSession)
                .where(
                    AuthSession.id == session_id,
                    AuthSession.refresh_token_hash == old_hash,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > now,
                )
                .values(refresh_token_hash=new_hash, last_used_at=now)
            ),
        )
        return bool(result.rowcount)

    async def revoke(self, session: AsyncSession, session_id: UUID, now: datetime) -> None:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def revoke_for_user(self, session: AsyncSession, user_id: UUID, now: datetime) -> None:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def delete_expired(self, session: AsyncSession, now: datetime | None = None) -> int:
        cutoff = now or datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            await session.execute(delete(AuthSession).where(AuthSession.expires_at < cutoff)),
        )
        return int(result.rowcount or 0)
