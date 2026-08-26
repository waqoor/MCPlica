from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from app.clients.database import DatabaseClient
from app.core.crypto import AesGcmSecretCipher
from app.core.exceptions import InvalidStateError, NotFoundError, ValidationError
from app.domain.credentials import (
    CredentialRecord,
    CredentialScheme,
    validate_credential_secret,
)
from app.repositories.audit import AuditRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.projects import ProjectRepository


class CredentialDeploymentLifecycle(Protocol):
    async def redeploy_active(
        self,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
        stop_old_first: bool,
        event_type: str,
    ) -> object | None: ...

    async def stop_project(
        self,
        *,
        project_id: UUID,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> object | None: ...


def _aad(project_id: UUID, credential_id: UUID, scheme: CredentialScheme) -> bytes:
    return (f"project:{project_id}:credential:{credential_id}:scheme:{scheme.value}").encode()


class CredentialService:
    def __init__(
        self,
        database: DatabaseClient,
        credentials: CredentialRepository,
        projects: ProjectRepository,
        audit: AuditRepository,
        cipher: AesGcmSecretCipher,
        deployments: CredentialDeploymentLifecycle,
    ) -> None:
        self._database = database
        self._credentials = credentials
        self._projects = projects
        self._audit = audit
        self._cipher = cipher
        self._deployments = deployments

    async def list(self, project_id: UUID) -> list[CredentialRecord]:
        async with self._database.session_scope() as session:
            if await self._projects.get(session, project_id) is None:
                raise NotFoundError("Project was not found")
            return await self._credentials.list(session, project_id)

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
            current = await self._credentials.get_for_update(session, credential_id)
            if current is None or current.project_id != project_id:
                raise NotFoundError("Credential was not found")
            if current.revoked_at is not None:
                raise InvalidStateError("Revoked credentials cannot be rotated")
            effective_metadata = metadata if metadata is not None else current.metadata
            _validate_secret(current.scheme_type, secret, effective_metadata)
            encrypted = self._cipher.encrypt_json(
                secret,
                associated_data=_aad(project_id, credential_id, current.scheme_type),
            )
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
        await self._deployments.redeploy_active(
            project_id=project_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            stop_old_first=False,
            event_type="deployment.credential_rotation_requested",
        )
        return rotated

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
        await self._deployments.stop_project(
            project_id=project_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        return revoked

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
