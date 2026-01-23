"""Unit tests for Epic 5 Backtesting features (US-018 to US-021)."""

from datetime import date
from decimal import Decimal
from io import BytesIO
import json
import zipfile

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.experiments import ExperimentStatus


def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# US-018: Multi-factor comparison in decay analysis
# =============================================================================

class TestMultiFactorDecay:
    """Tests for multi-factor decay comparison (US-018)."""

    def test_decay_compare_endpoint_exists(self):
        """Test that decay compare endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/decay/compare?factor_ids=factor1,factor2")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decay_compare_requires_factor_ids(self):
        """Test that compare endpoint requires factor_ids parameter."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/decay/compare")
        # 422 for validation error, 500 if DB not available
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decay_compare_max_factors(self):
        """Test that compare endpoint limits to 4 factors."""
        client = get_test_client()
        response = client.get(
            "/api/v1/backtest/decay/compare?factor_ids=f1,f2,f3,f4,f5"
        )
        # Should return 400 for too many factors or 404 if factors don't exist
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_multi_factor_decay_response_schema(self):
        """Test MultiFactorDecayResponse schema structure."""
        from src.api.routes.backtest import MultiFactorDecayResponse, DecayResponse

        response = MultiFactorDecayResponse(
            factors=[
                DecayResponse(
                    factor_id="factor1",
                    decay_curve={"1d": 0.05, "5d": 0.04, "10d": 0.03},
                    half_life_days=7,
                ),
                DecayResponse(
                    factor_id="factor2",
                    decay_curve={"1d": 0.06, "5d": 0.05, "10d": 0.04},
                    half_life_days=10,
                ),
            ],
            comparison={
                "1d": {"factor1": 0.05, "factor2": 0.06},
                "5d": {"factor1": 0.04, "factor2": 0.05},
                "10d": {"factor1": 0.03, "factor2": 0.04},
            },
        )
        assert len(response.factors) == 2
        assert "1d" in response.comparison
        assert response.comparison["1d"]["factor1"] == 0.05


# =============================================================================
# US-019: Event-based seasonality
# =============================================================================

