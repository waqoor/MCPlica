from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AdminPrincipal, CsrfProtection, user_service
from app.schemas.auth import UserCreate, UserRead, UserUpdate
from app.schemas.pagination import Page
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _to_read(user: object) -> UserRead:
    return UserRead.model_validate(user)


@router.get("", response_model=Page[UserRead])
async def list_users(
    _principal: AdminPrincipal,
    service: Annotated[UserService, Depends(user_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[UserRead]:
    users, total = await service.list(page=page, page_size=page_size)
    return Page(
        items=[_to_read(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[UserService, Depends(user_service)],
) -> UserRead:
    user = await service.create(
        email=str(payload.email),
        display_name=payload.display_name,
        password=payload.password.get_secret_value(),
        role=payload.role,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _to_read(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[UserService, Depends(user_service)],
) -> UserRead:
    values = payload.model_dump(exclude_unset=True)
    password = values.pop("password", None)
    user = await service.update(
        user_id,
        display_name=values.get("display_name"),
        password=password.get_secret_value() if password else None,
        role=values.get("role"),
        is_active=values.get("is_active"),
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return _to_read(user)
