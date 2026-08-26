from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminPrincipal, services
from app.container import ServiceContainer
from app.schemas.audit import AuditEventRead, AuditPage
from app.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


def _audit(
    container: Annotated[ServiceContainer, Depends(services)],
) -> AuditService:
    return container.audit


@router.get("", response_model=AuditPage)
async def list_audit(
    _principal: AdminPrincipal,
    service: Annotated[AuditService, Depends(_audit)],
    actor: Annotated[str | None, Query(max_length=320)] = None,
    project_id: UUID | None = None,
    event_type: Annotated[str | None, Query(max_length=120)] = None,
    created_from: Annotated[datetime | None, Query(alias="from")] = None,
    created_to: Annotated[datetime | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditPage:
    items, total = await service.list(
        project_id=project_id,
        event_type=event_type,
        actor=actor,
        created_from=created_from,
        created_to=created_to,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return AuditPage(
        items=[AuditEventRead.model_validate(item.model_dump()) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
