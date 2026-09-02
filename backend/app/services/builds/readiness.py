from dataclasses import dataclass
from uuid import UUID

from app.domain.credentials import CredentialRecord, CredentialScheme
from app.domain.sources import (
    SecuritySchemeDiscoveryRecord,
    SourceConfigurationDiscoveryRecord,
)
from app.services.builds.auth_selection import (
    AuthSchemeSpec,
    CredentialCandidate,
    credential_is_compatible,
    select_auth_alternative,
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
    if not credential_is_compatible(
        CredentialCandidate(UUID(int=0), scheme_type, metadata),
        _scheme_spec(scheme),
        [],
    ):
        raise ValueError(
            f"Credential type or metadata is incompatible with source security scheme {name!r}"
        )


def credential_mapping_readiness(
    discovery: SourceConfigurationDiscoveryRecord,
    credentials: list[CredentialRecord],
) -> CredentialMappingReadiness:
    """Evaluate source auth alternatives with the compiler's fail-closed rules."""

    active = [
        CredentialCandidate(credential.id, credential.scheme_type, credential.metadata)
        for credential in credentials
        if credential.revoked_at is None
    ]
    schemes = {scheme.name: _scheme_spec(scheme) for scheme in discovery.security_schemes}
    bound: set[str] = set()
    unresolved: list[str] = []
    required = False
    for operation in discovery.security_requirements:
        if operation.anonymous_allowed:
            continue
        required = True
        selection, _rejections = select_auth_alternative(
            operation.alternatives,
            schemes,
            active,
        )
        if selection is None:
            unresolved.append(operation.operation_key)
        else:
            bound.add(selection.scheme_name)
    return CredentialMappingReadiness(
        required=required,
        complete=not unresolved,
        bound_scheme_names=tuple(sorted(bound)),
        unresolved_operation_keys=tuple(sorted(unresolved)),
    )


def _scheme_spec(scheme: SecuritySchemeDiscoveryRecord) -> AuthSchemeSpec:
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
    return AuthSchemeSpec(
        name=scheme.name,
        expected_credential_scheme=expected,
        parameter_name=scheme.parameter_name if scheme.type == "api_key" else None,
        advertised_scopes=frozenset(scheme.advertised_scopes),
        oauth=scheme.type == "oauth2_client_credentials",
    )
