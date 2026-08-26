import base64
from urllib.parse import parse_qs

import httpx
import pytest
from mcp_contracts import AuthProfile, ServerDefinition, UpstreamCredential

from app.clients.oauth_client import OAuthTokenClient
from app.executor.errors import DestinationPolicyError
from app.security.url_policy import UpstreamUrlPolicy


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_method", ["client_secret_basic", "client_secret_post"])
async def test_oauth_client_credentials_uses_declared_auth_method(auth_method: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode("utf-8"))
        assert form["grant_type"] == ["client_credentials"]
        assert form["scope"] == ["read write"]
        if auth_method == "client_secret_basic":
            expected = base64.b64encode(b"client%3Aid:secret%2Bvalue").decode("ascii")
            assert request.headers["authorization"] == f"Basic {expected}"
            assert "client_id" not in form
        else:
            assert "authorization" not in request.headers
            assert form["client_id"] == ["client:id"]
            assert form["client_secret"] == ["secret+value"]
        return httpx.Response(
            200,
            json={"access_token": "issued-token", "token_type": "Bearer", "expires_in": 120},
            headers={"content-type": "application/json"},
        )

    profile = AuthProfile.model_validate(
        {
            "id": "oauth",
            "type": "oauth2_client_credentials",
            "credential_ref": "oauth-ref",
            "token_url": "https://8.8.8.8/token",
            "scopes": ["read", "write"],
            "token_auth_method": auth_method,
        }
    )
    credential = UpstreamCredential.model_validate(
        {
            "type": "oauth2_client_credentials",
            "client_id": "client:id",
            "client_secret": "secret+value",
        }
    )
    policy = UpstreamUrlPolicy(
        [ServerDefinition.model_validate({"id": "oauth", "url": "https://8.8.8.8"})]
    )
    client = OAuthTokenClient(policy, transport=httpx.MockTransport(handler))
    try:
        token = await client.fetch_client_credentials(profile, credential)
    finally:
        await client.close()
    assert token.value == "issued-token"
    assert token.expires_in_seconds == 120


@pytest.mark.asyncio
async def test_oauth_token_endpoint_requires_https_outside_development() -> None:
    profile = AuthProfile.model_validate(
        {
            "id": "oauth",
            "type": "oauth2_client_credentials",
            "credential_ref": "oauth-ref",
            "token_url": "http://8.8.8.8/token",
        }
    )
    credential = UpstreamCredential.model_validate(
        {
            "type": "oauth2_client_credentials",
            "client_id": "client",
            "client_secret": "secret",
        }
    )
    policy = UpstreamUrlPolicy(
        [ServerDefinition.model_validate({"id": "oauth", "url": "http://8.8.8.8"})]
    )
    client = OAuthTokenClient(policy)
    try:
        with pytest.raises(DestinationPolicyError):
            await client.fetch_client_credentials(profile, credential)
    finally:
        await client.close()
