from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from app.api.deps import require_deployer
from app.container import ServiceContainer
from app.core.exceptions import PermissionDeniedError
from app.domain.auth import AuthPrincipal, UserIdentity, UserRole


def _principal(role: UserRole) -> AuthPrincipal:
    return AuthPrincipal(
        user=UserIdentity(
            id=UUID(int=1),
            email="role-matrix@example.com",
            display_name="Role matrix",
            role=role,
            is_active=True,
            created_at=datetime(2026, 9, 4, tzinfo=UTC),
            updated_at=datetime(2026, 9, 4, tzinfo=UTC),
        ),
        session_id=UUID(int=2),
        csrf_token="csrf",
    )


def _container(builders_can_deploy: bool) -> ServiceContainer:
    async def get_operational() -> object:
        return SimpleNamespace(builders_can_deploy=builders_can_deploy)

    return cast(
        ServiceContainer,
        SimpleNamespace(settings=SimpleNamespace(get_operational=get_operational)),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("builders_can_deploy", [False, True])
async def test_admin_can_execute_every_deployment_lifecycle_action(
    builders_can_deploy: bool,
) -> None:
    principal = _principal(UserRole.ADMIN)
    assert await require_deployer(principal, _container(builders_can_deploy)) is principal


@pytest.mark.asyncio
async def test_builder_can_execute_lifecycle_only_when_setting_allows_it() -> None:
    principal = _principal(UserRole.BUILDER)
    assert await require_deployer(principal, _container(True)) is principal
    with pytest.raises(PermissionDeniedError, match="Deployment permission"):
        await require_deployer(principal, _container(False))
