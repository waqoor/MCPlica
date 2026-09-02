from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.credentials import CredentialScheme


@dataclass(frozen=True, slots=True)
class AuthSchemeSpec:
    name: str
    expected_credential_scheme: CredentialScheme | None
    parameter_name: str | None = None
    advertised_scopes: frozenset[str] = frozenset()
    oauth: bool = False


@dataclass(frozen=True, slots=True)
class CredentialCandidate:
    id: UUID
    scheme_type: CredentialScheme
    metadata: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class AuthSelectionPlan:
    scheme_name: str
    credential_id: UUID
    scopes: tuple[str, ...]
    token_auth_method: Literal["client_secret_basic", "client_secret_post"]


@dataclass(frozen=True, slots=True)
class AuthAlternativeRejection:
    reason: str
    security_scheme: str | None = None
    compatible_credential_ids: tuple[UUID, ...] = ()


def select_auth_alternative(
    alternatives: list[dict[str, list[str]]],
    schemes: dict[str, AuthSchemeSpec],
    credentials: list[CredentialCandidate],
) -> tuple[AuthSelectionPlan | None, tuple[AuthAlternativeRejection, ...]]:
    rejections: list[AuthAlternativeRejection] = []
    for alternative in alternatives:
        if len(alternative) != 1:
            rejections.append(AuthAlternativeRejection("combined_requirement_unsupported"))
            continue
        scheme_name, required_scopes = next(iter(alternative.items()))
        scheme = schemes.get(scheme_name)
        if scheme is None:
            rejections.append(AuthAlternativeRejection("undefined", scheme_name))
            continue
        candidates = [
            credential
            for credential in credentials
            if credential_is_compatible(credential, scheme, required_scopes)
        ]
        explicitly_bound = [
            credential
            for credential in candidates
            if _explicit_scheme_name(credential.metadata) == scheme_name.casefold()
        ]
        if explicitly_bound:
            candidates = explicitly_bound
        if len(candidates) != 1:
            rejections.append(
                AuthAlternativeRejection(
                    "missing" if not candidates else "ambiguous",
                    scheme_name,
                    tuple(sorted((item.id for item in candidates), key=str)),
                )
            )
            continue
        credential = candidates[0]
        raw_default_scope = credential.metadata.get("scope")
        default_scopes = raw_default_scope.split() if isinstance(raw_default_scope, str) else []
        scopes = tuple(sorted(set(required_scopes or default_scopes))) if scheme.oauth else ()
        raw_method = credential.metadata.get("token_auth_method", "client_secret_basic")
        method: Literal["client_secret_basic", "client_secret_post"] = (
            "client_secret_post" if raw_method == "client_secret_post" else "client_secret_basic"
        )
        return AuthSelectionPlan(scheme_name, credential.id, scopes, method), tuple(rejections)
    return None, tuple(rejections)


def credential_is_compatible(
    credential: CredentialCandidate,
    scheme: AuthSchemeSpec,
    required_scopes: list[str],
) -> bool:
    if (
        scheme.expected_credential_scheme is None
        or credential.scheme_type is not scheme.expected_credential_scheme
    ):
        return False
    explicit_name = _explicit_scheme_name(credential.metadata)
    if explicit_name is not None and explicit_name != scheme.name.casefold():
        return False
    if scheme.parameter_name is not None:
        configured_name = credential.metadata.get("name")
        if (
            not isinstance(configured_name, str)
            or configured_name.casefold() != scheme.parameter_name.casefold()
        ):
            return False
    if not scheme.oauth:
        return not required_scopes
    advertised = scheme.advertised_scopes
    if not set(required_scopes) <= advertised:
        return False
    raw_default = credential.metadata.get("scope")
    default_scopes = raw_default.split() if isinstance(raw_default, str) else []
    if not set(default_scopes) <= advertised:
        return False
    return credential.metadata.get("token_auth_method", "client_secret_basic") in {
        "client_secret_basic",
        "client_secret_post",
    }


def _explicit_scheme_name(metadata: Mapping[str, object]) -> str | None:
    value = metadata.get("security_scheme")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().casefold()
