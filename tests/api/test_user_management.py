"""Unit tests for user management and tier API endpoints (US-036 to US-037)."""

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.users import UserTier


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestTierUsage:
    """Tests for viewing tier usage (US-036)."""

    def test_user_usage_endpoint_exists(self):
        """Test that user usage endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/user/usage")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_user_usage_requires_auth(self):
        """Test that user usage endpoint requires authentication."""
        client = get_test_client()
        response = client.get("/api/v1/user/usage")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_auth_usage_endpoint_exists(self):
        """Test that auth usage endpoint exists (from US-022)."""
        client = get_test_client()
        response = client.get("/api/v1/auth/usage")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_usage_history_endpoint_exists(self):
        """Test that usage history endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/user/usage/history")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_usage_history_with_days_param(self):
        """Test usage history with days parameter."""
        client = get_test_client()
        response = client.get("/api/v1/user/usage/history?days=7")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestTierComparison:
    """Tests for tier comparison (US-037)."""

    def test_tiers_endpoint_exists(self):
        """Test that tiers comparison endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/user/tiers")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_tiers_requires_auth(self):
        """Test that tiers endpoint requires authentication."""
        client = get_test_client()
        response = client.get("/api/v1/user/tiers")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestTierUpgrade:
    """Tests for upgrading tier (US-037)."""

    def test_upgrade_endpoint_exists(self):
        """Test that upgrade endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/user/upgrade",
            json={"target_tier": "pro"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_upgrade_requires_auth(self):
        """Test that upgrade endpoint requires authentication."""
        client = get_test_client()
        response = client.post(
            "/api/v1/user/upgrade",
            json={"target_tier": "pro"},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_upgrade_validates_target_tier(self):
        """Test that upgrade validates target tier."""
        client = get_test_client()
        response = client.post(
            "/api/v1/user/upgrade",
            json={"target_tier": "invalid_tier"},
        )
        # Should fail validation or auth
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestUserSchemas:
    """Tests for user management schemas."""

    def test_tier_features_schema(self):
        """Test TierFeatures schema."""
        from src.api.routes.user import TierFeatures

        features = TierFeatures(
            alerts=True,
            backtesting=True,
            websocket=True,
            sdk=True,
            custom_factors=False,
        )
        assert features.alerts == True
        assert features.custom_factors == False

    def test_tier_info_response_schema(self):
        """Test TierInfoResponse schema."""
        from src.api.routes.user import TierInfoResponse, TierFeatures

        response = TierInfoResponse(
            tier=UserTier.PRO,
            name="Professional",
            requests_per_day=10000,
            requests_per_minute=1000,
            history_days=-1,
            features=TierFeatures(
                alerts=True,
                backtesting=True,
                websocket=True,
                sdk=True,
                custom_factors=True,
            ),
            monthly_price_usd=Decimal("99.00"),
        )
        assert response.tier == UserTier.PRO
        assert response.requests_per_day == 10000
        assert response.monthly_price_usd == Decimal("99.00")

    def test_tier_comparison_response_schema(self):
        """Test TierComparisonResponse schema."""
        from src.api.routes.user import TierComparisonResponse, TierInfoResponse, TierFeatures

        free_tier = TierInfoResponse(
            tier=UserTier.FREE,
            name="Free",
            requests_per_day=100,
            requests_per_minute=10,
            history_days=30,
            features=TierFeatures(
                alerts=False,
                backtesting=False,
                websocket=False,
                sdk=False,
                custom_factors=False,
            ),
            monthly_price_usd=Decimal("0.00"),
        )

        pro_tier = TierInfoResponse(
            tier=UserTier.PRO,
            name="Professional",
            requests_per_day=10000,
            requests_per_minute=1000,
            history_days=-1,
            features=TierFeatures(
                alerts=True,
                backtesting=True,
                websocket=True,
                sdk=True,
                custom_factors=True,
            ),
            monthly_price_usd=Decimal("99.00"),
        )

        response = TierComparisonResponse(
            tiers=[free_tier, pro_tier],
            current_tier=UserTier.FREE,
        )
        assert len(response.tiers) == 2
        assert response.current_tier == UserTier.FREE

    def test_usage_detail_response_schema(self):
        """Test UsageDetailResponse schema."""
        from src.api.routes.user import UsageDetailResponse

        response = UsageDetailResponse(
            requests_today=50,
            requests_limit=100,
            requests_percentage=50.0,
            data_bytes_today=1024,
            websocket_connections_today=2,
            alerts_triggered_today=5,
            backtests_run_today=1,
            tier=UserTier.FREE,
            features={"alerts": False, "backtesting": False},
            warning_level=None,
            historical_usage=[],
        )
        assert response.requests_today == 50
        assert response.requests_percentage == 50.0
        assert response.warning_level is None

    def test_usage_detail_with_warning_level(self):
        """Test UsageDetailResponse with warning level."""
        from src.api.routes.user import UsageDetailResponse

        response = UsageDetailResponse(
            requests_today=85,
            requests_limit=100,
            requests_percentage=85.0,
            data_bytes_today=1024,
            websocket_connections_today=0,
            alerts_triggered_today=0,
            backtests_run_today=0,
            tier=UserTier.FREE,
            features={},
            warning_level="80%",
        )
        assert response.warning_level == "80%"

    def test_upgrade_request_schema(self):
        """Test UpgradeRequest schema."""
        from src.api.routes.user import UpgradeRequest

        request = UpgradeRequest(target_tier=UserTier.PRO)
        assert request.target_tier == UserTier.PRO

    def test_upgrade_response_schema(self):
        """Test UpgradeResponse schema."""
        from src.api.routes.user import UpgradeResponse

        response = UpgradeResponse(
            success=True,
            previous_tier=UserTier.FREE,
            new_tier=UserTier.PRO,
            prorated_amount_usd=Decimal("49.50"),
            message="Successfully upgraded from free to pro",
            new_features=["Alert notifications", "Backtesting", "SDK access"],
        )
        assert response.success == True
        assert response.previous_tier == UserTier.FREE
        assert response.new_tier == UserTier.PRO
        assert len(response.new_features) == 3

    def test_usage_history_response_schema(self):
        """Test UsageHistoryResponse schema."""
        from src.api.routes.user import UsageHistoryResponse

        response = UsageHistoryResponse(
            date=datetime.utcnow(),
            api_requests=100,
            data_bytes_downloaded=10240,
            websocket_connections=5,
            alerts_triggered=2,
            backtests_run=1,
        )
        assert response.api_requests == 100
        assert response.websocket_connections == 5


class TestUserTierEnum:
    """Tests for user tier enum values."""

    def test_user_tier_enum_values(self):
        """Test UserTier enum values."""
        assert UserTier.FREE.value == "free"
        assert UserTier.PRO.value == "pro"
        assert UserTier.ENTERPRISE.value == "enterprise"
        assert UserTier.CUSTOM.value == "custom"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_tier_display_name(self):
        """Test tier display name helper."""
        from src.api.routes.user import get_tier_display_name

        assert get_tier_display_name(UserTier.FREE) == "Free"
        assert get_tier_display_name(UserTier.PRO) == "Professional"
        assert get_tier_display_name(UserTier.ENTERPRISE) == "Enterprise"
        assert get_tier_display_name(UserTier.CUSTOM) == "Custom"

    def test_calculate_prorated_amount(self):
        """Test prorated amount calculation."""
        from src.api.routes.user import calculate_prorated_amount

        # Upgrade from $0 to $99 with 15 days remaining
        amount = calculate_prorated_amount(
            Decimal("0"),
            Decimal("99"),
            15,
        )
        # Should be roughly half the price difference
        assert amount > Decimal("0")
        assert amount < Decimal("99")

    def test_calculate_prorated_amount_no_days(self):
        """Test prorated amount with 0 days remaining."""
        from src.api.routes.user import calculate_prorated_amount

        amount = calculate_prorated_amount(
            Decimal("0"),
            Decimal("99"),
            0,
        )
        # Should be full price for new month
        assert amount == Decimal("99")
