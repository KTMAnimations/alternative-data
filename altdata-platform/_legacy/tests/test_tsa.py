"""Tests for TSA checkpoint data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.tsa_checkpoint import TSACheckpointCollector
from src.models.tsa import TSACheckpoint
from src.transformations.factors.tsa_factors import (
    calc_tsa_throughput_momentum,
    calc_tsa_weekday_weekend_ratio,
    calc_tsa_enplanement_nowcast,
    calc_tsa_holiday_vs_baseline,
    calc_tsa_rolling_volatility,
    TSAThroughputMomentum,
    TSAWeekdayWeekendRatio,
    TSAEnplanementNowcast,
    TSAHolidaySpike,
    TSAThroughputVolatility,
    AIRLINE_TICKERS,
    SECTOR_ETF,
)


# =============================================================================
# TSA Model Tests
# =============================================================================

class TestTSAModels:
    """Test TSA database models."""

    def test_tsa_checkpoint_model(self):
        """Test TSACheckpoint model creation."""
        checkpoint = TSACheckpoint(
            date=date(2024, 6, 15),
            current_year_throughput=2500000,
            prior_year_throughput=2300000,
            yoy_change_pct=8.7,
            day_of_week=5,  # Saturday
            is_holiday_period=False,
        )
        assert checkpoint.date == date(2024, 6, 15)
        assert checkpoint.current_year_throughput == 2500000
        assert checkpoint.yoy_change_pct == 8.7
        assert checkpoint.day_of_week == 5

    def test_tsa_checkpoint_with_holiday(self):
        """Test TSACheckpoint with holiday flag."""
        checkpoint = TSACheckpoint(
            date=date(2024, 7, 4),
            current_year_throughput=2800000,
            prior_year_throughput=2600000,
            yoy_change_pct=7.69,
            day_of_week=3,  # Thursday
            is_holiday_period=True,
        )
        assert checkpoint.is_holiday_period is True
        assert checkpoint.current_year_throughput == 2800000

    def test_tsa_checkpoint_nullable_fields(self):
        """Test TSACheckpoint with minimal required fields."""
        checkpoint = TSACheckpoint(
            date=date(2024, 1, 1),
        )
        assert checkpoint.date == date(2024, 1, 1)
        assert checkpoint.current_year_throughput is None
        assert checkpoint.yoy_change_pct is None


# =============================================================================
# TSA Collector Tests
# =============================================================================

class TestTSACheckpointCollector:
    """Test TSA checkpoint collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = TSACheckpointCollector()
        assert collector.SOURCE_NAME == "tsa_checkpoint"

    def test_collector_url(self):
        """Test collector has correct URL."""
        collector = TSACheckpointCollector()
        assert "tsa.gov" in collector.TSA_URL.lower()

    def test_parse_returns_list(self):
        """Test parse returns list of records for valid HTML input."""
        collector = TSACheckpointCollector()
        # HTML with table returns list
        html = """<html><body>
        <table id="passengers_table">
        <tr><th>Date</th><th>2024</th><th>2023</th></tr>
        <tr><td>1/1/2024</td><td>2,500,000</td><td>2,300,000</td></tr>
        </table></body></html>"""
        result = collector.parse(html)
        assert isinstance(result, list)


# =============================================================================
# TSA Factor Calculation Tests
# =============================================================================

class TestTSAFactorCalculations:
    """Test TSA factor calculation functions."""

    @patch("src.transformations.factors.tsa_factors.SessionLocal")
    def test_calc_throughput_momentum(self, mock_session_local):
        """Test TSA throughput momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current week avg: 2,500,000
        # Prior year week avg: 2,300,000
        # Change = (2.5M - 2.3M) / 2.3M * 100 = 8.7%
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            2500000.0,  # current week avg
            2300000.0,  # prior year week avg
        ]

        result = calc_tsa_throughput_momentum(date(2024, 6, 15), lookback_days=7)

        assert result is not None
        assert abs(result - 8.7) < 0.1
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.tsa_factors.SessionLocal")
    def test_calc_throughput_momentum_no_prior_data(self, mock_session_local):
        """Test momentum returns None without prior year data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            2500000.0,  # current
            None,  # no prior data
        ]

        result = calc_tsa_throughput_momentum(date(2024, 6, 15))

        assert result is None

    @patch("src.transformations.factors.tsa_factors.SessionLocal")
    def test_calc_weekday_weekend_ratio(self, mock_session_local):
        """Test weekday/weekend ratio calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Weekday avg: 2,400,000; Weekend avg: 2,000,000
        # Ratio = 2.4M / 2.0M = 1.2
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            2400000.0,  # weekday avg
            2000000.0,  # weekend avg
        ]

        result = calc_tsa_weekday_weekend_ratio(date(2024, 6, 15))

        assert result is not None
        assert abs(result - 1.2) < 0.01

    @patch("src.transformations.factors.tsa_factors.SessionLocal")
    def test_calc_enplanement_nowcast(self, mock_session_local):
        """Test enplanement nowcast calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Sum of month's throughput: 60,000,000
        mock_session.query.return_value.filter.return_value.scalar.return_value = 60000000

        result = calc_tsa_enplanement_nowcast(date(2024, 6, 15))

        assert result is not None
        # Result is returned in millions (60M * 0.97 = 58.2M)
        assert result > 50  # Should be around 58.2 million

    @patch("src.transformations.factors.tsa_factors.SessionLocal")
    def test_calc_holiday_spike(self, mock_session_local):
        """Test holiday spike calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Holiday avg: 2,800,000; Baseline avg: 2,200,000
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            2800000.0,  # holiday period avg
            2200000.0,  # baseline avg
        ]

        result = calc_tsa_holiday_vs_baseline(date(2024, 11, 28))  # Thanksgiving

        assert result is not None
        # Result should show holiday spike relative to baseline
        assert result > 0  # Positive spike indicates holiday effect

    @patch("src.transformations.factors.tsa_factors.SessionLocal")
    def test_calc_throughput_volatility(self, mock_session_local):
        """Test throughput volatility calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 150000.0

        result = calc_tsa_rolling_volatility(date(2024, 6, 15))

        assert result is not None
        assert result == 150000.0


