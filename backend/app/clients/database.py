from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.clients.base import AsyncClient


class DatabaseClient(AsyncClient):
    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout_seconds: float = 30.0,
    ) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout_seconds,
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> AsyncSession:
        return self.session_factory()

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        async with self.session_factory() as session, session.begin():
            yield session

    async def health(self) -> bool:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self.engine.dispose()
