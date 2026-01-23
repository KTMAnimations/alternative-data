"""Authentication API endpoints."""

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.database import get_db
from src.models.schemas import APIKey

from .models import User, RefreshToken
from .schemas import (
    UserCreate, UserResponse, TokenResponse, TokenRefresh,
    AccessTokenResponse, APIKeyCreate, APIKeyResponse, APIKeyListItem,
    PasswordChange
)
from .security import (
    get_password_hash, verify_password, hash_token,
    create_access_token, create_refresh_token, decode_token,
    generate_api_key
)
from .dependencies import get_current_user_required

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ============================================
# User Registration and Login
# ============================================

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """Register a new user account."""
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login and receive access and refresh tokens.

    Uses OAuth2 password flow - username field is the email.
    """
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Update last login
    user.last_login_at = datetime.utcnow()

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store refresh token hash
    refresh_token_record = RefreshToken(
        token_hash=hash_token(refresh_token),
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(refresh_token_record)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token."""
    payload = decode_token(token_data.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify token exists and not revoked
    token_hash = hash_token(token_data.refresh_token)
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    ).first()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or revoked",
        )

    if stored_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Get user
    user = db.query(User).filter(User.id == stored_token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new access token (don't rotate refresh token on every refresh)
    access_token = create_access_token(data={"sub": str(user.id)})

    return AccessTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=200)
async def logout(
    token_data: TokenRefresh,
    db: Session = Depends(get_db),
):
    """Logout by revoking refresh token."""
    token_hash = hash_token(token_data.refresh_token)
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
    ).first()

    if stored_token:
        stored_token.revoked_at = datetime.utcnow()
        db.commit()

    return {"message": "Successfully logged out"}


# ============================================
# Current User
# ============================================

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user_required),
):
    """Get current authenticated user."""
    return current_user


@router.post("/change-password", status_code=200)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Change current user's password."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Password changed successfully"}


# ============================================
# API Key Management
# ============================================

@router.post("/api-keys", response_model=APIKeyResponse, status_code=201)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Create a new API key for the current user."""
    # Generate a secure random API key
    raw_key = generate_api_key()

    api_key = APIKey(
        key_hash=hash_token(raw_key),
        name=key_data.name,
        description=key_data.description,
        permissions=key_data.permissions,
        rate_limit=key_data.rate_limit,
        user_id=current_user.id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    # Return with the plain key (only time it's visible)
    return APIKeyResponse(
        id=api_key.id,
        key=raw_key,
        name=api_key.name,
        description=api_key.description,
        permissions=api_key.permissions,
        rate_limit=api_key.rate_limit,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.get("/api-keys", response_model=List[APIKeyListItem])
async def list_api_keys(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user."""
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    return keys


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Delete an API key."""
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id,
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    db.delete(api_key)
    db.commit()
