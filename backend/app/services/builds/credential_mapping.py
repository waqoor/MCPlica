from collections.abc import Iterable
from typing import Literal, cast

from mcp_contracts import CanonicalApi, CanonicalSecurityScheme, SecuritySchemeType

from app.core.exceptions import CompilationError
from app.domain.builds import BuildCredentialSnapshot, BuildSecuritySelection
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
) -> dict[str, BuildSecuritySelection]:
    """Choose one executable auth alternative per operation or fail closed."""

    available = list(credentials)
    result: dict[str, BuildSecuritySelection] = {}
    for operation in canonical.operations:
        if operation.key in excluded_operation_keys or not operation.security:
            continue
        if any(not requirement.scheme_scopes for requirement in operation.security):
            # An explicit empty requirement means anonymous access is permitted.
            continue
        alternative_failures: list[dict[str, object]] = []
        for requirement in operation.security:
            if len(requirement.scheme_scopes) != 1:
                alternative_failures.append({"reason": "combined_requirement_unsupported"})
                continue
            scheme_name, required_scopes = next(iter(requirement.scheme_scopes.items()))
            scheme = canonical.security_schemes.get(scheme_name)
            if scheme is None:
                alternative_failures.append({"security_scheme": scheme_name, "reason": "undefined"})
                continue
            candidates = [
                credential
                for credential in available
                if _compatible(credential, scheme_name, scheme)
            ]
            explicitly_bound = [
                credential
                for credential in candidates
                if _explicit_scheme_name(credential) == scheme_name.casefold()
            ]
            if explicitly_bound:
                candidates = explicitly_bound
            if len(candidates) != 1:
                alternative_failures.append(
                    {
                        "security_scheme": scheme_name,
                        "reason": "missing" if not candidates else "ambiguous",
                        "compatible_credential_ids": [
                            str(item.id)
                            for item in sorted(candidates, key=lambda item: str(item.id))
                        ],
                    }
                )
                continue
            credential = candidates[0]
            result[operation.key] = _selection(
                scheme_name,
                scheme,
                credential,
                required_scopes,
            )
            break
        else:
            reasons = {str(item.get("reason")) for item in alternative_failures}
            summary = "ambiguous" if "ambiguous" in reasons else "missing"
            raise CompilationError(
                f"Operation {operation.key!r} has no executable credential mapping ({summary})",
                details={
                    "operation_key": operation.key,
                    "alternatives": alternative_failures,
                },
            )
    return result


def _selection(
    scheme_name: str,
    scheme: CanonicalSecurityScheme,
    credential: BuildCredentialSnapshot,
    required_scopes: list[str],
) -> BuildSecuritySelection:
    scopes: list[str] = []
    method: Literal["client_secret_basic", "client_secret_post"] = "client_secret_basic"
    if scheme.type is SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS:
        advertised = set(scheme.scopes)
        unknown = set(required_scopes) - advertised
        if unknown:
            raise CompilationError(
                f"OAuth security scheme {scheme_name!r} requests unadvertised scopes",
                details={"security_scheme": scheme_name, "scopes": sorted(unknown)},
            )
        raw_default_scope = credential.metadata.get("scope")
        default_scopes = raw_default_scope.split() if isinstance(raw_default_scope, str) else []
        unknown_defaults = set(default_scopes) - advertised
        if unknown_defaults:
            raise CompilationError(
                f"OAuth credential for {scheme_name!r} configures unadvertised scopes",
                details={"security_scheme": scheme_name, "scopes": sorted(unknown_defaults)},
            )
        scopes = sorted(set(required_scopes or default_scopes))
        raw_method = credential.metadata.get("token_auth_method", "client_secret_basic")
        if raw_method not in {"client_secret_basic", "client_secret_post"}:
            raise CompilationError(
                f"OAuth credential for {scheme_name!r} has an invalid token auth method"
            )
        method = cast(Literal["client_secret_basic", "client_secret_post"], raw_method)
    elif required_scopes:
        raise CompilationError(f"Non-OAuth security scheme {scheme_name!r} cannot request scopes")
    return BuildSecuritySelection(
        scheme_name=scheme_name,
        credential_ref=str(credential.id),
        scopes=scopes,
        token_auth_method=method,
    )


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
