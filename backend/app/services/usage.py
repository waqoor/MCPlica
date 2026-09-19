from datetime import datetime

from app.clients.database import DatabaseClient
from app.domain.builds import BuildAIRunRecord, ModelUsageRecord
from app.repositories.builds import BuildAIRunRepository


class UsageService:
    def __init__(self, database: DatabaseClient, ai_runs: BuildAIRunRepository) -> None:
        self._database = database
        self._ai_runs = ai_runs

    async def by_model(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[ModelUsageRecord]:
        async with self._database.session_scope() as session:
            return await self._ai_runs.usage_by_model(session, since=since, until=until)

    async def logs_by_model(
        self,
        *,
        model: str,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[BuildAIRunRecord], int]:
        async with self._database.session_scope() as session:
            return await self._ai_runs.list_by_model(
                session,
                model=model,
                since=since,
                until=until,
                page=page,
                page_size=page_size,
            )
