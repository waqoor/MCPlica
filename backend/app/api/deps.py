from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.projects import ProjectService


async def db_session(request: Request) -> AsyncIterator[AsyncSession]:
    client = request.app.state.database
    async with client.session_factory() as session:
        yield session


def project_service(request: Request) -> ProjectService:
    return request.app.state.project_service
