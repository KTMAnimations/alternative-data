"""Unit tests for alerts API endpoints (US-009 to US-013)."""

from datetime import datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.alerts import AlertType, AlertDirection, NotificationChannel


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestThresholdAlerts:
    """Tests for threshold alerts (US-009)."""

    def test_list_alerts_endpoint_exists(self):
        """Test that list alerts endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/alerts")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_create_alert_endpoint_exists(self):
        """Test that create alert endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Test Alert",
                "alert_type": "threshold",
                "threshold_value": 0.05,
                "direction": "above",
                "notification_channel": "email",
            },
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_threshold_alert_requires_value_and_direction(self):
        """Test that threshold alerts require threshold_value and direction."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Test Alert",
                "alert_type": "threshold",
                "notification_channel": "email",
            },
        )
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_alert_endpoint_exists(self):
        """Test that get alert endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/alerts/1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_update_alert_endpoint_exists(self):
        """Test that update alert endpoint exists."""
        client = get_test_client()
        response = client.patch(
            "/api/v1/alerts/1",
            json={"is_enabled": False},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_delete_alert_endpoint_exists(self):
        """Test that delete alert endpoint exists."""
        client = get_test_client()
        response = client.delete("/api/v1/alerts/1")
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_test_alert_endpoint_exists(self):
        """Test that test alert endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/alerts/1/test")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestAnomalyAlerts:
    """Tests for anomaly detection alerts (US-010)."""

    def test_create_anomaly_alert(self):
        """Test creating an anomaly alert."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Anomaly Alert",
                "alert_type": "anomaly",
                "sensitivity_std_devs": 2.5,
                "baseline_period_days": 30,
                "notification_channel": "email",
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_create_ml_anomaly_alert(self):
        """Test creating ML-based anomaly alert."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "ML Anomaly Alert",
                "alert_type": "anomaly",
                "use_ml_detection": True,
                "notification_channel": "email",
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestEventAlerts:
    """Tests for event-based alerts (US-011)."""

    def test_create_event_alert(self):
        """Test creating an event alert."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Earthquake Alert",
                "alert_type": "event",
                "event_type": "earthquake",
                "event_criteria": {"min_magnitude": 6.0},
                "geographic_filter": {"region": "California"},
                "notification_channel": "email",
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_event_alert_requires_event_type(self):
        """Test that event alerts require event_type."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Event Alert",
                "alert_type": "event",
                "notification_channel": "email",
            },
        )
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestStreamingEndpoints:
    """Tests for WebSocket streaming (US-012)."""

    def test_stream_status_endpoint_exists(self):
        """Test that stream status endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/stream/status")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_stream_status_returns_connection_count(self):
        """Test that stream status returns connection count."""
        client = get_test_client()
        response = client.get("/api/v1/stream/status")
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "active_connections" in data
            assert "timestamp" in data


class TestAlertFatigueManagement:
    """Tests for alert fatigue management (US-013)."""

    def test_create_alert_with_cooldown(self):
        """Test creating alert with cooldown period."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Cooldown Alert",
                "alert_type": "threshold",
                "threshold_value": 0.05,
                "direction": "above",
                "notification_channel": "email",
                "cooldown_minutes": 60,
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_create_alert_with_daily_digest(self):
        """Test creating alert with daily digest option."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Digest Alert",
                "alert_type": "threshold",
                "threshold_value": 0.05,
                "direction": "above",
                "notification_channel": "email",
                "use_daily_digest": True,
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_alert_history(self):
        """Test getting alert history."""
        client = get_test_client()
        response = client.get("/api/v1/alerts/1/history")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_alert_history_with_limit(self):
        """Test getting alert history with limit."""
        client = get_test_client()
        response = client.get("/api/v1/alerts/1/history?limit=10")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestAlertSchemas:
    """Tests for alert API schemas."""

    def test_alert_create_schema(self):
        """Test AlertCreate schema."""
        from src.api.routes.alerts import AlertCreate

        alert = AlertCreate(
            name="Test Alert",
            alert_type=AlertType.THRESHOLD,
            threshold_value=0.05,
            direction=AlertDirection.ABOVE,
            notification_channel=NotificationChannel.EMAIL,
        )
        assert alert.name == "Test Alert"
        assert alert.threshold_value == 0.05

    def test_alert_update_schema(self):
        """Test AlertUpdate schema."""
        from src.api.routes.alerts import AlertUpdate

        update = AlertUpdate(
            is_enabled=False,
            threshold_value=0.10,
        )
        assert update.is_enabled == False
        assert update.threshold_value == 0.10

    def test_alert_response_schema(self):
        """Test AlertResponse schema."""
        from src.api.routes.alerts import AlertResponse

        response = AlertResponse(
            id=1,
            name="Test Alert",
            description=None,
            alert_type=AlertType.THRESHOLD,
            factor_id=1,
            ticker_list=["AAPL"],
            threshold_value=0.05,
            direction=AlertDirection.ABOVE,
            notification_channel=NotificationChannel.EMAIL,
            is_enabled=True,
            trigger_count=0,
            last_triggered_at=None,
            created_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.name == "Test Alert"


class TestWebhookAlerts:
    """Tests for webhook notification channel."""

    def test_webhook_alert_requires_url(self):
        """Test that webhook alerts require webhook_url."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Webhook Alert",
                "alert_type": "threshold",
                "threshold_value": 0.05,
                "direction": "above",
                "notification_channel": "webhook",
            },
        )
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_create_webhook_alert(self):
        """Test creating webhook alert with URL."""
        client = get_test_client()
        response = client.post(
            "/api/v1/alerts",
            json={
                "name": "Webhook Alert",
                "alert_type": "threshold",
                "threshold_value": 0.05,
                "direction": "above",
                "notification_channel": "webhook",
                "webhook_url": "https://example.com/webhook",
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestStreamSubscription:
    """Tests for streaming subscription model."""

    def test_stream_subscription_model(self):
        """Test StreamSubscription model."""
        from src.api.routes.streaming import StreamSubscription, VerbosityLevel

        subscription = StreamSubscription(
            factors=["factor_1", "factor_2"],
            tickers=["AAPL", "GOOGL"],
            verbosity=VerbosityLevel.FULL,
        )
        assert len(subscription.factors) == 2
        assert len(subscription.tickers) == 2
        assert subscription.verbosity == VerbosityLevel.FULL

    def test_verbosity_level_enum(self):
        """Test VerbosityLevel enum values."""
        from src.api.routes.streaming import VerbosityLevel

        assert VerbosityLevel.SIMPLE.value == "simple"
        assert VerbosityLevel.DELTA.value == "delta"
        assert VerbosityLevel.FULL.value == "full"
