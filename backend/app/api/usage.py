from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminPrincipal, services
from app.container import ServiceContainer
from app.schemas.build import BuildAIRunRead
from app.schemas.pagination import Page
from app.schemas.usage import ModelUsageRead

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/by-model", response_model=list[ModelUsageRead])
async def usage_by_model(
    _principal: AdminPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
    since: Annotated[datetime | None, Query(alias="from")] = None,
    until: Annotated[datetime | None, Query(alias="to")] = None,
) -> list[ModelUsageRead]:
    records = await container.usage.by_model(since=since, until=until)
    return [ModelUsageRead(**record.model_dump()) for record in records]


@router.get("/logs", response_model=Page[BuildAIRunRead])
async def usage_logs(
    _principal: AdminPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
    model: Annotated[str, Query(min_length=1)],
    since: Annotated[datetime | None, Query(alias="from")] = None,
    until: Annotated[datetime | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[BuildAIRunRead]:
    runs, total = await container.usage.logs_by_model(
        model=model,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[
            BuildAIRunRead.model_validate(item.model_dump(exclude={"response"}))
            for item in runs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
