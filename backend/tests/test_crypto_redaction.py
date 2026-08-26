import base64

import pytest

from app.core.crypto import AesGcmSecretCipher
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
