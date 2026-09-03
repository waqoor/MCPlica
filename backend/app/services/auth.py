import hashlib
import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.clients.cache import RedisClient
from app.clients.database import DatabaseClient
from app.core.auth import PasswordManager, TokenManager
from app.core.exceptions import AuthenticationError, RateLimitError
from app.domain.auth import AuthPrincipal, UserAccount, UserIdentity
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository


@dataclass(frozen=True, slots=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    csrf_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    user: UserAccount


def _identity(user: UserAccount) -> UserIdentity:
    return UserIdentity(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


def _hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _ip_prefix(value: str | None) -> str | None:
    if not value:
        return None
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 64
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


class AuthService:
    def __init__(
        self,
        database: DatabaseClient,
        cache: RedisClient,
        users: UserRepository,
        sessions: AuthSessionRepository,
        audit: AuditRepository,
        passwords: PasswordManager,
        tokens: TokenManager,
        *,
        refresh_ttl_seconds: int,
        rate_limit_attempts: int,
        rate_limit_window_seconds: int,
    ) -> None:
        self._database = database
        self._cache = cache
        self._users = users
        self._sessions = sessions
        self._audit = audit
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl = timedelta(seconds=refresh_ttl_seconds)
        self._rate_limit_attempts = rate_limit_attempts
        self._rate_limit_window = rate_limit_window_seconds
        self._dummy_password_hash = passwords.hash("not-a-real-user-password")

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        remote_ip: str | None,
        request_id: str | None,
    ) -> AuthTokens:
        rate_key_material = f"{email.strip().casefold()}|{_ip_prefix(remote_ip) or '-'}"
        rate_key = "login:" + hashlib.sha256(rate_key_material.encode("utf-8")).hexdigest()
        if await self._cache.rate_limit_exceeded(
            rate_key,
            limit=self._rate_limit_attempts,
            window_seconds=self._rate_limit_window,
        ):
            raise RateLimitError("Too many login attempts; try again later")

        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            user = await self._users.get_by_email(session, email)
            password_hash = user.password_hash if user else self._dummy_password_hash
            verified, updated_password_hash = await self._passwords.verify_and_update_async(
                password,
                password_hash,
            )
            if user is None or not verified or not user.is_active:
                await self._audit.append(
                    session,
                    actor_user_id=user.id if user else None,
                    event_type="auth.login_failed",
                    entity_type="auth_session",
                    request_id=request_id,
                    metadata={
                        "reason": "invalid_credentials",
                        "email_sha256": _hash_optional(email.strip().casefold()),
                        "ip_prefix": _ip_prefix(remote_ip),
                        "user_agent_sha256": _hash_optional(user_agent),
                    },
                )
            else:
                if updated_password_hash is not None:
                    refreshed = await self._users.update(
                        session,
                        user.id,
                        password_hash=updated_password_hash,
                    )
                    if refreshed is not None:
                        user = refreshed

                session_id = uuid4()
                refresh_token = self._tokens.new_refresh_token()
                refresh_expires_at = now + self._refresh_ttl
                csrf_token = self._tokens.new_csrf_token()
                await self._sessions.create(
                    session,
                    session_id=session_id,
                    user_id=user.id,
                    refresh_token_hash=self._tokens.hash_refresh_token(refresh_token),
                    expires_at=refresh_expires_at,
                    user_agent_hash=_hash_optional(user_agent),
                    ip_prefix=_ip_prefix(remote_ip),
                    now=now,
                )
                await self._users.set_last_login(session, user.id, now)
                access_token, access_expires_at = self._tokens.issue_access_token(
                    user_id=user.id,
                    session_id=session_id,
                    role=user.role,
                    csrf_token=csrf_token,
                    now=now,
                )
                await self._audit.append(
                    session,
                    actor_user_id=user.id,
                    event_type="auth.login_succeeded",
                    entity_type="auth_session",
                    entity_id=session_id,
                    request_id=request_id,
                    metadata={},
                )
                return AuthTokens(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    csrf_token=csrf_token,
                    access_expires_at=access_expires_at,
                    refresh_expires_at=refresh_expires_at,
                    user=user,
                )

        # The denial exception is deliberately raised only after the transaction
        # commits its sanitized audit event. No session or login state is written.
        raise AuthenticationError("Email or password is invalid")

    async def authenticate(self, access_token: str) -> AuthPrincipal:
        claims = self._tokens.decode_access_token(access_token)
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            auth_session = await self._sessions.get(session, claims.session_id)
            user = await self._users.get(session, claims.user_id)
            if (
                auth_session is None
                or auth_session.user_id != claims.user_id
                or auth_session.revoked_at is not None
                or auth_session.expires_at <= now
                or user is None
                or not user.is_active
            ):
                raise AuthenticationError("Authentication session is invalid or expired")
            return AuthPrincipal(
                user=_identity(user),
                session_id=auth_session.id,
                csrf_token=claims.csrf_token,
            )

    async def refresh(
        self,
        *,
        refresh_token: str,
        request_id: str | None,
    ) -> AuthTokens:
        old_hash = self._tokens.hash_refresh_token(refresh_token)
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            auth_session = await self._sessions.get_by_refresh_hash(session, old_hash)
            if (
                auth_session is None
                or auth_session.revoked_at is not None
                or auth_session.expires_at <= now
            ):
                raise AuthenticationError("Refresh session is invalid or expired")
            user = await self._users.get(session, auth_session.user_id)
            if user is None or not user.is_active:
                raise AuthenticationError("Refresh session is invalid or expired")

            new_refresh = self._tokens.new_refresh_token()
            new_hash = self._tokens.hash_refresh_token(new_refresh)
            rotated = await self._sessions.rotate_refresh_token(
                session,
                auth_session.id,
                old_hash=old_hash,
                new_hash=new_hash,
                now=now,
            )
            if not rotated:
                raise AuthenticationError("Refresh session was already rotated or revoked")
            csrf_token = self._tokens.new_csrf_token()
            access_token, access_expires_at = self._tokens.issue_access_token(
                user_id=user.id,
                session_id=auth_session.id,
                role=user.role,
                csrf_token=csrf_token,
                now=now,
            )
            await self._audit.append(
                session,
                actor_user_id=user.id,
                event_type="auth.session_refreshed",
                entity_type="auth_session",
                entity_id=auth_session.id,
                request_id=request_id,
                metadata={},
            )
            return AuthTokens(
                access_token=access_token,
                refresh_token=new_refresh,
                csrf_token=csrf_token,
                access_expires_at=access_expires_at,
                refresh_expires_at=auth_session.expires_at,
                user=user,
            )

    async def logout(
        self,
        *,
        refresh_token: str | None,
        principal: AuthPrincipal | None,
        request_id: str | None,
    ) -> None:
        now = datetime.now(UTC)
        async with self._database.session_scope() as session:
            session_id: UUID | None = principal.session_id if principal else None
            actor_id: UUID | None = principal.user.id if principal else None
            if session_id is None and refresh_token:
                record = await self._sessions.get_by_refresh_hash(
                    session, self._tokens.hash_refresh_token(refresh_token)
                )
                if record:
                    session_id = record.id
                    actor_id = record.user_id
            if session_id is not None:
                await self._sessions.revoke(session, session_id, now)
                await self._audit.append(
                    session,
                    actor_user_id=actor_id,
                    event_type="auth.logout",
                    entity_type="auth_session",
                    entity_id=session_id,
                    request_id=request_id,
                    metadata={},
                )
