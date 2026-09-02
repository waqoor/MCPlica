import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import jwt
from jwt.types import Options
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp_contracts import InboundAuthSecrets, RuntimeSecretBundle
from pydantic import AnyHttpUrl

from app.clients.oidc_client import OidcJwksClient
from app.core.config import RuntimeSettings
from app.executor.errors import RuntimeExecutionError


class StaticBearerTokenVerifier(TokenVerifier):
    def __init__(self, config: InboundAuthSecrets) -> None:
        self._tokens = tuple(config.static_tokens)

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 4096:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)
        matched_id: str | None = None
        for verifier in self._tokens:
            digest_matches = hmac.compare_digest(digest, verifier.sha256)
            not_expired = verifier.expires_at is None or verifier.expires_at > now
            if digest_matches and not_expired:
                matched_id = verifier.id
        if matched_id is None:
            return None
        return AccessToken(
            token="verified",
            client_id=matched_id,
            scopes=[],
            expires_at=None,
        )


class OidcKeyProvider(Protocol):
    async def get_key(
        self, key_id: str, *, force_refresh: bool = False
    ) -> dict[str, object] | None: ...

    async def close(self) -> None: ...


class OidcTokenVerifier(TokenVerifier):
    def __init__(self, config: InboundAuthSecrets, client: OidcKeyProvider) -> None:
        assert config.issuer_url is not None
        # OIDC issuer comparison is exact; in particular, trailing-slash and
        # non-trailing-slash issuer identifiers are not interchangeable.
        self._issuer = str(config.issuer_url)
        self._audiences = config.audiences
        self._algorithms = config.allowed_algorithms
        self._client = client

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 16_384:
            return None
        try:
            header = jwt.get_unverified_header(token)
            key_id = header.get("kid")
            algorithm = header.get("alg")
            if (
                not isinstance(key_id, str)
                or not key_id
                or not isinstance(algorithm, str)
                or algorithm not in self._algorithms
            ):
                return None
            key_data = await self._client.get_key(key_id)
            if key_data is None:
                key_data = await self._client.get_key(key_id, force_refresh=True)
            if key_data is None:
                return None
            if key_data.get("use") not in {None, "sig"}:
                return None
            key_operations = key_data.get("key_ops")
            if isinstance(key_operations, list) and "verify" not in key_operations:
                return None
            declared_algorithm = key_data.get("alg")
            if declared_algorithm is not None and declared_algorithm != algorithm:
                return None
            key = jwt.PyJWK.from_dict(key_data, algorithm=algorithm).key
            options: Options = {
                "require": ["exp", "iss", "sub"],
                "verify_aud": bool(self._audiences),
            }
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[algorithm],
                audience=self._audiences or None,
                issuer=self._issuer,
                leeway=30,
                options=options,
            )
        except (jwt.PyJWTError, RuntimeExecutionError, ValueError, TypeError):
            return None
        scopes = _token_scopes(claims.get("scope"))
        subject = claims.get("sub")
        client_id = claims.get("azp") or claims.get("client_id") or subject
        expires_at = claims.get("exp")
        if not isinstance(subject, str) or not isinstance(client_id, str):
            return None
        if not isinstance(expires_at, int | float) or expires_at <= time.time() - 30:
            return None
        return AccessToken(
            token="verified",
            client_id=client_id,
            scopes=scopes,
            expires_at=int(expires_at),
            subject=subject,
            claims={"iss": self._issuer},
        )

    async def close(self) -> None:
        await self._client.close()


def _token_scopes(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part for part in value.split() if part]
    if isinstance(value, list):
        scopes: list[str] = []
        for part in cast(list[object], value):
            if not isinstance(part, str):
                return []
            scopes.append(part)
        return scopes
    return []


@dataclass(frozen=True, slots=True)
class InboundAuthContext:
    verifier: TokenVerifier | None
    settings: AuthSettings | None
    oidc_verifier: OidcTokenVerifier | None = None

    async def close(self) -> None:
        if self.oidc_verifier is not None:
            await self.oidc_verifier.close()


def build_inbound_auth(
    bundle: RuntimeSecretBundle,
    settings: RuntimeSettings,
    *,
    oidc_client: OidcJwksClient | None = None,
) -> InboundAuthContext:
    secrets = bundle.inbound_auth
    if secrets.mode == "static_bearer":
        # The SDK only installs its bearer authentication middleware when auth
        # settings are present. Static tokens do not advertise an OAuth issuer,
        # so the nullable resource URL intentionally suppresses OAuth metadata.
        auth_settings = AuthSettings(
            issuer_url=AnyHttpUrl(settings.public_base_url),
            resource_server_url=None,
            required_scopes=[],
        )
        return InboundAuthContext(StaticBearerTokenVerifier(secrets), auth_settings)
    if secrets.mode == "disabled_dev":
        if not settings.is_development:
            raise ValueError(
                "unauthenticated MCP mode is restricted to explicit development/test mode"
            )
        return InboundAuthContext(None, None)

    if oidc_client is None:
        raise ValueError("OIDC verifier client is required for OIDC mode")
    verifier = OidcTokenVerifier(secrets, oidc_client)
    assert secrets.issuer_url is not None
    assert secrets.resource_url is not None
    expected_resource_url = f"{settings.public_base_url}/mcp"
    if str(secrets.resource_url).rstrip("/") != expected_resource_url:
        raise ValueError("OIDC resource URL must match the published MCP endpoint")
    auth_settings = AuthSettings(
        issuer_url=secrets.issuer_url,
        resource_server_url=secrets.resource_url,
        required_scopes=secrets.required_scopes,
    )
    return InboundAuthContext(verifier, auth_settings, verifier)
