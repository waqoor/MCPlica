import hashlib
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import httpx2
import pytest
from mcp_contracts import MCPManifest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.clients.mcp import MCPValidationClient
from app.core.config import Settings
from app.core.exceptions import InvalidStateError, ProtocolValidationError, ValidationError
from app.domain.deployments import (
    DeploymentIntent,
    MCPAccessTokenRecord,
    MCPAuthConfigRecord,
    MCPAuthMode,
)
from app.repositories.audit import AuditRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.mcp_access import MCPAccessRepository, MCPTokenVerifierRecord
from app.repositories.runtime_commands import RuntimeCommandRepository
from app.services.deployment.service import DeploymentService
from app.services.mcp_access import MCPAccessService


def _fixture() -> MCPManifest:
    path = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"
    return MCPManifest.model_validate_json(path.read_bytes())


def test_mcp_runtime_evidence_limit_cannot_exceed_schema_capacity() -> None:
    with pytest.raises(ValueError, match="outside supported limits"):
        MCPValidationClient(max_items=100_001)


@pytest.mark.asyncio
async def test_mcp_manifest_validation_requires_and_verifies_runtime_evidence() -> None:
    manifest = _fixture()
    with pytest.raises(ProtocolValidationError, match="not configured"):
        await MCPValidationClient().inspect_manifest(
            manifest,
            runtime_version="1.0.0",
        )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        payload = await request.aread()
        candidate = MCPManifest.model_validate_json(payload)
        tools = [tool.name for tool in candidate.enabled_tools()]
        resources = [str(resource.uri) for resource in candidate.resources]
        return httpx2.Response(
            200,
            json={
                "runtime_version": "1.0.0",
                "protocol_version": "2025-11-25",
                "manifest_sha256": hashlib.sha256(payload).hexdigest(),
                "tool_count": len(tools),
                "tools": tools,
                "resource_count": len(resources),
                "resources": resources,
                "exercised_tool_count": len(tools),
                "exercised_tools": tools,
                "request_mapping_count": len(tools),
            },
        )

    inspected = await MCPValidationClient(
        validator_endpoint="http://runtime-validator:8090/validate",
        validator_transport=httpx2.MockTransport(handler),
    ).inspect_manifest(manifest, runtime_version="1.0.0")
    assert inspected["tools"] == [tool.name for tool in manifest.enabled_tools()]
    assert inspected["resources"] == [str(resource.uri) for resource in manifest.resources]
    assert inspected["protocol_version"] == "2025-11-25"


