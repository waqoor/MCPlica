import base64
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.exceptions import ValidationError

NONCE_BYTES: Final = 12


def configured_secret_cipher(
    encoded_key: str | None,
    key_version: str,
    *,
    allow_ephemeral: bool = False,
) -> "AesGcmSecretCipher":
    if encoded_key is None:
        if not allow_ephemeral:
            raise ValueError("secret encryption key is required")
        encoded_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    return AesGcmSecretCipher.from_base64_key(encoded_key, key_version)


@dataclass(frozen=True, slots=True)
class EncryptedSecret:
    key_version: str
    payload: bytes


class AesGcmSecretCipher:
    """Versioned AES-256-GCM envelope with caller-supplied associated data."""

    def __init__(self, keys: Mapping[str, bytes], active_key_version: str) -> None:
        normalized = dict(keys)
        if not normalized:
            raise ValueError("at least one encryption key is required")
        for version, key in normalized.items():
            if not version:
                raise ValueError("encryption key version cannot be empty")
            if len(key) != 32:
                raise ValueError("AES-256-GCM keys must be exactly 32 bytes")
        if active_key_version not in normalized:
            raise ValueError("active encryption key version is not present in key ring")
        self._keys = normalized
        self.active_key_version = active_key_version

    @classmethod
    def from_base64_key(cls, key: str, key_version: str = "v1") -> "AesGcmSecretCipher":
        try:
            decoded = base64.urlsafe_b64decode(key.encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("secret encryption key must be URL-safe base64") from exc
        return cls({key_version: decoded}, key_version)

    def encrypt_bytes(self, plaintext: bytes, *, associated_data: bytes) -> EncryptedSecret:
        nonce = os.urandom(NONCE_BYTES)
        cipher = AESGCM(self._keys[self.active_key_version])
        ciphertext = cipher.encrypt(nonce, plaintext, associated_data)
        return EncryptedSecret(self.active_key_version, nonce + ciphertext)

    def decrypt_bytes(
        self,
        encrypted: bytes,
        *,
        key_version: str,
        associated_data: bytes,
    ) -> bytes:
        if key_version not in self._keys:
            raise ValidationError(f"Unknown secret encryption key version: {key_version}")
        if len(encrypted) <= NONCE_BYTES:
            raise ValidationError("Encrypted secret payload is malformed")
        nonce, ciphertext = encrypted[:NONCE_BYTES], encrypted[NONCE_BYTES:]
        try:
            return AESGCM(self._keys[key_version]).decrypt(nonce, ciphertext, associated_data)
        except InvalidTag as exc:
            raise ValidationError("Encrypted secret authentication failed") from exc

    def encrypt_json(
        self, value: Mapping[str, object], *, associated_data: bytes
    ) -> EncryptedSecret:
        plaintext = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.encrypt_bytes(plaintext, associated_data=associated_data)

    def decrypt_json(
        self,
        encrypted: bytes,
        *,
        key_version: str,
        associated_data: bytes,
    ) -> dict[str, object]:
        plaintext = self.decrypt_bytes(
            encrypted,
            key_version=key_version,
            associated_data=associated_data,
        )
        try:
            value = cast(object, json.loads(plaintext))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Decrypted secret payload is invalid") from exc
        if not isinstance(value, dict):
            raise ValidationError("Decrypted secret payload must be an object")
        payload = cast(dict[object, object], value)
        return {str(key): item for key, item in payload.items()}
