import pytest

from app.domain.credentials import CredentialScheme, validate_credential_secret


def test_credential_public_metadata_is_bounded_and_explicit() -> None:
    validate_credential_secret(
        CredentialScheme.BEARER,
        {"token": "secret"},
        {"security_scheme": "BearerAuth"},
    )
    with pytest.raises(ValueError, match="unexpected public credential metadata"):
        validate_credential_secret(
            CredentialScheme.BEARER,
            {"token": "secret"},
            {"token_preview": "secret"},
        )


def test_credential_headers_cannot_override_transport_headers() -> None:
    with pytest.raises(ValueError, match="invalid or forbidden"):
        validate_credential_secret(
            CredentialScheme.API_KEY_HEADER,
            {"value": "secret"},
            {"name": "Host"},
        )
    with pytest.raises(ValueError, match="forbidden"):
        validate_credential_secret(
            CredentialScheme.STATIC_HEADERS,
            {"headers": {"Content-Length": "100"}},
            {},
        )


def test_oauth_endpoint_and_scope_are_non_secret_build_metadata() -> None:
    with pytest.raises(ValueError, match="unexpected secret fields"):
        validate_credential_secret(
            CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
            {
                "client_id": "client",
                "client_secret": "secret",
                "token_url": "https://user:password@identity.example/token#fragment",
            },
            {},
        )
    validate_credential_secret(
        CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
        {"client_id": "client", "client_secret": "secret"},
        {
            "security_scheme": "oauth",
            "scope": "read write",
            "token_auth_method": "client_secret_post",
        },
    )
    with pytest.raises(ValueError, match="token_auth_method"):
        validate_credential_secret(
            CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
            {"client_id": "client", "client_secret": "secret"},
            {"token_auth_method": "private_key_jwt"},
        )


def test_rejects_basic_username_with_colon_but_allows_unicode_password() -> None:
    with pytest.raises(ValueError, match="cannot contain a colon"):
        validate_credential_secret(
            CredentialScheme.BASIC,
            {"username": "operator:name", "password": "valid password"},
            {},
        )

    validate_credential_secret(
        CredentialScheme.BASIC,
        {"username": "operator", "password": "كلمة مرور: آمنة\nحتى هنا"},
        {},
    )


@pytest.mark.parametrize("unsafe", ["line\rbreak", "line\nbreak", "nul\x00value"])
@pytest.mark.parametrize(
    ("scheme", "field", "metadata"),
    [
        (CredentialScheme.BEARER, "token", {}),
        (CredentialScheme.API_KEY_HEADER, "value", {"name": "X-Api-Key"}),
    ],
)
def test_rejects_unsafe_scalar_header_secrets(
    scheme: CredentialScheme,
    field: str,
    metadata: dict[str, object],
    unsafe: str,
) -> None:
    with pytest.raises(ValueError, match="unsafe characters"):
        validate_credential_secret(scheme, {field: unsafe}, metadata)


def test_query_api_key_uses_url_encoding_contract_not_header_character_rules() -> None:
    validate_credential_secret(
        CredentialScheme.API_KEY_QUERY,
        {"value": "value with spaces/and?delimiters"},
        {"name": "api_key"},
    )


@pytest.mark.parametrize("unsafe", ["line\rbreak", "line\nbreak", "nul\x00value"])
def test_rejects_unsafe_static_header_values(unsafe: str) -> None:
    with pytest.raises(ValueError, match="values must be non-empty text"):
        validate_credential_secret(
            CredentialScheme.STATIC_HEADERS,
            {"headers": {"X-Trace": unsafe}},
            {},
        )


def test_rejects_case_insensitive_duplicate_static_header_names() -> None:
    with pytest.raises(ValueError, match="unique ignoring case"):
        validate_credential_secret(
            CredentialScheme.STATIC_HEADERS,
            {"headers": {"X-Trace": "one", "x-trace": "two"}},
            {},
        )
