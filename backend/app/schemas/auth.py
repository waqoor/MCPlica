from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.domain.auth import UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=1_024)


class UserRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: UserRead
    access_expires_at: datetime


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    display_name: str = Field(min_length=1, max_length=160)
    password: SecretStr = Field(min_length=12, max_length=1_024)
    role: UserRole

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_password(self) -> "UserCreate":
        if len(self.password.get_secret_value()) < 12:
            raise ValueError("password must contain at least 12 characters")
        return self


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    password: SecretStr | None = Field(default=None, min_length=12, max_length=1_024)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_optional_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_password(self) -> "UserUpdate":
        if self.password is not None and len(self.password.get_secret_value()) < 12:
            raise ValueError("password must contain at least 12 characters")
        return self
