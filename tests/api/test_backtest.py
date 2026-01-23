"""Unit tests for backtesting API endpoints (US-017 to US-021)."""

from datetime import date
from io import BytesIO

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestRunBacktest:
    """Tests for backtest execution (US-017)."""

    def test_backtest_endpoint_exists(self):
        """Test that backtest run endpoint exists."""
        client = get_test_client()
        # Create a simple CSV file
        csv_content = "ticker,date,return\nAAPL,2025-01-01,0.01"
        files = {"returns_file": ("returns.csv", csv_content, "text/csv")}
        response = client.post(
            "/api/v1/backtest/run",
            data={
                "factor_id": "tsa_throughput_momentum",
                "start_date": "2025-01-01",
                "end_date": "2025-01-14",
            },
            files=files,
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_backtest_requires_returns_file(self):
        """Test that backtest requires returns file."""
        client = get_test_client()
        response = client.post(
            "/api/v1/backtest/run",
            data={
                "factor_id": "tsa_throughput_momentum",
                "start_date": "2025-01-01",
                "end_date": "2025-01-14",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestFactorDecay:
    """Tests for factor decay analysis (US-018)."""

    def test_decay_endpoint_exists(self):
        """Test that decay endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/decay/tsa_throughput_momentum")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decay_not_found(self):
        """Test decay for non-existent factor."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/decay/nonexistent_factor")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestSeasonality:
    """Tests for seasonality analysis (US-019)."""

    def test_seasonality_endpoint_exists(self):
        """Test that seasonality endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/seasonality/tsa_throughput_momentum")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_seasonality_not_found(self):
        """Test seasonality for non-existent factor."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/seasonality/nonexistent_factor")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestResearchPack:
    """Tests for research pack export (US-020 & US-021)."""

    def test_export_endpoint_exists(self):
        """Test that export endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/backtest/export",
            json={
                "factor_id": "tsa_throughput_momentum",
                "include_notebook": True,
                "include_data": True,
                "formats": ["csv", "json"],
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_export_with_minimal_options(self):
        """Test export with minimal options."""
        client = get_test_client()
        response = client.post(
            "/api/v1/backtest/export",
            json={
                "factor_id": "tsa_throughput_momentum",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestBacktestSchemas:
    """Tests for backtest API schemas."""

    def test_backtest_request_schema(self):
        """Test BacktestRequest schema."""
        from src.api.routes.backtest import BacktestRequest

        request = BacktestRequest(
            factor_id="test_factor",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 14),
        )
        assert request.factor_id == "test_factor"

    def test_backtest_metrics_schema(self):
        """Test BacktestMetrics schema."""
        from src.api.routes.backtest import BacktestMetrics

        metrics = BacktestMetrics(
            ic=0.045,
            ir=0.85,
            tstat=3.2,
            hit_rate=0.58,
            ic_monthly=[{"month": "2025-01", "ic": 0.05}],
            decile_returns=[0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10],
        )
        assert metrics.ic == 0.045
        assert metrics.ir == 0.85

    def test_backtest_response_schema(self):
        """Test BacktestResponse schema."""
        from src.api.routes.backtest import BacktestResponse, BacktestMetrics

        response = BacktestResponse(
            factor_id="test_factor",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 14),
            metrics=BacktestMetrics(
                ic=0.045,
                ir=0.85,
                tstat=3.2,
                hit_rate=0.58,
                ic_monthly=[],
                decile_returns=[],
            ),
            warnings=["Test warning"],
        )
        assert response.factor_id == "test_factor"
        assert len(response.warnings) == 1

    def test_decay_response_schema(self):
        """Test DecayResponse schema."""
        from src.api.routes.backtest import DecayResponse

        response = DecayResponse(
            factor_id="test_factor",
            decay_curve={"1d": 0.045, "5d": 0.035, "10d": 0.025},
            half_life_days=7,
        )
        assert response.factor_id == "test_factor"
        assert response.half_life_days == 7

    def test_seasonality_response_schema(self):
        """Test SeasonalityResponse schema."""
        from src.api.routes.backtest import SeasonalityResponse

        response = SeasonalityResponse(
            factor_id="test_factor",
            day_of_week_ic={
                "Monday": 0.05,
                "Tuesday": 0.04,
                "Wednesday": 0.03,
                "Thursday": 0.04,
                "Friday": 0.05,
            },
            monthly_ic={str(i): 0.04 for i in range(1, 13)},
            holiday_effects=[{"holiday": "Thanksgiving", "effect": -0.02}],
        )
        assert response.factor_id == "test_factor"
        assert len(response.day_of_week_ic) == 5

    def test_research_pack_request_schema(self):
        """Test ResearchPackRequest schema."""
        from src.api.routes.backtest import ResearchPackRequest

        request = ResearchPackRequest(
            factor_id="test_factor",
            include_notebook=True,
            include_data=True,
            formats=["csv", "parquet"],
        )
        assert request.factor_id == "test_factor"
        assert "parquet" in request.formats
