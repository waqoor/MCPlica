from uuid import uuid4

import pytest

from app.core.auth import PasswordManager, TokenManager
from app.core.exceptions import AuthenticationError
from app.domain.auth import UserRole


def _tokens() -> TokenManager:
    return TokenManager(
        signing_key="s" * 32,
        refresh_pepper="p" * 32,
        access_ttl_seconds=900,
    )


def test_access_token_is_signed_and_contains_session_csrf_and_role() -> None:
    manager = _tokens()
    user_id = uuid4()
    session_id = uuid4()
    token, expires_at = manager.issue_access_token(
        user_id=user_id,
        session_id=session_id,
        role=UserRole.BUILDER,
        csrf_token="csrf-value",
    )

    claims = manager.decode_access_token(token)
    assert claims.user_id == user_id
    assert claims.session_id == session_id
    assert claims.role is UserRole.BUILDER
    assert claims.csrf_token == "csrf-value"
    assert claims.expires_at == expires_at.replace(microsecond=0)

    with pytest.raises(AuthenticationError):
        TokenManager(
            signing_key="x" * 32,
            refresh_pepper="p" * 32,
            access_ttl_seconds=900,
        ).decode_access_token(token)


def test_refresh_verifier_is_keyed_and_passwords_use_argon2() -> None:
    first = _tokens().hash_refresh_token("refresh-token")
    second = TokenManager(
        signing_key="s" * 32,
        refresh_pepper="different-pepper-which-is-long-enough",
        access_ttl_seconds=900,
    ).hash_refresh_token("refresh-token")
    assert first != second

    passwords = PasswordManager()
    password_hash = passwords.hash("correct horse battery staple")
    assert password_hash.startswith("$argon2")
    assert passwords.verify("correct horse battery staple", password_hash)
    assert not passwords.verify("wrong", password_hash)
    assert passwords.verify_and_update("correct horse battery staple", password_hash) == (
        True,
        None,
    )
