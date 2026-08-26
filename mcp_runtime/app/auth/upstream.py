import asyncio
import base64
import time
from dataclasses import dataclass
from typing import Protocol

from mcp_contracts import AuthProfile, MCPManifest, RuntimeSecretBundle, UpstreamCredential

from app.clients.oauth_client import OAuthAccessToken
from app.executor.errors import RuntimeConfigurationError


@dataclass(frozen=True, slots=True)
class AuthInjection:
    headers: tuple[tuple[str, str], ...] = ()
    query: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class _CachedToken:
    value: str
    refresh_at: float


class OAuthTokenProvider(Protocol):
    async def fetch_client_credentials(
        self, profile: AuthProfile, credential: UpstreamCredential
    ) -> OAuthAccessToken: ...

    async def close(self) -> None: ...


class UpstreamAuthManager:
    def __init__(
        self,
        manifest: MCPManifest,
        secret_bundle: RuntimeSecretBundle,
        oauth_client: OAuthTokenProvider,
    ) -> None:
        self._profiles = {profile.id: profile for profile in manifest.auth_profiles}
        self._credentials = secret_bundle.upstream_credentials
        self._oauth_client = oauth_client
        self._tokens: dict[str, _CachedToken] = {}
        self._locks = {profile_id: asyncio.Lock() for profile_id in self._profiles}
        self.validate_configuration(manifest)

    def validate_configuration(self, manifest: MCPManifest) -> None:
        referenced = {
            tool.security_profile_ref
            for tool in manifest.enabled_tools()
            if tool.security_profile_ref is not None
        }
        required_credentials: set[str] = set()
        for profile_id in referenced:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise RuntimeConfigurationError("Manifest references an unknown auth profile")
            if profile.type == "none":
                continue
            credential_ref = profile.credential_ref or ""
            required_credentials.add(credential_ref)
            credential = self._credentials.get(credential_ref)
            if credential is None or credential.type != profile.type:
                raise RuntimeConfigurationError(
                    f"Credential material for auth profile {profile_id!r} is missing or mismatched"
                )
        if set(self._credentials) != required_credentials:
            raise RuntimeConfigurationError(
                "Runtime secret bundle does not exactly match enabled tool credentials"
            )
        for credential_ref in required_credentials:
            profiles = [
                self._profiles[profile_id]
                for profile_id in referenced
                if self._profiles[profile_id].credential_ref == credential_ref
            ]
            credential = self._credentials[credential_ref]
            if credential.type == "static_header":
                expected_names = {
                    profile.name.casefold() for profile in profiles if profile.name is not None
                }
                actual_names = {name.casefold() for name in (credential.headers or {})}
                if actual_names != expected_names:
                    raise RuntimeConfigurationError(
                        "Static-header credential does not exactly match enabled profiles"
                    )

    async def injection_for(self, profile_id: str | None) -> AuthInjection:
        if profile_id is None:
            return AuthInjection()
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise RuntimeConfigurationError("Manifest references an unknown auth profile")
        if profile.type == "none":
            return AuthInjection()
        credential = self._credentials.get(profile.credential_ref or "")
        if credential is None or credential.type != profile.type:
            raise RuntimeConfigurationError()
        return await self._build(profile, credential)

    async def _build(self, profile: AuthProfile, credential: UpstreamCredential) -> AuthInjection:
        if profile.type == "bearer":
            assert credential.token is not None
            return AuthInjection(
                headers=(("Authorization", f"Bearer {credential.token.get_secret_value()}"),)
            )
        if profile.type == "api_key":
            if not profile.name or not profile.location or credential.api_key is None:
                raise RuntimeConfigurationError("API-key auth profile is incomplete")
            value = f"{profile.prefix or ''}{credential.api_key.get_secret_value()}"
            if profile.location == "header":
                return AuthInjection(headers=((profile.name, value),))
            return AuthInjection(query=((profile.name, value),))
        if profile.type == "basic":
            if credential.username is None or credential.password is None:
                raise RuntimeConfigurationError("Basic auth profile is incomplete")
            raw = (
                f"{credential.username.get_secret_value()}:{credential.password.get_secret_value()}"
            )
            encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
            return AuthInjection(headers=(("Authorization", f"Basic {encoded}"),))
        if profile.type == "oauth2_client_credentials":
            token = await self._oauth_token(profile, credential)
            return AuthInjection(headers=(("Authorization", f"Bearer {token}"),))
        if profile.type == "static_header":
            if not profile.name or credential.headers is None:
                raise RuntimeConfigurationError("Static-header auth profile is incomplete")
            header_value = next(
                (
                    value
                    for name, value in credential.headers.items()
                    if name.lower() == profile.name.lower()
                ),
                None,
            )
            if header_value is None:
                raise RuntimeConfigurationError("Static-header credential is missing its value")
            return AuthInjection(headers=((profile.name, header_value.get_secret_value()),))
        raise RuntimeConfigurationError("Unsupported upstream authentication profile")

    async def _oauth_token(self, profile: AuthProfile, credential: UpstreamCredential) -> str:
        profile_id = profile.id
        cached = self._tokens.get(profile_id)
        now = time.monotonic()
        if cached is not None and cached.refresh_at > now:
            return cached.value
        async with self._locks[profile_id]:
            cached = self._tokens.get(profile_id)
            now = time.monotonic()
            if cached is not None and cached.refresh_at > now:
                return cached.value
            token = await self._oauth_client.fetch_client_credentials(profile, credential)
            self._tokens[profile_id] = self._cache_entry(token)
            return token.value

    @staticmethod
    def _cache_entry(token: OAuthAccessToken) -> _CachedToken:
        safety_margin = min(30.0, max(1.0, token.expires_in_seconds * 0.1))
        return _CachedToken(
            value=token.value,
            refresh_at=time.monotonic() + max(1.0, token.expires_in_seconds - safety_margin),
        )

    async def close(self) -> None:
        await self._oauth_client.close()
