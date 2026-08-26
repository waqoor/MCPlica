import json
import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


class UpstreamCredential(BaseModel):
    """Secret-only runtime credential material keyed by manifest credential_ref."""

    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "bearer",
        "api_key",
        "basic",
        "oauth2_client_credentials",
        "static_header",
    ]
    token: SecretStr | None = None
    api_key: SecretStr | None = None
    username: SecretStr | None = None
    password: SecretStr | None = None
    client_id: SecretStr | None = None
    client_secret: SecretStr | None = None
    headers: dict[str, SecretStr] | None = None

    @model_validator(mode="after")
    def validate_exact_secret_shape(self) -> "UpstreamCredential":
        required: dict[str, set[str]] = {
            "bearer": {"token"},
            "api_key": {"api_key"},
            "basic": {"username", "password"},
            "oauth2_client_credentials": {"client_id", "client_secret"},
            "static_header": {"headers"},
        }
        present = {
            name
            for name in (
                "token",
                "api_key",
                "username",
                "password",
                "client_id",
                "client_secret",
                "headers",
            )
            if getattr(self, name) is not None
        }
        if present != required[self.type]:
            raise ValueError(f"{self.type} credential secret shape is invalid")
        for field_name in present - {"headers"}:
            value = getattr(self, field_name)
            if isinstance(value, SecretStr) and not value.get_secret_value():
                raise ValueError(f"{self.type} credential contains an empty secret")
        if (
            self.type == "basic"
            and self.username is not None
            and ":" in self.username.get_secret_value()
        ):
            raise ValueError("Basic-auth usernames cannot contain a colon")
        if self.headers is not None:
            lowered: set[str] = set()
            for name, value in self.headers.items():
                if not _HEADER_NAME.fullmatch(name) or name.lower() in lowered:
                    raise ValueError("static secret headers contain an invalid or duplicate name")
                if not value.get_secret_value() or any(
                    character in value.get_secret_value() for character in "\r\n\x00"
                ):
                    raise ValueError("static secret header value is empty or invalid")
                lowered.add(name.lower())
        return self


class StaticTokenDigest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=128)
    sha256: str
    expires_at: datetime | None = None

    @field_validator("sha256")
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        normalized = value.removeprefix("sha256:").lower()
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError("token verifier must be a SHA-256 digest")
        return normalized

    @field_validator("id")
    @classmethod
    def valid_identifier(cls, value: str) -> str:
        if any(character in value for character in "\r\n\x00"):
            raise ValueError("token verifier identifier contains forbidden characters")
        return value

    @field_validator("expires_at")
    @classmethod
    def expiration_has_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("token verifier expiration must include a timezone")
        return value


class InboundAuthSecrets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["static_bearer", "external_oauth_oidc", "disabled_dev"]
    static_tokens: list[StaticTokenDigest] = Field(default_factory=list[StaticTokenDigest])
    issuer_url: AnyHttpUrl | None = None
    jwks_url: AnyHttpUrl | None = None
    resource_url: AnyHttpUrl | None = None
    audiences: list[str] = Field(default_factory=list)
    required_scopes: list[str] = Field(default_factory=list)
    allowed_algorithms: list[str] = Field(default_factory=list)

    @field_validator("audiences", "required_scopes", "allowed_algorithms")
    @classmethod
    def normalize_string_sets(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if not item or len(item) > 512 or any(character in item for character in "\r\n\x00"):
                raise ValueError("inbound authentication values are invalid")
            if item not in normalized:
                normalized.append(item)
        if len(normalized) > 100:
            raise ValueError("inbound authentication contains too many values")
        return normalized

    @model_validator(mode="after")
    def mode_configuration_is_complete(self) -> "InboundAuthSecrets":
        token_ids = [token.id for token in self.static_tokens]
        if len(token_ids) != len(set(token_ids)):
            raise ValueError("static bearer token verifier identifiers must be unique")
        if self.mode == "static_bearer":
            if not self.static_tokens:
                raise ValueError("static bearer mode requires at least one token verifier")
            if (
                self.issuer_url
                or self.jwks_url
                or self.resource_url
                or self.audiences
                or self.required_scopes
                or self.allowed_algorithms
            ):
                raise ValueError("static bearer mode cannot contain OIDC configuration")
        elif self.mode == "external_oauth_oidc":
            if not self.issuer_url or not self.resource_url or not self.audiences:
                raise ValueError("OIDC mode requires issuer, resource URL, and audience")
            if self.static_tokens:
                raise ValueError("OIDC mode cannot contain static token verifiers")
            permitted = {
                "RS256",
                "RS384",
                "RS512",
                "PS256",
                "PS384",
                "PS512",
                "ES256",
                "ES384",
                "ES512",
                "EdDSA",
            }
            if not self.allowed_algorithms or not set(self.allowed_algorithms) <= permitted:
                raise ValueError("OIDC algorithms must be an explicit asymmetric allowlist")
        elif (
            self.static_tokens
            or self.issuer_url
            or self.jwks_url
            or self.resource_url
            or self.audiences
            or self.required_scopes
            or self.allowed_algorithms
        ):
            raise ValueError("disabled authentication mode cannot contain verifier material")
        return self


class RuntimeNetworkPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_private_hosts: list[str] = Field(default_factory=list)
    allowed_development_hosts: list[str] = Field(default_factory=list)

    @field_validator("allowed_private_hosts", "allowed_development_hosts")
    @classmethod
    def normalize_host_allowlist(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            if (
                not value
                or "://" in value
                or any(character in value for character in "/?#@\\\r\n\x00")
            ):
                raise ValueError("runtime network allowlists contain invalid host names")
            parsed = urlsplit(f"//{value}")
            if not parsed.hostname or parsed.port is not None:
                raise ValueError("runtime network allowlists contain invalid host names")
            try:
                host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
            except UnicodeError as exc:
                raise ValueError("runtime network allowlists contain invalid host names") from exc
            if host not in normalized:
                normalized.append(host)
        return normalized


class RuntimeSecretBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["mcplica-runtime-secrets/v1"] = "mcplica-runtime-secrets/v1"
    upstream_credentials: dict[str, UpstreamCredential] = Field(default_factory=dict)
    inbound_auth: InboundAuthSecrets
    network_policy: RuntimeNetworkPolicy = Field(default_factory=RuntimeNetworkPolicy)

    @field_validator("upstream_credentials")
    @classmethod
    def validate_credential_references(
        cls, values: dict[str, UpstreamCredential]
    ) -> dict[str, UpstreamCredential]:
        for reference in values:
            if (
                not reference
                or len(reference) > 200
                or any(character in reference for character in "\r\n\x00")
            ):
                raise ValueError("runtime credential reference is invalid")
        return values

    def serialize_for_secret_mount(self) -> bytes:
        """Serialize plaintext only at the deployment-worker secret-mount boundary."""
        payload = self.model_dump(mode="json", exclude={"upstream_credentials"})
        credentials: dict[str, object] = {}
        for reference, credential in self.upstream_credentials.items():
            item: dict[str, object] = {"type": credential.type}
            for field_name in (
                "token",
                "api_key",
                "username",
                "password",
                "client_id",
                "client_secret",
            ):
                value = getattr(credential, field_name)
                if isinstance(value, SecretStr):
                    item[field_name] = value.get_secret_value()
            if credential.headers is not None:
                item["headers"] = {
                    name: value.get_secret_value() for name, value in credential.headers.items()
                }
            credentials[reference] = item
        payload["upstream_credentials"] = credentials
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
