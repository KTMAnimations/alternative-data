"""Authentication API routes."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.models.users import User, APIKey, UserTier

router = APIRouter()

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/token")


# Pydantic schemas
class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    company: Optional[str] = None


class UserResponse(BaseModel):
    """Response schema for user."""

    id: int
    email: str
    full_name: Optional[str]
    company: Optional[str]
    tier: UserTier
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class APIKeyCreate(BaseModel):
    """Schema for API key creation."""

    name: str = Field(..., min_length=1, max_length=100)


class APIKeyResponse(BaseModel):
    """Response for API key (shown once on creation)."""

    id: int
    name: str
    key_prefix: str
    key: Optional[str] = None  # Only shown on creation
    rate_limit_per_minute: int
    created_at: datetime

    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    """Usage statistics response."""

    requests_today: int
    requests_limit: int
    data_bytes_today: int
    tier: UserTier
    features: dict


# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


# Routes
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    # Check if email exists
    query = select(User).where(User.email == user_data.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        company=user_data.company,
        tier=UserTier.FREE,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login and get access token."""
    query = select(User).where(User.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    access_token = create_access_token(data={"sub": user.id})

    return Token(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key."""
    import secrets

    # Generate key
    raw_key = secrets.token_urlsafe(32)
    key_prefix = raw_key[:8]
    key_hash = get_password_hash(raw_key)

    # Get rate limit based on tier
    rate_limits = {
        UserTier.FREE: 100,
        UserTier.PRO: 1000,
        UserTier.ENTERPRISE: 10000,
        UserTier.CUSTOM: 10000,
    }

    api_key = APIKey(
        user_id=current_user.id,
        name=key_data.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        rate_limit_per_minute=rate_limits.get(current_user.tier, 100),
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    response = APIKeyResponse.model_validate(api_key)
    response.key = f"altdata_{raw_key}"  # Only shown once

    return response


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's API keys."""
    query = (
        select(APIKey)
        .where(APIKey.user_id == current_user.id)
        .where(APIKey.is_active == True)
    )

    result = await db.execute(query)
    keys = result.scalars().all()

    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API key."""
    query = (
        select(APIKey)
        .where(APIKey.id == key_id)
        .where(APIKey.user_id == current_user.id)
    )

    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key.is_active = False
    await db.commit()


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics for current user."""
    from src.models.users import UsageRecord, TierLimit

    # Get today's usage
    today = datetime.utcnow().date()
    usage_query = (
        select(UsageRecord)
        .where(UsageRecord.user_id == current_user.id)
        .where(UsageRecord.date >= datetime.combine(today, datetime.min.time()))
    )

    usage_result = await db.execute(usage_query)
    usage_records = usage_result.scalars().all()

    requests_today = sum(r.api_requests for r in usage_records)
    data_bytes_today = sum(r.data_bytes_downloaded for r in usage_records)

    # Get tier limits
    tier_query = select(TierLimit).where(TierLimit.tier == current_user.tier)
    tier_result = await db.execute(tier_query)
    tier_limit = tier_result.scalar_one_or_none()

    features = {}
    if tier_limit:
        features = {
            "alerts": tier_limit.alerts_allowed,
            "backtesting": tier_limit.backtesting_allowed,
            "websocket": tier_limit.websocket_allowed,
            "sdk": tier_limit.sdk_access,
            "custom_factors": tier_limit.custom_factors_allowed,
        }

    return UsageResponse(
        requests_today=requests_today,
        requests_limit=tier_limit.requests_per_day if tier_limit else 100,
        data_bytes_today=data_bytes_today,
        tier=current_user.tier,
        features=features,
    )
