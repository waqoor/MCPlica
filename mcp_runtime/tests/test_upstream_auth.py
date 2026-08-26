import base64
from pathlib import Path

import pytest
from mcp_contracts import AuthProfile, MCPManifest, RuntimeSecretBundle, UpstreamCredential
from pydantic import SecretStr

from app.auth.upstream import UpstreamAuthManager
from app.clients.oauth_client import OAuthAccessToken
from app.executor.errors import RuntimeConfigurationError


class _OAuthClient:
    calls = 0

    async def fetch_client_credentials(
        self, profile: AuthProfile, credential: UpstreamCredential
    ) -> OAuthAccessToken:
        del profile, credential
        self.calls += 1
        return OAuthAccessToken("oauth-access-token", 300)

    async def close(self) -> None:
        return None


def _fixture() -> MCPManifest:
    path = Path(__file__).parents[2] / "tests" / "fixtures" / "manifests" / "petstore.json"
    return MCPManifest.model_validate_json(path.read_bytes())


@pytest.mark.asyncio
async def test_all_upstream_auth_modes_inject_only_secret_bundle_values() -> None:
    profiles = [
        AuthProfile(id="bearer", type="bearer", credential_ref="bearer-ref"),
        AuthProfile(
            id="header-key",
            type="api_key",
            credential_ref="header-key-ref",
            location="header",
            name="X-API-Key",
            prefix="Key ",
        ),
        AuthProfile(
            id="query-key",
            type="api_key",
            credential_ref="query-key-ref",
            location="query",
            name="api_key",
        ),
        AuthProfile(id="basic", type="basic", credential_ref="basic-ref"),
        AuthProfile.model_validate(
            {
                "id": "oauth",
                "type": "oauth2_client_credentials",
                "credential_ref": "oauth-ref",
                "token_url": "https://auth.example.com/token",
                "scopes": ["read", "write"],
            }
        ),
        AuthProfile(
            id="static",
            type="static_header",
            credential_ref="static-ref",
            name="X-Product-Secret",
        ),
    ]
    template = _fixture().tools[0]
    tools = [
        template.model_copy(update={"name": f"tool_{index}", "security_profile_ref": profile.id})
        for index, profile in enumerate(profiles)
    ]
    manifest = _fixture().model_copy(update={"auth_profiles": profiles, "tools": tools})
    bundle = RuntimeSecretBundle.model_validate(
        {
            "upstream_credentials": {
                "bearer-ref": {"type": "bearer", "token": "bearer-value"},
                "header-key-ref": {"type": "api_key", "api_key": "header-value"},
                "query-key-ref": {"type": "api_key", "api_key": "query-value"},
                "basic-ref": {
                    "type": "basic",
                    "username": "runtime-user",
                    "password": "runtime-password",
                },
                "oauth-ref": {
                    "type": "oauth2_client_credentials",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                },
                "static-ref": {
                    "type": "static_header",
                    "headers": {"X-Product-Secret": "static-value"},
                },
            },
            "inbound_auth": {
                "mode": "static_bearer",
                "static_tokens": [{"id": "inbound", "sha256": "1" * 64}],
            },
        }
    )
    oauth = _OAuthClient()
    manager = UpstreamAuthManager(manifest, bundle, oauth)
    try:
        bearer = await manager.injection_for("bearer")
        header_key = await manager.injection_for("header-key")
        query_key = await manager.injection_for("query-key")
        basic = await manager.injection_for("basic")
        first_oauth = await manager.injection_for("oauth")
        second_oauth = await manager.injection_for("oauth")
        static = await manager.injection_for("static")
    finally:
        await manager.close()

    assert bearer.headers == (("Authorization", "Bearer bearer-value"),)
    assert header_key.headers == (("X-API-Key", "Key header-value"),)
    assert query_key.query == (("api_key", "query-value"),)
    expected_basic = base64.b64encode(b"runtime-user:runtime-password").decode("ascii")
    assert basic.headers == (("Authorization", f"Basic {expected_basic}"),)
    assert first_oauth.headers == (("Authorization", "Bearer oauth-access-token"),)
    assert second_oauth == first_oauth
    assert oauth.calls == 1
    assert static.headers == (("X-Product-Secret", "static-value"),)


def test_static_header_bundle_rejects_unused_secret_values() -> None:
    profile = AuthProfile(
        id="static",
        type="static_header",
        credential_ref="static-ref",
        name="X-Expected",
    )
    tool = _fixture().tools[0].model_copy(update={"security_profile_ref": profile.id})
    manifest = _fixture().model_copy(update={"auth_profiles": [profile], "tools": [tool]})
    bundle = RuntimeSecretBundle.model_validate(
        {
            "upstream_credentials": {
                "static-ref": UpstreamCredential(
                    type="static_header",
                    headers={
                        "X-Expected": SecretStr("expected"),
                        "X-Unused": SecretStr("must-not-be-mounted"),
                    },
                )
            },
            "inbound_auth": {
                "mode": "static_bearer",
                "static_tokens": [{"id": "inbound", "sha256": "2" * 64}],
            },
        }
    )
    with pytest.raises(RuntimeConfigurationError, match="exactly match"):
        UpstreamAuthManager(manifest, bundle, _OAuthClient())
