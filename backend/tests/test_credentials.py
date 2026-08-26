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


def test_oauth_token_url_rejects_embedded_credentials_and_fragments() -> None:
    with pytest.raises(ValueError, match="credentials or a fragment"):
        validate_credential_secret(
            CredentialScheme.OAUTH2_CLIENT_CREDENTIALS,
            {
                "client_id": "client",
                "client_secret": "secret",
                "token_url": "https://user:password@identity.example/token#fragment",
            },
            {},
        )
