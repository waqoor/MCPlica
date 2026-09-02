from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.credentials import CredentialScheme
from app.models.credential import ProjectCredential
from app.models.setting import SystemSecret


@dataclass(frozen=True, slots=True)
class CredentialSecretEnvelope:
    id: UUID
    project_id: UUID
    scheme: CredentialScheme
    encrypted_payload: bytes
    key_version: str


@dataclass(frozen=True, slots=True)
class SystemSecretEnvelope:
    key: str
    encrypted_payload: bytes
    key_version: str


class SecretRotationRepository:
    async def claim_credentials(
        self,
        session: AsyncSession,
        *,
        active_key_version: str,
        limit: int,
    ) -> list[CredentialSecretEnvelope]:
        rows = (
            await session.execute(
                select(
                    ProjectCredential.id,
                    ProjectCredential.project_id,
                    ProjectCredential.scheme_type,
                    ProjectCredential.encrypted_payload,
                    ProjectCredential.key_version,
                )
                .where(ProjectCredential.key_version != active_key_version)
                .order_by(ProjectCredential.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).tuples()
        return [CredentialSecretEnvelope(*row) for row in rows]

    async def claim_system_secrets(
        self,
        session: AsyncSession,
        *,
        active_key_version: str,
        limit: int,
    ) -> list[SystemSecretEnvelope]:
        rows = (
            await session.execute(
                select(
                    SystemSecret.key,
                    SystemSecret.encrypted_payload,
                    SystemSecret.key_version,
                )
                .where(SystemSecret.key_version != active_key_version)
                .order_by(SystemSecret.key)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).tuples()
        return [SystemSecretEnvelope(*row) for row in rows]

    async def replace_credential(
        self,
        session: AsyncSession,
        envelope: CredentialSecretEnvelope,
        *,
        encrypted_payload: bytes,
        key_version: str,
    ) -> bool:
        result = await session.execute(
            update(ProjectCredential)
            .where(
                ProjectCredential.id == envelope.id,
                ProjectCredential.key_version == envelope.key_version,
                ProjectCredential.encrypted_payload == envelope.encrypted_payload,
            )
            .values(encrypted_payload=encrypted_payload, key_version=key_version)
        )
        return getattr(result, "rowcount", 0) == 1

    async def replace_system_secret(
        self,
        session: AsyncSession,
        envelope: SystemSecretEnvelope,
        *,
        encrypted_payload: bytes,
        key_version: str,
    ) -> bool:
        result = await session.execute(
            update(SystemSecret)
            .where(
                SystemSecret.key == envelope.key,
                SystemSecret.key_version == envelope.key_version,
                SystemSecret.encrypted_payload == envelope.encrypted_payload,
            )
            .values(encrypted_payload=encrypted_payload, key_version=key_version)
        )
        return getattr(result, "rowcount", 0) == 1

    async def counts_by_key_version(self, session: AsyncSession) -> dict[str, int]:
        result: dict[str, int] = {}
        for model in (ProjectCredential, SystemSecret):
            rows = (
                await session.execute(
                    select(model.key_version, func.count()).group_by(model.key_version)
                )
            ).tuples()
            for version, count in rows:
                result[str(version)] = result.get(str(version), 0) + int(count)
        return result
