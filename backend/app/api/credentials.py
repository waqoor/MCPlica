from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import AdminPrincipal, CsrfProtection, credential_service
from app.schemas.credential import CredentialCreate, CredentialRead, CredentialRotate
from app.services.credentials import CredentialService

router = APIRouter(prefix="/projects/{project_id}/credentials", tags=["credentials"])


@router.get("", response_model=list[CredentialRead])
async def list_credentials(
    project_id: UUID,
    _principal: AdminPrincipal,
    service: Annotated[CredentialService, Depends(credential_service)],
) -> list[CredentialRead]:
    return [CredentialRead.model_validate(item) for item in await service.list(project_id)]


@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
async def create_credential(
    project_id: UUID,
    payload: CredentialCreate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[CredentialService, Depends(credential_service)],
) -> CredentialRead:
    credential = await service.create(
        project_id=project_id,
        name=payload.name,
        scheme_type=payload.scheme_type,
        secret=payload.secret.plaintext(),
        metadata=dict(payload.metadata),
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return CredentialRead.model_validate(credential)


@router.post("/{credential_id}/rotate", response_model=CredentialRead)
async def rotate_credential(
    project_id: UUID,
    credential_id: UUID,
    payload: CredentialRotate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[CredentialService, Depends(credential_service)],
) -> CredentialRead:
    credential = await service.rotate(
        project_id=project_id,
        credential_id=credential_id,
        secret=payload.secret.plaintext(),
        metadata=dict(payload.metadata) if payload.metadata is not None else None,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return CredentialRead.model_validate(credential)


@router.delete("/{credential_id}", response_model=CredentialRead)
async def revoke_credential(
    project_id: UUID,
    credential_id: UUID,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[CredentialService, Depends(credential_service)],
) -> CredentialRead:
    credential = await service.revoke(
        project_id=project_id,
        credential_id=credential_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return CredentialRead.model_validate(credential)
