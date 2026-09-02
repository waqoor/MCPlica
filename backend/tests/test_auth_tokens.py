import asyncio
import threading
import time
from typing import Any, cast
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


@pytest.mark.asyncio
async def test_async_password_hashing_is_offloaded_and_concurrency_bounded() -> None:
    class SlowHasher:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def hash(self, password: str) -> str:
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.08)
            with self.lock:
                self.active -= 1
            return f"hashed:{password}"

    manager = PasswordManager(max_concurrency=2)
    slow = SlowHasher()
    manager._hasher = cast(Any, slow)

    tasks = [asyncio.create_task(manager.hash_async(str(index))) for index in range(5)]
    started = time.monotonic()
    await asyncio.sleep(0.02)

    assert time.monotonic() - started < 0.07
    assert await asyncio.gather(*tasks) == [f"hashed:{index}" for index in range(5)]
    assert slow.max_active == 2
