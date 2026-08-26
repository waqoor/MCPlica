from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.credentials import CredentialRecord, CredentialScheme
from app.models.credential import ProjectCredential


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    metadata: CredentialRecord
    encrypted_payload: bytes


def _to_domain(model: ProjectCredential) -> CredentialRecord:
    return CredentialRecord(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        scheme_type=model.scheme_type,
        key_version=model.key_version,
        metadata=model.metadata_json,
        created_by=model.created_by,
        created_at=model.created_at,
        rotated_at=model.rotated_at,
        revoked_at=model.revoked_at,
    )


class CredentialRepository:
    async def list(self, session: AsyncSession, project_id: UUID) -> list[CredentialRecord]:
        result = await session.scalars(
            select(ProjectCredential)
            .where(ProjectCredential.project_id == project_id)
            .order_by(ProjectCredential.created_at.asc())
        )
        return [_to_domain(model) for model in result]

    async def get(self, session: AsyncSession, credential_id: UUID) -> CredentialRecord | None:
        model = await session.get(ProjectCredential, credential_id)
        return _to_domain(model) if model else None

    async def get_for_update(
        self,
        session: AsyncSession,
        credential_id: UUID,
    ) -> CredentialRecord | None:
        model = await session.scalar(
            select(ProjectCredential).where(ProjectCredential.id == credential_id).with_for_update()
        )
        return _to_domain(model) if model else None

    async def get_encrypted(
        self, session: AsyncSession, credential_id: UUID
    ) -> EncryptedCredential | None:
        model = await session.get(ProjectCredential, credential_id)
        if model is None:
            return None
        return EncryptedCredential(_to_domain(model), model.encrypted_payload)

    async def get_encrypted_many(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        credential_ids: set[UUID],
    ) -> list[EncryptedCredential]:
        if not credential_ids:
            return []
        result = await session.scalars(
            select(ProjectCredential).where(
                ProjectCredential.project_id == project_id,
                ProjectCredential.id.in_(credential_ids),
            )
        )
        return [EncryptedCredential(_to_domain(model), model.encrypted_payload) for model in result]

    async def create(
        self,
        session: AsyncSession,
        *,
        credential_id: UUID,
        project_id: UUID,
        name: str,
        scheme_type: CredentialScheme,
        encrypted_payload: bytes,
        key_version: str,
        metadata: dict[str, object],
        created_by: UUID,
    ) -> CredentialRecord:
        model = ProjectCredential(
            id=credential_id,
            project_id=project_id,
            name=name,
            scheme_type=scheme_type,
            encrypted_payload=encrypted_payload,
            key_version=key_version,
            metadata_json=metadata,
            created_by=created_by,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_domain(model)

    async def rotate(
        self,
        session: AsyncSession,
        credential_id: UUID,
        *,
        encrypted_payload: bytes,
        key_version: str,
        metadata: dict[str, object],
        rotated_at: datetime,
    ) -> CredentialRecord | None:
        await session.execute(
            update(ProjectCredential)
            .where(
                ProjectCredential.id == credential_id,
                ProjectCredential.revoked_at.is_(None),
            )
            .values(
                encrypted_payload=encrypted_payload,
                key_version=key_version,
                metadata_json=metadata,
                rotated_at=rotated_at,
            )
        )
        return await self.get(session, credential_id)

    async def revoke(
        self, session: AsyncSession, credential_id: UUID, revoked_at: datetime
    ) -> CredentialRecord | None:
        await session.execute(
            update(ProjectCredential)
            .where(
                ProjectCredential.id == credential_id,
                ProjectCredential.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        return await self.get(session, credential_id)
