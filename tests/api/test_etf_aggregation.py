"""Tests for ETF ticker aggregation (US-024)."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.factors import (
    ETF_CONSTITUENT_WEIGHTS,
    FactorValueResponse,
    _compute_etf_weighted_averages,
)


def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestETFConstituentWeights:
    """Tests for ETF constituent weight mappings."""

    def test_jets_etf_exists(self):
        """Test JETS ETF has constituent mappings."""
        assert "JETS" in ETF_CONSTITUENT_WEIGHTS
        assert "DAL" in ETF_CONSTITUENT_WEIGHTS["JETS"]
        assert "UAL" in ETF_CONSTITUENT_WEIGHTS["JETS"]
        assert "LUV" in ETF_CONSTITUENT_WEIGHTS["JETS"]

    def test_pej_etf_exists(self):
        """Test PEJ (restaurant) ETF has constituent mappings."""
        assert "PEJ" in ETF_CONSTITUENT_WEIGHTS
        assert "DRI" in ETF_CONSTITUENT_WEIGHTS["PEJ"]
        assert "MCD" in ETF_CONSTITUENT_WEIGHTS["PEJ"]
        assert "SBUX" in ETF_CONSTITUENT_WEIGHTS["PEJ"]

    def test_xhb_etf_exists(self):
        """Test XHB (homebuilder) ETF has constituent mappings."""
        assert "XHB" in ETF_CONSTITUENT_WEIGHTS
        assert "DHI" in ETF_CONSTITUENT_WEIGHTS["XHB"]
        assert "LEN" in ETF_CONSTITUENT_WEIGHTS["XHB"]
        assert "HD" in ETF_CONSTITUENT_WEIGHTS["XHB"]

    def test_rez_etf_exists(self):
        """Test REZ (REIT) ETF has constituent mappings."""
        assert "REZ" in ETF_CONSTITUENT_WEIGHTS
        assert "EQR" in ETF_CONSTITUENT_WEIGHTS["REZ"]
        assert "AVB" in ETF_CONSTITUENT_WEIGHTS["REZ"]
        assert "INVH" in ETF_CONSTITUENT_WEIGHTS["REZ"]

    def test_pbs_etf_exists(self):
        """Test PBS (entertainment) ETF has constituent mappings."""
        assert "PBS" in ETF_CONSTITUENT_WEIGHTS
        assert "DIS" in ETF_CONSTITUENT_WEIGHTS["PBS"]
        assert "WBD" in ETF_CONSTITUENT_WEIGHTS["PBS"]
        assert "CMCSA" in ETF_CONSTITUENT_WEIGHTS["PBS"]

    def test_iak_etf_exists(self):
        """Test IAK (insurance) ETF has constituent mappings."""
        assert "IAK" in ETF_CONSTITUENT_WEIGHTS
        assert "ALL" in ETF_CONSTITUENT_WEIGHTS["IAK"]
        assert "TRV" in ETF_CONSTITUENT_WEIGHTS["IAK"]
        assert "PGR" in ETF_CONSTITUENT_WEIGHTS["IAK"]

    def test_cibr_etf_exists(self):
        """Test CIBR (cybersecurity) ETF has constituent mappings."""
        assert "CIBR" in ETF_CONSTITUENT_WEIGHTS
        assert "NET" in ETF_CONSTITUENT_WEIGHTS["CIBR"]
        assert "CRWD" in ETF_CONSTITUENT_WEIGHTS["CIBR"]
        assert "PANW" in ETF_CONSTITUENT_WEIGHTS["CIBR"]

    def test_weights_sum_reasonable(self):
        """Test that weights for each ETF sum to a reasonable total."""
        for etf, weights in ETF_CONSTITUENT_WEIGHTS.items():
            total = sum(weights.values())
            # Weights should sum to something between 0.5 and 1.0
            # (not all constituents need to be mapped)
            assert 0.5 <= total <= 1.0, f"ETF {etf} weights sum to {total}"

    def test_weights_are_positive(self):
        """Test that all weights are positive."""
        for etf, weights in ETF_CONSTITUENT_WEIGHTS.items():
            for ticker, weight in weights.items():
                assert weight > 0, f"ETF {etf} ticker {ticker} has non-positive weight"


class TestComputeETFWeightedAverages:
    """Tests for _compute_etf_weighted_averages function."""

    def test_basic_weighted_average(self):
        """Test basic weighted average computation."""
        data = [
            FactorValueResponse(
                ticker="DAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.10,
                variance=0.001,
                data_quality=1.0,
                revision_status="original",
            ),
            FactorValueResponse(
                ticker="UAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.20,
                variance=0.002,
                data_quality=1.0,
                revision_status="original",
            ),
        ]

        etf_tickers = {
            "TEST_ETF": {
                "DAL": 0.6,
                "UAL": 0.4,
            }
        }

        results = _compute_etf_weighted_averages(data, etf_tickers, "test_factor")

        assert len(results) == 1
        result = results[0]
        assert result.ticker == "TEST_ETF"
        assert result.as_of_date == date(2025, 1, 15)
        assert result.factor_id == "test_factor"
        assert result.revision_status == "computed"

        # Weighted mean: 0.6 * 0.10 + 0.4 * 0.20 = 0.06 + 0.08 = 0.14
        expected_mean = 0.6 * 0.10 + 0.4 * 0.20
        assert abs(result.mean - expected_mean) < 0.0001

    def test_weighted_average_with_missing_constituent(self):
        """Test weighted average when some constituents are missing."""
        data = [
            FactorValueResponse(
                ticker="DAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.10,
                variance=0.001,
                data_quality=1.0,
                revision_status="original",
            ),
            # UAL is missing
        ]

        etf_tickers = {
            "TEST_ETF": {
                "DAL": 0.6,
                "UAL": 0.4,
            }
        }

        results = _compute_etf_weighted_averages(data, etf_tickers, "test_factor")

        assert len(results) == 1
        result = results[0]

        # Only DAL contributes, normalized by its weight
        # Weighted mean: 0.6 * 0.10 / 0.6 = 0.10
        expected_mean = 0.10
        assert abs(result.mean - expected_mean) < 0.0001

        # Data quality should be reduced (only 1 of 2 constituents)
        assert result.data_quality < 1.0

    def test_weighted_average_multiple_dates(self):
        """Test weighted average for multiple dates."""
        data = [
            FactorValueResponse(
                ticker="DAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 14),
                mean=0.10,
                variance=0.001,
                data_quality=1.0,
                revision_status="original",
            ),
            FactorValueResponse(
                ticker="DAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.12,
                variance=0.001,
                data_quality=1.0,
                revision_status="original",
            ),
            FactorValueResponse(
                ticker="UAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 14),
                mean=0.20,
                variance=0.002,
                data_quality=1.0,
                revision_status="original",
            ),
            FactorValueResponse(
                ticker="UAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.22,
                variance=0.002,
                data_quality=1.0,
                revision_status="original",
            ),
        ]

        etf_tickers = {
            "TEST_ETF": {
                "DAL": 0.5,
                "UAL": 0.5,
            }
        }

        results = _compute_etf_weighted_averages(data, etf_tickers, "test_factor")

        assert len(results) == 2
        dates = {r.as_of_date for r in results}
        assert dates == {date(2025, 1, 14), date(2025, 1, 15)}

    def test_weighted_average_no_constituents(self):
        """Test that no result is returned when no constituents are present."""
        data = [
            FactorValueResponse(
                ticker="AAPL",  # Not a constituent
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.10,
                variance=0.001,
                data_quality=1.0,
                revision_status="original",
            ),
        ]

        etf_tickers = {
            "TEST_ETF": {
                "DAL": 0.6,
                "UAL": 0.4,
            }
        }

        results = _compute_etf_weighted_averages(data, etf_tickers, "test_factor")

        assert len(results) == 0

    def test_variance_computation(self):
        """Test variance is computed correctly for weighted sum."""
        data = [
            FactorValueResponse(
                ticker="DAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.10,
                variance=0.004,  # Variance of DAL
                data_quality=1.0,
                revision_status="original",
            ),
            FactorValueResponse(
                ticker="UAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.20,
                variance=0.001,  # Variance of UAL
                data_quality=1.0,
                revision_status="original",
            ),
        ]

        etf_tickers = {
            "TEST_ETF": {
                "DAL": 0.6,
                "UAL": 0.4,
            }
        }

        results = _compute_etf_weighted_averages(data, etf_tickers, "test_factor")

        assert len(results) == 1
        result = results[0]

        # Variance of weighted sum (assuming independence):
        # Var(aX + bY) = a^2 * Var(X) + b^2 * Var(Y)
        # = 0.6^2 * 0.004 + 0.4^2 * 0.001 = 0.36 * 0.004 + 0.16 * 0.001
        # = 0.00144 + 0.00016 = 0.0016
        # Note: result is normalized by total_weight^2, but weights sum to 1.0 here
        expected_variance = 0.6**2 * 0.004 + 0.4**2 * 0.001
        assert abs(result.variance - expected_variance) < 0.0001

    def test_data_quality_minimum(self):
        """Test that data quality is the minimum of constituents."""
        data = [
            FactorValueResponse(
                ticker="DAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.10,
                variance=0.001,
                data_quality=0.95,  # DAL quality
                revision_status="original",
            ),
            FactorValueResponse(
                ticker="UAL",
                factor_id="test_factor",
                as_of_date=date(2025, 1, 15),
                mean=0.20,
                variance=0.002,
                data_quality=0.80,  # UAL quality (lower)
                revision_status="original",
            ),
        ]

        etf_tickers = {
            "TEST_ETF": {
                "DAL": 0.5,
                "UAL": 0.5,
            }
        }

        results = _compute_etf_weighted_averages(data, etf_tickers, "test_factor")

        assert len(results) == 1
        result = results[0]

        # Data quality should be based on minimum quality and coverage
        assert result.data_quality <= 0.80


class TestETFAggregationAPI:
    """Tests for ETF aggregation via API endpoint."""

    def test_history_expand_etf_parameter(self):
        """Test that expand_etf parameter is accepted."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/test_factor/history?tickers=JETS&expand_etf=true"
        )
        # Should not be 404 or 422 (parameter should be recognized)
        assert response.status_code != status.HTTP_404_NOT_FOUND
        assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_history_expand_etf_false(self):
        """Test expand_etf=false (default) behavior."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/test_factor/history?tickers=DAL&expand_etf=false"
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_history_mixed_tickers(self):
        """Test request with both ETF and regular tickers."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/test_factor/history?tickers=JETS,AAPL&expand_etf=true"
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND
        assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY


