import asyncio
import base64
import json
import math
from dataclasses import dataclass
from typing import cast
from urllib.parse import quote_plus

import httpx
from mcp_contracts import AuthProfile, UpstreamCredential

from app.clients.pinned_transport import PolicyAsyncHttpTransport
from app.clients.response_reader import read_bounded_body
from app.executor.errors import (
    UpstreamAuthenticationError,
    UpstreamConnectionError,
    UpstreamTimeoutError,
)
from app.security.url_policy import UpstreamUrlPolicy

_MAX_TOKEN_RESPONSE_BYTES = 1_000_000
_TOKEN_OPERATION_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class OAuthAccessToken:
    value: str
    expires_in_seconds: float


class OAuthTokenClient:
    def __init__(
        self,
        policy: UpstreamUrlPolicy,
        *,
        tls_verify: bool = True,
        trust_env: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if trust_env:
            raise ValueError("Runtime HTTP clients cannot inherit environment proxies")
        self._policy = policy
        effective_transport = transport or PolicyAsyncHttpTransport(
            policy,
            verify=tls_verify,
            max_connections=10,
            max_keepalive_connections=5,
        )
        self._client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(connect=10.0, read=20.0, write=20.0, pool=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            trust_env=False,
            transport=effective_transport,
        )

    async def fetch_client_credentials(
        self, profile: AuthProfile, credential: UpstreamCredential
    ) -> OAuthAccessToken:
        if (
            profile.token_url is None
            or credential.client_id is None
            or credential.client_secret is None
        ):
            raise UpstreamAuthenticationError()
        token_url = str(profile.token_url)
        await self._policy.validate_configured_destination(token_url)
        await self._policy.validate_before_connect(token_url)
        client_id = credential.client_id.get_secret_value()
        client_secret = credential.client_secret.get_secret_value()
        headers = {"Accept": "application/json"}
        form: list[tuple[str, str]] = [("grant_type", "client_credentials")]
        if profile.scopes:
            form.append(("scope", " ".join(profile.scopes)))
        if profile.token_auth_method == "client_secret_basic":
            encoded_client_id = quote_plus(client_id, safe="")
            encoded_client_secret = quote_plus(client_secret, safe="")
            basic = base64.b64encode(
                f"{encoded_client_id}:{encoded_client_secret}".encode()
            ).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"
        else:
            form.extend((("client_id", client_id), ("client_secret", client_secret)))
        request = self._client.build_request(
            "POST",
            token_url,
            headers=headers,
            data=dict(form),
        )
        try:
            async with asyncio.timeout(_TOKEN_OPERATION_TIMEOUT_SECONDS):
                try:
                    response = await self._client.send(request, stream=True)
                except httpx.TimeoutException as exc:
                    raise UpstreamTimeoutError() from exc
                except httpx.HTTPError as exc:
                    raise UpstreamConnectionError() from exc
                try:
                    body = await read_bounded_body(response, max_bytes=_MAX_TOKEN_RESPONSE_BYTES)
                finally:
                    await response.aclose()
        except TimeoutError as exc:
            raise UpstreamTimeoutError() from exc
        if not response.is_success:
            raise UpstreamAuthenticationError()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type != "application/json" and not content_type.endswith("+json"):
            raise UpstreamAuthenticationError()
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpstreamAuthenticationError() from exc
        if not isinstance(payload, dict):
            raise UpstreamAuthenticationError()
        token_payload = cast(dict[str, object], payload)
        token = token_payload.get("access_token")
        token_type = token_payload.get("token_type", "Bearer")
        expires_in = token_payload.get("expires_in", 300)
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 16_384
            or not isinstance(token_type, str)
            or token_type.lower() != "bearer"
            or not isinstance(expires_in, int | float)
            or isinstance(expires_in, bool)
            or not math.isfinite(float(expires_in))
            or expires_in <= 0
        ):
            raise UpstreamAuthenticationError()
        return OAuthAccessToken(token, min(float(expires_in), 86_400.0))

    async def close(self) -> None:
        await self._client.aclose()
