"""Pydantic schemas for authentication."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class UserCreate(BaseModel):
    """Request schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Request schema for login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response schema for token endpoints."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class TokenRefresh(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str


class AccessTokenResponse(BaseModel):
    """Response schema for refresh endpoint (only access token)."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class APIKeyCreate(BaseModel):
    """Request schema for creating an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: Optional[List[str]] = None
    rate_limit: int = Field(1000, ge=1, le=100000)


class APIKeyResponse(BaseModel):
    """Response schema for API key (returned only on creation)."""
    id: int
    key: str  # Only returned on creation, plain text
    name: str
    description: Optional[str]
    permissions: Optional[List[str]]
    rate_limit: int
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class APIKeyListItem(BaseModel):
    """Response schema for listing API keys (no key value)."""
    id: int
    name: str
    description: Optional[str]
    permissions: Optional[List[str]]
    rate_limit: int
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    """Request schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v
