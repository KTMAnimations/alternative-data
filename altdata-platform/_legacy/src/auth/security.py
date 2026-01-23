"""Security utilities for password hashing and JWT tokens."""

from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets

from jose import jwt, JWTError
from passlib.context import CryptContext

from src.config.settings import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def hash_token(token: str) -> str:
    """Create SHA-256 hash of a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"ak_{secrets.token_urlsafe(32)}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token (should include 'sub' for user ID).
        expires_delta: Optional custom expiration time.

    Returns:
        Encoded JWT token string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow(),
    })
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token.

    Args:
        data: Data to encode in the token (should include 'sub' for user ID).

    Returns:
        Encoded JWT refresh token string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow(),
    })
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None
