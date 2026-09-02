from typing import Any, cast
from uuid import UUID

import pytest

from app.repositories.builds import BuildAIRunRepository


class _CapturingSession:
    def __init__(self) -> None:
        self.summary_statement: object | None = None

    async def scalar(self, statement: object) -> int:
        del statement
        return 250

    async def scalars(self, statement: object) -> list[object]:
        self.summary_statement = statement
        return []


@pytest.mark.asyncio
async def test_ai_run_page_is_bounded_stable_and_does_not_select_response_payload() -> None:
    session = _CapturingSession()

    runs, total = await BuildAIRunRepository().list_page_for_build(
        cast(Any, session),
        UUID(int=42),
        page=2,
        page_size=50,
    )

    assert runs == []
    assert total == 250
    assert session.summary_statement is not None
    sql = str(session.summary_statement)
    selected_columns = sql.split("FROM build_ai_runs", maxsplit=1)[0]
    assert "response_json" not in selected_columns
    assert "ORDER BY build_ai_runs.created_at ASC, build_ai_runs.id ASC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql
