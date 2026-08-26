from collections.abc import Iterable

from mcp_contracts import CanonicalApi, CanonicalSecurityScheme, SecuritySchemeType

from app.core.exceptions import CompilationError
from app.domain.builds import BuildCredentialSnapshot
from app.domain.credentials import CredentialScheme

_COMPATIBLE_SCHEMES: dict[SecuritySchemeType, frozenset[CredentialScheme]] = {
    SecuritySchemeType.HTTP_BEARER: frozenset({CredentialScheme.BEARER}),
    SecuritySchemeType.HTTP_BASIC: frozenset({CredentialScheme.BASIC}),
    SecuritySchemeType.API_KEY: frozenset(
        {CredentialScheme.API_KEY_HEADER, CredentialScheme.API_KEY_QUERY}
    ),
    SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS: frozenset(
        {CredentialScheme.OAUTH2_CLIENT_CREDENTIALS}
    ),
    SecuritySchemeType.STATIC_HEADERS: frozenset({CredentialScheme.STATIC_HEADERS}),
}


def map_credentials(
    canonical: CanonicalApi,
    credentials: Iterable[BuildCredentialSnapshot],
    *,
    excluded_operation_keys: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Resolve source security schemes to frozen credential UUIDs or fail closed."""

    available = list(credentials)
    referenced = {
        name
        for operation in canonical.operations
        if operation.key not in excluded_operation_keys
        for requirement in operation.security
        for name in requirement.scheme_scopes
    }
    result: dict[str, str] = {}
    for scheme_name in sorted(referenced):
        scheme = canonical.security_schemes.get(scheme_name)
        if scheme is None:
            raise CompilationError(f"Security scheme {scheme_name!r} is referenced but undefined")
        candidates = [
            credential for credential in available if _compatible(credential, scheme_name, scheme)
        ]
        explicitly_bound = [
            credential
            for credential in candidates
            if _explicit_scheme_name(credential) == scheme_name.casefold()
        ]
        if explicitly_bound:
            candidates = explicitly_bound
        if len(candidates) != 1:
            reason = "missing" if not candidates else "ambiguous"
            raise CompilationError(
                f"Security scheme {scheme_name!r} has {reason} credential mapping",
                details={
                    "security_scheme": scheme_name,
                    "compatible_credential_ids": [
                        str(item.id) for item in sorted(candidates, key=lambda item: str(item.id))
                    ],
                },
            )
        result[scheme_name] = str(candidates[0].id)
    return result


def _compatible(
    credential: BuildCredentialSnapshot,
    scheme_name: str,
    scheme: CanonicalSecurityScheme,
) -> bool:
    compatible = _COMPATIBLE_SCHEMES.get(scheme.type, frozenset())
    if credential.scheme_type not in compatible:
        return False
    explicit_name = _explicit_scheme_name(credential)
    if explicit_name is not None and explicit_name != scheme_name.casefold():
        return False
    if scheme.type is not SecuritySchemeType.API_KEY:
        return True
    expected_by_location = {
        "header": CredentialScheme.API_KEY_HEADER,
        "query": CredentialScheme.API_KEY_QUERY,
    }
    expected_type = (
        expected_by_location.get(scheme.location) if scheme.location is not None else None
    )
    if credential.scheme_type is not expected_type:
        return False
    configured_name = credential.metadata.get("name")
    return (
        isinstance(configured_name, str)
        and scheme.name is not None
        and configured_name.casefold() == scheme.name.casefold()
    )


def _explicit_scheme_name(credential: BuildCredentialSnapshot) -> str | None:
    value = credential.metadata.get("security_scheme")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().casefold()
