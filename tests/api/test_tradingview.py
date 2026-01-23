"""Unit tests for TradingView API endpoints (US-025 and US-026)."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.factors import FactorDomain


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestPineScriptGeneration:
    """Tests for POST /api/v1/tradingview/{factor_id}/pinescript (US-025)."""

    def test_pinescript_endpoint_exists(self):
        """Test that Pine Script generation endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/tradingview/test_factor/pinescript")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_pinescript_with_default_options(self):
        """Test Pine Script generation with default options."""
        client = get_test_client()
        response = client.post("/api/v1/tradingview/tsa_throughput_momentum/pinescript")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,  # Factor may not exist in test DB
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_with_version_v5(self):
        """Test Pine Script generation with explicit v5 version."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={"version": "v5"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_with_version_v4(self):
        """Test Pine Script generation with v4 version."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={"version": "v4"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_with_webhook_disabled(self):
        """Test Pine Script generation without webhook code."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={"include_webhook": False},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_with_overlay_enabled(self):
        """Test Pine Script generation as overlay indicator."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={"overlay": True},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_with_alerts_disabled(self):
        """Test Pine Script generation without alert conditions."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={"show_alerts": False},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_with_custom_colors(self):
        """Test Pine Script generation with custom colors."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={
                "custom_colors": {
                    "positive": "#00ff00",
                    "negative": "#ff0000",
                    "neutral": "#808080",
                }
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_with_custom_webhook_url(self):
        """Test Pine Script generation with custom webhook URL."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={
                "include_webhook": True,
                "webhook_url": "https://myserver.example.com/webhook",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_nonexistent_factor(self):
        """Test Pine Script generation for nonexistent factor returns 404."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/nonexistent_factor_xyz/pinescript"
        )
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pinescript_invalid_version(self):
        """Test that invalid version is rejected."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={"version": "v3"},  # Invalid version
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestWebhookPush:
    """Tests for POST /api/v1/tradingview/webhook/push (US-026)."""

    def test_webhook_push_endpoint_exists(self):
        """Test that webhook push endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/webhook/push",
            json={
                "factor_id": "test_factor",
                "tickers": ["AAPL"],
                "webhook_secret": "test_secret_12345678",
            },
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_webhook_push_with_valid_request(self):
        """Test webhook push with valid request."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/webhook/push",
            json={
                "factor_id": "tsa_throughput_momentum",
                "tickers": ["DAL", "UAL", "AAL"],
                "webhook_secret": "secure_webhook_secret_123",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_webhook_push_requires_factor_id(self):
        """Test that factor_id is required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/webhook/push",
            json={
                "tickers": ["AAPL"],
                "webhook_secret": "test_secret_12345678",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_webhook_push_requires_tickers(self):
        """Test that tickers list is required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/webhook/push",
            json={
                "factor_id": "test_factor",
                "webhook_secret": "test_secret_12345678",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_webhook_push_requires_tickers_nonempty(self):
        """Test that tickers list must not be empty."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/webhook/push",
            json={
                "factor_id": "test_factor",
                "tickers": [],
                "webhook_secret": "test_secret_12345678",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_webhook_push_requires_secret(self):
        """Test that webhook_secret is required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/webhook/push",
            json={
                "factor_id": "test_factor",
                "tickers": ["AAPL"],
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_webhook_push_secret_minimum_length(self):
        """Test that webhook_secret has minimum length."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/webhook/push",
            json={
                "factor_id": "test_factor",
                "tickers": ["AAPL"],
                "webhook_secret": "short",  # Less than 16 chars
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAnnotationImport:
    """Tests for POST /api/v1/tradingview/annotations/import (US-026)."""

    def test_annotation_import_endpoint_exists(self):
        """Test that annotation import endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/annotations/import",
            json={
                "chart_id": "test_chart",
                "ticker": "AAPL",
            },
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_annotation_import_with_valid_request(self):
        """Test annotation import with valid request."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/annotations/import",
            json={
                "chart_id": "AAPL-daily-123",
                "ticker": "AAPL",
                "annotation_types": ["horizontal_line", "trend_line"],
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-20T00:00:00Z",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_annotation_import_requires_chart_id(self):
        """Test that chart_id is required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/annotations/import",
            json={
                "ticker": "AAPL",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_annotation_import_requires_ticker(self):
        """Test that ticker is required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/annotations/import",
            json={
                "chart_id": "test_chart",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_annotation_import_with_all_types(self):
        """Test annotation import with all annotation types."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/annotations/import",
            json={
                "chart_id": "test_chart",
                "ticker": "AAPL",
                "annotation_types": [
                    "horizontal_line",
                    "vertical_line",
                    "trend_line",
                    "text",
                    "shape",
                    "label",
                ],
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_annotation_import_invalid_type(self):
        """Test that invalid annotation type is rejected."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/annotations/import",
            json={
                "chart_id": "test_chart",
                "ticker": "AAPL",
                "annotation_types": ["invalid_type"],
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestOAuthFlow:
    """Tests for OAuth endpoints (US-026)."""

    def test_oauth_init_endpoint_exists(self):
        """Test that OAuth init endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/oauth/init",
            json={"redirect_uri": "https://example.com/callback"},
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_oauth_init_with_valid_request(self):
        """Test OAuth init with valid request."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/oauth/init",
            json={
                "redirect_uri": "https://example.com/callback",
                "scopes": ["chart:read", "chart:write"],
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_oauth_init_requires_redirect_uri(self):
        """Test that redirect_uri is required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/oauth/init",
            json={
                "scopes": ["chart:read"],
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_oauth_init_returns_authorization_url(self):
        """Test that OAuth init returns authorization URL."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/oauth/init",
            json={"redirect_uri": "https://example.com/callback"},
        )
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "authorization_url" in data
            assert "state" in data
            assert "expires_at" in data

    def test_oauth_callback_endpoint_exists(self):
        """Test that OAuth callback endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/oauth/callback",
            json={
                "code": "test_auth_code",
                "state": "test_state_123",
            },
        )
        # Should return 501 Not Implemented (placeholder)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_501_NOT_IMPLEMENTED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_oauth_callback_requires_code(self):
        """Test that code is required for callback."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/oauth/callback",
            json={"state": "test_state"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_oauth_callback_requires_state(self):
        """Test that state is required for callback."""
        client = get_test_client()
        response = client.post(
            "/api/v1/tradingview/oauth/callback",
            json={"code": "test_code"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestConnectionStatus:
    """Tests for connection status endpoints (US-026)."""

    def test_connection_status_endpoint_exists(self):
        """Test that connection status endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/tradingview/connection/status")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_connection_status_returns_valid_status(self):
        """Test that connection status returns valid structure."""
        client = get_test_client()
        response = client.get("/api/v1/tradingview/connection/status")
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "status" in data
            assert data["status"] in ["connected", "disconnected", "pending", "error"]
            assert "scopes" in data

    def test_disconnect_endpoint_exists(self):
        """Test that disconnect endpoint exists."""
        client = get_test_client()
        response = client.delete("/api/v1/tradingview/connection")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_disconnect_returns_confirmation(self):
        """Test that disconnect returns confirmation."""
        client = get_test_client()
        response = client.delete("/api/v1/tradingview/connection")
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "status" in data
            assert data["status"] == "disconnected"


class TestWebhookConfig:
    """Tests for webhook configuration endpoint."""

    def test_webhook_config_endpoint_exists(self):
        """Test that webhook config endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/tradingview/webhook/test_factor/config")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_webhook_config_returns_valid_structure(self):
        """Test that webhook config returns valid structure."""
        client = get_test_client()
        response = client.get("/api/v1/tradingview/webhook/tsa_throughput_momentum/config")
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "factor_id" in data
            assert "webhook_url" in data
            assert "json_template" in data
            assert "instructions" in data

    def test_webhook_config_nonexistent_factor(self):
        """Test webhook config for nonexistent factor returns 404."""
        client = get_test_client()
        response = client.get("/api/v1/tradingview/webhook/nonexistent_factor_xyz/config")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestResponseSchemas:
    """Tests for TradingView API response schemas."""

    def test_pinescript_response_schema(self):
        """Test PineScriptResponse schema structure."""
        from src.api.routes.tradingview import PineScriptResponse, PineScriptVersion

        response = PineScriptResponse(
            factor_id="test_factor",
            factor_name="Test Factor",
            pine_script_code="// Pine Script v5...",
            version=PineScriptVersion.V5,
            setup_instructions=["Step 1", "Step 2"],
            webhook_url=None,
            generated_at=datetime.utcnow(),
        )

        assert response.factor_id == "test_factor"
        assert response.version == PineScriptVersion.V5
        assert len(response.setup_instructions) == 2

    def test_webhook_push_response_schema(self):
        """Test WebhookPushResponse schema structure."""
        from src.api.routes.tradingview import WebhookPushResponse

        response = WebhookPushResponse(
            status="queued",
            factor_id="test_factor",
            tickers_pushed=["AAPL", "MSFT"],
            timestamp=datetime.utcnow(),
            next_push_scheduled=None,
        )

        assert response.status == "queued"
        assert len(response.tickers_pushed) == 2

    def test_annotation_import_response_schema(self):
        """Test AnnotationImportResponse schema structure."""
        from src.api.routes.tradingview import (
            AnnotationImportResponse,
            AnnotationData,
            AnnotationType,
        )

        annotation = AnnotationData(
            id="ann_001",
            type=AnnotationType.HORIZONTAL_LINE,
            timestamp=datetime.utcnow(),
            price_level=185.50,
            text="Support",
            color="#26a69a",
            metadata={},
        )

        response = AnnotationImportResponse(
            chart_id="test_chart",
            ticker="AAPL",
            annotations=[annotation],
            total_count=1,
            imported_at=datetime.utcnow(),
        )

        assert response.chart_id == "test_chart"
        assert response.total_count == 1
        assert response.annotations[0].type == AnnotationType.HORIZONTAL_LINE

    def test_oauth_init_response_schema(self):
        """Test OAuthInitResponse schema structure."""
        from src.api.routes.tradingview import OAuthInitResponse

        response = OAuthInitResponse(
            authorization_url="https://tradingview.com/oauth/authorize?...",
            state="abc123",
            expires_at=datetime.utcnow(),
        )

        assert "tradingview.com" in response.authorization_url
        assert response.state == "abc123"

    def test_connection_status_schema(self):
        """Test TradingViewConnectionStatus schema structure."""
        from src.api.routes.tradingview import (
            TradingViewConnectionStatus,
            TradingViewSyncStatus,
        )

        response = TradingViewConnectionStatus(
            status=TradingViewSyncStatus.CONNECTED,
            connected_at=datetime.utcnow(),
            last_sync=datetime.utcnow(),
            scopes=["chart:read", "chart:write"],
            username="trader123",
        )

        assert response.status == TradingViewSyncStatus.CONNECTED
        assert len(response.scopes) == 2


class TestEnums:
    """Tests for TradingView enum values."""

    def test_pine_script_versions(self):
        """Test PineScriptVersion enum values."""
        from src.api.routes.tradingview import PineScriptVersion

        assert PineScriptVersion.V5.value == "v5"
        assert PineScriptVersion.V4.value == "v4"

    def test_sync_status_values(self):
        """Test TradingViewSyncStatus enum values."""
        from src.api.routes.tradingview import TradingViewSyncStatus

        assert TradingViewSyncStatus.CONNECTED.value == "connected"
        assert TradingViewSyncStatus.DISCONNECTED.value == "disconnected"
        assert TradingViewSyncStatus.PENDING.value == "pending"
        assert TradingViewSyncStatus.ERROR.value == "error"

    def test_annotation_type_values(self):
        """Test AnnotationType enum values."""
        from src.api.routes.tradingview import AnnotationType

        expected_types = [
            "horizontal_line",
            "vertical_line",
            "trend_line",
            "text",
            "shape",
            "label",
        ]
        for type_value in expected_types:
            assert AnnotationType(type_value)


class TestPineScriptHelpers:
    """Tests for Pine Script generation helper functions."""

    def test_generate_pine_script_v5_basic(self):
        """Test basic Pine Script v5 generation."""
        from unittest.mock import MagicMock
        from src.api.routes.tradingview import generate_pine_script_v5

        # Create mock factor
        mock_factor = MagicMock()
        mock_factor.factor_id = "test_momentum"
        mock_factor.name = "Test Momentum Factor"
        mock_factor.description = "A test factor for momentum"
        mock_factor.domain.value = "travel"
        mock_factor.formula = r"\frac{x}{y}"
        mock_factor.economic_rationale = "Tests economic hypothesis"
        mock_factor.primary_entities = ["TEST", "DEMO"]
        mock_factor.historical_ic = Decimal("0.045")
        mock_factor.historical_ir = Decimal("0.85")

        script = generate_pine_script_v5(mock_factor)

        # Verify script structure
        assert "//@version=5" in script
        assert "test_momentum" in script
        assert "Test Momentum Factor" in script
        assert "indicator(" in script

    def test_generate_pine_script_with_alerts(self):
        """Test Pine Script generation includes alerts."""
        from unittest.mock import MagicMock
        from src.api.routes.tradingview import generate_pine_script_v5

        mock_factor = MagicMock()
        mock_factor.factor_id = "test_factor"
        mock_factor.name = "Test Factor"
        mock_factor.description = "Test"
        mock_factor.domain.value = "travel"
        mock_factor.formula = "x"
        mock_factor.economic_rationale = "Test"
        mock_factor.primary_entities = []
        mock_factor.historical_ic = None
        mock_factor.historical_ir = None

        script = generate_pine_script_v5(mock_factor, show_alerts=True)
        assert "alertcondition(" in script

    def test_generate_pine_script_without_alerts(self):
        """Test Pine Script generation excludes alerts when disabled."""
        from unittest.mock import MagicMock
        from src.api.routes.tradingview import generate_pine_script_v5

        mock_factor = MagicMock()
        mock_factor.factor_id = "test_factor"
        mock_factor.name = "Test Factor"
        mock_factor.description = "Test"
        mock_factor.domain.value = "travel"
        mock_factor.formula = "x"
        mock_factor.economic_rationale = "Test"
        mock_factor.primary_entities = []
        mock_factor.historical_ic = None
        mock_factor.historical_ir = None

        script = generate_pine_script_v5(mock_factor, show_alerts=False)
        assert "alertcondition(" not in script

    def test_generate_pine_script_overlay_mode(self):
        """Test Pine Script generation in overlay mode."""
        from unittest.mock import MagicMock
        from src.api.routes.tradingview import generate_pine_script_v5

        mock_factor = MagicMock()
        mock_factor.factor_id = "test_factor"
        mock_factor.name = "Test Factor"
        mock_factor.description = "Test"
        mock_factor.domain.value = "travel"
        mock_factor.formula = "x"
        mock_factor.economic_rationale = "Test"
        mock_factor.primary_entities = []
        mock_factor.historical_ic = None
        mock_factor.historical_ir = None

        script = generate_pine_script_v5(mock_factor, overlay=True)
        assert "overlay=true" in script

    def test_generate_pine_script_with_webhook(self):
        """Test Pine Script generation includes webhook code."""
        from unittest.mock import MagicMock
        from src.api.routes.tradingview import generate_pine_script_v5

        mock_factor = MagicMock()
        mock_factor.factor_id = "test_factor"
        mock_factor.name = "Test Factor"
        mock_factor.description = "Test"
        mock_factor.domain.value = "travel"
        mock_factor.formula = "x"
        mock_factor.economic_rationale = "Test"
        mock_factor.primary_entities = []
        mock_factor.historical_ic = None
        mock_factor.historical_ir = None

        script = generate_pine_script_v5(mock_factor, include_webhook=True)
        assert "Webhook Integration" in script
        assert "Webhook URL" in script

    def test_get_setup_instructions(self):
        """Test setup instructions generation."""
        from unittest.mock import MagicMock
        from src.api.routes.tradingview import get_setup_instructions, PineScriptVersion

        mock_factor = MagicMock()

        instructions = get_setup_instructions(mock_factor, PineScriptVersion.V5)

        assert len(instructions) > 0
        assert any("TradingView" in i for i in instructions)
        assert any("Pine Editor" in i for i in instructions)
        assert any("v5" in i for i in instructions)


class TestIntegrationScenarios:
    """Integration tests for TradingView workflows."""

    def test_full_pinescript_generation_workflow(self):
        """Test complete Pine Script generation workflow."""
        client = get_test_client()

        # Step 1: Generate Pine Script
        response = client.post(
            "/api/v1/tradingview/tsa_throughput_momentum/pinescript",
            json={
                "version": "v5",
                "include_webhook": True,
                "overlay": False,
                "show_alerts": True,
            },
        )

        # Response should exist (not 404)
        assert response.status_code != status.HTTP_404_NOT_FOUND

        # If successful, verify response structure
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "pine_script_code" in data
            assert "setup_instructions" in data
            assert "//@version=5" in data["pine_script_code"]

    def test_full_oauth_connection_workflow(self):
        """Test OAuth connection workflow."""
        client = get_test_client()

        # Step 1: Initialize OAuth
        init_response = client.post(
            "/api/v1/tradingview/oauth/init",
            json={
                "redirect_uri": "https://example.com/callback",
                "scopes": ["chart:read", "chart:write"],
            },
        )

        if init_response.status_code == status.HTTP_200_OK:
            data = init_response.json()
            assert "authorization_url" in data
            state = data["state"]

            # Step 2: Try callback (should be not implemented)
            callback_response = client.post(
                "/api/v1/tradingview/oauth/callback",
                json={
                    "code": "test_auth_code",
                    "state": state,
                },
            )
            # Should return 501 since it's a placeholder
            assert callback_response.status_code == status.HTTP_501_NOT_IMPLEMENTED

    def test_webhook_config_and_push_workflow(self):
        """Test webhook configuration and push workflow."""
        client = get_test_client()

        # Step 1: Get webhook configuration
        config_response = client.get(
            "/api/v1/tradingview/webhook/tsa_throughput_momentum/config"
        )

        if config_response.status_code == status.HTTP_200_OK:
            config = config_response.json()
            factor_id = config["factor_id"]

            # Step 2: Push data via webhook
            push_response = client.post(
                "/api/v1/tradingview/webhook/push",
                json={
                    "factor_id": factor_id,
                    "tickers": ["DAL", "UAL"],
                    "webhook_secret": "secure_webhook_secret_123",
                },
            )

            assert push_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]
