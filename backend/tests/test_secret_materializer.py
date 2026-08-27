from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from mcp_contracts import MCPManifest

from app.core.config import Settings
from app.core.exceptions import InvalidStateError, ValidationError
from app.domain.credentials import CredentialScheme
from app.domain.deployments import MCPAuthConfigRecord, MCPAuthMode
from app.repositories.mcp_access import MCPTokenVerifierRecord
from app.services.deployment.secret_materializer import (
    DeploymentSecretMaterializer,
    materialize_inbound_auth,
)

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ID = UUID(int=1)
ACTOR_ID = UUID(int=9)
NOW = datetime(2026, 8, 27, tzinfo=UTC)


class _Credentials:
    def __init__(self) -> None:
        self.requested: set[UUID] = set()
        self.values: dict[UUID, tuple[CredentialScheme, dict[str, object]]] = {
            UUID(int=101): (CredentialScheme.BEARER, {"token": "bearer-secret"}),
            UUID(int=102): (
                CredentialScheme.BASIC,
                {"username": "matrix-user", "password": "basic-secret"},
            ),
            UUID(int=103): (
                CredentialScheme.API_KEY_HEADER,
                {"value": "header-secret"},
            ),
            UUID(int=104): (
                CredentialScheme.API_KEY_QUERY,
                {"value": "query-secret"},
            ),
            UUID(int=105): (
                CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
                {"client_id": "matrix-client", "client_secret": "oauth-secret"},
            ),
        }

    async def decrypt_many_for_execution(
        self,
        *,
        project_id: UUID,
        credential_ids: set[UUID],
    ) -> dict[UUID, tuple[CredentialScheme, dict[str, object]]]:
        assert project_id == PROJECT_ID
        self.requested = credential_ids
        return {identifier: self.values[identifier] for identifier in credential_ids}


def _manifest() -> MCPManifest:
    return MCPManifest.model_validate_json(
        ROOT.joinpath(
            "tests", "fixtures", "manifests", "pipeline-matrix-3.1-json.json"
        ).read_bytes()
    )


def _auth(mode: MCPAuthMode) -> MCPAuthConfigRecord:
    return MCPAuthConfigRecord(
        project_id=PROJECT_ID,
        mode=mode,
        issuer_url=(
            "https://identity.example.com" if mode is MCPAuthMode.EXTERNAL_OAUTH_OIDC else None
        ),
        audiences=["matrix-api"] if mode is MCPAuthMode.EXTERNAL_OAUTH_OIDC else [],
        required_scopes=["mcp:call"] if mode is MCPAuthMode.EXTERNAL_OAUTH_OIDC else [],
        metadata={},
        updated_by=ACTOR_ID,
        updated_at=NOW,
    )


async def test_bundle_materializes_only_enabled_profile_secrets_with_exact_schemes() -> None:
    credentials = _Credentials()
    materializer = DeploymentSecretMaterializer(
        credentials,  # pyright: ignore[reportArgumentType]
        Settings(env="test"),
    )

    bundle = await materializer.build_bundle(
        project_id=PROJECT_ID,
        hostname="matrix.mcp.example.com",
        manifest=_manifest(),
        auth_config=_auth(MCPAuthMode.DISABLED_DEV),
        token_verifiers=[],
    )

    assert credentials.requested == set(credentials.values)
    assert {value.type for value in bundle.upstream_credentials.values()} == {
        "bearer",
        "basic",
        "api_key",
        "oauth2_client_credentials",
    }
    assert bundle.upstream_credentials[str(UUID(int=101))].token is not None
    basic_username = bundle.upstream_credentials[str(UUID(int=102))].username
    assert basic_username is not None
    assert basic_username.get_secret_value() == "matrix-user"
    assert bundle.inbound_auth.mode == "disabled_dev"


@pytest.mark.parametrize("failure", ["unknown_profile", "non_uuid_reference", "scheme_mismatch"])
async def test_bundle_fails_closed_on_manifest_or_secret_mismatch(failure: str) -> None:
    manifest = _manifest()
    credentials = _Credentials()
    expected: type[Exception]
    if failure == "unknown_profile":
        tool = manifest.tools[0].model_copy(update={"security_profile_ref": "missing"})
        manifest = manifest.model_copy(update={"tools": [tool, *manifest.tools[1:]]})
        expected = ValidationError
    elif failure == "non_uuid_reference":
        profile = manifest.auth_profiles[0].model_copy(update={"credential_ref": "opaque"})
        manifest = manifest.model_copy(
            update={"auth_profiles": [profile, *manifest.auth_profiles[1:]]}
        )
        expected = ValidationError
    else:
        credentials.values[UUID(int=101)] = (
            CredentialScheme.BASIC,
            {"username": "wrong", "password": "wrong"},
        )
        expected = InvalidStateError
    materializer = DeploymentSecretMaterializer(
        credentials,  # pyright: ignore[reportArgumentType]
        Settings(env="test"),
    )

    with pytest.raises(expected):
        await materializer.build_bundle(
            project_id=PROJECT_ID,
            hostname="matrix.mcp.example.com",
            manifest=manifest,
            auth_config=_auth(MCPAuthMode.DISABLED_DEV),
            token_verifiers=[],
        )


def test_inbound_auth_modes_are_complete_and_production_safe() -> None:
    test_settings = Settings(env="test")
    verifier = MCPTokenVerifierRecord(
        id=UUID(int=20),
        token_hash="a" * 64,
        expires_at=None,
    )
    static = materialize_inbound_auth(
        hostname="matrix.mcp.example.com",
        config=_auth(MCPAuthMode.STATIC_BEARER),
        verifiers=[verifier],
        settings=test_settings,
    )
    assert static.mode == "static_bearer"
    assert static.static_tokens[0].sha256 == "a" * 64

    oidc = materialize_inbound_auth(
        hostname="matrix.mcp.example.com",
        config=_auth(MCPAuthMode.EXTERNAL_OAUTH_OIDC),
        verifiers=[],
        settings=test_settings,
    )
    assert oidc.mode == "external_oauth_oidc"
    assert str(oidc.resource_url) == "http://matrix.mcp.example.com/mcp"
    assert oidc.allowed_algorithms == ["RS256", "ES256"]

    production = test_settings.model_copy(update={"env": "production"})
    with pytest.raises(InvalidStateError, match="forbidden in production"):
        materialize_inbound_auth(
            hostname="matrix.mcp.example.com",
            config=_auth(MCPAuthMode.DISABLED_DEV),
            verifiers=[],
            settings=production,
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"jwks_url": 42},
        {"allowed_algorithms": "RS256"},
        {"allowed_algorithms": ["RS256", 42]},
    ],
)
def test_oidc_metadata_is_typed_before_secret_materialization(
    metadata: dict[str, object],
) -> None:
    config = _auth(MCPAuthMode.EXTERNAL_OAUTH_OIDC).model_copy(update={"metadata": metadata})
    with pytest.raises(InvalidStateError, match="OIDC"):
        materialize_inbound_auth(
            hostname="matrix.mcp.example.com",
            config=config,
            verifiers=[],
            settings=Settings(env="test"),
        )
