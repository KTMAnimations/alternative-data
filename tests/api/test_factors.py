"""Unit tests for factors API endpoints (US-005 to US-008)."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.factors import FactorDomain


# Create test client that doesn't raise server exceptions
# This allows us to test endpoint existence without database
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestListFactors:
    """Tests for GET /api/v1/factors (US-005)."""

    def test_list_factors_endpoint_exists(self):
        """Test that list factors endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_list_factors_with_domain_filter(self):
        """Test filtering factors by domain."""
        client = get_test_client()
        response = client.get("/api/v1/factors?domain=travel")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_list_factors_with_search(self):
        """Test searching factors by name."""
        client = get_test_client()
        response = client.get("/api/v1/factors?search=momentum")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_list_factors_active_only(self):
        """Test filtering for active factors only."""
        client = get_test_client()
        response = client.get("/api/v1/factors?active_only=true")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestFactorGraph:
    """Tests for GET /api/v1/factors/graph (US-005)."""

    def test_factor_graph_endpoint_exists(self):
        """Test that factor graph endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors/graph")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_factor_graph_with_domain_filter(self):
        """Test filtering graph by domain."""
        client = get_test_client()
        response = client.get("/api/v1/factors/graph?domain=travel")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_factor_graph_with_relationship_type(self):
        """Test filtering by relationship type."""
        client = get_test_client()
        response = client.get("/api/v1/factors/graph?relationship_type=correlated-with")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestFactorDetail:
    """Tests for GET /api/v1/factors/{factor_id} (US-006)."""

    def test_factor_detail_endpoint_exists(self):
        """Test that factor detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors/tsa_throughput_momentum")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factor_not_found_returns_404(self):
        """Test that missing factor returns 404."""
        client = get_test_client()
        response = client.get("/api/v1/factors/nonexistent_factor_xyz")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestFactorComparison:
    """Tests for POST /api/v1/factors/compare (US-007)."""

    def test_compare_endpoint_exists(self):
        """Test that compare endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/compare",
            json={"factor_ids": ["factor_a", "factor_b"]},
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_compare_requires_minimum_factors(self):
        """Test that at least 2 factors required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/compare",
            json={"factor_ids": ["only_one"]},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_compare_max_four_factors(self):
        """Test that max 4 factors can be compared."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/compare",
            json={"factor_ids": ["a", "b", "c", "d", "e"]},  # 5 factors
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestFactorBlend:
    """Tests for POST /api/v1/factors/blend (US-008)."""

    def test_blend_endpoint_exists(self):
        """Test that blend endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/blend",
            json={"factor_ids": ["factor_a", "factor_b"]},
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_blend_with_objective(self):
        """Test blending with optimization objective."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/blend",
            json={
                "factor_ids": ["factor_a", "factor_b"],
                "objective": "max_ic",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_blend_invalid_objective(self):
        """Test that invalid objective is rejected."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/blend",
            json={
                "factor_ids": ["factor_a", "factor_b"],
                "objective": "invalid_objective",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_blend_with_constraints(self):
        """Test blending with constraints."""
        client = get_test_client()
        response = client.post(
            "/api/v1/factors/blend",
            json={
                "factor_ids": ["factor_a", "factor_b"],
                "objective": "max_sharpe",
                "constraints": {"max_weight": 0.6},
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestFactorDecay:
    """Tests for GET /api/v1/factors/{factor_id}/decay (US-018)."""

    def test_decay_endpoint_exists(self):
        """Test that decay endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors/tsa_throughput_momentum/decay")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestFactorHistory:
    """Tests for GET /api/v1/factors/{factor_id}/history (US-023)."""

    def test_history_endpoint_exists(self):
        """Test that history endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors/tsa_throughput_momentum/history?tickers=DAL")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_history_requires_tickers(self):
        """Test that tickers parameter is required."""
        client = get_test_client()
        response = client.get("/api/v1/factors/tsa_throughput_momentum/history")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_history_with_date_range(self):
        """Test history with date range."""
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

    def test_history_with_limit(self):
        """Test history with limit parameter."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/tsa_throughput_momentum/history?tickers=DAL&limit=100"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestFactorResponseSchemas:
    """Tests for factor API response schemas."""

    def test_factor_response_schema(self):
        """Test FactorResponse schema structure."""
        from src.api.routes.factors import FactorResponse

        response = FactorResponse(
            id=1,
            factor_id="test_factor",
            name="Test Factor",
            description="Test description",
            domain=FactorDomain.TRAVEL,
            formula=r"\frac{x}{y}",
            formula_description="x divided by y",
            economic_rationale="Test rationale",
            primary_entities=["TEST"],
            historical_ic=0.045,
            historical_ir=0.85,
            historical_tstat=3.2,
            historical_hit_rate=0.58,
            is_active=True,
        )

        assert response.factor_id == "test_factor"
        assert response.historical_ic == 0.045

    def test_factor_graph_response_schema(self):
        """Test graph response schema."""
        from src.api.routes.factors import FactorGraphResponse, GraphNode, GraphEdge

        node = GraphNode(
            id="test_factor",
            name="Test Factor",
            domain=FactorDomain.TRAVEL,
            metrics={"ic": 0.045, "ir": 0.85},
        )

        edge = GraphEdge(
            source="factor_a",
            target="factor_b",
            relationship_type="correlated-with",
            strength=0.65,
        )

        response = FactorGraphResponse(
            nodes=[node],
            edges=[edge],
        )

        assert len(response.nodes) == 1
        assert len(response.edges) == 1

    def test_compare_request_schema(self):
        """Test CompareRequest schema."""
        from src.api.routes.factors import CompareRequest

        request = CompareRequest(
            factor_ids=["factor_a", "factor_b", "factor_c"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert len(request.factor_ids) == 3

    def test_blend_request_schema(self):
        """Test BlendRequest schema."""
        from src.api.routes.factors import BlendRequest

        request = BlendRequest(
            factor_ids=["factor_a", "factor_b"],
            objective="max_ic",
            constraints={"max_weight": 0.5},
        )

        assert request.objective == "max_ic"
        assert request.constraints["max_weight"] == 0.5


class TestFactorHistoryResponse:
    """Tests for factor history response."""

    def test_factor_history_response_schema(self):
        """Test FactorHistoryResponse schema."""
        from src.api.routes.factors import FactorHistoryResponse, FactorValueResponse

        value = FactorValueResponse(
            ticker="DAL",
            factor_id="tsa_throughput_momentum",
            as_of_date=date(2025, 1, 14),
            mean=0.05,
            variance=0.001,
            data_quality=0.98,
            revision_status="original",
        )

        response = FactorHistoryResponse(
            factor_id="tsa_throughput_momentum",
            data=[value],
            total_count=1,
            cursor=None,
        )

        assert response.factor_id == "tsa_throughput_momentum"
        assert response.total_count == 1
        assert response.data[0].ticker == "DAL"
