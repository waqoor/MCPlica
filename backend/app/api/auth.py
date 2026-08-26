from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    CsrfCookiePair,
    CurrentPrincipal,
    auth_service,
    optional_principal,
)
from app.core.exceptions import AuthenticationError
from app.domain.auth import AuthPrincipal
from app.schemas.auth import AuthResponse, LoginRequest, UserRead
from app.services.auth import AuthService, AuthTokens

router = APIRouter(prefix="/auth", tags=["authentication"])


def _user_read(tokens: AuthTokens) -> UserRead:
    user = tokens.user
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


def _set_auth_cookies(response: Response, request: Request, tokens: AuthTokens) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.auth_cookie_name,
        tokens.access_token,
        httponly=True,
        max_age=settings.access_token_ttl_seconds,
        secure=bool(settings.secure_cookies),
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        tokens.refresh_token,
        httponly=True,
        max_age=settings.refresh_token_ttl_seconds,
        secure=bool(settings.secure_cookies),
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        tokens.csrf_token,
        httponly=False,
        max_age=settings.refresh_token_ttl_seconds,
        secure=bool(settings.secure_cookies),
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response, request: Request) -> None:
    settings = request.app.state.settings
    for name in (
        settings.auth_cookie_name,
        settings.refresh_cookie_name,
        settings.csrf_cookie_name,
    ):
        response.delete_cookie(name, path="/", secure=settings.secure_cookies, samesite="lax")


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(auth_service)],
) -> AuthResponse:
    tokens = await service.login(
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        user_agent=request.headers.get("User-Agent"),
        remote_ip=request.client.host if request.client else None,
        request_id=request.state.request_id,
    )
    _set_auth_cookies(response, request, tokens)
    return AuthResponse(user=_user_read(tokens), access_expires_at=tokens.access_expires_at)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    _csrf: CsrfCookiePair,
    service: Annotated[AuthService, Depends(auth_service)],
) -> AuthResponse:
    refresh_token = request.cookies.get(request.app.state.settings.refresh_cookie_name)
    if not refresh_token:
        raise AuthenticationError("Refresh session is required")
    tokens = await service.refresh(
        refresh_token=refresh_token,
        request_id=request.state.request_id,
    )
    _set_auth_cookies(response, request, tokens)
    return AuthResponse(user=_user_read(tokens), access_expires_at=tokens.access_expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    _csrf: CsrfCookiePair,
    principal: Annotated[AuthPrincipal | None, Depends(optional_principal)],
    service: Annotated[AuthService, Depends(auth_service)],
) -> Response:
    await service.logout(
        refresh_token=request.cookies.get(request.app.state.settings.refresh_cookie_name),
        principal=principal,
        request_id=request.state.request_id,
    )
    _clear_auth_cookies(response, request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
async def me(principal: CurrentPrincipal) -> UserRead:
    user = principal.user
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )
