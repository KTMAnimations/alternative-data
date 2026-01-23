"""User and authentication models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class UserTier(str, Enum):
    """Subscription tiers."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class User(Base, TimestampMixin):
    """User accounts."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Subscription
    tier: Mapped[UserTier] = mapped_column(SQLEnum(UserTier), default=UserTier.FREE)
    tier_upgraded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", lazy="dynamic")
    usage_records = relationship("UsageRecord", back_populates="user", lazy="dynamic")
    experiments = relationship("Experiment", back_populates="user", lazy="dynamic")


class APIKey(Base, TimestampMixin):
    """API keys for programmatic access."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_key_user", "user_id"),
        Index("ix_api_key_hash", "key_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Key info (hash stored, never plain text)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)  # First few chars for identification
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Permissions and limits
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_endpoints: Mapped[Optional[list]] = mapped_column(Text, nullable=True)  # JSON list or null for all

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Usage stats
    total_requests: Mapped[int] = mapped_column(BigInteger, default=0)
    total_data_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Relationships
    user = relationship("User", back_populates="api_keys")


class UsageRecord(Base):
    """Usage tracking for billing and limits."""

    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_user_date", "user_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Usage metrics
    api_requests: Mapped[int] = mapped_column(Integer, default=0)
    data_bytes_downloaded: Mapped[int] = mapped_column(BigInteger, default=0)
    websocket_connections: Mapped[int] = mapped_column(Integer, default=0)
    alerts_triggered: Mapped[int] = mapped_column(Integer, default=0)
    backtests_run: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="usage_records")


class TierLimit(Base, TimestampMixin):
    """Rate limits and features per tier."""

    __tablename__ = "tier_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tier: Mapped[UserTier] = mapped_column(SQLEnum(UserTier), unique=True, nullable=False)

    # Rate limits
    requests_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)

    # Data access
    history_days: Mapped[int] = mapped_column(Integer, nullable=False)  # -1 for unlimited
    data_sources_allowed: Mapped[list] = mapped_column(Text, nullable=True)  # JSON list or null for all

    # Features
    alerts_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    backtesting_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    websocket_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    sdk_access: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_factors_allowed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Pricing
    monthly_price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
