from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.domain.credentials import CredentialRecord, CredentialScheme
from app.domain.sources import (
    OperationSecurityRequirementRecord,
    SecuritySchemeDiscoveryRecord,
    SourceConfigurationDiscoveryRecord,
)
from app.services.builds.readiness import (
    credential_mapping_readiness,
    validate_credential_binding,
)

NOW = datetime(2026, 8, 27, tzinfo=UTC)


def _credential(
    value: int,
    *,
    scheme_type: CredentialScheme = CredentialScheme.BEARER,
    security_scheme: str | None = None,
) -> CredentialRecord:
    return CredentialRecord(
        id=UUID(int=value),
        project_id=UUID(int=1),
        name=f"credential-{value}",
        scheme_type=scheme_type,
        key_version="v1",
        metadata=({"security_scheme": security_scheme} if security_scheme is not None else {}),
        created_by=UUID(int=2),
        created_at=NOW,
        rotated_at=None,
        revoked_at=None,
    )


def _discovery(
    alternatives: list[dict[str, list[str]]],
) -> SourceConfigurationDiscoveryRecord:
    return SourceConfigurationDiscoveryRecord(
        source_version_ids=[UUID(int=3)],
        configuration_sha256="a" * 64,
        servers=[],
        operations=[],
        security_schemes=[
            SecuritySchemeDiscoveryRecord(
                name="bearerAuth",
                type="http_bearer",
                location=None,
                parameter_name=None,
                token_url=None,
                advertised_scopes=[],
                applicable_operation_keys=["get_items"],
                optional_for_all_operations=False,
                source_pointer="#/components/securitySchemes/bearerAuth",
            ),
            SecuritySchemeDiscoveryRecord(
                name="backupAuth",
                type="http_bearer",
                location=None,
                parameter_name=None,
                token_url=None,
                advertised_scopes=[],
                applicable_operation_keys=["get_items"],
                optional_for_all_operations=False,
                source_pointer="#/components/securitySchemes/backupAuth",
            ),
        ],
        security_requirements=[
            OperationSecurityRequirementRecord(
                operation_key="get_items",
                alternatives=alternatives,
                anonymous_allowed=False,
            )
        ],
        routing_complete=True,
    )


def test_credential_readiness_honors_alternatives_and_explicit_bindings() -> None:
    discovery = _discovery([{"bearerAuth": []}, {"backupAuth": []}])

    ambiguous = credential_mapping_readiness(
        discovery,
        [_credential(10), _credential(11)],
    )
    assert not ambiguous.complete
    assert ambiguous.unresolved_operation_keys == ("get_items",)

    explicit = credential_mapping_readiness(
        discovery,
        [_credential(10, security_scheme="bearerAuth"), _credential(11)],
    )
    assert explicit.complete
    assert explicit.bound_scheme_names == ("bearerAuth",)


def test_credential_readiness_rejects_unsupported_combined_requirement() -> None:
    result = credential_mapping_readiness(
        _discovery([{"bearerAuth": [], "backupAuth": []}]),
        [
            _credential(10, security_scheme="bearerAuth"),
            _credential(11, security_scheme="backupAuth"),
        ],
    )

    assert result.required
    assert not result.complete
    assert result.unresolved_operation_keys == ("get_items",)


def test_credential_binding_must_name_a_compatible_discovered_scheme() -> None:
    discovery = _discovery([{"bearerAuth": []}])

    validate_credential_binding(
        discovery,
        scheme_type=CredentialScheme.BEARER,
        metadata={"security_scheme": "bearerAuth"},
    )
    with pytest.raises(ValueError, match="must bind"):
        validate_credential_binding(
            discovery,
            scheme_type=CredentialScheme.BEARER,
            metadata={},
        )
    with pytest.raises(ValueError, match="incompatible"):
        validate_credential_binding(
            discovery,
            scheme_type=CredentialScheme.BASIC,
            metadata={"security_scheme": "bearerAuth"},
        )


def test_readiness_tries_later_alternative_after_invalid_oauth_defaults() -> None:
    discovery = _discovery([{"oauth": ["read"]}, {"backupAuth": []}]).model_copy(
        update={
            "security_schemes": [
                SecuritySchemeDiscoveryRecord(
                    name="oauth",
                    type="oauth2_client_credentials",
                    token_url="https://identity.example/token",
                    advertised_scopes=["read"],
                    applicable_operation_keys=["get_items"],
                    source_pointer="#/components/securitySchemes/oauth",
                ),
                SecuritySchemeDiscoveryRecord(
                    name="backupAuth",
                    type="http_bearer",
                    applicable_operation_keys=["get_items"],
                    source_pointer="#/components/securitySchemes/backupAuth",
                ),
            ]
        }
    )
    oauth = _credential(
        20,
        scheme_type=CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
        security_scheme="oauth",
    ).model_copy(update={"metadata": {"security_scheme": "oauth", "scope": "unknown"}})
    backup = _credential(21, security_scheme="backupAuth")

    result = credential_mapping_readiness(discovery, [oauth, backup])

    assert result.complete
    assert result.bound_scheme_names == ("backupAuth",)
