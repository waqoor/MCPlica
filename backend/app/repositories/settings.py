import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import SystemSecret, SystemSetting


@dataclass(frozen=True, slots=True)
class EncryptedSystemSecret:
    key: str
    encrypted_payload: bytes
    key_version: str
    rotated_at: datetime | None


@dataclass(frozen=True, slots=True)
class SystemSettingRecord:
    key: str
    value: object
    updated_at: datetime


class SettingsRepository:
    async def lock_key(self, session: AsyncSession, key: str) -> None:
        digest = hashlib.sha256(key.encode()).digest()
        lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
        await session.execute(select(func.pg_advisory_xact_lock(lock_id)))

    async def all(self, session: AsyncSession) -> dict[str, object]:
        result = await session.scalars(select(SystemSetting).order_by(SystemSetting.key))
        return {model.key: model.value_json for model in result}

    async def get(self, session: AsyncSession, key: str) -> object | None:
        model = await session.get(SystemSetting, key)
        return model.value_json if model else None

    async def get_record(
        self,
        session: AsyncSession,
        key: str,
    ) -> SystemSettingRecord | None:
        model = await session.get(SystemSetting, key)
        if model is None:
            return None
        return SystemSettingRecord(
            key=model.key,
            value=model.value_json,
            updated_at=model.updated_at,
        )

    async def set(
        self, session: AsyncSession, *, key: str, value: object, updated_by: UUID
    ) -> SystemSettingRecord:
        model = await session.get(SystemSetting, key)
        if model is None:
            model = SystemSetting(key=key, value_json=value, updated_by=updated_by)
            session.add(model)
        else:
            model.value_json = value
            model.updated_by = updated_by
        await session.flush()
        await session.refresh(model)
        return SystemSettingRecord(
            key=model.key,
            value=model.value_json,
            updated_at=model.updated_at,
        )

    async def get_secret(self, session: AsyncSession, key: str) -> EncryptedSystemSecret | None:
        model = await session.get(SystemSecret, key)
        if model is None:
            return None
        return EncryptedSystemSecret(
            key=model.key,
            encrypted_payload=model.encrypted_payload,
            key_version=model.key_version,
            rotated_at=model.rotated_at,
        )

    async def set_secret(
        self,
        session: AsyncSession,
        *,
        key: str,
        encrypted_payload: bytes,
        key_version: str,
        updated_by: UUID,
    ) -> None:
        model = await session.get(SystemSecret, key)
        if model is None:
            session.add(
                SystemSecret(
                    key=key,
                    encrypted_payload=encrypted_payload,
                    key_version=key_version,
                    updated_by=updated_by,
                )
            )
        else:
            model.encrypted_payload = encrypted_payload
            model.key_version = key_version
            model.updated_by = updated_by
            model.rotated_at = datetime.now(UTC)