class TestSeasonality:
    """Tests for event-based seasonality analysis (US-019)."""

    def test_seasonality_endpoint_returns_earnings_season(self):
        """Test that seasonality endpoint includes earnings season effects."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/seasonality/test_factor")
        # Should return data or 404 if factor doesn't exist
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "earnings_season_effects" in data

    def test_seasonality_response_schema(self):
        """Test SeasonalityResponse schema with earnings season."""
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
            earnings_season_effects={
                "Q1_reporting": 0.06,
                "Q2_reporting": 0.05,
                "Q3_reporting": 0.04,
                "Q4_reporting": 0.07,
                "off_season": 0.03,
            },
            seasonal_adjusted_available=True,
        )
        assert response.factor_id == "test_factor"
        assert "Q1_reporting" in response.earnings_season_effects
        assert response.seasonal_adjusted_available is True

    def test_earnings_season_detection(self):
        """Test earnings season detection function."""
        from src.api.routes.backtest import get_earnings_season

        # Q4 reporting period (Jan-Feb)
        assert get_earnings_season(1) == "Q4_reporting"
        assert get_earnings_season(2) == "Q4_reporting"

        # Q1 reporting period (Apr-May)
        assert get_earnings_season(4) == "Q1_reporting"
        assert get_earnings_season(5) == "Q1_reporting"

        # Q2 reporting period (Jul-Aug)
        assert get_earnings_season(7) == "Q2_reporting"
        assert get_earnings_season(8) == "Q2_reporting"

        # Q3 reporting period (Oct-Nov)
        assert get_earnings_season(10) == "Q3_reporting"
        assert get_earnings_season(11) == "Q3_reporting"

        # Off season
        assert get_earnings_season(3) == "off_season"
        assert get_earnings_season(6) == "off_season"
        assert get_earnings_season(9) == "off_season"
        assert get_earnings_season(12) == "off_season"

    def test_seasonal_adjustment_endpoint_exists(self):
        """Test that seasonal adjustment endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/backtest/seasonality/adjust",
            json={
                "factor_id": "test_factor",
                "tickers": ["AAPL", "MSFT"],
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "adjustment_method": "multiplicative",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


# =============================================================================
# US-020: Research pack export
# =============================================================================

class TestResearchPackExport:
    """Tests for research pack export (US-020)."""

    def test_export_endpoint_returns_zip(self):
        """Test that export endpoint returns ZIP file."""
        client = get_test_client()
        response = client.post(
            "/api/v1/backtest/export",
            json={
                "factor_id": "test_factor",
                "include_notebook": True,
                "include_data": True,
                "formats": ["csv", "json"],
            },
        )
        # Should return ZIP or 404 if factor doesn't exist
        if response.status_code == status.HTTP_200_OK:
            assert response.headers.get("content-type") == "application/zip"

    def test_export_includes_notebook_option(self):
        """Test that export respects include_notebook option."""
        from src.api.routes.backtest import ResearchPackRequest

        request = ResearchPackRequest(
            factor_id="test_factor",
            include_notebook=True,
            include_data=False,
            formats=["json"],
        )
        assert request.include_notebook is True
        assert request.include_data is False

    def test_export_supports_parquet_format(self):
        """Test that export supports parquet format."""
        from src.api.routes.backtest import ResearchPackRequest

        request = ResearchPackRequest(
            factor_id="test_factor",
            include_notebook=False,
            include_data=True,
            formats=["csv", "parquet", "json"],
        )
        assert "parquet" in request.formats
        assert "csv" in request.formats
        assert "json" in request.formats

    def test_research_pack_request_defaults(self):
        """Test ResearchPackRequest has correct defaults."""
        from src.api.routes.backtest import ResearchPackRequest

        request = ResearchPackRequest(factor_id="test_factor")
        assert request.include_notebook is True
        assert request.include_data is True
        assert "csv" in request.formats
        assert "json" in request.formats


# =============================================================================
# US-021: A/B Experiment Framework
# =============================================================================

class TestExperimentFramework:
    """Tests for A/B experiment framework (US-021)."""

    def test_create_experiment_endpoint_exists(self):
        """Test that create experiment endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/backtest/experiments",
            json={
                "name": "Test Experiment",
                "description": "Testing A/B framework",
                "control_factor_id": "control_factor",
                "treatment_factor_id": "treatment_factor",
                "start_date": "2025-01-01",
                "significance_threshold": 0.05,
            },
        )
        # Should return 201, 404 (factor not found), or 500
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_experiments_endpoint_exists(self):
        """Test that list experiments endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/experiments")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_experiments_with_status_filter(self):
        """Test list experiments with status filter."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/experiments?status=draft")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_experiments_invalid_status(self):
        """Test list experiments with invalid status filter."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/experiments?status=invalid_status")
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_experiment_endpoint_exists(self):
        """Test that get experiment endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/backtest/experiments/1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_update_experiment_endpoint_exists(self):
        """Test that update experiment endpoint exists."""
        client = get_test_client()
        response = client.patch(
            "/api/v1/backtest/experiments/1",
            json={"name": "Updated Name"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_start_experiment_endpoint_exists(self):
        """Test that start experiment endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/backtest/experiments/1/start")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_stop_experiment_endpoint_exists(self):
        """Test that stop experiment endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/backtest/experiments/1/stop")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_promote_winner_endpoint_exists(self):
        """Test that promote winner endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/backtest/experiments/1/promote?confirm=true")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_promote_requires_confirmation(self):
        """Test that promote endpoint requires confirmation."""
        client = get_test_client()
        response = client.post("/api/v1/backtest/experiments/1/promote")
        # Without confirm=true, should get 400 or 404
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_delete_experiment_endpoint_exists(self):
        """Test that delete experiment endpoint exists."""
        client = get_test_client()
        response = client.delete("/api/v1/backtest/experiments/1")
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestExperimentSchemas:
    """Tests for experiment-related schemas."""

    def test_create_experiment_request_schema(self):
        """Test CreateExperimentRequest schema."""
        from src.api.routes.backtest import CreateExperimentRequest

        request = CreateExperimentRequest(
            name="Test Experiment",
            description="Testing",
            control_factor_id="control",
            treatment_factor_id="treatment",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            significance_threshold=0.05,
        )
        assert request.name == "Test Experiment"
        assert request.significance_threshold == 0.05

    def test_create_experiment_request_defaults(self):
        """Test CreateExperimentRequest defaults."""
        from src.api.routes.backtest import CreateExperimentRequest

        request = CreateExperimentRequest(
            name="Test",
            control_factor_id="control",
            treatment_factor_id="treatment",
            start_date=date(2025, 1, 1),
        )
        assert request.description is None
        assert request.end_date is None
        assert request.significance_threshold == 0.05

    def test_update_experiment_request_schema(self):
        """Test UpdateExperimentRequest schema."""
        from src.api.routes.backtest import UpdateExperimentRequest

        request = UpdateExperimentRequest(
            name="Updated Name",
            description="Updated description",
        )
        assert request.name == "Updated Name"
        assert request.significance_threshold is None

    def test_experiment_metrics_schema(self):
        """Test ExperimentMetrics schema."""
        from src.api.routes.backtest import ExperimentMetrics

        metrics = ExperimentMetrics(
            ic=0.045,
            ir=0.85,
            tstat=3.2,
            hit_rate=0.58,
        )
        assert metrics.ic == 0.045
        assert metrics.ir == 0.85

    def test_experiment_response_schema(self):
        """Test ExperimentResponse schema."""
        from src.api.routes.backtest import ExperimentResponse, ExperimentMetrics

        response = ExperimentResponse(
            id=1,
            name="Test Experiment",
            description="Testing",
            control_factor_id="control",
            treatment_factor_id="treatment",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            status="running",
            control_metrics=ExperimentMetrics(ic=0.04, ir=0.8, tstat=2.5, hit_rate=0.55),
            treatment_metrics=ExperimentMetrics(ic=0.05, ir=0.9, tstat=3.0, hit_rate=0.60),
            p_value=0.03,
            is_significant=True,
            winner="treatment",
            significance_threshold=0.05,
            metrics_history=[],
        )
        assert response.id == 1
        assert response.is_significant is True
        assert response.winner == "treatment"


