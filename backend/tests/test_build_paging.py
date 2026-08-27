from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID

from app.domain.builds import BuildStatus
from app.repositories.builds import BuildRepository
from app.services.builds.service import BuildService


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[object]:
        yield object()


class _Builds:
    def __init__(self) -> None:
        self.count_scopes: list[UUID | None] = []

    async def status_counts(
        self,
        _session: object,
        *,
        project_id: UUID | None = None,
    ) -> dict[BuildStatus, int]:
        self.count_scopes.append(project_id)
        return (
            {BuildStatus.READY: 1}
            if project_id is not None
            else {BuildStatus.READY: 1, BuildStatus.INDEXING: 1}
        )

    async def list_all(self, *_args: object, **_kwargs: object) -> list[Any]:
        return []

    async def count_all(self, *_args: object, **_kwargs: object) -> int:
        return 1


async def test_project_build_page_does_not_inherit_another_projects_active_state() -> None:
    repository = _Builds()
    service = object.__new__(BuildService)
    service._database = cast(Any, _Database())
    service._builds = cast(BuildRepository, repository)
    project_id = UUID(int=41)

    _items, total, has_active = await service.page_all(
        project_id=project_id,
        limit=50,
        offset=0,
    )
    assert total == 1
    assert has_active is False

    _items, _total, global_has_active = await service.page_all(
        limit=50,
        offset=0,
    )
    assert global_has_active is True
    assert repository.count_scopes == [project_id, None]