class TestETFIntegration:
    """Integration tests for ETF functionality."""

    def test_jets_etf_constituents_complete(self):
        """Test JETS ETF has all major airline tickers."""
        jets = ETF_CONSTITUENT_WEIGHTS["JETS"]

        # Major airlines should be present
        required_tickers = ["DAL", "UAL", "LUV", "AAL", "JBLU"]
        for ticker in required_tickers:
            assert ticker in jets, f"{ticker} missing from JETS ETF"

    def test_etf_weights_normalized(self):
        """Test that ETF weights can be used for normalization."""
        for etf, weights in ETF_CONSTITUENT_WEIGHTS.items():
            total = sum(weights.values())
            # Should be able to normalize
            normalized = {k: v / total for k, v in weights.items()}
            normalized_sum = sum(normalized.values())
            assert abs(normalized_sum - 1.0) < 0.0001

    def test_compute_weighted_average_jets_realistic(self):
        """Test realistic JETS ETF computation."""
        # Create realistic airline factor data
        airlines = ["DAL", "UAL", "LUV", "AAL", "JBLU"]
        factor_values = [0.05, 0.04, 0.06, 0.03, 0.02]

        data = [
            FactorValueResponse(
                ticker=ticker,
                factor_id="tsa_throughput_momentum",
                as_of_date=date(2025, 1, 15),
                mean=value,
                variance=0.001,
                data_quality=0.95,
                revision_status="original",
            )
            for ticker, value in zip(airlines, factor_values)
        ]

        etf_tickers = {"JETS": ETF_CONSTITUENT_WEIGHTS["JETS"]}

        results = _compute_etf_weighted_averages(data, etf_tickers, "tsa_throughput_momentum")

        assert len(results) == 1
        result = results[0]
        assert result.ticker == "JETS"
        assert result.factor_id == "tsa_throughput_momentum"

        # Weighted average should be reasonable
        assert 0.01 <= result.mean <= 0.10  # Within expected range
        assert result.variance > 0
        assert result.data_quality > 0
