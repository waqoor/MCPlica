from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.crypto import AesGcmSecretCipher
from app.core.exceptions import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from app.domain.credentials import (
    CredentialRecord,
    CredentialScheme,
    validate_credential_secret,
)
from app.domain.sources import SourceConfigurationDiscoveryRecord
from app.repositories.audit import AuditRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.projects import ProjectRepository
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.builds.readiness import validate_credential_binding
from app.services.deployment.effect_state import runtime_effect_update


class CredentialDeploymentLifecycle(Protocol):
    async def schedule_redeploy_active(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool,
        event_type: str,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
    ) -> object | None: ...

    async def schedule_stop_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        reason: str,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
    ) -> object | None: ...

    def notify_runtime_commands(self) -> None: ...


class SourceConfigurationProvider(Protocol):
    async def discover_configuration(
        self, project_id: UUID
    ) -> SourceConfigurationDiscoveryRecord: ...


def _aad(project_id: UUID, credential_id: UUID, scheme: CredentialScheme) -> bytes:
    return (f"project:{project_id}:credential:{credential_id}:scheme:{scheme.value}").encode()


class CredentialService:
    def __init__(
        self,
        database: DatabaseClient,
        credentials: CredentialRepository,
        projects: ProjectRepository,
        commands: RuntimeCommandRepository,
        audit: AuditRepository,
        cipher: AesGcmSecretCipher,
        deployments: CredentialDeploymentLifecycle,
        source_configuration: SourceConfigurationProvider | None = None,
    ) -> None:
        self._database = database
        self._credentials = credentials
        self._projects = projects
        self._commands = commands
        self._audit = audit
        self._cipher = cipher
        self._deployments = deployments
        self._source_configuration = source_configuration

    async def list(self, project_id: UUID) -> list[CredentialRecord]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            credentials = await self._credentials.list(session, project_id)
            return [
                await self._with_runtime_state(session, credential) for credential in credentials
            ]

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        scheme_type: CredentialScheme,
        secret: dict[str, object],
        metadata: dict[str, object],
        actor_user_id: UUID,
        request_id: str | None,
    ) -> CredentialRecord:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Credential name cannot be empty")
        metadata = await self._validate_source_binding(
            project_id,
            scheme_type=scheme_type,
            metadata=metadata,
        )
        _validate_secret(scheme_type, secret, metadata)
        credential_id = uuid4()
        encrypted = self._cipher.encrypt_json(
            secret,
            associated_data=_aad(project_id, credential_id, scheme_type),
        )
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            credential = await self._credentials.create(
                session,
                credential_id=credential_id,
                project_id=project_id,
                name=normalized_name,
                scheme_type=scheme_type,
                encrypted_payload=encrypted.payload,
                key_version=encrypted.key_version,
                metadata=metadata,
                created_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="credential.created",
                entity_type="project_credential",
                entity_id=credential.id,
                project_id=project_id,
                request_id=request_id,
                metadata={"name": credential.name, "scheme_type": scheme_type.value},
            )
            return credential

    async def rotate(
        self,
        *,
        project_id: UUID,
        credential_id: UUID,
        secret: dict[str, object],
        metadata: dict[str, object] | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> CredentialRecord:
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            observed = await self._credentials.get(session, credential_id)
        if observed is None or observed.project_id != project_id:
            raise NotFoundError("Credential was not found")
        if observed.revoked_at is not None:
            raise InvalidStateError("Revoked credentials cannot be rotated")
        effective_metadata = dict(observed.metadata)
        if metadata is not None:
            requested_metadata = dict(metadata)
            raw_name = requested_metadata.get("security_scheme")
            if isinstance(raw_name, str):
                requested_metadata["security_scheme"] = raw_name.strip()
            if requested_metadata != effective_metadata:
                raise ValidationError(
                    "Credential mapping metadata is immutable during secret rotation; "
                    "create a replacement credential and a new Build to remap it"
                )
        _validate_secret(observed.scheme_type, secret, effective_metadata)
        encrypted = self._cipher.encrypt_json(
            secret,
            associated_data=_aad(project_id, credential_id, observed.scheme_type),
        )
        async with self._database.session_scope() as session:
            current = await self._credentials.get_for_update(session, credential_id)
            if current is None or current.project_id != project_id:
                raise NotFoundError("Credential was not found")
            if current.revoked_at is not None:
                raise InvalidStateError("Revoked credentials cannot be rotated")
            if (
                current.rotated_at != observed.rotated_at
                or current.key_version != observed.key_version
                or current.metadata != observed.metadata
            ):
                raise ConflictError("Credential changed during rotation; reload it before retrying")
            rotated = await self._credentials.rotate(
                session,
                credential_id,
                encrypted_payload=encrypted.payload,
                key_version=encrypted.key_version,
                metadata=effective_metadata,
                rotated_at=now,
            )
            if rotated is None:
                raise NotFoundError("Credential was not found")
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="credential.rotated",
                entity_type="project_credential",
                entity_id=credential_id,
                project_id=project_id,
                request_id=request_id,
                metadata={"scheme_type": current.scheme_type.value},
            )
            await self._deployments.schedule_redeploy_active(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                stop_old_first=True,
                event_type="deployment.credential_rotation_requested",
                subject_type="project_credential",
                subject_id=credential_id,
            )
        self._deployments.notify_runtime_commands()
        return await self._load_runtime_state(rotated)

    async def revoke(
        self,
        *,
        project_id: UUID,
        credential_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> CredentialRecord:
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            current = await self._credentials.get_for_update(session, credential_id)
            if current is None or current.project_id != project_id:
                raise NotFoundError("Credential was not found")
            if current.revoked_at is not None:
                raise InvalidStateError("Credential is already revoked")
            revoked = await self._credentials.revoke(session, credential_id, now)
            if revoked is None:
                raise NotFoundError("Credential was not found")
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="credential.revoked",
                entity_type="project_credential",
                entity_id=credential_id,
                project_id=project_id,
                request_id=request_id,
                metadata={"scheme_type": current.scheme_type.value},
            )
            await self._deployments.schedule_stop_project(
                session,
                project_id=project_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                reason="deployment.credential_revocation_requested",
                subject_type="project_credential",
                subject_id=credential_id,
            )
        self._deployments.notify_runtime_commands()
        return await self._load_runtime_state(revoked)

    async def _validate_source_binding(
        self,
        project_id: UUID,
        *,
        scheme_type: CredentialScheme,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        if self._source_configuration is None:
            raise InvalidStateError(
                "Source security discovery is unavailable for credential mutation"
            )
        normalized = dict(metadata)
        raw_name = normalized.get("security_scheme")
        if isinstance(raw_name, str):
            normalized["security_scheme"] = raw_name.strip()
        discovery = await self._source_configuration.discover_configuration(project_id)
        try:
            validate_credential_binding(
                discovery,
                scheme_type=scheme_type,
                metadata=normalized,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return normalized

    async def _load_runtime_state(self, credential: CredentialRecord) -> CredentialRecord:
        async with self._database.session_scope() as session:
            return await self._with_runtime_state(session, credential)

    async def _with_runtime_state(
        self,
        session: AsyncSession,
        credential: CredentialRecord,
    ) -> CredentialRecord:
        update = await runtime_effect_update(
            session,
            self._commands,
            project_id=credential.project_id,
            subject_type="project_credential",
            subject_id=credential.id,
        )
        return credential.model_copy(update=update)

    async def decrypt_for_execution(
        self, *, project_id: UUID, credential_id: UUID
    ) -> dict[str, object]:
        """Internal build/deployment boundary; never expose this result through an API DTO."""
        async with self._database.session_scope() as session:
            encrypted = await self._credentials.get_encrypted(session, credential_id)
            if encrypted is None or encrypted.metadata.project_id != project_id:
                raise NotFoundError("Credential was not found")
            if encrypted.metadata.revoked_at is not None:
                raise InvalidStateError("Credential is revoked")
            return self._cipher.decrypt_json(
                encrypted.encrypted_payload,
                key_version=encrypted.metadata.key_version,
                associated_data=_aad(
                    project_id,
                    credential_id,
                    encrypted.metadata.scheme_type,
                ),
            )

    async def decrypt_many_for_execution(
        self, *, project_id: UUID, credential_ids: set[UUID]
    ) -> dict[UUID, tuple[CredentialScheme, dict[str, object]]]:
        """Batch-only deployment boundary; plaintext never crosses an API DTO."""
        async with self._database.session_scope() as session:
            encrypted_credentials = await self._credentials.get_encrypted_many(
                session,
                project_id=project_id,
                credential_ids=credential_ids,
            )
            if len(encrypted_credentials) != len(credential_ids):
                raise NotFoundError("A required deployment credential was not found")
            result: dict[UUID, tuple[CredentialScheme, dict[str, object]]] = {}
            for encrypted in encrypted_credentials:
                metadata = encrypted.metadata
                if metadata.revoked_at is not None:
                    raise InvalidStateError("A required deployment credential is revoked")
                result[metadata.id] = (
                    metadata.scheme_type,
                    self._cipher.decrypt_json(
                        encrypted.encrypted_payload,
                        key_version=metadata.key_version,
                        associated_data=_aad(project_id, metadata.id, metadata.scheme_type),
                    ),
                )
            return result


def _validate_secret(
    scheme: CredentialScheme,
    secret: dict[str, object],
    metadata: dict[str, object],
) -> None:
    try:
        validate_credential_secret(scheme, secret, metadata)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