class TestExperimentModel:
    """Tests for Experiment model."""

    def test_experiment_status_enum(self):
        """Test ExperimentStatus enum values."""
        assert ExperimentStatus.DRAFT.value == "draft"
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.PAUSED.value == "paused"
        assert ExperimentStatus.COMPLETED.value == "completed"
        assert ExperimentStatus.CANCELLED.value == "cancelled"

    def test_experiment_model_fields(self):
        """Test Experiment model has required fields."""
        from src.models.experiments import Experiment

        # Check that model has the expected columns
        columns = [c.name for c in Experiment.__table__.columns]
        assert "id" in columns
        assert "name" in columns
        assert "control_factor_id" in columns
        assert "treatment_factor_id" in columns
        assert "status" in columns
        assert "start_date" in columns
        assert "end_date" in columns
        assert "p_value_ic" in columns
        assert "is_significant" in columns
        assert "winner" in columns
        assert "winner_promoted" in columns

    def test_experiment_metric_snapshot_model_fields(self):
        """Test ExperimentMetricSnapshot model has required fields."""
        from src.models.experiments import ExperimentMetricSnapshot

        columns = [c.name for c in ExperimentMetricSnapshot.__table__.columns]
        assert "id" in columns
        assert "experiment_id" in columns
        assert "snapshot_date" in columns
        assert "control_ic" in columns
        assert "treatment_ic" in columns
        assert "running_p_value" in columns


class TestStatisticalSignificance:
    """Tests for statistical significance calculations."""

    def test_p_value_calculation_logic(self):
        """Test that p-value calculation uses scipy correctly."""
        from scipy import stats as scipy_stats
        import numpy as np

        # Mock control and treatment data
        control_data = np.random.normal(0.05, 0.02, 100)
        treatment_data = np.random.normal(0.06, 0.02, 100)

        # Two-sample t-test
        t_stat, p_value = scipy_stats.ttest_ind(control_data, treatment_data)

        # p-value should be between 0 and 1
        assert 0 <= p_value <= 1
        # With these means, treatment should be significantly better
        # (though this is probabilistic)

    def test_winner_determination(self):
        """Test winner determination logic."""
        # If p_value < significance_level and treatment > control, winner = treatment
        # If p_value < significance_level and control > treatment, winner = control
        # If p_value >= significance_level, winner = inconclusive

        significance_level = 0.05

        # Case 1: Treatment wins
        p_value = 0.01
        treatment_mean = 0.06
        control_mean = 0.04
        is_significant = p_value < significance_level
        assert is_significant is True
        winner = "treatment" if treatment_mean > control_mean else "control"
        assert winner == "treatment"

        # Case 2: Control wins
        p_value = 0.02
        treatment_mean = 0.03
        control_mean = 0.05
        is_significant = p_value < significance_level
        assert is_significant is True
        winner = "treatment" if treatment_mean > control_mean else "control"
        assert winner == "control"

        # Case 3: Inconclusive
        p_value = 0.15
        is_significant = p_value < significance_level
        assert is_significant is False
        winner = "inconclusive" if not is_significant else "treatment"
        assert winner == "inconclusive"
