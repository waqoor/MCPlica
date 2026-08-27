import hashlib
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from mcp_contracts import MCPManifest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DeployabilityError, PayloadTooLargeError
from app.domain.credentials import CredentialRecord, CredentialScheme
from app.domain.deployments import DeployableBuildRecord, MCPAuthConfigRecord, MCPAuthMode
from app.providers.storage import ArtifactStorage
from app.repositories.credentials import CredentialRepository, EncryptedCredential
from app.repositories.mcp_access import MCPAccessRepository, MCPTokenVerifierRecord
from app.services.deployment.preflight import DeploymentPreflight

PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")
BUILD_ID = UUID("00000000-0000-0000-0000-000000000002")
CREDENTIAL_ID = UUID("00000000-0000-0000-0000-000000000003")
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000004")
NOW = datetime(2026, 8, 27, tzinfo=UTC)
CONFIGURATION_SHA256 = "4" * 64


def _manifest_bytes() -> bytes:
    manifest = MCPManifest.model_validate(
        {
            "manifest_id": "1" * 64,
            "project": {
                "id": str(PROJECT_ID),
                "name": "Inventory",
                "slug": "inventory",
            },
            "runtime_compatibility": ">=1.0,<2.0",
            "servers": [{"id": "main", "url": "https://api.example.com"}],
            "auth_profiles": [
                {
                    "id": "auth",
                    "type": "bearer",
                    "credential_ref": str(CREDENTIAL_ID),
                }
            ],
            "tools": [
                {
                    "name": "list_items",
                    "title": "List items",
                    "description": "List items",
                    "input_schema": {
                        "type": "object",
                        "additionalProperties": False,
                    },
                    "operation_key": "op_list_items",
                    "request_mapping": {
                        "server_ref": "main",
                        "method": "GET",
                        "path": "/items",
                    },
                    "security_profile_ref": "auth",
                }
            ],
            "security": {"allowed_upstream_hosts": ["api.example.com"]},
            "build": {
                "build_id": str(BUILD_ID),
                "source_version_ids": ["source-1"],
                "source_digest": "2" * 64,
                "canonical_sha256": "3" * 64,
                "created_at": NOW.isoformat(),
                "compiler_version": "1.0.0",
            },
        }
    )
    return manifest.model_dump_json(by_alias=True).encode()


class _Storage:
    def __init__(self, value: bytes) -> None:
        self.value = value

    async def get(self, storage_key: str, *, max_bytes: int | None = None) -> bytes:
        assert storage_key == "manifests/build.json"
        if max_bytes is not None and len(self.value) > max_bytes:
            raise PayloadTooLargeError("Stored object exceeds configured byte limit")
        return self.value


class _Access:
    def __init__(
        self,
        config: MCPAuthConfigRecord | None,
        verifiers: list[MCPTokenVerifierRecord],
    ) -> None:
        self.config = config
        self.verifiers = verifiers

    async def get_config(
        self, session: AsyncSession, project_id: UUID
    ) -> MCPAuthConfigRecord | None:
        return self.config

    async def active_verifiers(
        self, session: AsyncSession, project_id: UUID
    ) -> list[MCPTokenVerifierRecord]:
        return self.verifiers


class _Credentials:
    def __init__(self, values: list[EncryptedCredential]) -> None:
        self.values = values

    async def get_encrypted_many(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        credential_ids: set[UUID],
    ) -> list[EncryptedCredential]:
        return [item for item in self.values if item.metadata.id in credential_ids]


class _Configuration:
    def __init__(self, value: str = CONFIGURATION_SHA256) -> None:
        self.value = value

    async def current_sha256(self, session: AsyncSession, project_id: UUID) -> str:
        assert project_id == PROJECT_ID
        return self.value


def _auth(
    *,
    mode: MCPAuthMode = MCPAuthMode.STATIC_BEARER,
    issuer_url: str | None = None,
    audiences: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> MCPAuthConfigRecord:
    return MCPAuthConfigRecord(
        project_id=PROJECT_ID,
        mode=mode,
        issuer_url=issuer_url,
        audiences=audiences or [],
        required_scopes=[],
        metadata=metadata or {},
        updated_by=ACTOR_ID,
        updated_at=NOW,
    )


def _credential(*, revoked: bool = False) -> EncryptedCredential:
    return EncryptedCredential(
        CredentialRecord(
            id=CREDENTIAL_ID,
            project_id=PROJECT_ID,
            name="Bearer",
            scheme_type=CredentialScheme.BEARER,
            key_version="v1",
            metadata={"security_scheme": "bearerAuth"},
            created_by=ACTOR_ID,
            created_at=NOW,
            rotated_at=None,
            revoked_at=NOW if revoked else None,
        ),
        b"encrypted",
    )


def _build(value: bytes) -> DeployableBuildRecord:
    return DeployableBuildRecord(
        id=BUILD_ID,
        project_id=PROJECT_ID,
        status="READY",
        executable_configuration_sha256=CONFIGURATION_SHA256,
        runtime_manifest_max_bytes=10_000_000,
        manifest_sha256=hashlib.sha256(value).hexdigest(),
        manifest_storage_key="manifests/build.json",
    )


def _preflight(
    value: bytes,
    *,
    config: MCPAuthConfigRecord | None,
    verifiers: list[MCPTokenVerifierRecord],
    credentials: list[EncryptedCredential],
    settings: Settings | None = None,
    current_configuration_sha256: str = CONFIGURATION_SHA256,
) -> DeploymentPreflight:
    return DeploymentPreflight(
        cast(MCPAccessRepository, _Access(config, verifiers)),
        cast(CredentialRepository, _Credentials(credentials)),
        _Configuration(current_configuration_sha256),
        cast(ArtifactStorage, _Storage(value)),
        settings or Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
        manifest_max_bytes=1_000_000,
    )


@pytest.mark.asyncio
async def test_preflight_rejects_known_invalid_access_before_deployment_creation() -> None:
    value = _manifest_bytes()
    session = cast(AsyncSession, object())
    with pytest.raises(DeployabilityError) as missing_config:
        await _preflight(
            value,
            config=None,
            verifiers=[],
            credentials=[_credential()],
        ).validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=_build(value),
            runtime_version="1.0.0",
        )
    assert missing_config.value.details["reason_code"] == "ACCESS_CONFIG_MISSING"

    with pytest.raises(DeployabilityError) as missing_token:
        await _preflight(
            value,
            config=_auth(),
            verifiers=[],
            credentials=[_credential()],
        ).validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=_build(value),
            runtime_version="1.0.0",
        )
    assert missing_token.value.details["reason_code"] == "ACCESS_CONFIG_INVALID"


@pytest.mark.asyncio
async def test_preflight_enforces_frozen_and_effective_runtime_manifest_limit() -> None:
    value = _manifest_bytes()
    build = _build(value).model_copy(update={"runtime_manifest_max_bytes": len(value) - 1})

    with pytest.raises(DeployabilityError) as error:
        await _preflight(
            value,
            config=_auth(),
            verifiers=[MCPTokenVerifierRecord(UUID(int=10), "a" * 64, None)],
            credentials=[_credential()],
        ).validate(
            cast(AsyncSession, object()),
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=build,
            runtime_version="1.0.0",
        )

    assert error.value.details["reason_code"] == "MANIFEST_EXCEEDS_RUNTIME_LIMIT"


@pytest.mark.asyncio
async def test_preflight_rejects_stale_or_unidentified_build_configuration() -> None:
    value = _manifest_bytes()
    session = cast(AsyncSession, object())
    preflight = _preflight(
        value,
        config=_auth(),
        verifiers=[MCPTokenVerifierRecord(UUID(int=10), "a" * 64, None)],
        credentials=[_credential()],
        current_configuration_sha256="5" * 64,
    )

    with pytest.raises(DeployabilityError) as stale:
        await preflight.validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=_build(value),
            runtime_version="1.0.0",
        )
    assert stale.value.details == {
        "reason_code": "BUILD_INPUTS_STALE",
        "field": "build_id",
        "remediation": ("Create a new build from the current source and routing configuration."),
    }

    historical = await preflight.validate(
        session,
        project_id=PROJECT_ID,
        hostname="inventory.mcp.localhost",
        build=_build(value),
        runtime_version="1.0.0",
        require_current_configuration=False,
    )
    assert historical.manifest.build.build_id == str(BUILD_ID)

    with pytest.raises(DeployabilityError) as unidentified:
        await preflight.validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=_build(value).model_copy(update={"executable_configuration_sha256": None}),
            runtime_version="1.0.0",
        )
    assert unidentified.value.details["reason_code"] == "BUILD_CONFIGURATION_IDENTITY_MISSING"


@pytest.mark.asyncio
async def test_preflight_rejects_revoked_credentials_and_accepts_complete_state() -> None:
    value = _manifest_bytes()
    verifier = MCPTokenVerifierRecord(UUID(int=10), "a" * 64, None)
    session = cast(AsyncSession, object())
    with pytest.raises(DeployabilityError) as revoked:
        await _preflight(
            value,
            config=_auth(),
            verifiers=[verifier],
            credentials=[_credential(revoked=True)],
        ).validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=_build(value),
            runtime_version="1.0.0",
        )
    assert revoked.value.details["reason_code"] == "CREDENTIAL_REVOKED"

    result = await _preflight(
        value,
        config=_auth(),
        verifiers=[verifier],
        credentials=[_credential()],
    ).validate(
        session,
        project_id=PROJECT_ID,
        hostname="inventory.mcp.localhost",
        build=_build(value),
        runtime_version="1.0.0",
    )
    assert result.manifest.build.build_id == str(BUILD_ID)
    assert result.token_verifiers == [verifier]


@pytest.mark.asyncio
async def test_preflight_accepts_complete_oidc_and_rejects_incomplete_oidc() -> None:
    value = _manifest_bytes()
    session = cast(AsyncSession, object())
    incomplete = _auth(
        mode=MCPAuthMode.EXTERNAL_OAUTH_OIDC,
        issuer_url="https://issuer.example.com",
    )
    with pytest.raises(DeployabilityError) as error:
        await _preflight(
            value,
            config=incomplete,
            verifiers=[],
            credentials=[_credential()],
        ).validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=_build(value),
            runtime_version="1.0.0",
        )
    assert error.value.details == {
        "reason_code": "ACCESS_CONFIG_INVALID",
        "field": "access",
        "remediation": (
            "Add an unexpired static token or complete the OIDC configuration for this environment."
        ),
    }

    complete = _auth(
        mode=MCPAuthMode.EXTERNAL_OAUTH_OIDC,
        issuer_url="https://issuer.example.com",
        audiences=["inventory-api"],
        metadata={"allowed_algorithms": ["RS256"]},
    )
    result = await _preflight(
        value,
        config=complete,
        verifiers=[],
        credentials=[_credential()],
    ).validate(
        session,
        project_id=PROJECT_ID,
        hostname="inventory.mcp.localhost",
        build=_build(value),
        runtime_version="1.0.0",
    )
    assert result.auth_config == complete
    assert result.token_verifiers == []


@pytest.mark.asyncio
async def test_preflight_allows_disabled_mode_only_outside_production() -> None:
    value = _manifest_bytes()
    session = cast(AsyncSession, object())
    disabled = _auth(mode=MCPAuthMode.DISABLED_DEV)
    development = await _preflight(
        value,
        config=disabled,
        verifiers=[],
        credentials=[_credential()],
    ).validate(
        session,
        project_id=PROJECT_ID,
        hostname="inventory.mcp.localhost",
        build=_build(value),
        runtime_version="1.0.0",
    )
    assert development.auth_config.mode is MCPAuthMode.DISABLED_DEV

    production = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        env="production",
        secret_encryption_key="test-only-encryption-key",
        auth_signing_key="test-only-signing-key",
        refresh_token_pepper="test-only-pepper",
        default_admin_email=None,
        default_admin_password=None,
        mcp_domain="mcp.example.com",
        traefik_tls=True,
        mcp_runtime_image="mcplica/runtime@sha256:" + "f" * 64,
    )
    with pytest.raises(DeployabilityError) as error:
        await _preflight(
            value,
            config=disabled,
            verifiers=[],
            credentials=[_credential()],
            settings=production,
        ).validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.example.com",
            build=_build(value),
            runtime_version="1.0.0",
        )
    assert error.value.details["reason_code"] == "ACCESS_CONFIG_INVALID"


@pytest.mark.asyncio
async def test_worker_preflight_rejects_access_revoked_after_request_preflight() -> None:
    value = _manifest_bytes()
    verifier = MCPTokenVerifierRecord(UUID(int=10), "a" * 64, None)
    access = _Access(_auth(), [verifier])
    credentials = _Credentials([_credential()])
    preflight = DeploymentPreflight(
        cast(MCPAccessRepository, access),
        cast(CredentialRepository, credentials),
        _Configuration(),
        cast(ArtifactStorage, _Storage(value)),
        Settings(_env_file=None, env="test"),  # pyright: ignore[reportCallIssue]
        manifest_max_bytes=1_000_000,
    )
    session = cast(AsyncSession, object())

    await preflight.validate(
        session,
        project_id=PROJECT_ID,
        hostname="inventory.mcp.localhost",
        build=_build(value),
        runtime_version="1.0.0",
    )

    # Simulate a token revocation committed after the API transaction and before
    # the deployment worker obtains its lock and reruns the same invariant.
    access.verifiers = []
    with pytest.raises(DeployabilityError) as error:
        await preflight.validate(
            session,
            project_id=PROJECT_ID,
            hostname="inventory.mcp.localhost",
            build=_build(value),
            runtime_version="1.0.0",
        )
    assert error.value.details["reason_code"] == "ACCESS_CONFIG_INVALID"
