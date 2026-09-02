from dataclasses import dataclass

from app.clients.database import DatabaseClient
from app.core.crypto import AesGcmSecretCipher, system_secret_aad
from app.core.exceptions import ConflictError
from app.domain.credentials import credential_secret_aad
from app.repositories.secret_rotation import SecretRotationRepository


@dataclass(frozen=True, slots=True)
class SecretRotationResult:
    credentials_reencrypted: int
    system_secrets_reencrypted: int
    counts_by_key_version: dict[str, int]


class SecretRotationService:
    """Resumable in-place re-encryption using each record's canonical AAD."""

    def __init__(
        self,
        database: DatabaseClient,
        repository: SecretRotationRepository,
        cipher: AesGcmSecretCipher,
    ) -> None:
        self._database = database
        self._repository = repository
        self._cipher = cipher

    async def reencrypt_all(self, *, batch_size: int = 100) -> SecretRotationResult:
        if batch_size < 1 or batch_size > 10_000:
            raise ValueError("secret rotation batch size must be between 1 and 10000")
        credentials_reencrypted = 0
        system_secrets_reencrypted = 0
        while True:
            async with self._database.session_scope() as session:
                credentials = await self._repository.claim_credentials(
                    session,
                    active_key_version=self._cipher.active_key_version,
                    limit=batch_size,
                )
                remaining = batch_size - len(credentials)
                system_secrets = await self._repository.claim_system_secrets(
                    session,
                    active_key_version=self._cipher.active_key_version,
                    limit=remaining,
                )
                for envelope in credentials:
                    plaintext = self._cipher.decrypt_bytes(
                        envelope.encrypted_payload,
                        key_version=envelope.key_version,
                        associated_data=credential_secret_aad(
                            envelope.project_id,
                            envelope.id,
                            envelope.scheme,
                        ),
                    )
                    replacement = self._cipher.encrypt_bytes(
                        plaintext,
                        associated_data=credential_secret_aad(
                            envelope.project_id,
                            envelope.id,
                            envelope.scheme,
                        ),
                    )
                    if not await self._repository.replace_credential(
                        session,
                        envelope,
                        encrypted_payload=replacement.payload,
                        key_version=replacement.key_version,
                    ):
                        raise ConflictError("Credential changed during secret re-encryption")
                for envelope in system_secrets:
                    plaintext = self._cipher.decrypt_bytes(
                        envelope.encrypted_payload,
                        key_version=envelope.key_version,
                        associated_data=system_secret_aad(envelope.key),
                    )
                    replacement = self._cipher.encrypt_bytes(
                        plaintext,
                        associated_data=system_secret_aad(envelope.key),
                    )
                    if not await self._repository.replace_system_secret(
                        session,
                        envelope,
                        encrypted_payload=replacement.payload,
                        key_version=replacement.key_version,
                    ):
                        raise ConflictError("System secret changed during secret re-encryption")
            credentials_reencrypted += len(credentials)
            system_secrets_reencrypted += len(system_secrets)
            if not credentials and not system_secrets:
                break

        async with self._database.session_scope() as session:
            counts = await self._repository.counts_by_key_version(session)
        return SecretRotationResult(
            credentials_reencrypted=credentials_reencrypted,
            system_secrets_reencrypted=system_secrets_reencrypted,
            counts_by_key_version=counts,
        )
