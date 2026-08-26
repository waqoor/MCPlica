import hashlib
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from mcp_contracts import MCPManifest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.clients.mcp import MCPValidationClient
from app.core.config import Settings
from app.core.exceptions import ProtocolValidationError, ValidationError
from app.domain.deployments import MCPAccessTokenRecord
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.mcp_access import MCPAccessRepository
from app.services.deployment.service import DeploymentService
from app.services.mcp_access import MCPAccessService


def _fixture() -> MCPManifest:
    path = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"
    return MCPManifest.model_validate_json(path.read_bytes())


@pytest.mark.asyncio
async def test_mcp_manifest_round_trip_preserves_exact_protocol_contract() -> None:
    manifest = _fixture()
    inspected = await MCPValidationClient().inspect_manifest(manifest)
    assert inspected["tools"] == [tool.name for tool in manifest.enabled_tools()]
    assert inspected["resources"] == [str(resource.uri) for resource in manifest.resources]


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://api.example.com/mcp",
        "https://user:password@api.example.com/mcp",
        "https://127.0.0.1/mcp",
        "https://api.example.com/mcp?access_token=forbidden",
        "https://api.example.com/mcp#fragment",
    ],
)
@pytest.mark.asyncio
async def test_mcp_endpoint_rejects_insecure_or_ambiguous_destinations(endpoint: str) -> None:
    with pytest.raises(ProtocolValidationError):
        await MCPValidationClient(timeout_seconds=0.01).inspect(endpoint)


@pytest.mark.asyncio
async def test_mcp_endpoint_dns_is_rejected_or_pinned_before_protocol_connect() -> None:
    async def private_resolver(_: str, __: int) -> Iterable[str]:
        return ["127.0.0.1"]

    with pytest.raises(ProtocolValidationError, match="blocked address"):
        await MCPValidationClient(resolver=private_resolver).inspect("https://api.example.com/mcp")

    async def public_resolver(_: str, __: int) -> Iterable[str]:
        return ["93.184.216.34"]

    client = MCPValidationClient(resolver=public_resolver)
    pinned = await client._pin_endpoint(  # pyright: ignore[reportPrivateUsage]
        "https://api.example.com/mcp"
    )
    assert pinned.url == "https://93.184.216.34/mcp"
    assert pinned.authority == "api.example.com"


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        yield cast(AsyncSession, object())


class _Deployments:
    async def lock_project(self, session: AsyncSession, project_id: UUID) -> object:
        return object()


class _Access:
    def __init__(self) -> None:
        self.token_hash = ""

    async def get_config(self, session: AsyncSession, project_id: UUID) -> None:
        return None

    async def create_token(
        self,
        session: AsyncSession,
        *,
        token_id: UUID,
        project_id: UUID,
        name: str,
        token_prefix: str,
        token_hash: str,
        created_by: UUID,
        expires_at: datetime | None,
    ) -> MCPAccessTokenRecord:
        self.token_hash = token_hash
        return MCPAccessTokenRecord(
            id=token_id,
            project_id=project_id,
            name=name,
            token_prefix=token_prefix,
            created_by=created_by,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            last_used_at=None,
            revoked_at=None,
        )


class _Audit:
    async def append(self, session: AsyncSession, **kwargs: object) -> None:
        return None


class _DeploymentService:
    async def redeploy_active(self, **kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_mcp_access_token_is_returned_once_and_only_digest_is_persisted() -> None:
    access = _Access()
    service = MCPAccessService(
        cast(DatabaseClient, _Database()),
        cast(MCPAccessRepository, access),
        cast(DeploymentRepository, _Deployments()),
        cast(AuditRepository, _Audit()),
        cast(DeploymentService, _DeploymentService()),
        Settings(env="test"),
    )
    project_id = UUID(int=1)
    actor_id = UUID(int=2)
    issued = await service.create_token(
        project_id=project_id,
        name="automation",
        expires_at=None,
        actor_user_id=actor_id,
        request_id="request-1",
    )

    assert issued.plaintext.startswith("mcp_")
    assert issued.plaintext not in access.token_hash
    assert access.token_hash == (
        "sha256:" + hashlib.sha256(issued.plaintext.encode("utf-8")).hexdigest()
    )
    assert issued.token.token_prefix == issued.plaintext[:12]

    with pytest.raises(ValidationError, match="Token name"):
        await service.create_token(
            project_id=project_id,
            name="invalid\nname",
            expires_at=None,
            actor_user_id=actor_id,
            request_id="request-2",
        )
