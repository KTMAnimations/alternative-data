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


class CorporateActionStatus(str, Enum):
    """Status of corporate action processing."""

    DETECTED = "detected"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class NotificationType(str, Enum):
    """Types of notifications."""

    MAPPING_STATUS_CHANGE = "mapping_status_change"
    SUGGESTION_STATUS_CHANGE = "suggestion_status_change"
    CORPORATE_ACTION_DETECTED = "corporate_action_detected"
    CORPORATE_ACTION_APPLIED = "corporate_action_applied"
    COVERAGE_THRESHOLD_ALERT = "coverage_threshold_alert"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""

    EMAIL = "email"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class AuditActionType(str, Enum):
    """Types of audit actions."""

    CREATE = "create"
    UPDATE = "update"
    APPROVE = "approve"
    REJECT = "reject"
    CORRECT = "correct"
    BULK_APPROVE = "bulk_approve"
    CORPORATE_ACTION_APPLY = "corporate_action_apply"


class CorporateAction(Base, TimestampMixin):
    """Corporate actions affecting entity mappings."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        Index("ix_corporate_action_ticker", "old_ticker"),
        Index("ix_corporate_action_date", "effective_date"),
        Index("ix_corporate_action_status", "status"),
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
    status: Mapped[CorporateActionStatus] = mapped_column(
        SQLEnum(CorporateActionStatus), default=CorporateActionStatus.DETECTED
    )
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
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Historical adjustment preview
    preview_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class MappingAuditLog(Base, TimestampMixin):
    """Audit trail for entity mapping changes (US-027)."""

    __tablename__ = "mapping_audit_logs"
    __table_args__ = (
        Index("ix_audit_mapping", "mapping_id"),
        Index("ix_audit_user", "user_id"),
        Index("ix_audit_timestamp", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mapping_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entity_mappings.id"), nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Action details
    action: Mapped[AuditActionType] = mapped_column(
        SQLEnum(AuditActionType), nullable=False
    )

    # Change tracking
    old_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Context
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class Notification(Base, TimestampMixin):
    """User notifications for mapping status changes (US-028)."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_user", "user_id"),
        Index("ix_notification_read", "is_read"),
        Index("ix_notification_type", "notification_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Notification type and content
    notification_type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Related entity (optional)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Delivery
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CoverageSnapshot(Base, TimestampMixin):
    """Historical coverage snapshots for trend tracking (US-029)."""

    __tablename__ = "coverage_snapshots"
    __table_args__ = (
        Index("ix_coverage_source_date", "source_id", "snapshot_date"),
        UniqueConstraint("source_id", "snapshot_date", name="uq_coverage_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_sources.id"), nullable=False
    )
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Coverage metrics
    total_entities: Mapped[int] = mapped_column(Integer, nullable=False)
    mapped_entities: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    # Value metrics
    total_value_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    mapped_value_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    unmapped_value_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )

    # Volume metrics
    total_volume: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    mapped_volume: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    unmapped_volume: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )

    # High-value unmapped
    high_value_unmapped_count: Mapped[int] = mapped_column(Integer, default=0)


class EntityTradingMetrics(Base, TimestampMixin):
    """Trading metrics for entity prioritization (US-029)."""

    __tablename__ = "entity_trading_metrics"
    __table_args__ = (
        Index("ix_trading_entity", "source_entity_id"),
        Index("ix_trading_volume", "avg_daily_volume"),
        UniqueConstraint("source_id", "source_entity_id", name="uq_entity_trading"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_sources.id"), nullable=False
    )
    source_entity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_entity_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Value metrics ($ terms)
    market_cap_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    avg_daily_value_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )

    # Volume metrics
    avg_daily_volume: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )

    # Prioritization score (computed)
    priority_score: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=0
    )

    # Last updated from external source
    metrics_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
