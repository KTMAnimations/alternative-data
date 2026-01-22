"""Tests for the alerting system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.alerts.models import AlertRule, AlertNotification, AlertCondition, NotificationChannel, NotificationStatus
from src.alerts.engine import AlertEngine
from src.alerts.notifiers import SlackNotifier, EmailNotifier, WebhookNotifier, get_notifier


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    return session


@pytest.fixture
def sample_rule():
    """Create a sample alert rule."""
    rule = AlertRule(
        id=1,
        name="Test Alert",
        description="Test description",
        factor_name="insider_transaction_momentum",
        entity_id="AAPL",
        condition=AlertCondition.GT,
        threshold=1000.0,
        lookback_days=30,
        is_active=True,
        notification_channel=NotificationChannel.SLACK,
        notification_config='{"webhook_url": "https://hooks.slack.com/test"}',
        cooldown_minutes=60,
    )
    return rule


@pytest.fixture
def sample_notification(sample_rule):
    """Create a sample notification."""
    return AlertNotification(
        id=1,
        rule_id=sample_rule.id,
        entity_id="AAPL",
        factor_value=1500.0,
        threshold=1000.0,
        triggered_at=datetime.utcnow(),
        notification_channel=NotificationChannel.SLACK,
        notification_status=NotificationStatus.PENDING,
    )


# ===========================================
# ALERT CONDITION TESTS
# ===========================================


class TestAlertConditions:
    """Tests for alert condition evaluation."""

    def test_condition_gt(self):
        """Test greater than condition."""
        assert AlertCondition.GT.value == "gt"

    def test_condition_lt(self):
        """Test less than condition."""
        assert AlertCondition.LT.value == "lt"

    def test_condition_eq(self):
        """Test equal condition."""
        assert AlertCondition.EQ.value == "eq"

    def test_condition_zscore_gt(self):
        """Test z-score greater than condition."""
        assert AlertCondition.ZSCORE_GT.value == "zscore_gt"

    def test_condition_zscore_lt(self):
        """Test z-score less than condition."""
        assert AlertCondition.ZSCORE_LT.value == "zscore_lt"


# ===========================================
# ALERT ENGINE TESTS
# ===========================================


class TestAlertEngine:
    """Tests for the AlertEngine class."""

    def test_init(self, mock_session):
        """Test engine initialization."""
        engine = AlertEngine(session=mock_session)
        assert engine._session == mock_session
        assert not engine._owns_session

    def test_init_without_session(self):
        """Test engine initialization without session."""
        engine = AlertEngine()
        assert engine._session is None
        assert engine._owns_session

    def test_evaluate_condition_gt_true(self, mock_session, sample_rule):
        """Test GT condition evaluation when true."""
        engine = AlertEngine(session=mock_session)
        sample_rule.condition = AlertCondition.GT
        sample_rule.threshold = 1000.0

        triggered, computed = engine._evaluate_condition(sample_rule, "AAPL", 1500.0)
        assert triggered is True
        assert computed is None

    def test_evaluate_condition_gt_false(self, mock_session, sample_rule):
        """Test GT condition evaluation when false."""
        engine = AlertEngine(session=mock_session)
        sample_rule.condition = AlertCondition.GT
        sample_rule.threshold = 1000.0

        triggered, computed = engine._evaluate_condition(sample_rule, "AAPL", 500.0)
        assert triggered is False

    def test_evaluate_condition_lt_true(self, mock_session, sample_rule):
        """Test LT condition evaluation when true."""
        engine = AlertEngine(session=mock_session)
        sample_rule.condition = AlertCondition.LT
        sample_rule.threshold = 1000.0

        triggered, computed = engine._evaluate_condition(sample_rule, "AAPL", 500.0)
        assert triggered is True

    def test_evaluate_condition_lt_false(self, mock_session, sample_rule):
        """Test LT condition evaluation when false."""
        engine = AlertEngine(session=mock_session)
        sample_rule.condition = AlertCondition.LT
        sample_rule.threshold = 1000.0

        triggered, computed = engine._evaluate_condition(sample_rule, "AAPL", 1500.0)
        assert triggered is False

    def test_evaluate_condition_eq_true(self, mock_session, sample_rule):
        """Test EQ condition evaluation when true."""
        engine = AlertEngine(session=mock_session)
        sample_rule.condition = AlertCondition.EQ
        sample_rule.threshold = 1000.0

        triggered, computed = engine._evaluate_condition(sample_rule, "AAPL", 1000.0)
        assert triggered is True

    def test_calculate_zscore(self, mock_session, sample_rule):
        """Test z-score calculation."""
        engine = AlertEngine(session=mock_session)

        # Mock the history retrieval
        engine._get_factor_history = Mock(return_value=[110, 100, 100, 100, 100, 100])

        zscore = engine.calculate_zscore("test_factor", "AAPL", 30)

        # Current is 110, historical mean is 100, std is 0
        # Since std would be 0 for identical values, need different data
        engine._get_factor_history = Mock(return_value=[120, 100, 110, 90, 105, 95])
        zscore = engine.calculate_zscore("test_factor", "AAPL", 30)

        assert zscore is not None

    def test_calculate_zscore_insufficient_data(self, mock_session):
        """Test z-score with insufficient data."""
        engine = AlertEngine(session=mock_session)
        engine._get_factor_history = Mock(return_value=[100, 100])

        zscore = engine.calculate_zscore("test_factor", "AAPL", 30)
        assert zscore is None

    def test_format_message(self, mock_session, sample_rule, sample_notification):
        """Test message formatting."""
        engine = AlertEngine(session=mock_session)
        message = engine._format_message(sample_rule, sample_notification)

        assert message["title"] == f"Alert: {sample_rule.name}"
        assert message["factor_name"] == sample_rule.factor_name
        assert message["entity_id"] == sample_notification.entity_id
        assert message["threshold"] == sample_rule.threshold
        assert message["current_value"] == sample_notification.factor_value


# ===========================================
# NOTIFIER TESTS
# ===========================================


class TestSlackNotifier:
    """Tests for Slack notifier."""

    def test_init(self):
        """Test Slack notifier initialization."""
        notifier = SlackNotifier("https://hooks.slack.com/test")
        assert notifier.webhook_url == "https://hooks.slack.com/test"

    @patch("httpx.post")
    def test_send_success(self, mock_post):
        """Test successful Slack notification."""
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()

        notifier = SlackNotifier("https://hooks.slack.com/test")
        message = {
            "title": "Test Alert",
            "rule_name": "Test Rule",
            "factor_name": "test_factor",
            "entity_id": "AAPL",
            "condition": "greater than",
            "threshold": 1000,
            "current_value": 1500,
            "triggered_at": datetime.utcnow().isoformat(),
        }

        result = notifier.send(message)
        assert result is True
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_send_failure(self, mock_post):
        """Test failed Slack notification."""
        mock_post.side_effect = Exception("Connection error")

        notifier = SlackNotifier("https://hooks.slack.com/test")
        message = {
            "title": "Test Alert",
            "rule_name": "Test Rule",
            "factor_name": "test_factor",
            "entity_id": "AAPL",
            "condition": "greater than",
            "threshold": 1000,
            "current_value": 1500,
            "triggered_at": datetime.utcnow().isoformat(),
        }

        result = notifier.send(message)
        assert result is False


class TestWebhookNotifier:
    """Tests for webhook notifier."""

    def test_init(self):
        """Test webhook notifier initialization."""
        notifier = WebhookNotifier("https://example.com/webhook")
        assert notifier.url == "https://example.com/webhook"

    def test_init_with_headers(self):
        """Test webhook notifier with custom headers."""
        headers = {"Authorization": "Bearer token"}
        notifier = WebhookNotifier("https://example.com/webhook", headers=headers)
        assert notifier.headers == headers

    @patch("httpx.post")
    def test_send_success(self, mock_post):
        """Test successful webhook notification."""
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()

        notifier = WebhookNotifier("https://example.com/webhook")
        message = {"title": "Test", "rule_name": "Rule"}

        result = notifier.send(message)
        assert result is True


class TestGetNotifier:
    """Tests for notifier factory function."""

    def test_get_slack_notifier(self):
        """Test getting Slack notifier."""
        config = '{"webhook_url": "https://hooks.slack.com/test"}'
        notifier = get_notifier(NotificationChannel.SLACK, config)
        assert isinstance(notifier, SlackNotifier)

    def test_get_webhook_notifier(self):
        """Test getting webhook notifier."""
        config = '{"url": "https://example.com/webhook"}'
        notifier = get_notifier(NotificationChannel.WEBHOOK, config)
        assert isinstance(notifier, WebhookNotifier)

    def test_get_slack_notifier_missing_url(self):
        """Test Slack notifier with missing webhook_url."""
        with pytest.raises(ValueError, match="webhook_url"):
            get_notifier(NotificationChannel.SLACK, "{}")

    def test_get_webhook_notifier_missing_url(self):
        """Test webhook notifier with missing url."""
        with pytest.raises(ValueError, match="url"):
            get_notifier(NotificationChannel.WEBHOOK, "{}")


# ===========================================
# MODEL TESTS
# ===========================================


class TestAlertRule:
    """Tests for AlertRule model."""

    def test_create_rule(self):
        """Test creating an alert rule."""
        rule = AlertRule(
            name="Test Rule",
            factor_name="test_factor",
            condition=AlertCondition.GT,
            threshold=100.0,
            is_active=True,
            lookback_days=30,
        )
        assert rule.name == "Test Rule"
        assert rule.factor_name == "test_factor"
        assert rule.condition == AlertCondition.GT
        assert rule.threshold == 100.0
        assert rule.is_active is True
        assert rule.lookback_days == 30

    def test_rule_repr(self, sample_rule):
        """Test rule string representation."""
        repr_str = repr(sample_rule)
        assert "AlertRule" in repr_str
        assert sample_rule.name in repr_str


class TestAlertNotification:
    """Tests for AlertNotification model."""

    def test_create_notification(self):
        """Test creating a notification."""
        notification = AlertNotification(
            rule_id=1,
            entity_id="AAPL",
            factor_value=1500.0,
            threshold=1000.0,
            notification_status=NotificationStatus.PENDING,
        )
        assert notification.rule_id == 1
        assert notification.entity_id == "AAPL"
        assert notification.notification_status == NotificationStatus.PENDING

    def test_notification_repr(self, sample_notification):
        """Test notification string representation."""
        repr_str = repr(sample_notification)
        assert "AlertNotification" in repr_str


# ===========================================
# INTEGRATION TESTS
# ===========================================


class TestAlertIntegration:
    """Integration tests for alerting system."""

    def test_full_alert_flow(self, mock_session, sample_rule):
        """Test complete alert flow from rule to notification."""
        engine = AlertEngine(session=mock_session)

        # Mock methods
        engine._get_latest_factor_value = Mock(return_value=1500.0)
        engine._is_in_cooldown = Mock(return_value=False)
        engine._send_notification = Mock(return_value=True)

        mock_session.add = Mock()
        mock_session.query = Mock()

        # Check the rule
        notifications = engine.check_rule(sample_rule)

        # Verify notification was created
        assert len(notifications) == 1
        assert notifications[0].factor_value == 1500.0
        assert notifications[0].threshold == 1000.0

    def test_alert_respects_cooldown(self, mock_session, sample_rule):
        """Test that alerts respect cooldown period."""
        engine = AlertEngine(session=mock_session)

        # Mock cooldown to return True
        engine._get_latest_factor_value = Mock(return_value=1500.0)
        engine._is_in_cooldown = Mock(return_value=True)

        notifications = engine.check_rule(sample_rule)

        # No notifications because of cooldown
        assert len(notifications) == 0
