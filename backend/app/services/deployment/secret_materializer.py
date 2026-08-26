from typing import cast
from uuid import UUID

from mcp_contracts import (
    InboundAuthSecrets,
    MCPManifest,
    RuntimeNetworkPolicy,
    RuntimeSecretBundle,
    StaticTokenDigest,
    UpstreamCredential,
)
from pydantic import AnyHttpUrl, SecretStr

from app.core.config import Settings
from app.core.exceptions import InvalidStateError, ValidationError
from app.domain.credentials import CredentialScheme
from app.domain.deployments import MCPAuthConfigRecord, MCPAuthMode
from app.repositories.mcp_access import MCPTokenVerifierRecord
from app.services.credentials import CredentialService


class DeploymentSecretMaterializer:
    def __init__(self, credentials: CredentialService, settings: Settings) -> None:
        self._credentials = credentials
        self._settings = settings

    async def build_bundle(
        self,
        *,
        project_id: UUID,
        hostname: str,
        manifest: MCPManifest,
        auth_config: MCPAuthConfigRecord | None,
        token_verifiers: list[MCPTokenVerifierRecord],
    ) -> RuntimeSecretBundle:
        references: dict[str, UUID] = {}
        profiles_by_id = {profile.id: profile for profile in manifest.auth_profiles}
        required_profile_ids = {
            tool.security_profile_ref
            for tool in manifest.enabled_tools()
            if tool.security_profile_ref is not None
        }
        for profile_id in required_profile_ids:
            profile = profiles_by_id.get(profile_id)
            if profile is None:
                raise ValidationError("Manifest references an unknown authentication profile")
            if profile.type == "none":
                continue
            if not profile.credential_ref:
                raise ValidationError("Manifest authentication profile has no credential reference")
            try:
                references[profile.credential_ref] = UUID(profile.credential_ref)
            except ValueError as exc:
                raise ValidationError(
                    "Manifest credential references must be immutable credential UUIDs"
                ) from exc
        decrypted = await self._credentials.decrypt_many_for_execution(
            project_id=project_id,
            credential_ids=set(references.values()),
        )
        upstream: dict[str, UpstreamCredential] = {}
        for reference, credential_id in references.items():
            scheme, secret = decrypted[credential_id]
            upstream[reference] = self._runtime_credential(
                manifest,
                reference,
                scheme,
                secret,
                required_profile_ids,
            )
        return RuntimeSecretBundle(
            upstream_credentials=upstream,
            inbound_auth=self._inbound_auth(
                manifest,
                hostname,
                auth_config,
                token_verifiers,
            ),
            network_policy=RuntimeNetworkPolicy(
                allowed_private_hosts=self._settings.runtime_allowed_private_hosts,
                allowed_development_hosts=(
                    self._settings.runtime_allowed_development_hosts
                    if not self._settings.is_production
                    else []
                ),
            ),
        )

    def _runtime_credential(
        self,
        manifest: MCPManifest,
        reference: str,
        scheme: CredentialScheme,
        secret: dict[str, object],
        required_profile_ids: set[str],
    ) -> UpstreamCredential:
        profiles = [
            profile
            for profile in manifest.auth_profiles
            if profile.id in required_profile_ids and profile.credential_ref == reference
        ]
        profile_types = {profile.type for profile in profiles}
        expected: dict[CredentialScheme, tuple[str, str]] = {
            CredentialScheme.BEARER: ("bearer", "bearer"),
            CredentialScheme.API_KEY_HEADER: ("api_key", "header"),
            CredentialScheme.API_KEY_QUERY: ("api_key", "query"),
            CredentialScheme.BASIC: ("basic", "basic"),
            CredentialScheme.OAUTH2_CLIENT_CREDENTIALS: (
                "oauth2_client_credentials",
                "oauth2_client_credentials",
            ),
            CredentialScheme.STATIC_HEADERS: ("static_header", "static_header"),
        }
        runtime_type, required_location = expected[scheme]
        if profile_types != {runtime_type}:
            raise InvalidStateError("Deployment credential scheme does not match the manifest")
        if runtime_type == "api_key" and any(
            profile.location != required_location for profile in profiles
        ):
            raise InvalidStateError("Deployment API-key location does not match the manifest")
        if runtime_type == "bearer":
            return UpstreamCredential(type="bearer", token=SecretStr(self._text(secret, "token")))
        if runtime_type == "api_key":
            return UpstreamCredential(
                type="api_key", api_key=SecretStr(self._text(secret, "value"))
            )
        if runtime_type == "basic":
            return UpstreamCredential(
                type="basic",
                username=SecretStr(self._text(secret, "username")),
                password=SecretStr(self._text(secret, "password")),
            )
        if runtime_type == "oauth2_client_credentials":
            configured_token_url = self._text(secret, "token_url")
            if any(str(profile.token_url) != configured_token_url for profile in profiles):
                raise InvalidStateError("OAuth token endpoint does not match the manifest")
            return UpstreamCredential(
                type="oauth2_client_credentials",
                client_id=SecretStr(self._text(secret, "client_id")),
                client_secret=SecretStr(self._text(secret, "client_secret")),
            )
        raw_headers = secret.get("headers")
        if not isinstance(raw_headers, dict):
            raise InvalidStateError("Static-header deployment credential is malformed")
        header_values = cast(dict[object, object], raw_headers)
        expected_names = {profile.name.lower() for profile in profiles if profile.name}
        available_by_name = {
            str(name).lower(): (str(name), value) for name, value in header_values.items()
        }
        if not expected_names <= set(available_by_name):
            raise InvalidStateError("Static-header deployment credential is incomplete")
        headers = {
            available_by_name[name][0]: SecretStr(self._plain_text(available_by_name[name][1]))
            for name in sorted(expected_names)
        }
        return UpstreamCredential(type="static_header", headers=headers)

    def _inbound_auth(
        self,
        manifest: MCPManifest,
        hostname: str,
        config: MCPAuthConfigRecord | None,
        verifiers: list[MCPTokenVerifierRecord],
    ) -> InboundAuthSecrets:
        mode = config.mode if config is not None else MCPAuthMode.STATIC_BEARER
        manifest_mode = manifest.security.inbound_auth_mode
        expected_manifest_mode = {
            MCPAuthMode.STATIC_BEARER: "static_bearer",
            MCPAuthMode.EXTERNAL_OAUTH_OIDC: "oidc",
            MCPAuthMode.DISABLED_DEV: "none",
        }[mode]
        if manifest_mode != expected_manifest_mode:
            raise InvalidStateError(
                "Build manifest authentication mode does not match project MCP access settings"
            )
        if mode == MCPAuthMode.STATIC_BEARER:
            return InboundAuthSecrets(
                mode="static_bearer",
                static_tokens=[
                    StaticTokenDigest(
                        id=str(verifier.id),
                        sha256=verifier.token_hash,
                        expires_at=verifier.expires_at,
                    )
                    for verifier in verifiers
                ],
            )
        if mode == MCPAuthMode.DISABLED_DEV:
            if self._settings.is_production:
                raise InvalidStateError("Unauthenticated MCP access is forbidden in production")
            return InboundAuthSecrets(mode="disabled_dev")
        if config is None or not config.issuer_url:
            raise InvalidStateError("OIDC access configuration is incomplete")
        scheme = "https" if self._settings.traefik_tls else "http"
        metadata = config.metadata
        jwks_url = metadata.get("jwks_url")
        raw_algorithms = metadata.get("allowed_algorithms", ["RS256", "ES256"])
        if jwks_url is not None and not isinstance(jwks_url, str):
            raise InvalidStateError("OIDC JWKS URL is invalid")
        if not isinstance(raw_algorithms, list):
            raise InvalidStateError("OIDC algorithm allowlist is invalid")
        algorithm_values = cast(list[object], raw_algorithms)
        if not all(isinstance(value, str) for value in algorithm_values):
            raise InvalidStateError("OIDC algorithm allowlist is invalid")
        algorithms = [str(value) for value in algorithm_values]
        return InboundAuthSecrets(
            mode="external_oauth_oidc",
            issuer_url=AnyHttpUrl(config.issuer_url),
            jwks_url=AnyHttpUrl(jwks_url) if jwks_url is not None else None,
            resource_url=AnyHttpUrl(f"{scheme}://{hostname}/mcp"),
            audiences=config.audiences,
            required_scopes=config.required_scopes,
            allowed_algorithms=algorithms,
        )

    @classmethod
    def _text(cls, secret: dict[str, object], name: str) -> str:
        if name not in secret:
            raise InvalidStateError("Deployment credential is incomplete")
        return cls._plain_text(secret[name])

    @staticmethod
    def _plain_text(value: object) -> str:
        if not isinstance(value, str) or not value:
            raise InvalidStateError("Deployment credential contains an invalid secret value")
        return value
