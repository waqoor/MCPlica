import asyncio

from app.clients.database import DatabaseClient
from app.core.auth import PasswordManager
from app.core.config import Settings, get_settings
from app.domain.auth import UserRole
from app.repositories.audit import AuditRepository
from app.repositories.users import UserRepository

DEFAULT_DEVELOPMENT_ADMIN_DISPLAY_NAME = "MCPlica Admin"


def _require_development_environment(environment: str) -> None:
    if environment != "development":
        raise RuntimeError(
            "The default administrator is development-only and cannot be created "
            f"when ENV={environment}"
        )


def _development_admin_credentials(settings: Settings) -> tuple[str, str]:
    _require_development_environment(settings.env)
    if settings.default_admin_email is None or settings.default_admin_password is None:
        raise RuntimeError(
            "DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD must be configured "
            "for the development administrator"
        )
    return (
        str(settings.default_admin_email),
        settings.default_admin_password.get_secret_value(),
    )


async def _ensure() -> None:
    settings = get_settings()
    email, password = _development_admin_credentials(settings)
    database = DatabaseClient(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
    )
    users = UserRepository()
    try:
        async with database.session_scope() as session:
            await users.lock_admin_mutations(session)
            await users.lock_email(session, email)
            existing = await users.get_by_email(session, email)
            if existing is not None:
                print(f"Development administrator {existing.email} already exists")
                return
            user = await users.create(
                session,
                email=email,
                display_name=DEFAULT_DEVELOPMENT_ADMIN_DISPLAY_NAME,
                password_hash=PasswordManager().hash(password),
                role=UserRole.ADMIN,
            )
            await AuditRepository().append(
                session,
                actor_user_id=user.id,
                event_type="user.development_admin_created",
                entity_type="user",
                entity_id=user.id,
                metadata={"development_only": True},
            )
            print(f"Created development administrator {user.email} ({user.id})")
    finally:
        await database.close()


def main() -> None:
    try:
        asyncio.run(_ensure())
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
