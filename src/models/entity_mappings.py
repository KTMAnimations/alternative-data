"""Entity mapping models for data-to-ticker relationships."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MappingStatus(str, Enum):
    """Status of entity mapping."""

    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    MANUAL_APPROVED = "manual_approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class SuggestionStatus(str, Enum):
    """Status of user-submitted mapping suggestions."""

    SUBMITTED = "submitted"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class CorporateActionType(str, Enum):
    """Types of corporate actions."""

    TICKER_CHANGE = "ticker_change"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    SPINOFF = "spinoff"
    DELISTING = "delisting"
    NAME_CHANGE = "name_change"


class EntityMapping(Base, TimestampMixin):
    """Mapping between source entities and tickers."""

    __tablename__ = "entity_mappings"
    __table_args__ = (
        UniqueConstraint("source_id", "source_entity_id", name="uq_entity_mapping"),
        Index("ix_entity_mapping_ticker", "ticker"),
        Index("ix_entity_mapping_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_sources.id"), nullable=False
    )
    source_entity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_entity_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Mapped ticker
    ticker: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Confidence and status
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[MappingStatus] = mapped_column(
        SQLEnum(MappingStatus), default=MappingStatus.PENDING
    )

    # AI alternatives
    ai_suggestions: Mapped[list] = mapped_column(JSON, nullable=True)  # List of {ticker, score, reason}

    # Review info
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Version tracking for corporate actions
    version: Mapped[int] = mapped_column(Integer, default=1)
    previous_ticker: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    effective_from: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MappingSuggestion(Base, TimestampMixin):
    """User-submitted mapping suggestions."""

    __tablename__ = "mapping_suggestions"
    __table_args__ = (
        Index("ix_mapping_suggestion_status", "status"),
        Index("ix_mapping_suggestion_user", "submitted_by_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_sources.id"), nullable=False
    )
    source_entity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_entity_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Suggested mapping
    suggested_ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    # User info
    submitted_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Status tracking
    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus), default=SuggestionStatus.SUBMITTED
    )
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CorporateAction(Base, TimestampMixin):
    """Corporate actions affecting entity mappings."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        Index("ix_corporate_action_ticker", "old_ticker"),
        Index("ix_corporate_action_date", "effective_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_type: Mapped[CorporateActionType] = mapped_column(
        SQLEnum(CorporateActionType), nullable=False
    )

    # Ticker info
    old_ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    new_ticker: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Details
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    announcement_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Related entities (for mergers/spinoffs)
    related_tickers: Mapped[list] = mapped_column(JSON, nullable=True)
    adjustment_factor: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )  # For price adjustments

    # Status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    affected_mappings_count: Mapped[int] = mapped_column(Integer, default=0)

    # Approval
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
