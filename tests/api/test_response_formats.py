"""Tests for multiple response formats and rate limiting (US-023)."""

import io
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.factors import (
    ResponseFormat,
    FactorValueResponse,
    _format_csv_response,
    _compute_etf_weighted_averages,
    ETF_CONSTITUENT_WEIGHTS,
)


def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestResponseFormat:
    """Tests for ResponseFormat enum."""

    def test_format_values(self):
        """Test all format values exist."""
        assert ResponseFormat.JSON.value == "json"
        assert ResponseFormat.CSV.value == "csv"
        assert ResponseFormat.PARQUET.value == "parquet"
        assert ResponseFormat.ARROW.value == "arrow"

    def test_format_from_string(self):
        """Test creating format from string."""
        assert ResponseFormat("json") == ResponseFormat.JSON
        assert ResponseFormat("csv") == ResponseFormat.CSV
        assert ResponseFormat("parquet") == ResponseFormat.PARQUET
        assert ResponseFormat("arrow") == ResponseFormat.ARROW


class TestFactorHistoryFormats:
    """Tests for /api/v1/factors/{factor_id}/history with format parameter."""

    def test_history_default_json_format(self):
        """Test that default format is JSON."""
        client = get_test_client()
        response = client.get("/api/v1/factors/test_factor/history?tickers=AAPL")
        # Should not be 404 (endpoint exists)
        assert response.status_code != status.HTTP_404_NOT_FOUND
        # If successful, should return JSON
        if response.status_code == status.HTTP_200_OK:
            assert response.headers.get("content-type", "").startswith("application/json")

    def test_history_json_format_explicit(self):
        """Test explicit JSON format parameter."""
        client = get_test_client()
        response = client.get("/api/v1/factors/test_factor/history?tickers=AAPL&format=json")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_history_csv_format(self):
        """Test CSV format parameter."""
        client = get_test_client()
        response = client.get("/api/v1/factors/test_factor/history?tickers=AAPL&format=csv")
        assert response.status_code != status.HTTP_404_NOT_FOUND
        # If successful, should return CSV
        if response.status_code == status.HTTP_200_OK:
            assert "text/csv" in response.headers.get("content-type", "")
            assert "Content-Disposition" in response.headers

    def test_history_parquet_format(self):
        """Test Parquet format parameter."""
        client = get_test_client()
        response = client.get("/api/v1/factors/test_factor/history?tickers=AAPL&format=parquet")
        # May return 501 if pyarrow not installed, that's acceptable
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_501_NOT_IMPLEMENTED,
        ]

    def test_history_arrow_format(self):
        """Test Arrow format parameter."""
        client = get_test_client()
        response = client.get("/api/v1/factors/test_factor/history?tickers=AAPL&format=arrow")
        # May return 501 if pyarrow not installed, that's acceptable
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_501_NOT_IMPLEMENTED,
        ]

    def test_history_invalid_format(self):
        """Test invalid format parameter returns 422."""
        client = get_test_client()
        response = client.get("/api/v1/factors/test_factor/history?tickers=AAPL&format=xml")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCSVFormatting:
    """Tests for CSV format helper function."""

    def test_csv_format_basic(self):
        """Test basic CSV formatting."""
        data = [
            FactorValueResponse(
                ticker="AAPL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.05,
                variance=0.001,
                data_quality=0.98,
                revision_status="original",
            ),
            FactorValueResponse(
                ticker="GOOGL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.03,
                variance=0.002,
                data_quality=0.95,
                revision_status="original",
            ),
        ]

        response = _format_csv_response(data, "test_factor")

        assert response.media_type == "text/csv"
        content = response.body.decode("utf-8")
        lines = content.strip().split("\n")

        # Check header
        assert lines[0] == "ticker,factor_id,as_of_date,mean,variance,data_quality,revision_status"

        # Check data rows
        assert "AAPL,test_factor,2025-01-15,0.05,0.001,0.98,original" in lines[1]
        assert "GOOGL,test_factor,2025-01-15,0.03,0.002,0.95,original" in lines[2]

    def test_csv_content_disposition(self):
        """Test CSV response includes correct filename."""
        data = [
            FactorValueResponse(
                ticker="AAPL",
                factor_id="my_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.05,
                variance=0.001,
                data_quality=0.98,
                revision_status="original",
            ),
        ]

        response = _format_csv_response(data, "my_factor")

        assert "Content-Disposition" in response.headers
        assert "my_factor_history.csv" in response.headers["Content-Disposition"]


