import base64

import pytest

from app.core.crypto import AesGcmSecretCipher, configured_secret_cipher
from app.core.exceptions import ValidationError
from app.core.redaction import REDACTED, redact


def _cipher() -> AesGcmSecretCipher:
    key = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
    return AesGcmSecretCipher.from_base64_key(key, "test-v1")


def test_aes_gcm_round_trip_requires_matching_aad() -> None:
    cipher = _cipher()
    encrypted = cipher.encrypt_json({"token": "super-secret"}, associated_data=b"project:1")

    assert encrypted.key_version == "test-v1"
    assert cipher.decrypt_json(
        encrypted.payload,
        key_version=encrypted.key_version,
        associated_data=b"project:1",
    ) == {"token": "super-secret"}

    with pytest.raises(ValidationError, match="authentication failed"):
        cipher.decrypt_json(
            encrypted.payload,
            key_version=encrypted.key_version,
            associated_data=b"project:2",
        )


def test_secret_redaction_is_recursive_and_key_based() -> None:
    value = {
        "Authorization": "Bearer abc",
        "nested": [{"client_secret": "abc", "name": "visible"}],
    }

    assert redact(value) == {
        "Authorization": REDACTED,
        "nested": [{"client_secret": REDACTED, "name": "visible"}],
    }


def test_configured_cipher_reads_previous_keys_and_writes_only_with_active_key() -> None:
    old_key = base64.urlsafe_b64encode(b"o" * 32).decode()
    new_key = base64.urlsafe_b64encode(b"n" * 32).decode()
    old_cipher = AesGcmSecretCipher.from_base64_key(old_key, "old")
    old_value = old_cipher.encrypt_json({"token": "retained"}, associated_data=b"record")

    key_ring = configured_secret_cipher(
        new_key,
        "new",
        previous_encoded_keys={"old": old_key},
    )

    assert key_ring.key_versions == {"old", "new"}
    assert key_ring.decrypt_json(
        old_value.payload,
        key_version="old",
        associated_data=b"record",
    ) == {"token": "retained"}
    assert key_ring.encrypt_json({"token": "next"}, associated_data=b"record").key_version == (
        "new"
    )


def test_key_ring_rejects_duplicate_active_version_and_invalid_base64() -> None:
    key = base64.urlsafe_b64encode(b"k" * 32).decode()
    with pytest.raises(ValueError, match="cannot also be a previous key"):
        configured_secret_cipher(key, "v2", previous_encoded_keys={"v2": key})
    with pytest.raises(ValueError, match="URL-safe base64"):
        configured_secret_cipher("not base64!", "v2")
