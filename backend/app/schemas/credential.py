from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.domain.credentials import CredentialScheme, validate_credential_secret


class CredentialSecretInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: SecretStr | None = None
    value: SecretStr | None = None
    username: SecretStr | None = None
    password: SecretStr | None = None
    client_id: SecretStr | None = None
    client_secret: SecretStr | None = None
    token_url: SecretStr | None = None
    scope: SecretStr | None = None
    headers: dict[str, SecretStr] | None = None

    def plaintext(self) -> dict[str, object]:
        result: dict[str, object] = {}
        scalar_names = (
            "token",
            "value",
            "username",
            "password",
            "client_id",
            "client_secret",
            "token_url",
            "scope",
        )
        for name in scalar_names:
            value = getattr(self, name)
            if value is not None:
                result[name] = value.get_secret_value()
        if self.headers is not None:
            result["headers"] = {
                name: value.get_secret_value() for name, value in self.headers.items()
            }
        return result


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    scheme_type: CredentialScheme
    secret: CredentialSecretInput
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_secret_shape(self) -> "CredentialCreate":
        validate_credential_secret(
            self.scheme_type,
            self.secret.plaintext(),
            self.metadata,
        )
        return self


class CredentialRotate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: CredentialSecretInput
    metadata: dict[str, str] | None = None


class CredentialRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    scheme_type: CredentialScheme
    metadata: dict[str, object]
    configured: bool = True
    created_by: UUID
    created_at: datetime
    rotated_at: datetime | None
    revoked_at: datetime | None
