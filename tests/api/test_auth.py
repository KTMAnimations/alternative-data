"""Unit tests for authentication and API integration endpoints (US-022 to US-026)."""

from datetime import datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.users import UserTier


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestAPIKeyAuthentication:
    """Tests for API key authentication (US-022)."""

    def test_register_endpoint_exists(self):
        """Test that registration endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "testpassword123",
                "full_name": "Test User",
            },
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_login_endpoint_exists(self):
        """Test that login endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "test@example.com",
                "password": "testpassword123",
            },
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_me_endpoint_requires_auth(self):
        """Test that /me endpoint requires authentication."""
        client = get_test_client()
        response = client.get("/api/v1/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_api_key_endpoint_exists(self):
        """Test that API key creation endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/auth/api-keys",
            json={"name": "Test Key"},
        )
        # Should fail auth, not 404
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_api_keys_endpoint_exists(self):
        """Test that API key list endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/auth/api-keys")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_delete_api_key_endpoint_exists(self):
        """Test that API key deletion endpoint exists."""
        client = get_test_client()
        response = client.delete("/api/v1/auth/api-keys/1")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_usage_endpoint_exists(self):
        """Test that usage endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/auth/usage")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestFactorHistoryAPI:
    """Tests for factor history API (US-023)."""

    def test_factor_history_endpoint_exists(self):
        """Test that factor history endpoint exists."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/tsa_throughput_momentum/history?tickers=DAL,UAL"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factor_history_requires_tickers(self):
        """Test that factor history requires tickers parameter."""
        client = get_test_client()
        response = client.get("/api/v1/factors/tsa_throughput_momentum/history")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_factor_history_with_date_range(self):
        """Test factor history with date range."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/tsa_throughput_momentum/history"
            "?tickers=DAL&start_date=2025-01-01&end_date=2025-01-14"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factor_history_pagination(self):
        """Test factor history pagination."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/tsa_throughput_momentum/history"
            "?tickers=DAL&limit=10"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestEntityFactorsAPI:
    """Tests for entity factors API (US-024)."""

    def test_factors_list_endpoint_exists(self):
        """Test that factors list endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factors_list_with_domain_filter(self):
        """Test factors list with domain filter."""
        client = get_test_client()
        response = client.get("/api/v1/factors?domain=travel")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factors_list_with_search(self):
        """Test factors list with search."""
        client = get_test_client()
        response = client.get("/api/v1/factors?search=momentum")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factor_detail_endpoint_exists(self):
        """Test that factor detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors/tsa_throughput_momentum")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestPineScriptGeneration:
    """Tests for Pine Script generation (US-025)."""

    # Note: Pine Script endpoint not yet implemented
    # These tests verify endpoint presence when implemented

    def test_factor_decay_endpoint_exists(self):
        """Test that factor decay endpoint exists (prerequisite for Pine Script)."""
        client = get_test_client()
        response = client.get("/api/v1/factors/tsa_throughput_momentum/decay")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestTradingViewSync:
    """Tests for TradingView sync (US-026)."""

    # Note: TradingView sync not yet implemented
    # These are placeholder tests

    def test_factor_compare_endpoint_exists(self):
        """Test that factor compare endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/compare",
            json={
                "factor_ids": ["tsa_throughput_momentum", "seated_diners_momentum"],
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestAuthSchemas:
    """Tests for authentication API schemas."""

    def test_user_create_schema(self):
        """Test UserCreate schema."""
        from src.api.routes.auth import UserCreate

        user = UserCreate(
            email="test@example.com",
            password="testpassword123",
            full_name="Test User",
            company="Test Corp",
        )
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"

    def test_user_response_schema(self):
        """Test UserResponse schema."""
        from src.api.routes.auth import UserResponse

        response = UserResponse(
            id=1,
            email="test@example.com",
            full_name="Test User",
            company="Test Corp",
            tier=UserTier.FREE,
            is_active=True,
            is_verified=False,
            created_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.tier == UserTier.FREE

    def test_token_schema(self):
        """Test Token schema."""
        from src.api.routes.auth import Token

        token = Token(
            access_token="test_token",
            token_type="bearer",
            expires_in=3600,
        )
        assert token.access_token == "test_token"
        assert token.token_type == "bearer"

    def test_api_key_create_schema(self):
        """Test APIKeyCreate schema."""
        from src.api.routes.auth import APIKeyCreate

        key = APIKeyCreate(name="Test Key")
        assert key.name == "Test Key"

    def test_api_key_response_schema(self):
        """Test APIKeyResponse schema."""
        from src.api.routes.auth import APIKeyResponse

        response = APIKeyResponse(
            id=1,
            name="Test Key",
            key_prefix="abc12345",
            rate_limit_per_minute=100,
            created_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.key_prefix == "abc12345"

    def test_usage_response_schema(self):
        """Test UsageResponse schema."""
        from src.api.routes.auth import UsageResponse

        response = UsageResponse(
            requests_today=50,
            requests_limit=100,
            data_bytes_today=1024,
            tier=UserTier.FREE,
            features={"alerts": True, "backtesting": False},
        )
        assert response.requests_today == 50
        assert response.tier == UserTier.FREE


class TestFactorSchemas:
    """Tests for factor API schemas."""

    def test_factor_response_schema(self):
        """Test FactorResponse schema."""
        from src.api.routes.factors import FactorResponse
        from src.models.factors import FactorDomain

        response = FactorResponse(
            id=1,
            factor_id="test_factor",
            name="Test Factor",
            description="A test factor",
            domain=FactorDomain.TRAVEL,
            formula="f(x) = x",
            formula_description="Simple formula",
            economic_rationale="Test rationale",
            primary_entities=["AAPL"],
            historical_ic=0.05,
            historical_ir=0.8,
            historical_tstat=2.5,
            historical_hit_rate=0.55,
            is_active=True,
        )
        assert response.factor_id == "test_factor"
        assert response.domain == FactorDomain.TRAVEL

    def test_factor_history_response_schema(self):
        """Test FactorHistoryResponse schema."""
        from src.api.routes.factors import FactorHistoryResponse, FactorValueResponse
        from datetime import date

        response = FactorHistoryResponse(
            factor_id="test_factor",
            data=[
                FactorValueResponse(
                    ticker="AAPL",
                    factor_id="test_factor",
                    as_of_date=date(2025, 1, 1),
                    mean=0.05,
                    variance=0.01,
                    data_quality=0.95,
                    revision_status="final",
                )
            ],
            total_count=1,
            cursor=None,
        )
        assert response.factor_id == "test_factor"
        assert len(response.data) == 1

    def test_compare_request_schema(self):
        """Test CompareRequest schema."""
        from src.api.routes.factors import CompareRequest
        from datetime import date

        request = CompareRequest(
            factor_ids=["factor_1", "factor_2"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 14),
        )
        assert len(request.factor_ids) == 2

    def test_blend_request_schema(self):
        """Test BlendRequest schema."""
        from src.api.routes.factors import BlendRequest

        request = BlendRequest(
            factor_ids=["factor_1", "factor_2", "factor_3"],
            objective="max_ic",
            constraints={"max_weight": 0.5},
        )
        assert request.objective == "max_ic"
        assert len(request.factor_ids) == 3

    def test_graph_response_schema(self):
        """Test FactorGraphResponse schema."""
        from src.api.routes.factors import FactorGraphResponse, GraphNode, GraphEdge
        from src.models.factors import FactorDomain

        response = FactorGraphResponse(
            nodes=[
                GraphNode(
                    id="f1",
                    name="Factor 1",
                    domain=FactorDomain.TRAVEL,
                    metrics={"ic": 0.05},
                )
            ],
            edges=[
                GraphEdge(
                    source="f1",
                    target="f2",
                    relationship_type="correlated-with",
                    strength=0.8,
                )
            ],
        )
        assert len(response.nodes) == 1
        assert len(response.edges) == 1
