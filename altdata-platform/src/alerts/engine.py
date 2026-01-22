"""Alert engine for checking rules and triggering notifications."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np

from sqlalchemy.orm import Session

from src.models.database import SessionLocal
from src.models.schemas import Factor
from .models import AlertRule, AlertNotification, AlertCondition, NotificationStatus
from .notifiers import get_notifier

logger = logging.getLogger(__name__)


class AlertEngine:
    """Engine for processing alert rules."""

    def __init__(self, session: Optional[Session] = None):
        """Initialize the alert engine.

        Args:
            session: SQLAlchemy session. If not provided, creates a new one.
        """
        self._session = session
        self._owns_session = session is None

    def _get_session(self) -> Session:
        """Get or create a database session."""
        if self._session is None:
            self._session = SessionLocal()
        return self._session

    def close(self):
        """Close the session if we own it."""
        if self._owns_session and self._session:
            self._session.close()
            self._session = None

    def check_all_rules(self) -> List[AlertNotification]:
        """Check all active rules and trigger notifications.

        Returns:
            List of triggered AlertNotification objects.
        """
        session = self._get_session()
        triggered = []

        try:
            # Get all active rules
            rules = session.query(AlertRule).filter(AlertRule.is_active == True).all()
            logger.info(f"Checking {len(rules)} active alert rules")

            for rule in rules:
                try:
                    notifications = self.check_rule(rule)
                    triggered.extend(notifications)
                except Exception as e:
                    logger.error(f"Error checking rule {rule.id}: {e}")

            session.commit()
            return triggered

        except Exception as e:
            logger.error(f"Error checking rules: {e}")
            session.rollback()
            raise

    def check_rule(self, rule: AlertRule) -> List[AlertNotification]:
        """Check a single rule and create notifications if triggered.

        Args:
            rule: The alert rule to check.

        Returns:
            List of AlertNotification objects created.
        """
        session = self._get_session()
        notifications = []

        # Get entities to check
        if rule.entity_id:
            entities = [rule.entity_id]
        else:
            # Get all entities with data for this factor
            entities = self._get_entities_for_factor(rule.factor_name)

        for entity_id in entities:
            # Check cooldown
            if self._is_in_cooldown(rule, entity_id):
                continue

            # Get factor value
            factor_value = self._get_latest_factor_value(rule.factor_name, entity_id)
            if factor_value is None:
                continue

            # Evaluate condition
            triggered, computed_value = self._evaluate_condition(
                rule, entity_id, factor_value
            )

            if triggered:
                notification = AlertNotification(
                    rule_id=rule.id,
                    entity_id=entity_id,
                    factor_value=factor_value,
                    threshold=rule.threshold,
                    computed_value=computed_value,
                    notification_channel=rule.notification_channel,
                )
                session.add(notification)
                notifications.append(notification)

                # Send notification
                self._send_notification(rule, notification)

        return notifications

    def _get_entities_for_factor(self, factor_name: str) -> List[str]:
        """Get all entities that have data for a factor."""
        session = self._get_session()

        results = (
            session.query(Factor.entity_id)
            .filter(Factor.factor_name == factor_name)
            .distinct()
            .all()
        )

        return [r[0] for r in results]

    def _get_latest_factor_value(
        self, factor_name: str, entity_id: str
    ) -> Optional[float]:
        """Get the most recent factor value for an entity."""
        session = self._get_session()

        factor = (
            session.query(Factor)
            .filter(
                Factor.factor_name == factor_name,
                Factor.entity_id == entity_id,
            )
            .order_by(Factor.effective_date.desc())
            .first()
        )

        return factor.value if factor else None

    def _get_factor_history(
        self, factor_name: str, entity_id: str, lookback_days: int
    ) -> List[float]:
        """Get historical factor values for z-score calculation."""
        session = self._get_session()
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        factors = (
            session.query(Factor.value)
            .filter(
                Factor.factor_name == factor_name,
                Factor.entity_id == entity_id,
                Factor.effective_date >= cutoff_date,
                Factor.value.isnot(None),
            )
            .order_by(Factor.effective_date.desc())
            .all()
        )

        return [f[0] for f in factors]

    def _is_in_cooldown(self, rule: AlertRule, entity_id: str) -> bool:
        """Check if the rule is in cooldown for this entity."""
        session = self._get_session()
        cooldown_time = datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes)

        recent = (
            session.query(AlertNotification)
            .filter(
                AlertNotification.rule_id == rule.id,
                AlertNotification.entity_id == entity_id,
                AlertNotification.triggered_at >= cooldown_time,
            )
            .first()
        )

        return recent is not None

    def _evaluate_condition(
        self, rule: AlertRule, entity_id: str, factor_value: float
    ) -> tuple:
        """Evaluate if the alert condition is met.

        Returns:
            Tuple of (triggered: bool, computed_value: float or None)
        """
        condition = rule.condition
        threshold = rule.threshold

        if condition == AlertCondition.GT:
            return factor_value > threshold, None

        elif condition == AlertCondition.LT:
            return factor_value < threshold, None

        elif condition == AlertCondition.EQ:
            return abs(factor_value - threshold) < 0.0001, None

        elif condition == AlertCondition.ZSCORE_GT:
            zscore = self.calculate_zscore(
                rule.factor_name, entity_id, rule.lookback_days
            )
            if zscore is not None:
                return zscore > threshold, zscore
            return False, None

        elif condition == AlertCondition.ZSCORE_LT:
            zscore = self.calculate_zscore(
                rule.factor_name, entity_id, rule.lookback_days
            )
            if zscore is not None:
                return zscore < threshold, zscore
            return False, None

        elif condition == AlertCondition.PCT_CHANGE_GT:
            pct_change = self._calculate_pct_change(
                rule.factor_name, entity_id, rule.lookback_days
            )
            if pct_change is not None:
                return pct_change > threshold, pct_change
            return False, None

        elif condition == AlertCondition.PCT_CHANGE_LT:
            pct_change = self._calculate_pct_change(
                rule.factor_name, entity_id, rule.lookback_days
            )
            if pct_change is not None:
                return pct_change < threshold, pct_change
            return False, None

        return False, None

    def calculate_zscore(
        self, factor_name: str, entity_id: str, lookback_days: int = 30
    ) -> Optional[float]:
        """Calculate z-score for the latest factor value.

        Args:
            factor_name: Name of the factor.
            entity_id: Entity identifier.
            lookback_days: Number of days for historical mean/std calculation.

        Returns:
            Z-score value or None if insufficient data.
        """
        history = self._get_factor_history(factor_name, entity_id, lookback_days)

        if len(history) < 5:  # Need at least 5 data points
            return None

        current = history[0]
        historical = history[1:]

        mean = np.mean(historical)
        std = np.std(historical)

        if std == 0:
            return None

        return (current - mean) / std

    def _calculate_pct_change(
        self, factor_name: str, entity_id: str, lookback_days: int
    ) -> Optional[float]:
        """Calculate percentage change from lookback period."""
        history = self._get_factor_history(factor_name, entity_id, lookback_days)

        if len(history) < 2:
            return None

        current = history[0]
        previous = history[-1]  # Value from lookback_days ago

        if previous == 0:
            return None

        return (current - previous) / abs(previous) * 100

    def _send_notification(
        self, rule: AlertRule, notification: AlertNotification
    ) -> bool:
        """Send notification through the configured channel."""
        try:
            notifier = get_notifier(rule.notification_channel, rule.notification_config)

            message = self._format_message(rule, notification)
            success = notifier.send(message)

            if success:
                notification.notification_status = NotificationStatus.SENT
                notification.notified_at = datetime.utcnow()
            else:
                notification.notification_status = NotificationStatus.FAILED
                notification.error_message = "Notification send failed"

            return success

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            notification.notification_status = NotificationStatus.FAILED
            notification.error_message = str(e)
            return False

    def _format_message(
        self, rule: AlertRule, notification: AlertNotification
    ) -> dict:
        """Format the alert message."""
        condition_text = {
            AlertCondition.GT: "greater than",
            AlertCondition.LT: "less than",
            AlertCondition.EQ: "equal to",
            AlertCondition.ZSCORE_GT: "z-score greater than",
            AlertCondition.ZSCORE_LT: "z-score less than",
            AlertCondition.PCT_CHANGE_GT: "percent change greater than",
            AlertCondition.PCT_CHANGE_LT: "percent change less than",
        }

        return {
            "title": f"Alert: {rule.name}",
            "rule_name": rule.name,
            "factor_name": rule.factor_name,
            "entity_id": notification.entity_id,
            "condition": condition_text.get(rule.condition, str(rule.condition)),
            "threshold": rule.threshold,
            "current_value": notification.factor_value,
            "computed_value": notification.computed_value,
            "triggered_at": notification.triggered_at.isoformat(),
            "description": rule.description,
        }
