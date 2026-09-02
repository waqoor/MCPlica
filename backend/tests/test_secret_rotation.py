from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID

import pytest

from app.core.crypto import AesGcmSecretCipher, system_secret_aad
from app.domain.credentials import CredentialScheme, credential_secret_aad
from app.repositories.secret_rotation import CredentialSecretEnvelope, SystemSecretEnvelope
from app.services.secret_rotation import SecretRotationService


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[object]:
        yield object()


class _Repository:
    def __init__(
        self,
        credential: CredentialSecretEnvelope,
        system_secret: SystemSecretEnvelope,
    ) -> None:
        self.credential = credential
        self.system_secret = system_secret

    async def claim_credentials(
        self, session: object, *, active_key_version: str, limit: int
    ) -> list[CredentialSecretEnvelope]:
        del session
        return (
            [self.credential]
            if limit > 0 and self.credential.key_version != active_key_version
            else []
        )

    async def claim_system_secrets(
        self, session: object, *, active_key_version: str, limit: int
    ) -> list[SystemSecretEnvelope]:
        del session
        return (
            [self.system_secret]
            if limit > 0 and self.system_secret.key_version != active_key_version
            else []
        )

    async def replace_credential(
        self,
        session: object,
        envelope: CredentialSecretEnvelope,
        *,
        encrypted_payload: bytes,
        key_version: str,
    ) -> bool:
        del session
        assert envelope == self.credential
        self.credential = CredentialSecretEnvelope(
            envelope.id,
            envelope.project_id,
            envelope.scheme,
            encrypted_payload,
            key_version,
        )
        return True

    async def replace_system_secret(
        self,
        session: object,
        envelope: SystemSecretEnvelope,
        *,
        encrypted_payload: bytes,
        key_version: str,
    ) -> bool:
        del session
        assert envelope == self.system_secret
        self.system_secret = SystemSecretEnvelope(
            envelope.key,
            encrypted_payload,
            key_version,
        )
        return True

    async def counts_by_key_version(self, session: object) -> dict[str, int]:
        del session
        counts: dict[str, int] = {}
        for version in (self.credential.key_version, self.system_secret.key_version):
            counts[version] = counts.get(version, 0) + 1
        return counts


@pytest.mark.asyncio
async def test_secret_reencryption_is_resumable_idempotent_and_preserves_aad() -> None:
    old = AesGcmSecretCipher({"old": b"o" * 32}, "old")
    ring = AesGcmSecretCipher({"old": b"o" * 32, "new": b"n" * 32}, "new")
    credential_id = UUID(int=45)
    project_id = UUID(int=46)
    credential_aad = credential_secret_aad(project_id, credential_id, CredentialScheme.BEARER)
    old_credential = old.encrypt_json({"token": "secret"}, associated_data=credential_aad)
    old_system = old.encrypt_json(
        {"api_key": "secret"},
        associated_data=system_secret_aad("openrouter_api_key"),
    )
    repository = _Repository(
        CredentialSecretEnvelope(
            credential_id,
            project_id,
            CredentialScheme.BEARER,
            old_credential.payload,
            old_credential.key_version,
        ),
        SystemSecretEnvelope(
            "openrouter_api_key",
            old_system.payload,
            old_system.key_version,
        ),
    )
    service = SecretRotationService(
        cast(Any, _Database()),
        cast(Any, repository),
        ring,
    )

    first = await service.reencrypt_all(batch_size=1)
    second = await service.reencrypt_all(batch_size=1)

    assert first.credentials_reencrypted == 1
    assert first.system_secrets_reencrypted == 1
    assert first.counts_by_key_version == {"new": 2}
    assert second.credentials_reencrypted == 0
    assert second.system_secrets_reencrypted == 0
    assert ring.decrypt_json(
        repository.credential.encrypted_payload,
        key_version="new",
        associated_data=credential_aad,
    ) == {"token": "secret"}
    assert ring.decrypt_json(
        repository.system_secret.encrypted_payload,
        key_version="new",
        associated_data=system_secret_aad("openrouter_api_key"),
    ) == {"api_key": "secret"}
