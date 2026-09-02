import asyncio
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.exceptions import AuthenticationError
from app.domain.auth import UserRole

JWT_ALGORITHM: Final = "HS256"
JWT_ISSUER: Final = "mcplica-control-plane"
JWT_AUDIENCE: Final = "mcplica-browser"


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    session_id: UUID
    role: UserRole
    csrf_token: str
    expires_at: datetime


class PasswordManager:
    def __init__(self, *, max_concurrency: int = 2) -> None:
        if max_concurrency < 1 or max_concurrency > 32:
            raise ValueError("password hashing concurrency must be between 1 and 32")
        self._hasher = PasswordHash.recommended()
        self._slots = asyncio.Semaphore(max_concurrency)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password, password_hash)
        except (ValueError, TypeError):
            return False

    def verify_and_update(self, password: str, password_hash: str) -> tuple[bool, str | None]:
        try:
            return self._hasher.verify_and_update(password, password_hash)
        except (ValueError, TypeError):
            return False, None

    async def hash_async(self, password: str) -> str:
        async with self._slots:
            return await asyncio.to_thread(self.hash, password)

    async def verify_async(self, password: str, password_hash: str) -> bool:
        async with self._slots:
            return await asyncio.to_thread(self.verify, password, password_hash)

    async def verify_and_update_async(
        self, password: str, password_hash: str
    ) -> tuple[bool, str | None]:
        async with self._slots:
            return await asyncio.to_thread(self.verify_and_update, password, password_hash)


class TokenManager:
    def __init__(
        self,
        *,
        signing_key: str,
        refresh_pepper: str,
        access_ttl_seconds: int,
    ) -> None:
        if len(signing_key.encode("utf-8")) < 32:
            raise ValueError("auth signing key must contain at least 32 bytes")
        if len(refresh_pepper.encode("utf-8")) < 32:
            raise ValueError("refresh token pepper must contain at least 32 bytes")
        self._signing_key = signing_key
        self._refresh_pepper = refresh_pepper.encode("utf-8")
        self._access_ttl = timedelta(seconds=access_ttl_seconds)

    @staticmethod
    def new_csrf_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def new_refresh_token() -> str:
        return secrets.token_urlsafe(48)

    def hash_refresh_token(self, token: str) -> str:
        return hmac.new(self._refresh_pepper, token.encode("utf-8"), hashlib.sha256).hexdigest()

    def issue_access_token(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        role: UserRole,
        csrf_token: str,
        now: datetime | None = None,
    ) -> tuple[str, datetime]:
        issued_at = now or datetime.now(UTC)
        expires_at = issued_at + self._access_ttl
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "sub": str(user_id),
            "sid": str(session_id),
            "role": role.value,
            "csrf": csrf_token,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": expires_at,
        }
        return jwt.encode(payload, self._signing_key, algorithm=JWT_ALGORITHM), expires_at

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._signing_key,
                algorithms=[JWT_ALGORITHM],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
                options={"require": ["exp", "iat", "nbf", "sub", "sid", "role", "csrf"]},
            )
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
            return AccessTokenClaims(
                user_id=UUID(str(payload["sub"])),
                session_id=UUID(str(payload["sid"])),
                role=UserRole(str(payload["role"])),
                csrf_token=str(payload["csrf"]),
                expires_at=expires_at,
            )
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Authentication token is invalid or expired") from exc


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
