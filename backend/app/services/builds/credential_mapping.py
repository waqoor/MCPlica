from collections.abc import Iterable

from mcp_contracts import CanonicalApi, CanonicalSecurityScheme, SecuritySchemeType

from app.core.exceptions import CompilationError
from app.domain.builds import BuildCredentialSnapshot, BuildSecuritySelection
from app.domain.credentials import CredentialScheme
from app.services.builds.auth_selection import (
    AuthSchemeSpec,
    CredentialCandidate,
    select_auth_alternative,
)


def map_credentials(
    canonical: CanonicalApi,
    credentials: Iterable[BuildCredentialSnapshot],
    *,
    excluded_operation_keys: frozenset[str] = frozenset(),
) -> dict[str, BuildSecuritySelection]:
    """Choose one executable auth alternative per operation or fail closed."""

    available = [
        CredentialCandidate(item.id, item.scheme_type, item.metadata) for item in credentials
    ]
    schemes = {
        name: _scheme_spec(name, scheme) for name, scheme in canonical.security_schemes.items()
    }
    result: dict[str, BuildSecuritySelection] = {}
    for operation in canonical.operations:
        if operation.key in excluded_operation_keys or not operation.security:
            continue
        if any(not requirement.scheme_scopes for requirement in operation.security):
            # An explicit empty requirement means anonymous access is permitted.
            continue
        selection, rejections = select_auth_alternative(
            [dict(requirement.scheme_scopes) for requirement in operation.security],
            schemes,
            available,
        )
        if selection is None:
            alternative_failures = [
                {
                    "reason": rejection.reason,
                    **(
                        {"security_scheme": rejection.security_scheme}
                        if rejection.security_scheme is not None
                        else {}
                    ),
                    **(
                        {
                            "compatible_credential_ids": [
                                str(identifier)
                                for identifier in rejection.compatible_credential_ids
                            ]
                        }
                        if rejection.compatible_credential_ids
                        else {}
                    ),
                }
                for rejection in rejections
            ]
            reasons = {rejection.reason for rejection in rejections}
            summary = "ambiguous" if "ambiguous" in reasons else "missing"
            raise CompilationError(
                f"Operation {operation.key!r} has no executable credential mapping ({summary})",
                details={
                    "operation_key": operation.key,
                    "alternatives": alternative_failures,
                },
            )
        result[operation.key] = BuildSecuritySelection(
            scheme_name=selection.scheme_name,
            credential_ref=str(selection.credential_id),
            scopes=list(selection.scopes),
            token_auth_method=selection.token_auth_method,
        )
    return result


def _scheme_spec(
    scheme_name: str,
    scheme: CanonicalSecurityScheme,
) -> AuthSchemeSpec:
    expected = {
        SecuritySchemeType.HTTP_BEARER: CredentialScheme.BEARER,
        SecuritySchemeType.HTTP_BASIC: CredentialScheme.BASIC,
        SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS: (CredentialScheme.OAUTH2_CLIENT_CREDENTIALS),
        SecuritySchemeType.STATIC_HEADERS: CredentialScheme.STATIC_HEADERS,
    }.get(scheme.type)
    if scheme.type is SecuritySchemeType.API_KEY:
        expected = {
            "header": CredentialScheme.API_KEY_HEADER,
            "query": CredentialScheme.API_KEY_QUERY,
        }.get(scheme.location or "")
    return AuthSchemeSpec(
        name=scheme_name,
        expected_credential_scheme=expected,
        parameter_name=scheme.name if scheme.type is SecuritySchemeType.API_KEY else None,
        advertised_scopes=frozenset(scheme.scopes),
        oauth=scheme.type is SecuritySchemeType.OAUTH2_CLIENT_CREDENTIALS,
    )
