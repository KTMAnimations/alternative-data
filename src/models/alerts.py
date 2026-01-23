"""Alert models for real-time monitoring."""

from datetime import datetime, time
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
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class AlertType(str, Enum):
    """Types of alerts."""

    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    EVENT = "event"
    COMPOUND = "compound"


class AlertDirection(str, Enum):
    """Threshold direction for alerts."""

    ABOVE = "above"
    BELOW = "below"
    CROSSES = "crosses"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    WEBSOCKET = "websocket"


class AlertStatus(str, Enum):
    """Alert status."""

    ACTIVE = "active"
    TRIGGERED = "triggered"
    SUPPRESSED = "suppressed"
    DISABLED = "disabled"


class Alert(Base, TimestampMixin):
    """Alert configuration."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_active", "user_id", "is_enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Alert type configuration
    alert_type: Mapped[AlertType] = mapped_column(SQLEnum(AlertType), nullable=False)
    factor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=True
    )
    ticker_list: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Threshold alert config
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    direction: Mapped[Optional[AlertDirection]] = mapped_column(
        SQLEnum(AlertDirection), nullable=True
    )

    # Anomaly alert config
    sensitivity_std_devs: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    baseline_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    use_ml_detection: Mapped[bool] = mapped_column(Boolean, default=False)

    # Event alert config
    event_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    event_criteria: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    geographic_filter: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    include_impact_estimate: Mapped[bool] = mapped_column(Boolean, default=True)

    # Notification
    notification_channel: Mapped[NotificationChannel] = mapped_column(
        SQLEnum(NotificationChannel), nullable=False
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Fatigue management
    quiet_hours_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=0)
    use_daily_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    digest_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    history = relationship("AlertHistory", back_populates="alert", lazy="dynamic")


class AlertHistory(Base, TimestampMixin):
    """Historical record of triggered alerts."""

    __tablename__ = "alert_history"
    __table_args__ = (
        Index("ix_alert_history_alert_time", "alert_id", "triggered_at"),
        Index("ix_alert_history_user_time", "user_id", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("alerts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trigger_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    trigger_context: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Notification status
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notification_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # User interaction
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Suppression info
    was_suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    alert = relationship("Alert", back_populates="history")
