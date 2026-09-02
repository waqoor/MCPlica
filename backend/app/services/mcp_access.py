import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import InvalidStateError, MCPlicaError, NotFoundError, ValidationError
from app.domain.deployments import (
    DeploymentIntent,
    IssuedMCPAccessToken,
    MCPAccessSnapshot,
    MCPAccessStatusRecord,
    MCPAccessTokenRecord,
    MCPAuthConfigRecord,
    MCPAuthMode,
    RuntimeEffectState,
)
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.mcp_access import MCPAccessRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.effect_state import runtime_effect_update
from app.services.deployment.secret_materializer import materialize_inbound_auth
from app.services.deployment.service import DeploymentService


class MCPAccessService:
    def __init__(
        self,
        database: DatabaseClient,
        access: MCPAccessRepository,
        deployments: DeploymentRepository,
        commands: RuntimeCommandRepository,
        audit: AuditRepository,
        deployment_service: DeploymentService,
        settings: Settings,
    ) -> None:
        self._database = database
        self._access = access
        self._deployments = deployments
        self._commands = commands
        self._audit = audit
        self._deployment_service = deployment_service
        self._settings = settings

    async def get(self, project_id: UUID) -> MCPAccessSnapshot:
        async with self._database.session_scope() as session:
            if await self._deployments.get_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            auth_config = await self._access.get_config(session, project_id)
            tokens = await self._access.list_tokens(session, project_id)
            return MCPAccessSnapshot(
                auth_config=(
                    await self._config_with_runtime_state(session, auth_config)
                    if auth_config is not None
                    else None
                ),
                tokens=[await self._token_with_runtime_state(session, token) for token in tokens],
            )

    async def get_page(
        self, project_id: UUID, *, page: int, page_size: int
    ) -> tuple[MCPAccessSnapshot, int]:
        async with self._database.session_scope() as session:
            if await self._deployments.get_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            auth_config = await self._access.get_config(session, project_id)
            tokens, total = await self._access.list_tokens_page(
                session,
                project_id,
                page=page,
                page_size=page_size,
            )
            return (
                MCPAccessSnapshot(
                    auth_config=(
                        await self._config_with_runtime_state(session, auth_config)
                        if auth_config is not None
                        else None
                    ),
                    tokens=[
                        await self._token_with_runtime_state(session, token) for token in tokens
                    ],
                ),
                total,
            )

    async def get_status(self, project_id: UUID) -> MCPAccessStatusRecord:
        """Return non-secret readiness state safe for Builder workflows."""

        async with self._database.session_scope() as session:
            project = await self._deployments.get_project(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            config = await self._access.get_config(session, project_id)
            verifiers = await self._access.active_verifiers(session, project_id)
            tokens = await self._access.list_tokens(session, project_id)
            configured = False
            remediation: str | None = None
            if config is None:
                remediation = "Ask an administrator to configure inbound MCP access."
            else:
                try:
                    materialize_inbound_auth(
                        hostname=project.hostname,
                        config=config,
                        verifiers=verifiers,
                        settings=self._settings,
                    )
                    configured = True
                except (PydanticValidationError, MCPlicaError, ValueError):
                    remediation = (
                        "Ask an administrator to add an active access token."
                        if config.mode is MCPAuthMode.STATIC_BEARER
                        else "Ask an administrator to complete the OIDC access configuration."
                    )

            effects: list[MCPAuthConfigRecord | MCPAccessTokenRecord] = []
            if config is not None:
                effects.append(await self._config_with_runtime_state(session, config))
            effects.extend(
                [await self._token_with_runtime_state(session, token) for token in tokens]
            )
            selected = next(
                (
                    effect
                    for state in (RuntimeEffectState.FAILED, RuntimeEffectState.PENDING)
                    for effect in reversed(effects)
                    if effect.runtime_effect_state is state
                ),
                None,
            )
            return MCPAccessStatusRecord(
                project_id=project_id,
                mode=config.mode if config is not None else None,
                configured=configured,
                remediation=remediation,
                runtime_effect_state=(
                    selected.runtime_effect_state
                    if selected is not None
                    else RuntimeEffectState.EFFECTIVE
                ),
                runtime_command_id=(selected.runtime_command_id if selected is not None else None),
                runtime_error_code=(selected.runtime_error_code if selected is not None else None),
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
            await self._schedule_security_effect(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=False,
                event_type="deployment.mcp_auth_change_requested",
                subject_type="mcp_auth_config",
                subject_id=project_id,
            )
        self._deployment_service.notify_runtime_commands()
        return await self._load_config_runtime_state(config)

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
            await self._schedule_security_effect(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=False,
                event_type="deployment.mcp_token_change_requested",
                subject_type="mcp_access_token",
                subject_id=issued.token.id,
            )
        self._deployment_service.notify_runtime_commands()
        return issued.model_copy(
            update={"token": await self._load_token_runtime_state(issued.token)}
        )

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
            await self._schedule_security_effect(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=False,
                event_type="deployment.mcp_token_rotation_requested",
                subject_type="mcp_access_token",
                subject_id=issued.token.id,
            )
        self._deployment_service.notify_runtime_commands()
        return issued.model_copy(
            update={"token": await self._load_token_runtime_state(issued.token)}
        )

    async def revoke_token(
        self,
        *,
        project_id: UUID,
        token_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> MCPAccessTokenRecord:
        now = datetime.now(UTC)
        changed = False
        async with self._database.session_scope() as session:
            if await self._deployments.lock_project(session, project_id) is None:
                raise NotFoundError("Project was not found")
            current = await self._access.get_token(session, token_id)
            if current is None or current.project_id != project_id:
                raise NotFoundError("MCP access token was not found")
            if current.revoked_at is not None:
                revoked = current
            else:
                revoked = await self._access.revoke(session, token_id, now)
                assert revoked is not None
                changed = True
                await self._audit.append(
                    session,
                    actor_user_id=actor_user_id,
                    event_type="mcp_access.token_revoked",
                    entity_type="mcp_access_token",
                    entity_id=token_id,
                    project_id=project_id,
                    request_id=request_id,
                )
                await self._schedule_security_effect(
                    session,
                    project_id=project_id,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                    stop_old_first=False,
                    event_type="deployment.mcp_token_revocation_requested",
                    subject_type="mcp_access_token",
                    subject_id=token_id,
                )
        if changed:
            self._deployment_service.notify_runtime_commands()
        return await self._load_token_runtime_state(revoked)

    async def _schedule_security_effect(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool,
        event_type: str,
        subject_type: str,
        subject_id: UUID,
    ) -> None:
        """Refresh the exact active artifact, or durably stop if auth is unsafe."""

        project = await self._deployments.get_project(session, project_id)
        config = await self._access.get_config(session, project_id)
        verifiers = await self._access.active_verifiers(session, project_id)
        safely_servable = False
        if project is not None and config is not None:
            try:
                materialize_inbound_auth(
                    hostname=project.hostname,
                    config=config,
                    verifiers=verifiers,
                    settings=self._settings,
                )
            except (PydanticValidationError, MCPlicaError, ValueError):
                pass
            else:
                safely_servable = True
        if safely_servable:
            await self._deployment_service.schedule_redeploy_active(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=stop_old_first,
                event_type=event_type,
                subject_type=subject_type,
                subject_id=subject_id,
                intent=DeploymentIntent.SECURITY_REFRESH,
                fallback_to_stop=True,
            )
            return
        await self._deployment_service.schedule_stop_project(
            session,
            project_id=project_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            reason=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
        )

    async def _load_config_runtime_state(self, config: MCPAuthConfigRecord) -> MCPAuthConfigRecord:
        async with self._database.session_scope() as session:
            return await self._config_with_runtime_state(session, config)

    async def _config_with_runtime_state(
        self,
        session: AsyncSession,
        config: MCPAuthConfigRecord,
    ) -> MCPAuthConfigRecord:
        update = await runtime_effect_update(
            session,
            self._commands,
            project_id=config.project_id,
            subject_type="mcp_auth_config",
            subject_id=config.project_id,
        )
        return config.model_copy(update=update)

    async def _load_token_runtime_state(self, token: MCPAccessTokenRecord) -> MCPAccessTokenRecord:
        async with self._database.session_scope() as session:
            return await self._token_with_runtime_state(session, token)

    async def _token_with_runtime_state(
        self,
        session: AsyncSession,
        token: MCPAccessTokenRecord,
    ) -> MCPAccessTokenRecord:
        update = await runtime_effect_update(
            session,
            self._commands,
            project_id=token.project_id,
            subject_type="mcp_access_token",
            subject_id=token.id,
        )
        return token.model_copy(update=update)

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