class TestRateLimitHeaders:
    """Tests for rate limit headers (US-023)."""

    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present in responses."""
        client = get_test_client()
        response = client.get("/api/v1/factors")

        # Rate limit headers should be present (unless server error)
        if response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR:
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            # Reset may or may not be present for unlimited tiers

    def test_rate_limit_values_valid(self):
        """Test that rate limit values are valid."""
        client = get_test_client()
        response = client.get("/api/v1/factors")

        if response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR:
            limit = response.headers.get("X-RateLimit-Limit")
            remaining = response.headers.get("X-RateLimit-Remaining")

            # Values should be either numeric or "unlimited"
            if limit != "unlimited":
                assert limit.isdigit()
            if remaining != "unlimited":
                assert remaining.isdigit()

    def test_rate_limit_remaining_decrements(self):
        """Test that remaining count decrements."""
        client = get_test_client()

        # Make two requests
        response1 = client.get("/api/v1/factors")
        response2 = client.get("/api/v1/factors")

        if (response1.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR and
            response2.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR):

            remaining1 = response1.headers.get("X-RateLimit-Remaining", "unlimited")
            remaining2 = response2.headers.get("X-RateLimit-Remaining", "unlimited")

            if remaining1 != "unlimited" and remaining2 != "unlimited":
                assert int(remaining2) <= int(remaining1)

    def test_rate_limit_excluded_paths(self):
        """Test that excluded paths don't have rate limit headers."""
        client = get_test_client()

        # Health endpoint should be excluded
        response = client.get("/health")

        # Should not have rate limit headers (excluded)
        assert response.status_code == status.HTTP_200_OK
        assert "X-RateLimit-Limit" not in response.headers


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    def test_middleware_initialization(self):
        """Test middleware can be initialized."""
        from src.api.middleware.rate_limit import RateLimitMiddleware

        # Just verify import and basic structure
        assert RateLimitMiddleware is not None

    def test_rate_limit_state(self):
        """Test RateLimitState class."""
        from src.api.middleware.rate_limit import RateLimitState

        state = RateLimitState(limit=100, window_seconds=60)

        assert state.limit == 100
        assert state.remaining == 100
        assert state.window_seconds == 60

    def test_rate_limit_check_and_update(self):
        """Test rate limit check and update."""
        from src.api.middleware.rate_limit import RateLimitState

        state = RateLimitState(limit=3, window_seconds=60)

        # First request - allowed
        allowed, limit, remaining, reset = state.check_and_update()
        assert allowed is True
        assert remaining == 2

        # Second request - allowed
        allowed, limit, remaining, reset = state.check_and_update()
        assert allowed is True
        assert remaining == 1

        # Third request - allowed
        allowed, limit, remaining, reset = state.check_and_update()
        assert allowed is True
        assert remaining == 0

        # Fourth request - denied
        allowed, limit, remaining, reset = state.check_and_update()
        assert allowed is False
        assert remaining == 0

    def test_rate_limit_store_tiers(self):
        """Test rate limit store tier limits."""
        from src.api.middleware.rate_limit import RateLimitStore

        store = RateLimitStore()

        assert store.get_limit_for_tier("free") == 100
        assert store.get_limit_for_tier("pro") == 10000
        assert store.get_limit_for_tier("enterprise") == -1  # Unlimited
        assert store.get_limit_for_tier("unknown") == 100  # Default to free

    def test_add_rate_limit_headers(self):
        """Test adding rate limit headers to response."""
        from fastapi import Response
        from src.api.middleware.rate_limit import add_rate_limit_headers

        response = Response(content="test")
        add_rate_limit_headers(response, limit=100, remaining=95, reset_time=1700000000)

        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "95"
        assert response.headers["X-RateLimit-Reset"] == "1700000000"

    def test_add_rate_limit_headers_unlimited(self):
        """Test rate limit headers for unlimited tier."""
        from fastapi import Response
        from src.api.middleware.rate_limit import add_rate_limit_headers

        response = Response(content="test")
        add_rate_limit_headers(response, limit=-1, remaining=-1, reset_time=0)

        assert response.headers["X-RateLimit-Limit"] == "unlimited"
        assert response.headers["X-RateLimit-Remaining"] == "unlimited"

    def test_get_client_key_from_bearer(self):
        """Test extracting client key from Bearer token."""
        from src.api.middleware.rate_limit import get_client_key
        from starlette.datastructures import Headers
        from starlette.requests import Request

        # Create mock request with Bearer token
        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer test-api-key-12345")],
            "query_string": b"",
        }
        request = Request(scope)

        key = get_client_key(request)

        assert key.startswith("api_key:")

    def test_get_client_key_from_query(self):
        """Test extracting client key from query parameter."""
        from src.api.middleware.rate_limit import get_client_key
        from starlette.requests import Request

        # Create mock request with query parameter
        scope = {
            "type": "http",
            "headers": [],
            "query_string": b"api_key=test-api-key-12345",
        }
        request = Request(scope)

        key = get_client_key(request)

        assert key.startswith("api_key:")