@pytest.mark.asyncio
async def test_runtime_evidence_accepts_more_than_ten_thousand_tools() -> None:
    manifest = _fixture()
    base_tool = manifest.tools[0]
    tool_count = 10_001
    manifest = manifest.model_copy(
        update={
            "tools": [
                base_tool.model_copy(
                    update={
                        "name": f"tool_{index}",
                        "operation_key": f"operation-{index}",
                    }
                )
                for index in range(tool_count)
            ]
        }
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        payload = await request.aread()
        candidate = MCPManifest.model_validate_json(payload)
        tools = [tool.name for tool in candidate.enabled_tools()]
        return httpx2.Response(
            200,
            json={
                "runtime_version": "1.0.0",
                "protocol_version": "2025-11-25",
                "manifest_sha256": hashlib.sha256(payload).hexdigest(),
                "tool_count": len(tools),
                "tools": tools,
                "resource_count": 0,
                "resources": [],
                "exercised_tool_count": len(tools),
                "exercised_tools": tools,
                "request_mapping_count": len(tools),
            },
        )

    inspected = await MCPValidationClient(
        validator_endpoint="http://runtime-validator:8090/validate",
        validator_transport=httpx2.MockTransport(handler),
    ).inspect_manifest(manifest, runtime_version="1.0.0")

    assert inspected["tool_count"] == tool_count
    assert inspected["request_mapping_count"] == tool_count


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

    async def get_project(self, session: AsyncSession, project_id: UUID) -> object:
        return SimpleNamespace(hostname="project.mcp.localhost")


class _Access:
    def __init__(self) -> None:
        self.token_hash = ""
        self.config: MCPAuthConfigRecord | None = None
        self.tokens: dict[UUID, MCPAccessTokenRecord] = {}

    async def get_config(
        self, session: AsyncSession, project_id: UUID
    ) -> MCPAuthConfigRecord | None:
        return self.config

    async def active_verifiers(self, session: AsyncSession, project_id: UUID) -> list[object]:
        now = datetime.now(UTC)
        return [
            MCPTokenVerifierRecord(token.id, self.token_hash, token.expires_at)
            for token in self.tokens.values()
            if token.project_id == project_id
            and token.revoked_at is None
            and (token.expires_at is None or token.expires_at > now)
        ]

    async def list_tokens(
        self, session: AsyncSession, project_id: UUID
    ) -> list[MCPAccessTokenRecord]:
        return [token for token in self.tokens.values() if token.project_id == project_id]

    async def get_token(self, session: AsyncSession, token_id: UUID) -> MCPAccessTokenRecord | None:
        return self.tokens.get(token_id)

    async def upsert_config(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        mode: MCPAuthMode,
        issuer_url: str | None,
        audiences: list[str],
        required_scopes: list[str],
        metadata: dict[str, object],
        updated_by: UUID,
        updated_at: datetime,
    ) -> MCPAuthConfigRecord:
        self.config = MCPAuthConfigRecord(
            project_id=project_id,
            mode=mode,
            issuer_url=issuer_url,
            audiences=audiences,
            required_scopes=required_scopes,
            metadata=metadata,
            updated_by=updated_by,
            updated_at=updated_at,
        )
        return self.config

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
        token = MCPAccessTokenRecord(
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
        self.tokens[token_id] = token
        return token

    async def expire_for_rotation(
        self,
        session: AsyncSession,
        token_id: UUID,
        *,
        expires_at: datetime,
        revoke_immediately: bool,
    ) -> MCPAccessTokenRecord | None:
        token = self.tokens.get(token_id)
        if token is None:
            return None
        updated = token.model_copy(
            update={
                "expires_at": expires_at,
                "revoked_at": expires_at if revoke_immediately else None,
            }
        )
        self.tokens[token_id] = updated
        return updated

    async def revoke(
        self, session: AsyncSession, token_id: UUID, revoked_at: datetime
    ) -> MCPAccessTokenRecord | None:
        token = self.tokens.get(token_id)
        if token is None:
            return None
        if token.revoked_at is None:
            token = token.model_copy(update={"expires_at": revoked_at, "revoked_at": revoked_at})
            self.tokens[token_id] = token
        return token


class _Audit:
    async def append(self, session: AsyncSession, **kwargs: object) -> None:
        return None


class _DeploymentService:
    def __init__(self) -> None:
        self.redeploy_requests: list[dict[str, object]] = []
        self.stop_requests: list[dict[str, object]] = []

    async def schedule_redeploy_active(self, *args: object, **kwargs: object) -> None:
        self.redeploy_requests.append(dict(kwargs))
        return None

    async def schedule_stop_project(self, *args: object, **kwargs: object) -> None:
        self.stop_requests.append(dict(kwargs))
        return None

    def notify_runtime_commands(self) -> None:
        return None


class _Commands:
    async def latest_for_subject(self, *args: object, **kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_builder_access_status_is_redacted_and_fail_closed() -> None:
    service = MCPAccessService(
        cast(DatabaseClient, _Database()),
        cast(MCPAccessRepository, _Access()),
        cast(DeploymentRepository, _Deployments()),
        cast(RuntimeCommandRepository, _Commands()),
        cast(AuditRepository, _Audit()),
        cast(DeploymentService, _DeploymentService()),
        Settings(env="test"),
    )

    status = await service.get_status(UUID(int=1))

    assert status.configured is False
    assert status.mode is None
    assert status.remediation == ("Ask an administrator to configure inbound MCP access.")
    assert "token" not in status.model_dump()
    assert "issuer_url" not in status.model_dump()


@pytest.mark.asyncio
async def test_mcp_access_token_is_returned_once_and_only_digest_is_persisted() -> None:
    access = _Access()
    service = MCPAccessService(
        cast(DatabaseClient, _Database()),
        cast(MCPAccessRepository, access),
        cast(DeploymentRepository, _Deployments()),
        cast(RuntimeCommandRepository, _Commands()),
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


@pytest.mark.asyncio
async def test_mcp_access_rotation_enforces_overlap_and_rejects_expired_tokens() -> None:
    access = _Access()
    project_id = UUID(int=1)
    actor_id = UUID(int=2)
    access.config = MCPAuthConfigRecord(
        project_id=project_id,
        mode=MCPAuthMode.STATIC_BEARER,
        issuer_url=None,
        audiences=[],
        required_scopes=[],
        metadata={},
        updated_by=actor_id,
        updated_at=datetime.now(UTC),
    )
    service = MCPAccessService(
        cast(DatabaseClient, _Database()),
        cast(MCPAccessRepository, access),
        cast(DeploymentRepository, _Deployments()),
        cast(RuntimeCommandRepository, _Commands()),
        cast(AuditRepository, _Audit()),
        cast(DeploymentService, _DeploymentService()),
        Settings(env="test"),
    )
    original_expiration = datetime.now(UTC) + timedelta(hours=1)
    original = await service.create_token(
        project_id=project_id,
        name="automation",
        expires_at=original_expiration,
        actor_user_id=actor_id,
        request_id="create-before-rotation",
    )
    rotation_started = datetime.now(UTC)

    rotated = await service.rotate_token(
        project_id=project_id,
        token_id=original.token.id,
        overlap_seconds=120,
        actor_user_id=actor_id,
        request_id="rotate-with-overlap",
    )

    replaced = access.tokens[original.token.id]
    assert replaced.expires_at is not None
    assert rotation_started + timedelta(seconds=119) <= replaced.expires_at
    assert replaced.expires_at <= datetime.now(UTC) + timedelta(seconds=120)
    assert replaced.revoked_at is None
    assert rotated.token.id != original.token.id
    assert rotated.token.expires_at == original_expiration

    access.tokens[rotated.token.id] = rotated.token.model_copy(
        update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
    )
    with pytest.raises(InvalidStateError, match="Expired"):
        await service.rotate_token(
            project_id=project_id,
            token_id=rotated.token.id,
            overlap_seconds=0,
            actor_user_id=actor_id,
            request_id="reject-expired-rotation",
        )

    with pytest.raises(ValidationError, match="between 0 and 900"):
        await service.rotate_token(
            project_id=project_id,
            token_id=original.token.id,
            overlap_seconds=901,
            actor_user_id=actor_id,
            request_id="reject-invalid-overlap",
        )


@pytest.mark.asyncio
async def test_last_token_revocation_stops_and_duplicate_request_is_idempotent() -> None:
    access = _Access()
    deployments = _DeploymentService()
    project_id = UUID(int=1)
    actor_id = UUID(int=2)
    access.config = MCPAuthConfigRecord(
        project_id=project_id,
        mode=MCPAuthMode.STATIC_BEARER,
        issuer_url=None,
        audiences=[],
        required_scopes=[],
        metadata={},
        updated_by=actor_id,
        updated_at=datetime.now(UTC),
    )
    service = MCPAccessService(
        cast(DatabaseClient, _Database()),
        cast(MCPAccessRepository, access),
        cast(DeploymentRepository, _Deployments()),
        cast(RuntimeCommandRepository, _Commands()),
        cast(AuditRepository, _Audit()),
        cast(DeploymentService, deployments),
        Settings(env="test"),
    )
    issued = await service.create_token(
        project_id=project_id,
        name="only verifier",
        expires_at=None,
        actor_user_id=actor_id,
        request_id="create-only-token",
    )
    deployments.redeploy_requests.clear()

    revoked = await service.revoke_token(
        project_id=project_id,
        token_id=issued.token.id,
        actor_user_id=actor_id,
        request_id="revoke-only-token",
    )
    duplicate = await service.revoke_token(
        project_id=project_id,
        token_id=issued.token.id,
        actor_user_id=actor_id,
        request_id="revoke-only-token-again",
    )

    assert revoked.revoked_at is not None
    assert duplicate.revoked_at == revoked.revoked_at
    assert deployments.redeploy_requests == []
    assert len(deployments.stop_requests) == 1
    assert deployments.stop_requests[0]["subject_id"] == issued.token.id


@pytest.mark.asyncio
async def test_subset_token_revocation_uses_exact_build_security_refresh_intent() -> None:
    access = _Access()
    deployments = _DeploymentService()
    project_id = UUID(int=1)
    actor_id = UUID(int=2)
    access.config = MCPAuthConfigRecord(
        project_id=project_id,
        mode=MCPAuthMode.STATIC_BEARER,
        issuer_url=None,
        audiences=[],
        required_scopes=[],
        metadata={},
        updated_by=actor_id,
        updated_at=datetime.now(UTC),
    )
    service = MCPAccessService(
        cast(DatabaseClient, _Database()),
        cast(MCPAccessRepository, access),
        cast(DeploymentRepository, _Deployments()),
        cast(RuntimeCommandRepository, _Commands()),
        cast(AuditRepository, _Audit()),
        cast(DeploymentService, deployments),
        Settings(env="test"),
    )
    first = await service.create_token(
        project_id=project_id,
        name="first",
        expires_at=None,
        actor_user_id=actor_id,
        request_id="first",
    )
    await service.create_token(
        project_id=project_id,
        name="second",
        expires_at=None,
        actor_user_id=actor_id,
        request_id="second",
    )
    deployments.redeploy_requests.clear()

    await service.revoke_token(
        project_id=project_id,
        token_id=first.token.id,
        actor_user_id=actor_id,
        request_id="revoke-first",
    )

    assert deployments.stop_requests == []
    assert len(deployments.redeploy_requests) == 1
    assert deployments.redeploy_requests[0]["intent"] is DeploymentIntent.SECURITY_REFRESH


@pytest.mark.asyncio
async def test_active_access_mode_switch_uses_health_before_switch_overlay() -> None:
    access = _Access()
    deployments = _DeploymentService()
    service = MCPAccessService(
        cast(DatabaseClient, _Database()),
        cast(MCPAccessRepository, access),
        cast(DeploymentRepository, _Deployments()),
        cast(RuntimeCommandRepository, _Commands()),
        cast(AuditRepository, _Audit()),
        cast(DeploymentService, deployments),
        Settings(env="test"),
    )

    result = await service.configure(
        project_id=UUID(int=1),
        mode=MCPAuthMode.EXTERNAL_OAUTH_OIDC,
        issuer_url="https://issuer.example.com",
        audiences=["inventory-api"],
        required_scopes=["mcp.invoke"],
        metadata={"allowed_algorithms": ["RS256"]},
        actor_user_id=UUID(int=2),
        request_id="mode-switch",
    )

    assert result.mode is MCPAuthMode.EXTERNAL_OAUTH_OIDC
    assert len(deployments.redeploy_requests) == 1
    request = deployments.redeploy_requests[0]
    assert request["stop_old_first"] is False
    assert request["subject_type"] == "mcp_auth_config"
