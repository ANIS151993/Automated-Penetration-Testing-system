from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UserRead(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    user: UserRead
    expires_at: datetime


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    display_name: str = Field(min_length=2, max_length=120)
    role: str = Field(default="operator", pattern="^(admin|operator)$")


class UserSetPassword(BaseModel):
    new_password: str = Field(min_length=8, max_length=255)


class UserSetActive(BaseModel):
    active: bool
