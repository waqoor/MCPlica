from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    AdminPrincipal,
    BuilderPrincipal,
    CsrfProtection,
    mcp_access_service,
)
from app.schemas.mcp_access import (
    MCPAccessRead,
    MCPAccessStatusRead,
    MCPAccessTokenCreate,
    MCPAccessTokenIssued,
    MCPAccessTokenRead,
    MCPAccessTokenRotate,
    MCPAuthConfigRead,
    MCPAuthConfigUpdate,
)
from app.services.mcp_access import MCPAccessService

router = APIRouter(prefix="/projects/{project_id}/mcp-access", tags=["mcp-access"])


@router.get("", response_model=MCPAccessRead)
async def get_mcp_access(
    project_id: UUID,
    _principal: AdminPrincipal,
    service: Annotated[MCPAccessService, Depends(mcp_access_service)],
) -> MCPAccessRead:
    snapshot = await service.get(project_id)
    return MCPAccessRead(
        auth_config=(
            MCPAuthConfigRead.model_validate(snapshot.auth_config)
            if snapshot.auth_config is not None
            else None
        ),
        tokens=[MCPAccessTokenRead.model_validate(token) for token in snapshot.tokens],
    )


@router.get("/status", response_model=MCPAccessStatusRead)
async def get_mcp_access_status(
    project_id: UUID,
    _principal: BuilderPrincipal,
    service: Annotated[MCPAccessService, Depends(mcp_access_service)],
) -> MCPAccessStatusRead:
    return MCPAccessStatusRead.model_validate(await service.get_status(project_id))


@router.put("/auth-mode", response_model=MCPAuthConfigRead)
async def update_auth_mode(
    project_id: UUID,
    payload: MCPAuthConfigUpdate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[MCPAccessService, Depends(mcp_access_service)],
) -> MCPAuthConfigRead:
    config = await service.configure(
        project_id=project_id,
        mode=payload.mode,
        issuer_url=str(payload.issuer_url) if payload.issuer_url is not None else None,
        audiences=payload.audiences,
        required_scopes=payload.required_scopes,
        metadata=payload.metadata(),
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return MCPAuthConfigRead.model_validate(config)


@router.post(
    "/tokens",
    response_model=MCPAccessTokenIssued,
    status_code=status.HTTP_201_CREATED,
)
async def create_access_token(
    project_id: UUID,
    payload: MCPAccessTokenCreate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[MCPAccessService, Depends(mcp_access_service)],
) -> MCPAccessTokenIssued:
    issued = await service.create_token(
        project_id=project_id,
        name=payload.name,
        expires_at=payload.expires_at,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return MCPAccessTokenIssued(
        token=MCPAccessTokenRead.model_validate(issued.token),
        plaintext=issued.plaintext,
    )


@router.post(
    "/tokens/{token_id}/rotate",
    response_model=MCPAccessTokenIssued,
    status_code=status.HTTP_201_CREATED,
)
async def rotate_access_token(
    project_id: UUID,
    token_id: UUID,
    payload: MCPAccessTokenRotate,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[MCPAccessService, Depends(mcp_access_service)],
) -> MCPAccessTokenIssued:
    issued = await service.rotate_token(
        project_id=project_id,
        token_id=token_id,
        overlap_seconds=payload.overlap_seconds,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return MCPAccessTokenIssued(
        token=MCPAccessTokenRead.model_validate(issued.token),
        plaintext=issued.plaintext,
    )


@router.delete("/tokens/{token_id}", response_model=MCPAccessTokenRead)
async def revoke_access_token(
    project_id: UUID,
    token_id: UUID,
    request: Request,
    principal: AdminPrincipal,
    _csrf: CsrfProtection,
    service: Annotated[MCPAccessService, Depends(mcp_access_service)],
) -> MCPAccessTokenRead:
    revoked = await service.revoke_token(
        project_id=project_id,
        token_id=token_id,
        actor_user_id=principal.user.id,
        request_id=request.state.request_id,
    )
    return MCPAccessTokenRead.model_validate(revoked)
