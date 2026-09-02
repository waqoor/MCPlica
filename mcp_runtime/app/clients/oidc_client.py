import asyncio
import json
import time
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.clients.pinned_transport import PolicyAsyncHttpTransport
from app.clients.response_reader import read_bounded_body
from app.executor.errors import (
    UpstreamConnectionError,
    UpstreamTimeoutError,
)
from app.security.url_policy import UpstreamUrlPolicy

_MAX_DOCUMENT_BYTES = 1_000_000
_MAX_JWKS_KEYS = 100
_MIN_FORCED_REFRESH_SECONDS = 30.0
_OIDC_OPERATION_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class _CachedJwks:
    keys: dict[str, dict[str, object]]
    expires_at: float


class OidcJwksClient:
    def __init__(
        self,
        *,
        issuer_url: str,
        configured_jwks_url: str | None,
        policy: UpstreamUrlPolicy,
        tls_verify: bool = True,
        trust_env: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if trust_env:
            raise ValueError("Runtime HTTP clients cannot inherit environment proxies")
        # The issuer is an identifier, not a display URL.  A trailing slash is
        # significant for discovery metadata and JWT ``iss`` validation, so
        # preserve the exact configured value and normalize only the derived
        # well-known endpoint below.
        self._issuer_url = issuer_url
        self._configured_jwks_url = configured_jwks_url
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
        self._cache: _CachedJwks | None = None
        self._lock = asyncio.Lock()
        self._last_refresh = 0.0

    async def get_key(
        self, key_id: str, *, force_refresh: bool = False
    ) -> dict[str, object] | None:
        cache = await self._get_jwks(force_refresh=force_refresh)
        return cache.get(key_id)

    async def _get_jwks(self, *, force_refresh: bool) -> dict[str, dict[str, object]]:
        now = time.monotonic()
        if not force_refresh and self._cache is not None and self._cache.expires_at > now:
            return self._cache.keys
        async with self._lock:
            now = time.monotonic()
            if not force_refresh and self._cache is not None and self._cache.expires_at > now:
                return self._cache.keys
            if force_refresh and now - self._last_refresh < _MIN_FORCED_REFRESH_SECONDS:
                return self._cache.keys if self._cache is not None else {}
            jwks_url = self._configured_jwks_url or await self._discover_jwks_url()
            payload, ttl = await self._get_json(jwks_url)
            raw_keys = payload.get("keys")
            if not isinstance(raw_keys, list):
                raise ValueError("OIDC JWKS response does not contain keys")
            key_values = cast(list[object], raw_keys)
            if len(key_values) > _MAX_JWKS_KEYS:
                raise ValueError("OIDC JWKS response contains too many keys")
            keys: dict[str, dict[str, object]] = {}
            for raw in key_values:
                if not isinstance(raw, dict):
                    continue
                key = cast(dict[str, object], raw)
                key_id = key.get("kid")
                if isinstance(key_id, str) and key_id:
                    if key_id in keys:
                        raise ValueError("OIDC JWKS response contains duplicate key identifiers")
                    keys[key_id] = key
            if not keys:
                raise ValueError("OIDC JWKS response contains no usable keys")
            self._cache = _CachedJwks(keys, time.monotonic() + ttl) if ttl > 0 else None
            self._last_refresh = time.monotonic()
            return keys

    async def _discover_jwks_url(self) -> str:
        issuer = urlsplit(self._issuer_url)
        # OpenID Connect Discovery appends the well-known suffix to the
        # issuer, including any issuer path (unlike RFC 8414 OAuth metadata).
        issuer_path = issuer.path.rstrip("/")
        discovery_path = f"{issuer_path}/.well-known/openid-configuration"
        discovery_url = urlunsplit((issuer.scheme, issuer.netloc, discovery_path, "", ""))
        payload, _ = await self._get_json(discovery_url)
        if payload.get("issuer") != self._issuer_url:
            raise ValueError("OIDC discovery issuer does not match configuration")
        jwks_url = payload.get("jwks_uri")
        if not isinstance(jwks_url, str):
            raise ValueError("OIDC discovery does not provide a JWKS URI")
        return jwks_url

    async def _get_json(self, url: str) -> tuple[dict[str, object], float]:
        await self._policy.validate_configured_destination(url)
        request = self._client.build_request("GET", url, headers={"Accept": "application/json"})
        try:
            async with asyncio.timeout(_OIDC_OPERATION_TIMEOUT_SECONDS):
                try:
                    response = await self._client.send(request, stream=True)
                except httpx.TimeoutException as exc:
                    raise UpstreamTimeoutError() from exc
                except httpx.HTTPError as exc:
                    raise UpstreamConnectionError() from exc
                try:
                    body = await read_bounded_body(response, max_bytes=_MAX_DOCUMENT_BYTES)
                finally:
                    await response.aclose()
        except TimeoutError as exc:
            raise UpstreamTimeoutError() from exc
        if not response.is_success:
            raise ValueError("OIDC metadata endpoint returned an error")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type != "application/json" and not content_type.endswith("+json"):
            raise ValueError("OIDC metadata endpoint returned a non-JSON response")
        try:
            raw_payload: object = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("OIDC metadata endpoint returned invalid JSON") from exc
        if not isinstance(raw_payload, dict):
            raise ValueError("OIDC metadata endpoint returned an invalid document")
        payload = cast(dict[str, object], raw_payload)
        return payload, self._cache_ttl(response.headers.get("cache-control", ""))

    @staticmethod
    def _cache_ttl(cache_control: str) -> float:
        directives = [directive.strip() for directive in cache_control.split(",")]
        for directive in directives:
            name, _, _ = directive.partition("=")
            if name.lower() in {"no-cache", "no-store"}:
                return 0.0
        for directive in directives:
            name, separator, value = directive.partition("=")
            if separator and name.lower() == "max-age" and value.isdigit():
                return min(3_600.0, float(value))
        return 300.0

    async def close(self) -> None:
        await self._client.aclose()
