from typing import Annotated, cast

from fastapi import Depends, Request

from app.container import ServiceContainer
from app.core.auth import constant_time_equal
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.domain.auth import AuthPrincipal, UserRole
from app.services.auth import AuthService
from app.services.credentials import CredentialService
from app.services.deployment.service import DeploymentService
from app.services.mcp_access import MCPAccessService
from app.services.projects import ProjectService
from app.services.users import UserService


def services(request: Request) -> ServiceContainer:
    return cast(ServiceContainer, request.app.state.services)


def auth_service(container: Annotated[ServiceContainer, Depends(services)]) -> AuthService:
    return container.auth


def user_service(container: Annotated[ServiceContainer, Depends(services)]) -> UserService:
    return container.users


def project_service(container: Annotated[ServiceContainer, Depends(services)]) -> ProjectService:
    return container.projects


def credential_service(
    container: Annotated[ServiceContainer, Depends(services)],
) -> CredentialService:
    return container.credentials


def deployment_service(
    container: Annotated[ServiceContainer, Depends(services)],
) -> DeploymentService:
    return container.deployments


def mcp_access_service(
    container: Annotated[ServiceContainer, Depends(services)],
) -> MCPAccessService:
    return container.mcp_access


async def current_principal(
    request: Request,
    auth: Annotated[AuthService, Depends(auth_service)],
) -> AuthPrincipal:
    cached = getattr(request.state, "principal", None)
    if isinstance(cached, AuthPrincipal):
        return cached
    cookie_name = request.app.state.settings.auth_cookie_name
    access_token = request.cookies.get(cookie_name)
    request.state.cookie_auth = access_token is not None
    if access_token is None:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            access_token = authorization[7:].strip()
    if not access_token:
        raise AuthenticationError("Authentication is required")
    principal = await auth.authenticate(access_token)
    request.state.principal = principal
    return principal


async def optional_principal(
    request: Request,
    auth: Annotated[AuthService, Depends(auth_service)],
) -> AuthPrincipal | None:
    try:
        return await current_principal(request, auth)
    except AuthenticationError:
        return None


async def require_admin(
    principal: Annotated[AuthPrincipal, Depends(current_principal)],
) -> AuthPrincipal:
    if not principal.has_role(UserRole.ADMIN):
        raise PermissionDeniedError("Administrator role is required")
    return principal


async def require_builder(
    principal: Annotated[AuthPrincipal, Depends(current_principal)],
) -> AuthPrincipal:
    if not principal.has_role(UserRole.ADMIN, UserRole.BUILDER):
        raise PermissionDeniedError("Builder role is required")
    return principal


async def require_deployer(
    principal: Annotated[AuthPrincipal, Depends(current_principal)],
    container: Annotated[ServiceContainer, Depends(services)],
) -> AuthPrincipal:
    if principal.has_role(UserRole.ADMIN):
        return principal
    settings = await container.settings.get_operational()
    if principal.has_role(UserRole.BUILDER) and settings.builders_can_deploy:
        return principal
    raise PermissionDeniedError("Deployment permission is required")


async def require_csrf(
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(current_principal)],
) -> None:
    if not getattr(request.state, "cookie_auth", False):
        return
    cookie_token = request.cookies.get(request.app.state.settings.csrf_cookie_name)
    header_token = request.headers.get("X-CSRF-Token")
    if (
        not cookie_token
        or not header_token
        or not constant_time_equal(cookie_token, header_token)
        or not constant_time_equal(cookie_token, principal.csrf_token)
    ):
        raise PermissionDeniedError("A valid CSRF token is required")


async def require_csrf_cookie_pair(request: Request) -> None:
    cookie_token = request.cookies.get(request.app.state.settings.csrf_cookie_name)
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not constant_time_equal(cookie_token, header_token):
        raise PermissionDeniedError("A valid CSRF token is required")


CurrentPrincipal = Annotated[AuthPrincipal, Depends(current_principal)]
AdminPrincipal = Annotated[AuthPrincipal, Depends(require_admin)]
BuilderPrincipal = Annotated[AuthPrincipal, Depends(require_builder)]
DeployerPrincipal = Annotated[AuthPrincipal, Depends(require_deployer)]
CsrfProtection = Annotated[None, Depends(require_csrf)]
CsrfCookiePair = Annotated[None, Depends(require_csrf_cookie_pair)]
