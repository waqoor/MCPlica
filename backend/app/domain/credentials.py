import re
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.deployments import RuntimeEffectState


class CredentialScheme(StrEnum):
    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    API_KEY_QUERY = "api_key_query"
    BASIC = "basic"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    STATIC_HEADERS = "static_headers"


_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_FORBIDDEN_STATIC_HEADERS = {
    "connection",
    "content-length",
    "content-type",
    "cookie",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def credential_secret_aad(project_id: UUID, credential_id: UUID, scheme: CredentialScheme) -> bytes:
    return (f"project:{project_id}:credential:{credential_id}:scheme:{scheme.value}").encode()


def validate_credential_secret(
    scheme: CredentialScheme,
    secret: dict[str, object],
    metadata: Mapping[str, object],
) -> None:
    allowed_metadata = {"security_scheme"}
    if scheme in {CredentialScheme.API_KEY_HEADER, CredentialScheme.API_KEY_QUERY}:
        allowed_metadata.add("name")
    if scheme is CredentialScheme.OAUTH2_CLIENT_CREDENTIALS:
        allowed_metadata.update({"scope", "token_auth_method"})
    unknown_metadata = set(metadata) - allowed_metadata
    if unknown_metadata:
        raise ValueError(
            "unexpected public credential metadata: " + ", ".join(sorted(unknown_metadata))
        )
    for name, raw_value in metadata.items():
        if (
            not isinstance(raw_value, str)
            or not raw_value.strip()
            or len(raw_value) > 200
            or any(character in raw_value for character in "\r\n\x00")
        ):
            raise ValueError(f"credential metadata {name} must be non-empty safe text")
    expected: dict[CredentialScheme, set[str]] = {
        CredentialScheme.BEARER: {"token"},
        CredentialScheme.API_KEY_HEADER: {"value"},
        CredentialScheme.API_KEY_QUERY: {"value"},
        CredentialScheme.BASIC: {"username", "password"},
        CredentialScheme.OAUTH2_CLIENT_CREDENTIALS: {
            "client_id",
            "client_secret",
        },
        CredentialScheme.STATIC_HEADERS: {"headers"},
    }
    required = expected[scheme]
    supplied = set(secret)
    allowed = required
    if not required <= supplied:
        raise ValueError(f"{scheme.value} credential requires: {', '.join(sorted(required))}")
    if supplied - allowed:
        raise ValueError(
            f"unexpected secret fields for {scheme.value}: " + ", ".join(sorted(supplied - allowed))
        )
    for name in supplied - {"headers"}:
        value = secret[name]
        if not isinstance(value, str) or not value or len(value) > 10_000:
            raise ValueError(f"credential field {name} must be non-empty text")
    if scheme is CredentialScheme.BASIC:
        username = secret["username"]
        if isinstance(username, str) and ":" in username:
            raise ValueError("Basic-auth usernames cannot contain a colon")
    if scheme in {CredentialScheme.BEARER, CredentialScheme.API_KEY_HEADER}:
        secret_field = "token" if scheme is CredentialScheme.BEARER else "value"
        value = secret[secret_field]
        if isinstance(value, str) and any(character in value for character in "\r\n\x00"):
            raise ValueError(f"credential field {secret_field} contains unsafe characters")
    if scheme in {CredentialScheme.API_KEY_HEADER, CredentialScheme.API_KEY_QUERY}:
        name = metadata.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("API key credentials require non-secret metadata.name")
        if scheme is CredentialScheme.API_KEY_HEADER and (
            not _HEADER_NAME.fullmatch(name) or name.casefold() in _FORBIDDEN_STATIC_HEADERS
        ):
            raise ValueError("API key header name is invalid or forbidden")
    if scheme is CredentialScheme.OAUTH2_CLIENT_CREDENTIALS:
        method = metadata.get("token_auth_method", "client_secret_basic")
        if method not in {"client_secret_basic", "client_secret_post"}:
            raise ValueError("OAuth token_auth_method is invalid")
        raw_scope = metadata.get("scope")
        if raw_scope is not None:
            if not isinstance(raw_scope, str):
                raise ValueError("OAuth scope metadata must be text")
            scopes = raw_scope.split()
            if not scopes or len(scopes) != len(set(scopes)) or len(scopes) > 100:
                raise ValueError("OAuth scope metadata must contain unique scope tokens")
            if any(len(scope) > 200 for scope in scopes):
                raise ValueError("OAuth scope metadata contains an invalid scope token")
    if scheme is CredentialScheme.STATIC_HEADERS:
        raw_headers = secret.get("headers")
        if not isinstance(raw_headers, dict) or not raw_headers:
            raise ValueError("static_headers credentials require at least one header")
        header_values = cast(dict[object, object], raw_headers)
        if len(header_values) > 64:
            raise ValueError("static_headers credentials exceed the header-count limit")
        total_value_chars = 0
        normalized_names: set[str] = set()
        for raw_name, raw_value in header_values.items():
            if not isinstance(raw_name, str) or not _HEADER_NAME.fullmatch(raw_name):
                raise ValueError("static credential header name is invalid")
            normalized_name = raw_name.casefold()
            if normalized_name in normalized_names:
                raise ValueError("static credential header names must be unique ignoring case")
            if normalized_name in _FORBIDDEN_STATIC_HEADERS:
                raise ValueError(f"static credential header {raw_name!r} is forbidden")
            if (
                not isinstance(raw_value, str)
                or not raw_value
                or len(raw_value) > 10_000
                or any(character in raw_value for character in "\r\n\x00")
            ):
                raise ValueError("static credential header values must be non-empty text")
            normalized_names.add(normalized_name)
            total_value_chars += len(raw_value)
        if total_value_chars > 100_000:
            raise ValueError("static_headers credentials exceed the total value-size limit")


class CredentialRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    name: str
    scheme_type: CredentialScheme
    key_version: str
    metadata: dict[str, object]
    created_by: UUID
    created_at: datetime
    rotated_at: datetime | None
    revoked_at: datetime | None
    runtime_effect_state: RuntimeEffectState = RuntimeEffectState.EFFECTIVE
    runtime_command_id: UUID | None = None
    runtime_error_code: str | None = None
