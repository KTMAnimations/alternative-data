"""Database models for the alerting system."""

from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from src.models.database import Base


class AlertCondition(str, Enum):
    """Alert condition types."""
    GT = "gt"  # Greater than
    LT = "lt"  # Less than
    EQ = "eq"  # Equal to
    ZSCORE_GT = "zscore_gt"  # Z-score greater than
    ZSCORE_LT = "zscore_lt"  # Z-score less than
    PCT_CHANGE_GT = "pct_change_gt"  # Percent change greater than
    PCT_CHANGE_LT = "pct_change_lt"  # Percent change less than


class NotificationChannel(str, Enum):
    """Notification channel types."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


class NotificationStatus(str, Enum):
    """Notification status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AlertRule(Base):
    """Alert rule definition."""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    factor_name = Column(String(100), nullable=False)
    entity_id = Column(String(50))  # NULL = all entities
    condition = Column(SQLEnum(AlertCondition), nullable=False)
    threshold = Column(Float, nullable=False)
    lookback_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    notification_channel = Column(SQLEnum(NotificationChannel), default=NotificationChannel.SLACK)
    notification_config = Column(String(500))  # JSON config for channel
    cooldown_minutes = Column(Integer, default=60)  # Minimum time between alerts
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notifications = relationship("AlertNotification", back_populates="rule")

    def __repr__(self):
        return f"<AlertRule(id={self.id}, name='{self.name}', factor='{self.factor_name}')>"


class AlertNotification(Base):
    """Alert notification record."""

    __tablename__ = "alert_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    entity_id = Column(String(50))
    factor_value = Column(Float)
    threshold = Column(Float)
    computed_value = Column(Float)  # For z-score/pct_change
    triggered_at = Column(DateTime, default=datetime.utcnow)
    notified_at = Column(DateTime)
    notification_channel = Column(SQLEnum(NotificationChannel))
    notification_status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    error_message = Column(String(500))

    rule = relationship("AlertRule", back_populates="notifications")

    def __repr__(self):
        return f"<AlertNotification(id={self.id}, rule_id={self.rule_id}, status='{self.notification_status}')>"
