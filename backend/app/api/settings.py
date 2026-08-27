from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import AdminPrincipal, BuilderPrincipal, CsrfProtection, services
from app.container import ServiceContainer
from app.schemas.setting import (
    ModelCatalogItem,
    ModelSettingsRead,
    ModelSettingsUpdate,
    OpenRouterSecretUpdate,
    OpenRouterTestResult,
    SystemSettingsRead,
    SystemSettingsUpdate,
)
from app.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings(
    container: Annotated[ServiceContainer, Depends(services)],
) -> SettingsService:
    return container.settings


@router.get("", response_model=SystemSettingsRead)
async def get_settings(
    _principal: BuilderPrincipal,
    service: Annotated[SettingsService, Depends(_settings)],
) -> SystemSettingsRead:
    return await service.get_operational()


@router.patch("", response_model=SystemSettingsRead)
async def update_settings(
    payload: SystemSettingsUpdate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> SystemSettingsRead:
    result = await container.settings.update_operational(
        payload,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    container.build_admission.wake()
    return result


@router.get("/models", response_model=ModelSettingsRead)
async def get_models(
    _principal: BuilderPrincipal,
    service: Annotated[SettingsService, Depends(_settings)],
) -> ModelSettingsRead:
    return await service.get_models()


@router.put("/models", response_model=ModelSettingsRead)
async def update_models(
    payload: ModelSettingsUpdate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> ModelSettingsRead:
    return await container.settings.update_models(
        payload,
        container.ai,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )


@router.put("/openrouter", response_model=ModelSettingsRead)
async def update_openrouter(
    payload: OpenRouterSecretUpdate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[SettingsService, Depends(_settings)],
) -> ModelSettingsRead:
    return await service.rotate_openrouter_key(
        payload.api_key.get_secret_value(),
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )


@router.get("/models/catalog", response_model=list[ModelCatalogItem])
async def model_catalog(
    _principal: AdminPrincipal,
    container: Annotated[ServiceContainer, Depends(services)],
) -> list[ModelCatalogItem]:
    return await container.settings.model_catalog(container.ai)


@router.post("/openrouter/test", response_model=OpenRouterTestResult)
async def test_openrouter(
    _principal: AdminPrincipal,
    _csrf: CsrfProtection,
    container: Annotated[ServiceContainer, Depends(services)],
) -> OpenRouterTestResult:
    return await container.settings.test_openrouter(container.ai)
