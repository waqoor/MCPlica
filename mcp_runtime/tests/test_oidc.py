import base64
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp_contracts import InboundAuthSecrets, ServerDefinition

from app.auth.inbound import OidcTokenVerifier
from app.clients.oidc_client import OidcJwksClient
from app.security.url_policy import UpstreamUrlPolicy


class _KeyProvider:
    def __init__(self, key: dict[str, object]) -> None:
        self.key = key
        self.refreshes = 0

    async def get_key(
        self, key_id: str, *, force_refresh: bool = False
    ) -> dict[str, object] | None:
        if force_refresh:
            self.refreshes += 1
        return self.key if key_id == self.key["kid"] else None

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_oidc_verifier_enforces_asymmetric_alg_issuer_audience_and_expiry() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()

    def encode_uint(value: int) -> str:
        encoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")

    public_jwk: dict[str, object] = {
        "kty": "RSA",
        "n": encode_uint(public_numbers.n),
        "e": encode_uint(public_numbers.e),
        "kid": "signing-key",
        "use": "sig",
        "alg": "RS256",
    }
    config = InboundAuthSecrets.model_validate(
        {
            "mode": "external_oauth_oidc",
            "issuer_url": "https://issuer.example.com/tenant",
            "resource_url": "https://project.mcp.example.com/mcp",
            "audiences": ["mcplica-project"],
            "required_scopes": ["mcp:invoke"],
            "allowed_algorithms": ["RS256"],
        }
    )
    verifier = OidcTokenVerifier(config, _KeyProvider(public_jwk))
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://issuer.example.com/tenant",
            "sub": "subject-1",
            "aud": "mcplica-project",
            "scope": "mcp:invoke mcp:read",
            "iat": now,
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "signing-key"},
    )
    verified = await verifier.verify_token(token)
    assert verified is not None
    assert verified.client_id == "subject-1"
    assert verified.scopes == ["mcp:invoke", "mcp:read"]

    wrong_audience = jwt.encode(
        {
            "iss": "https://issuer.example.com/tenant",
            "sub": "subject-1",
            "aud": "another-service",
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "signing-key"},
    )
    assert await verifier.verify_token(wrong_audience) is None


@pytest.mark.asyncio
async def test_oidc_discovery_appends_well_known_path_and_rejects_duplicate_kids() -> None:
    requested_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://8.8.8.8/tenant",
                    "jwks_uri": "https://8.8.8.8/tenant/keys",
                },
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            200,
            json={"keys": [{"kid": "duplicate"}, {"kid": "duplicate"}]},
            headers={"content-type": "application/json"},
        )

    policy = UpstreamUrlPolicy(
        [ServerDefinition.model_validate({"id": "issuer", "url": "https://8.8.8.8/tenant"})]
    )
    client = OidcJwksClient(
        issuer_url="https://8.8.8.8/tenant",
        configured_jwks_url=None,
        policy=policy,
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(ValueError, match="duplicate"):
            await client.get_key("duplicate")
    finally:
        await client.close()
    assert requested_paths[0] == "/tenant/.well-known/openid-configuration"


@pytest.mark.parametrize(
    ("cache_control", "expected_ttl"),
    [
        ("no-store, max-age=300", 0.0),
        ("max-age=300, no-cache", 0.0),
        ("max-age=0", 0.0),
        ("max-age=7200", 3_600.0),
        ("public", 300.0),
    ],
)
def test_oidc_cache_control_respects_revalidation_and_bounded_ttl(
    cache_control: str, expected_ttl: float
) -> None:
    assert (
        OidcJwksClient._cache_ttl(cache_control)  # pyright: ignore[reportPrivateUsage]
        == expected_ttl
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("cache_control", ["no-store", "no-cache", "max-age=0"])
async def test_oidc_revalidation_directives_do_not_reuse_jwks(
    cache_control: str,
) -> None:
    requests = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            json={"keys": [{"kid": "signing-key", "kty": "RSA"}]},
            headers={
                "content-type": "application/json",
                "cache-control": cache_control,
            },
        )

    policy = UpstreamUrlPolicy(
        [ServerDefinition.model_validate({"id": "issuer", "url": "https://8.8.8.8/tenant"})]
    )
    client = OidcJwksClient(
        issuer_url="https://8.8.8.8/tenant",
        configured_jwks_url="https://8.8.8.8/tenant/keys",
        policy=policy,
        transport=httpx.MockTransport(handler),
    )
    try:
        assert await client.get_key("signing-key") is not None
        assert await client.get_key("signing-key") is not None
    finally:
        await client.close()
    assert requests == 2