# =============================================================================
# TSA Factor Class Tests
# =============================================================================

class TestTSAFactorClasses:
    """Test TSA factor classes."""

    def test_throughput_momentum_factor(self):
        """Test TSAThroughputMomentum factor class."""
        factor = TSAThroughputMomentum()
        assert factor.FACTOR_NAME == "tsa_throughput_momentum"
        assert factor.CATEGORY == "transportation"
        assert factor.ENTITY_TYPE == "company"
        assert factor.FREQUENCY == "daily"

    def test_weekday_weekend_ratio_factor(self):
        """Test TSAWeekdayWeekendRatio factor class."""
        factor = TSAWeekdayWeekendRatio()
        assert factor.FACTOR_NAME == "tsa_weekday_weekend_ratio"

    def test_enplanement_nowcast_factor(self):
        """Test TSAEnplanementNowcast factor class."""
        factor = TSAEnplanementNowcast()
        assert factor.FACTOR_NAME == "tsa_enplanement_nowcast"
        assert factor.ENTITY_TYPE == "sector"

    def test_holiday_spike_factor(self):
        """Test TSAHolidaySpike factor class."""
        factor = TSAHolidaySpike()
        assert factor.FACTOR_NAME == "tsa_holiday_spike"
        assert "holiday" in factor.FACTOR_DESCRIPTION.lower()

    def test_throughput_volatility_factor(self):
        """Test TSAThroughputVolatility factor class."""
        factor = TSAThroughputVolatility()
        assert factor.FACTOR_NAME == "tsa_throughput_volatility"
        assert factor.LOOKBACK_DAYS >= 7

    def test_momentum_only_for_airline_tickers(self):
        """Test momentum factor only applies to airlines."""
        factor = TSAThroughputMomentum()

        # Should return None for non-airline ticker
        with patch("src.transformations.factors.tsa_factors.calc_tsa_throughput_momentum") as mock_calc:
            mock_calc.return_value = 5.0
            result = factor.compute("AAPL", datetime(2024, 6, 15))
            assert result is None
            mock_calc.assert_not_called()

    @patch("src.transformations.factors.tsa_factors.calc_tsa_throughput_momentum")
    def test_momentum_compute_for_airline(self, mock_calc):
        """Test momentum compute for airline ticker."""
        mock_calc.return_value = 8.7

        factor = TSAThroughputMomentum()
        result = factor.compute("DAL", datetime(2024, 6, 15))

        assert result == 8.7
        mock_calc.assert_called_once()

    @patch("src.transformations.factors.tsa_factors.calc_tsa_throughput_momentum")
    def test_momentum_compute_for_jets_etf(self, mock_calc):
        """Test momentum compute for JETS ETF."""
        mock_calc.return_value = 10.5

        factor = TSAThroughputMomentum()
        result = factor.compute(SECTOR_ETF, datetime(2024, 6, 15))

        assert result == 10.5


# =============================================================================
# TSA Factor Registry Tests
# =============================================================================

class TestTSAFactorRegistry:
    """Test TSA factors in registry."""

    def test_tsa_factors_registered(self):
        """Test that all TSA factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        tsa_factors = [
            "tsa_throughput_momentum",
            "tsa_weekday_weekend_ratio",
            "tsa_enplanement_nowcast",
            "tsa_holiday_spike",
            "tsa_throughput_volatility",
        ]

        for factor in tsa_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_tsa_factors_category(self):
        """Test TSA factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        tsa_factors = [f for f in registered if f["id"].startswith("tsa_")]

        assert len(tsa_factors) == 5
        for factor in tsa_factors:
            assert factor["category"] == "transportation"


# =============================================================================
# Entity Mapping Tests
# =============================================================================

class TestTSAEntityMapping:
    """Test TSA entity mapping."""

    def test_airline_tickers_defined(self):
        """Test airline tickers are defined."""
        assert len(AIRLINE_TICKERS) >= 5
        assert "DAL" in AIRLINE_TICKERS
        assert "UAL" in AIRLINE_TICKERS
        assert "AAL" in AIRLINE_TICKERS
        assert "LUV" in AIRLINE_TICKERS
        assert "JBLU" in AIRLINE_TICKERS

    def test_sector_etf_defined(self):
        """Test sector ETF is defined."""
        assert SECTOR_ETF == "JETS"
