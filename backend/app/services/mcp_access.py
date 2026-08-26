import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import InvalidStateError, MCPlicaError, NotFoundError, ValidationError
from app.domain.deployments import (
    IssuedMCPAccessToken,
    MCPAccessSnapshot,
    MCPAccessTokenRecord,
    MCPAuthConfigRecord,
    MCPAuthMode,
)
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.mcp_access import MCPAccessRepository
from app.services.deployment.service import DeploymentService


class MCPAccessService:
    def __init__(
        self,
        database: DatabaseClient,
        access: MCPAccessRepository,
        deployments: DeploymentRepository,
        audit: AuditRepository,
        deployment_service: DeploymentService,
        settings: Settings,
    ) -> None:
        self._database = database
        self._access = access
        self._deployments = deployments
        self._audit = audit
        self._deployment_service = deployment_service
        self._settings = settings

    async def get(self, project_id: UUID) -> MCPAccessSnapshot:
        async with self._database.session_scope() as session:
            if await self._deployments.get_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return MCPAccessSnapshot(
                auth_config=await self._access.get_config(session, project_id),
                tokens=await self._access.list_tokens(session, project_id),
            )

    async def configure(
        self,
        *,
        project_id: UUID,
        mode: MCPAuthMode,
        issuer_url: str | None,
        audiences: list[str],
        required_scopes: list[str],
        metadata: dict[str, object],
        actor_user_id: UUID,
        request_id: str | None,
    ) -> MCPAuthConfigRecord:
        audiences = self._normalize_values(audiences, label="OIDC audience", limit=50)
        required_scopes = self._normalize_values(
            required_scopes,
            label="OIDC scope",
            limit=100,
        )
        self._validate_auth_configuration(
            mode,
            issuer_url,
            audiences,
            required_scopes,
            metadata,
        )
        metadata = dict(metadata)
        if mode == MCPAuthMode.EXTERNAL_OAUTH_OIDC:
            raw_algorithms = metadata.get("allowed_algorithms", ["RS256", "ES256"])
            assert isinstance(raw_algorithms, list)
            metadata["allowed_algorithms"] = sorted(
                {str(value) for value in cast(list[object], raw_algorithms)}
            )
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            if await self._deployments.lock_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            previous = await self._access.get_config(session, project_id)
            config = await self._access.upsert_config(
                session,
                project_id=project_id,
                mode=mode,
                issuer_url=issuer_url,
                audiences=audiences,
                required_scopes=required_scopes,
                metadata=metadata,
                updated_by=actor_user_id,
                updated_at=now,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="mcp_access.auth_mode_updated",
                entity_type="mcp_auth_config",
                project_id=project_id,
                request_id=request_id,
                metadata={"mode": mode.value},
            )
        previous_mode = previous.mode if previous is not None else MCPAuthMode.STATIC_BEARER
        if previous_mode != mode:
            await self._deployment_service.stop_project(
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
        else:
            await self._redeploy(
                project_id,
                actor_user_id,
                request_id,
                stop_old_first=mode == MCPAuthMode.EXTERNAL_OAUTH_OIDC,
                event_type="deployment.mcp_auth_change_requested",
            )
        return config

    async def create_token(
        self,
        *,
        project_id: UUID,
        name: str,
        expires_at: datetime | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> IssuedMCPAccessToken:
        if expires_at is not None and (
            expires_at.tzinfo is None or expires_at <= datetime.now(UTC)
        ):
            raise ValidationError("Token expiration must be a future timezone-aware value")
        async with self._database.session_scope() as session:
            if await self._deployments.lock_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            await self._require_static_mode(session, project_id)
            issued = await self._issue_token(
                session,
                project_id=project_id,
                name=name,
                expires_at=expires_at,
                actor_user_id=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="mcp_access.token_created",
                entity_type="mcp_access_token",
                entity_id=issued.token.id,
                project_id=project_id,
                request_id=request_id,
                metadata={"name": issued.token.name},
            )
        try:
            await self._redeploy(
                project_id,
                actor_user_id,
                request_id,
                stop_old_first=False,
                event_type="deployment.mcp_token_change_requested",
            )
        except MCPlicaError:
            await self._invalidate_unpublished_token(
                project_id=project_id,
                token_id=issued.token.id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            raise
        return issued

    async def rotate_token(
        self,
        *,
        project_id: UUID,
        token_id: UUID,
        overlap_seconds: int,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> IssuedMCPAccessToken:
        if not 0 <= overlap_seconds <= 900:
            raise ValidationError("Token rotation overlap must be between 0 and 900 seconds")
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            if await self._deployments.lock_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            await self._require_static_mode(session, project_id)
            current = await self._access.get_token(session, token_id)
            if current is None or current.project_id != project_id:
                raise NotFoundError("MCP access token was not found")
            if current.revoked_at is not None:
                raise InvalidStateError("Revoked MCP access tokens cannot be rotated")
            if current.expires_at is not None and current.expires_at <= now:
                raise InvalidStateError("Expired MCP access tokens cannot be rotated")
            original_expires_at = current.expires_at
            expires_at = now + timedelta(seconds=overlap_seconds)
            if current.expires_at is not None:
                expires_at = min(expires_at, current.expires_at)
            await self._access.expire_for_rotation(
                session,
                token_id,
                expires_at=expires_at,
                revoke_immediately=overlap_seconds == 0,
            )
            issued = await self._issue_token(
                session,
                project_id=project_id,
                name=current.name,
                expires_at=current.expires_at,
                actor_user_id=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="mcp_access.token_rotated",
                entity_type="mcp_access_token",
                entity_id=issued.token.id,
                project_id=project_id,
                request_id=request_id,
                metadata={
                    "replaced_token_id": str(token_id),
                    "overlap_seconds": overlap_seconds,
                },
            )
        try:
            await self._redeploy(
                project_id,
                actor_user_id,
                request_id,
                stop_old_first=overlap_seconds == 0,
                event_type="deployment.mcp_token_rotation_requested",
            )
        except MCPlicaError:
            async with self._database.session_scope() as session:
                await self._access.revoke(session, issued.token.id, datetime.now(UTC))
                await self._access.restore_rotation(
                    session,
                    token_id,
                    expires_at=original_expires_at,
                )
                await self._audit.append(
                    session,
                    actor_user_id=actor_user_id,
                    event_type="mcp_access.token_rotation_aborted",
                    entity_type="mcp_access_token",
                    entity_id=token_id,
                    project_id=project_id,
                    request_id=request_id,
                )
            raise
        return issued

    async def revoke_token(
        self,
        *,
        project_id: UUID,
        token_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> MCPAccessTokenRecord:
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            if await self._deployments.lock_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            current = await self._access.get_token(session, token_id)
            if current is None or current.project_id != project_id:
                raise NotFoundError("MCP access token was not found")
            revoked = await self._access.revoke(session, token_id, now)
            assert revoked is not None
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="mcp_access.token_revoked",
                entity_type="mcp_access_token",
                entity_id=token_id,
                project_id=project_id,
                request_id=request_id,
            )
        await self._redeploy(
            project_id,
            actor_user_id,
            request_id,
            stop_old_first=True,
            event_type="deployment.mcp_token_revocation_requested",
        )
        return revoked

    async def _issue_token(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        name: str,
        expires_at: datetime | None,
        actor_user_id: UUID,
    ) -> IssuedMCPAccessToken:
        normalized_name = name.strip()
        if (
            not normalized_name
            or len(normalized_name) > 160
            or any(character in normalized_name for character in "\r\n\x00")
        ):
            raise ValidationError("Token name must contain 1 to 160 characters")
        plaintext = f"mcp_{secrets.token_urlsafe(32)}"
        token_hash = f"sha256:{hashlib.sha256(plaintext.encode()).hexdigest()}"
        token = await self._access.create_token(
            session,
            token_id=uuid4(),
            project_id=project_id,
            name=normalized_name,
            token_prefix=plaintext[:12],
            token_hash=token_hash,
            created_by=actor_user_id,
            expires_at=expires_at,
        )
        return IssuedMCPAccessToken(token=token, plaintext=plaintext)

    async def _require_static_mode(self, session: AsyncSession, project_id: UUID) -> None:
        config = await self._access.get_config(session, project_id)
        if config is not None and config.mode != MCPAuthMode.STATIC_BEARER:
            raise InvalidStateError("Static access tokens require static bearer auth mode")

    async def _redeploy(
        self,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        *,
        stop_old_first: bool,
        event_type: str,
    ) -> None:
        await self._deployment_service.redeploy_active(
            project_id=project_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            stop_old_first=stop_old_first,
            event_type=event_type,
        )

    async def _invalidate_unpublished_token(
        self,
        *,
        project_id: UUID,
        token_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> None:
        async with self._database.session_scope() as session:
            await self._access.revoke(session, token_id, datetime.now(UTC))
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="mcp_access.token_issue_aborted",
                entity_type="mcp_access_token",
                entity_id=token_id,
                project_id=project_id,
                request_id=request_id,
            )

    def _validate_auth_configuration(
        self,
        mode: MCPAuthMode,
        issuer_url: str | None,
        audiences: list[str],
        required_scopes: list[str],
        metadata: dict[str, object],
    ) -> None:
        allowed_metadata = {"jwks_url", "allowed_algorithms"}
        if set(metadata) - allowed_metadata:
            raise ValidationError("OIDC metadata contains unsupported fields")
        if mode == MCPAuthMode.DISABLED_DEV and self._settings.is_production:
            raise InvalidStateError("Unauthenticated MCP access is forbidden in production")
        if mode == MCPAuthMode.EXTERNAL_OAUTH_OIDC:
            if not issuer_url or not audiences:
                raise ValidationError("OIDC mode requires an issuer URL and audience")
            self._validate_oidc_url(issuer_url, label="issuer")
            raw_algorithms = metadata.get("allowed_algorithms", ["RS256", "ES256"])
            permitted = {
                "RS256",
                "RS384",
                "RS512",
                "PS256",
                "PS384",
                "PS512",
                "ES256",
                "ES384",
                "ES512",
                "EdDSA",
            }
            if not isinstance(raw_algorithms, list) or not raw_algorithms:
                raise ValidationError("OIDC algorithms must be an asymmetric allowlist")
            algorithms = cast(list[object], raw_algorithms)
            if not all(isinstance(value, str) and value in permitted for value in algorithms):
                raise ValidationError("OIDC algorithms must be an asymmetric allowlist")
            jwks_url = metadata.get("jwks_url")
            if jwks_url is not None:
                if not isinstance(jwks_url, str):
                    raise ValidationError("OIDC JWKS URL is invalid")
                self._validate_oidc_url(jwks_url, label="JWKS")
        elif issuer_url or audiences or required_scopes or metadata:
            raise ValidationError("Only OIDC mode accepts issuer, audience, scope, or metadata")

    def _validate_oidc_url(self, value: str, *, label: str) -> None:
        parsed = urlsplit(value)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValidationError(f"OIDC {label} URL is invalid") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or len(value) > 2_048
        ):
            raise ValidationError(f"OIDC {label} URL is invalid")
        if self._settings.is_production and parsed.scheme != "https":
            raise ValidationError(f"Production OIDC {label} URL must use HTTPS")

    @staticmethod
    def _normalize_values(values: list[str], *, label: str, limit: int) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if not item or len(item) > 512 or any(character in item for character in "\r\n\x00"):
                raise ValidationError(f"{label} values are invalid")
            if item not in normalized:
                normalized.append(item)
        if len(normalized) > limit:
            raise ValidationError(f"Too many {label} values")
        return sorted(normalized)
