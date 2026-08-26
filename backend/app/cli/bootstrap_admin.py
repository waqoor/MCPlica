import argparse
import asyncio
import getpass
from typing import cast

from pydantic import EmailStr, TypeAdapter

from app.clients.database import DatabaseClient
from app.core.auth import PasswordManager
from app.core.config import get_settings
from app.core.exceptions import MCPlicaError
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.services.users import UserService


async def _bootstrap(email: str, display_name: str, supplied_secret: str, password: str) -> None:
    settings = get_settings()
    if settings.bootstrap_secret is None:
        raise RuntimeError("BOOTSTRAP_SECRET must be configured")
    database = DatabaseClient(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
    )
    try:
        service = UserService(
            database,
            UserRepository(),
            AuthSessionRepository(),
            AuditRepository(),
            PasswordManager(),
        )
        user = await service.bootstrap_first_admin(
            supplied_bootstrap_secret=supplied_secret,
            configured_bootstrap_secret=settings.bootstrap_secret.get_secret_value(),
            email=cast(str, TypeAdapter(EmailStr).validate_python(email)),
            display_name=display_name,
            password=password,
        )
        print(f"Created administrator {user.email} ({user.id})")
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first MCPlica administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Administrator password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    supplied_secret = getpass.getpass("Bootstrap secret: ")
    try:
        asyncio.run(_bootstrap(args.email, args.display_name, supplied_secret, password))
    except MCPlicaError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
