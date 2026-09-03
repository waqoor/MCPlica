from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRole(StrEnum):
    ADMIN = "admin"
    BUILDER = "builder"


class UserAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    email: EmailStr
    display_name: str
    password_hash: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class UserIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    email: EmailStr
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class AuthSessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    last_used_at: datetime


class AuthPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user: UserIdentity
    session_id: UUID
    csrf_token: str

    def has_role(self, *roles: UserRole) -> bool:
        return self.user.role in roles
