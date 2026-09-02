from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth import UserAccount, UserRole
from app.models.auth import User

_ADMIN_MUTATION_LOCK_KEY = 21_753_872_405_250_881


def _to_domain(model: User) -> UserAccount:
    return UserAccount(
        id=model.id,
        email=model.email,
        display_name=model.display_name,
        password_hash=model.password_hash,
        role=model.role,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        last_login_at=model.last_login_at,
    )


class UserRepository:
    async def lock_email(self, session: AsyncSession, email: str) -> None:
        await session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(f"mcplica:user-email:{email.casefold()}", 0)
                )
            )
        )

    async def lock_admin_mutations(self, session: AsyncSession) -> None:
        await session.execute(select(func.pg_advisory_xact_lock(_ADMIN_MUTATION_LOCK_KEY)))

    async def count(self, session: AsyncSession) -> int:
        return int(await session.scalar(select(func.count()).select_from(User)) or 0)

    async def count_active_admins(self, session: AsyncSession) -> int:
        statement = (
            select(func.count())
            .select_from(User)
            .where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
        )
        return int(await session.scalar(statement) or 0)

    async def list(self, session: AsyncSession) -> list[UserAccount]:
        result = await session.scalars(select(User).order_by(User.created_at.asc(), User.id.asc()))
        return [_to_domain(model) for model in result]

    async def list_page(
        self, session: AsyncSession, *, page: int, page_size: int
    ) -> tuple[list[UserAccount], int]:
        total = int(await session.scalar(select(func.count()).select_from(User)) or 0)
        result = await session.scalars(
            select(User)
            .order_by(User.created_at.asc(), User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [_to_domain(model) for model in result], total

    async def get(self, session: AsyncSession, user_id: UUID) -> UserAccount | None:
        model = await session.get(User, user_id)
        return _to_domain(model) if model else None

    async def get_by_email(self, session: AsyncSession, email: str) -> UserAccount | None:
        model = await session.scalar(select(User).where(User.email == email.strip().lower()))
        return _to_domain(model) if model else None

    async def create(
        self,
        session: AsyncSession,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        role: UserRole,
    ) -> UserAccount:
        model = User(
            email=email.strip().lower(),
            display_name=display_name.strip(),
            password_hash=password_hash,
            role=role,
            is_active=True,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def update(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        display_name: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        password_hash: str | None = None,
    ) -> UserAccount | None:
        values: dict[str, object] = {}
        if display_name is not None:
            values["display_name"] = display_name.strip()
        if role is not None:
            values["role"] = role
        if is_active is not None:
            values["is_active"] = is_active
        if password_hash is not None:
            values["password_hash"] = password_hash
        if values:
            await session.execute(update(User).where(User.id == user_id).values(**values))
        return await self.get(session, user_id)

    async def set_last_login(
        self, session: AsyncSession, user_id: UUID, occurred_at: datetime
    ) -> None:
        await session.execute(
            update(User).where(User.id == user_id).values(last_login_at=occurred_at)
        )
