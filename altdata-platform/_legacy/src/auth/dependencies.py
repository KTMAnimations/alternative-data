"""FastAPI dependencies for authentication."""

from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.database import get_db
from src.models.schemas import APIKey
from .models import User
from .security import decode_token, hash_token

# OAuth2 scheme for JWT tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Get current user from JWT token.

    Returns None if no valid token, does not raise exception.
    Use get_current_user_required for endpoints that require auth.
    """
    if not token:
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            return None
        return user
    except (ValueError, TypeError):
        return None


async def get_current_user_required(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Require authenticated user.

    Raises HTTPException 401 if not authenticated.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_superuser(
    user: User = Depends(get_current_user_required),
) -> User:
    """Require superuser access.

    Raises HTTPException 403 if not a superuser.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user


async def verify_api_key_or_token(
    x_api_key: Optional[str] = Header(None),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """Verify either API key or JWT token.

    Returns dict with auth_type and user/api_key info.

    This maintains backward compatibility with existing API key auth
    while also supporting JWT authentication.
    """
    # Development mode bypass
    if settings.is_development and not x_api_key and not token:
        return {"auth_type": "development", "user": None, "api_key": None}

    # Check JWT token first
    if token:
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
            if user_id:
                try:
                    user = db.query(User).filter(User.id == int(user_id)).first()
                    if user and user.is_active:
                        return {"auth_type": "jwt", "user": user, "api_key": None}
                except (ValueError, TypeError):
                    pass

    # Check API key
    if x_api_key:
        # Check against hardcoded keys (backward compatibility)
        valid_keys = [k for k in [settings.api_key_admin, settings.api_key_default] if k]
        if x_api_key in valid_keys:
            return {"auth_type": "legacy_api_key", "user": None, "api_key": None}

        # Check against database
        key_hash = hash_token(x_api_key)
        api_key = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,
        ).first()

        if api_key:
            # Update last_used_at
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            return {"auth_type": "api_key", "user": api_key.user, "api_key": api_key}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )
