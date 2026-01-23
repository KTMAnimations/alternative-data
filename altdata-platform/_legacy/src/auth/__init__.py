"""Authentication module for the Alternative Data Platform."""

from .models import User, RefreshToken
from .security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from .dependencies import (
    get_current_user,
    get_current_user_required,
    get_current_superuser,
    verify_api_key_or_token,
)
from .router import router as auth_router

__all__ = [
    "User",
    "RefreshToken",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_token",
    "get_current_user",
    "get_current_user_required",
    "get_current_superuser",
    "verify_api_key_or_token",
    "auth_router",
]
