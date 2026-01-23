"""User authentication database models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column, String, BigInteger, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship

from src.models.database import Base

if TYPE_CHECKING:
    from src.models.schemas import APIKey


class User(Base):
    """User account for authentication."""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime(timezone=True))

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", lazy="dynamic")
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class RefreshToken(Base):
    """Refresh tokens for JWT authentication."""
    __tablename__ = "refresh_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    revoked_at = Column(DateTime(timezone=True))

    # Relationship
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid (not expired or revoked)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at < datetime.utcnow():
            return False
        return True
