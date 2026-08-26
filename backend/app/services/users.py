import hmac
from uuid import UUID

from pydantic import EmailStr, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from app.clients.database import DatabaseClient
from app.core.auth import PasswordManager
from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError, ValidationError
from app.domain.auth import UserAccount, UserRole
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository

_EMAIL: TypeAdapter[EmailStr] = TypeAdapter(EmailStr)


def _normalize_email(value: str) -> str:
    try:
        return str(_EMAIL.validate_python(value)).casefold()
    except PydanticValidationError as exc:
        raise ValidationError("A valid email address is required") from exc


class UserService:
    def __init__(
        self,
        database: DatabaseClient,
        users: UserRepository,
        sessions: AuthSessionRepository,
        audit: AuditRepository,
        passwords: PasswordManager,
    ) -> None:
        self._database = database
        self._users = users
        self._sessions = sessions
        self._audit = audit
        self._passwords = passwords

    async def list(self) -> list[UserAccount]:
        async with self._database.session_scope() as session:
            return await self._users.list(session)

    async def create(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        role: UserRole,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> UserAccount:
        normalized_name = display_name.strip()
        if not normalized_name:
            raise ValidationError("Display name cannot be empty")
        if len(password) < 12 or len(password) > 1_024:
            raise ValidationError("Password must contain between 12 and 1024 characters")
        normalized_email = _normalize_email(email)
        async with self._database.session_scope() as session:
            await self._users.lock_email(session, normalized_email)
            if role is UserRole.ADMIN:
                await self._users.lock_admin_mutations(session)
            if await self._users.get_by_email(session, normalized_email) is not None:
                raise ConflictError("A user with this email already exists")
            user = await self._users.create(
                session,
                email=normalized_email,
                display_name=normalized_name,
                password_hash=self._passwords.hash(password),
                role=role,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="user.created",
                entity_type="user",
                entity_id=user.id,
                request_id=request_id,
                metadata={"role": role.value},
            )
            return user

    async def update(
        self,
        user_id: UUID,
        *,
        display_name: str | None,
        password: str | None,
        role: UserRole | None,
        is_active: bool | None,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> UserAccount:
        normalized_name = display_name.strip() if display_name is not None else None
        if display_name is not None and not normalized_name:
            raise ValidationError("Display name cannot be empty")
        if password is not None and (len(password) < 12 or len(password) > 1_024):
            raise ValidationError("Password must contain between 12 and 1024 characters")
        async with self._database.session_scope() as session:
            if role is not None or is_active is not None:
                await self._users.lock_admin_mutations(session)
            current = await self._users.get(session, user_id)
            if current is None:
                raise NotFoundError("User was not found")
            removes_admin = current.role is UserRole.ADMIN and (
                role is UserRole.BUILDER or is_active is False
            )
            if removes_admin and await self._users.count_active_admins(session) <= 1:
                raise InvalidStateError(
                    "The last active administrator cannot be disabled or demoted"
                )
            updated = await self._users.update(
                session,
                user_id,
                display_name=normalized_name,
                password_hash=self._passwords.hash(password) if password else None,
                role=role,
                is_active=is_active,
            )
            if updated is None:
                raise NotFoundError("User was not found")
            if password is not None or is_active is False or role is not None:
                from datetime import UTC, datetime

                await self._sessions.revoke_for_user(session, user_id, datetime.now(UTC))
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="user.updated",
                entity_type="user",
                entity_id=user_id,
                request_id=request_id,
                metadata={
                    "role_changed": role is not None,
                    "active_changed": is_active is not None,
                    "password_changed": password is not None,
                },
            )
            return updated

    async def bootstrap_first_admin(
        self,
        *,
        supplied_bootstrap_secret: str,
        configured_bootstrap_secret: str,
        email: str,
        display_name: str,
        password: str,
    ) -> UserAccount:
        if not hmac.compare_digest(
            supplied_bootstrap_secret.encode("utf-8"),
            configured_bootstrap_secret.encode("utf-8"),
        ):
            raise InvalidStateError("Bootstrap secret is invalid")
        normalized_name = display_name.strip()
        if not normalized_name:
            raise ValidationError("Display name cannot be empty")
        if len(password) < 12 or len(password) > 1_024:
            raise ValidationError("Password must contain between 12 and 1024 characters")
        normalized_email = _normalize_email(email)
        async with self._database.session_scope() as session:
            await self._users.lock_admin_mutations(session)
            await self._users.lock_email(session, normalized_email)
            if await self._users.count(session) != 0:
                raise InvalidStateError("Administrator bootstrap is disabled after the first user")
            user = await self._users.create(
                session,
                email=normalized_email,
                display_name=normalized_name,
                password_hash=self._passwords.hash(password),
                role=UserRole.ADMIN,
            )
            await self._audit.append(
                session,
                actor_user_id=user.id,
                event_type="user.bootstrap_admin_created",
                entity_type="user",
                entity_id=user.id,
                metadata={},
            )
            return user
