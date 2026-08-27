from dataclasses import dataclass

from app.domain.credentials import CredentialRecord, CredentialScheme
from app.domain.sources import (
    SecuritySchemeDiscoveryRecord,
    SourceConfigurationDiscoveryRecord,
)


@dataclass(frozen=True, slots=True)
class CredentialMappingReadiness:
    required: bool
    complete: bool
    bound_scheme_names: tuple[str, ...]
    unresolved_operation_keys: tuple[str, ...]


def validate_credential_binding(
    discovery: SourceConfigurationDiscoveryRecord,
    *,
    scheme_type: CredentialScheme,
    metadata: dict[str, object],
) -> None:
    raw_name = metadata.get("security_scheme")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError("Credential metadata must bind a discovered security_scheme")
    name = raw_name.strip()
    scheme = next(
        (candidate for candidate in discovery.security_schemes if candidate.name == name),
        None,
    )
    if scheme is None:
        raise ValueError(f"Source security scheme {name!r} was not discovered")
    if not _compatible_values(scheme_type, metadata, name, scheme, []):
        raise ValueError(
            f"Credential type or metadata is incompatible with source security scheme {name!r}"
        )


def credential_mapping_readiness(
    discovery: SourceConfigurationDiscoveryRecord,
    credentials: list[CredentialRecord],
) -> CredentialMappingReadiness:
    """Evaluate source auth alternatives with the compiler's fail-closed rules."""

    active = [credential for credential in credentials if credential.revoked_at is None]
    schemes = {scheme.name: scheme for scheme in discovery.security_schemes}
    bound: set[str] = set()
    unresolved: list[str] = []
    required = False
    for operation in discovery.security_requirements:
        if operation.anonymous_allowed:
            continue
        required = True
        selected: str | None = None
        for alternative in operation.alternatives:
            # The canonical compiler intentionally rejects combined requirements.
            if len(alternative) != 1:
                continue
            scheme_name, scopes = next(iter(alternative.items()))
            scheme = schemes.get(scheme_name)
            if scheme is None:
                continue
            candidates = [
                credential
                for credential in active
                if _compatible(credential, scheme_name, scheme, scopes)
            ]
            explicit = [
                credential
                for credential in candidates
                if _explicit_scheme_name(credential) == scheme_name.casefold()
            ]
            if explicit:
                candidates = explicit
            if len(candidates) == 1:
                selected = scheme_name
                break
        if selected is None:
            unresolved.append(operation.operation_key)
        else:
            bound.add(selected)
    return CredentialMappingReadiness(
        required=required,
        complete=not unresolved,
        bound_scheme_names=tuple(sorted(bound)),
        unresolved_operation_keys=tuple(sorted(unresolved)),
    )


def _compatible(
    credential: CredentialRecord,
    scheme_name: str,
    scheme: SecuritySchemeDiscoveryRecord,
    required_scopes: list[str],
) -> bool:
    return _compatible_values(
        credential.scheme_type,
        credential.metadata,
        scheme_name,
        scheme,
        required_scopes,
    )


def _compatible_values(
    credential_scheme: CredentialScheme,
    metadata: dict[str, object],
    scheme_name: str,
    scheme: SecuritySchemeDiscoveryRecord,
    required_scopes: list[str],
) -> bool:
    expected = {
        "http_bearer": CredentialScheme.BEARER,
        "http_basic": CredentialScheme.BASIC,
        "oauth2_client_credentials": CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
        "static_headers": CredentialScheme.STATIC_HEADERS,
    }.get(scheme.type)
    if scheme.type == "api_key":
        expected = (
            {
                "header": CredentialScheme.API_KEY_HEADER,
                "query": CredentialScheme.API_KEY_QUERY,
            }.get(scheme.location)
            if scheme.location is not None
            else None
        )
    if expected is None or credential_scheme is not expected:
        return False
    explicit_name = _explicit_scheme_name(metadata)
    if explicit_name is not None and explicit_name != scheme_name.casefold():
        return False
    if scheme.type == "api_key":
        configured_name = metadata.get("name")
        if (
            not isinstance(configured_name, str)
            or scheme.parameter_name is None
            or configured_name.casefold() != scheme.parameter_name.casefold()
        ):
            return False
    if scheme.type == "oauth2_client_credentials":
        advertised = set(scheme.advertised_scopes)
        if not set(required_scopes) <= advertised:
            return False
        raw_default = metadata.get("scope")
        default_scopes = raw_default.split() if isinstance(raw_default, str) else []
        if not set(default_scopes) <= advertised:
            return False
        method = metadata.get("token_auth_method", "client_secret_basic")
        if method not in {"client_secret_basic", "client_secret_post"}:
            return False
    elif required_scopes:
        return False
    return True


def _explicit_scheme_name(
    credential: CredentialRecord | dict[str, object],
) -> str | None:
    metadata = credential.metadata if isinstance(credential, CredentialRecord) else credential
    value = metadata.get("security_scheme")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().casefold()
