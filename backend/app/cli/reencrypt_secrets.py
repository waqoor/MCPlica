import argparse
import asyncio
import json

from app.clients.database import DatabaseClient
from app.core.config import get_settings
from app.core.crypto import configured_secret_cipher
from app.repositories.secret_rotation import SecretRotationRepository
from app.services.secret_rotation import SecretRotationService


async def _run(batch_size: int) -> None:
    settings = get_settings()
    if settings.secret_encryption_key is None:
        raise ValueError("SECRET_ENCRYPTION_KEY is required for secret re-encryption")
    cipher = configured_secret_cipher(
        settings.secret_encryption_key.get_secret_value(),
        settings.secret_encryption_key_version,
        previous_encoded_keys={
            version: key.get_secret_value()
            for version, key in settings.secret_encryption_previous_keys.items()
        },
    )
    database = DatabaseClient(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
    )
    try:
        result = await SecretRotationService(
            database,
            SecretRotationRepository(),
            cipher,
        ).reencrypt_all(batch_size=batch_size)
    finally:
        await database.close()
    print(
        json.dumps(
            {
                "active_key_version": cipher.active_key_version,
                "credentials_reencrypted": result.credentials_reencrypted,
                "system_secrets_reencrypted": result.system_secrets_reencrypted,
                "counts_by_key_version": result.counts_by_key_version,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-encrypt stored MCPlica secrets under the configured active key"
    )
    parser.add_argument("--batch-size", type=int, default=100)
    arguments = parser.parse_args()
    asyncio.run(_run(arguments.batch_size))


if __name__ == "__main__":
    main()
