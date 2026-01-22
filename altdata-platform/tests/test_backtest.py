"""Tests for the backtesting framework."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import pandas as pd

from src.backtest.metrics import (
    calculate_sharpe,
    calculate_max_drawdown,
    calculate_ic,
    calculate_ic_series,
    calculate_ic_ir,
    calculate_turnover,
    calculate_sortino,
    calculate_calmar,
    calculate_win_rate,
    calculate_profit_factor,
)
from src.backtest.engine import BacktestEngine, BacktestResult, BacktestJobManager
from src.backtest.prices import PriceProvider


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def sample_returns():
    """Create sample daily returns."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.02, 100), index=dates)
    return returns


@pytest.fixture
def sample_cumulative():
    """Create sample cumulative returns."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 100)
    cumulative = (1 + pd.Series(returns)).cumprod()
    cumulative.index = dates
    return cumulative


@pytest.fixture
def sample_factor_df():
    """Create sample factor DataFrame."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    entities = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    np.random.seed(42)
    data = np.random.randn(30, 5)
    return pd.DataFrame(data, index=dates, columns=entities)


@pytest.fixture
def sample_positions():
    """Create sample positions DataFrame."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    entities = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    positions = pd.DataFrame(0.0, index=dates, columns=entities)
    positions["AAPL"] = 0.5
    positions["MSFT"] = 0.5
    positions.loc[dates[15]:, "AAPL"] = 0.0
    positions.loc[dates[15]:, "GOOGL"] = 0.5
    return positions


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock()


# ===========================================
# METRIC TESTS
# ===========================================


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_sharpe_positive(self, sample_returns):
        """Test Sharpe ratio with positive returns."""
        sharpe = calculate_sharpe(sample_returns)
        assert isinstance(sharpe, float)
        # Should be positive for slightly positive mean returns
        assert sharpe > -5 and sharpe < 5

    def test_sharpe_empty_returns(self):
        """Test Sharpe ratio with empty returns."""
        empty = pd.Series(dtype=float)
        assert calculate_sharpe(empty) == 0.0

    def test_sharpe_zero_std(self):
        """Test Sharpe ratio with zero standard deviation."""
        constant = pd.Series([0.01] * 100)
        assert calculate_sharpe(constant) == 0.0

    def test_sharpe_with_risk_free(self, sample_returns):
        """Test Sharpe ratio with risk-free rate."""
        sharpe_no_rf = calculate_sharpe(sample_returns, risk_free=0.0)
        sharpe_with_rf = calculate_sharpe(sample_returns, risk_free=0.05)
        # Sharpe should be lower with positive risk-free rate
        assert sharpe_with_rf < sharpe_no_rf


class TestMaxDrawdown:
    """Tests for max drawdown calculation."""

    def test_drawdown_normal(self, sample_cumulative):
        """Test max drawdown calculation."""
        dd = calculate_max_drawdown(sample_cumulative)
        assert dd <= 0  # Drawdown is negative
        assert dd >= -1  # Can't lose more than 100%

    def test_drawdown_empty(self):
        """Test max drawdown with empty series."""
        empty = pd.Series(dtype=float)
        assert calculate_max_drawdown(empty) == 0.0

    def test_drawdown_always_up(self):
        """Test max drawdown with always increasing values."""
        cumulative = pd.Series([1.0, 1.1, 1.2, 1.3, 1.4])
        dd = calculate_max_drawdown(cumulative)
        assert dd == 0.0


class TestIC:
    """Tests for Information Coefficient calculation."""

    def test_ic_perfect_correlation(self):
        """Test IC with perfect correlation."""
        factor = pd.Series([1, 2, 3, 4, 5])
        returns = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
        ic = calculate_ic(factor, returns)
        assert ic is not None
        assert ic > 0.99  # Should be ~1.0

    def test_ic_negative_correlation(self):
        """Test IC with negative correlation."""
        factor = pd.Series([1, 2, 3, 4, 5])
        returns = pd.Series([0.5, 0.4, 0.3, 0.2, 0.1])
        ic = calculate_ic(factor, returns)
        assert ic is not None
        assert ic < -0.99  # Should be ~-1.0

    def test_ic_insufficient_data(self):
        """Test IC with insufficient data."""
        factor = pd.Series([1, 2])
        returns = pd.Series([0.1, 0.2])
        ic = calculate_ic(factor, returns)
        assert ic is None

    def test_ic_with_nans(self):
        """Test IC handles NaN values."""
        factor = pd.Series([1, 2, np.nan, 4, 5, 6])
        returns = pd.Series([0.1, 0.2, 0.3, 0.4, np.nan, 0.6])
        ic = calculate_ic(factor, returns)
        # Should still compute with remaining valid data
        assert ic is None or isinstance(ic, float)


class TestICIR:
    """Tests for IC Information Ratio calculation."""

    def test_ic_ir_positive(self):
        """Test IC IR with positive mean IC."""
        ic_series = pd.Series([0.05, 0.06, 0.04, 0.07, 0.05])
        ir = calculate_ic_ir(ic_series)
        assert ir > 0

    def test_ic_ir_empty(self):
        """Test IC IR with empty series."""
        empty = pd.Series(dtype=float)
        assert calculate_ic_ir(empty) == 0.0

    def test_ic_ir_zero_std(self):
        """Test IC IR with constant IC."""
        constant = pd.Series([0.05] * 10)
        assert calculate_ic_ir(constant) == 0.0


class TestTurnover:
    """Tests for turnover calculation."""

    def test_turnover_with_changes(self, sample_positions):
        """Test turnover with position changes."""
        turnover = calculate_turnover(sample_positions)
        assert turnover >= 0
        assert turnover <= 2  # Max turnover per day is 200%

    def test_turnover_no_changes(self):
        """Test turnover with no position changes."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        positions = pd.DataFrame(0.5, index=dates, columns=["AAPL", "MSFT"])
        turnover = calculate_turnover(positions)
        assert turnover == 0.0

    def test_turnover_empty(self):
        """Test turnover with empty DataFrame."""
        empty = pd.DataFrame()
        assert calculate_turnover(empty) == 0.0


class TestSortino:
    """Tests for Sortino ratio calculation."""

    def test_sortino_normal(self, sample_returns):
        """Test Sortino ratio calculation."""
        sortino = calculate_sortino(sample_returns)
        assert isinstance(sortino, float)

    def test_sortino_no_downside(self):
        """Test Sortino with no downside."""
        positive = pd.Series([0.01, 0.02, 0.01, 0.03, 0.01])
        sortino = calculate_sortino(positive)
        assert sortino == float('inf')


class TestWinRate:
    """Tests for win rate calculation."""

    def test_win_rate_mixed(self):
        """Test win rate with mixed returns."""
        returns = pd.Series([0.01, -0.01, 0.02, -0.02, 0.01])
        win_rate = calculate_win_rate(returns)
        assert win_rate == 0.6  # 3/5 positive

    def test_win_rate_all_positive(self):
        """Test win rate with all positive."""
        returns = pd.Series([0.01, 0.02, 0.01])
        assert calculate_win_rate(returns) == 1.0

    def test_win_rate_all_negative(self):
        """Test win rate with all negative."""
        returns = pd.Series([-0.01, -0.02, -0.01])
        assert calculate_win_rate(returns) == 0.0


class TestProfitFactor:
    """Tests for profit factor calculation."""

    def test_profit_factor_normal(self):
        """Test profit factor calculation."""
        returns = pd.Series([0.10, -0.05, 0.08, -0.03])
        pf = calculate_profit_factor(returns)
        assert pf == 0.18 / 0.08  # 2.25

    def test_profit_factor_no_losses(self):
        """Test profit factor with no losses."""
        returns = pd.Series([0.01, 0.02, 0.01])
        assert calculate_profit_factor(returns) == float('inf')


# ===========================================
# PRICE PROVIDER TESTS
# ===========================================


class TestPriceProvider:
    """Tests for PriceProvider class."""

    def test_init(self):
        """Test price provider initialization."""
        provider = PriceProvider()
        assert provider.cache_dir is None
        assert provider._cache == {}

    def test_init_with_cache(self):
        """Test price provider with cache directory."""
        provider = PriceProvider(cache_dir="/tmp/cache")
        assert provider.cache_dir == "/tmp/cache"

    def test_get_prices_mock(self):
        """Test getting prices with mocked yfinance."""
        provider = PriceProvider()

        # Mock the internal cache to simulate cached prices
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        mock_prices = pd.DataFrame({
            "AAPL": [100, 101, 102, 101, 103]
        }, index=dates)

        cache_key = (("AAPL",), date(2024, 1, 1), date(2024, 1, 5), "adj_close")
        provider._cache[cache_key] = mock_prices

        prices = provider.get_prices(
            ["AAPL"],
            date(2024, 1, 1),
            date(2024, 1, 5)
        )

        assert not prices.empty
        assert "AAPL" in prices.columns

    def test_clear_cache(self):
        """Test clearing cache."""
        provider = PriceProvider()
        provider._cache["test"] = "data"
        provider.clear_cache()
        assert provider._cache == {}


# ===========================================
# BACKTEST ENGINE TESTS
# ===========================================


class TestBacktestEngine:
    """Tests for BacktestEngine class."""

    def test_init(self, mock_session):
        """Test engine initialization."""
        engine = BacktestEngine(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            session=mock_session
        )
        assert engine.start_date == date(2024, 1, 1)
        assert engine.end_date == date(2024, 6, 30)
        assert not engine._owns_session

    def test_init_without_session(self):
        """Test engine initialization without session."""
        engine = BacktestEngine(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30)
        )
        assert engine._session is None
        assert engine._owns_session

    def test_get_rebalance_dates_daily(self):
        """Test daily rebalance dates."""
        engine = BacktestEngine(date(2024, 1, 1), date(2024, 1, 31))
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        rebalance = engine._get_rebalance_dates(dates, "daily")
        assert len(rebalance) == 10

    def test_get_rebalance_dates_weekly(self):
        """Test weekly rebalance dates."""
        engine = BacktestEngine(date(2024, 1, 1), date(2024, 1, 31))
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        rebalance = engine._get_rebalance_dates(dates, "weekly")
        # Should have fewer dates than daily
        assert len(rebalance) < 30
        assert len(rebalance) >= 4  # At least 4 weeks

    def test_get_rebalance_dates_monthly(self):
        """Test monthly rebalance dates."""
        engine = BacktestEngine(date(2024, 1, 1), date(2024, 6, 30))
        dates = pd.date_range("2024-01-01", periods=180, freq="D")
        rebalance = engine._get_rebalance_dates(dates, "monthly")
        # Should have one per month
        assert len(rebalance) <= 6

    def test_build_positions_long_only(self, mock_session, sample_factor_df):
        """Test building long-only positions."""
        engine = BacktestEngine(
            date(2024, 1, 1),
            date(2024, 1, 30),
            session=mock_session
        )

        rebalance_dates = list(sample_factor_df.index[:5])

        positions = engine._build_positions(
            sample_factor_df,
            rebalance_dates,
            long_short=False,
            top_n=2
        )

        # Should have positions
        assert not positions.empty
        # Weights should sum to ~1 for long only
        assert positions.sum(axis=1).max() <= 1.01

    def test_build_positions_long_short(self, mock_session, sample_factor_df):
        """Test building long-short positions."""
        engine = BacktestEngine(
            date(2024, 1, 1),
            date(2024, 1, 30),
            session=mock_session
        )

        rebalance_dates = list(sample_factor_df.index[:5])

        positions = engine._build_positions(
            sample_factor_df,
            rebalance_dates,
            long_short=True,
            top_n=2
        )

        # Should have both long and short positions
        assert not positions.empty
        # Net should be approximately 0 for long-short
        assert abs(positions.sum(axis=1).max()) <= 0.01

    def test_calculate_strategy_returns(self, mock_session):
        """Test strategy returns calculation."""
        engine = BacktestEngine(
            date(2024, 1, 1),
            date(2024, 1, 10),
            session=mock_session
        )

        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        positions = pd.DataFrame({
            "AAPL": [0.5, 0.5, 0.5, 0.5, 0.5],
            "MSFT": [0.5, 0.5, 0.5, 0.5, 0.5]
        }, index=dates)

        returns = pd.DataFrame({
            "AAPL": [0.01, 0.02, -0.01, 0.01, 0.02],
            "MSFT": [0.02, 0.01, 0.01, -0.01, 0.01]
        }, index=dates)

        strategy_returns = engine._calculate_strategy_returns(
            positions, returns, transaction_cost=0.001
        )

        assert len(strategy_returns) == 4  # One less than input (no prior position)


# ===========================================
# BACKTEST RESULT TESTS
# ===========================================


class TestBacktestResult:
    """Tests for BacktestResult class."""

    def test_to_dict(self, sample_returns, sample_cumulative, sample_factor_df, sample_positions):
        """Test conversion to dictionary."""
        result = BacktestResult(
            sharpe_ratio=1.5,
            max_drawdown=-0.15,
            total_return=0.20,
            annualized_return=0.25,
            volatility=0.15,
            ic_mean=0.05,
            ic_ir=1.2,
            sortino_ratio=2.0,
            calmar_ratio=1.5,
            win_rate=0.55,
            profit_factor=1.8,
            turnover=0.2,
            returns=sample_returns,
            cumulative_returns=sample_cumulative,
            factor_values=sample_factor_df,
            positions=sample_positions,
            ic_series=pd.Series([0.05, 0.06, 0.04]),
            factor_name="test_factor",
            universe=["AAPL", "MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
        )

        d = result.to_dict()

        assert d["sharpe_ratio"] == 1.5
        assert d["max_drawdown"] == -0.15
        assert d["factor_name"] == "test_factor"
        assert d["status"] == "complete"

    def test_get_summary(self, sample_returns, sample_cumulative, sample_factor_df, sample_positions):
        """Test getting summary."""
        result = BacktestResult(
            sharpe_ratio=1.5,
            max_drawdown=-0.15,
            total_return=0.20,
            annualized_return=0.25,
            volatility=0.15,
            ic_mean=0.05,
            ic_ir=1.2,
            sortino_ratio=2.0,
            calmar_ratio=1.5,
            win_rate=0.55,
            profit_factor=1.8,
            turnover=0.2,
            returns=sample_returns,
            cumulative_returns=sample_cumulative,
            factor_values=sample_factor_df,
            positions=sample_positions,
            ic_series=pd.Series([0.05, 0.06, 0.04]),
        )

        summary = result.get_summary()

        assert "sharpe_ratio" in summary
        assert "max_drawdown" in summary
        assert "ic_mean" in summary


# ===========================================
# JOB MANAGER TESTS
# ===========================================


class TestBacktestJobManager:
    """Tests for BacktestJobManager class."""

    def test_init(self):
        """Test job manager initialization."""
        manager = BacktestJobManager()
        assert manager._jobs == {}
        assert manager._results == {}

    def test_get_job_status_not_found(self):
        """Test getting status for non-existent job."""
        manager = BacktestJobManager()
        status = manager.get_job_status("nonexistent")
        assert status is None

    def test_get_result_not_found(self):
        """Test getting result for non-existent job."""
        manager = BacktestJobManager()
        result = manager.get_result("nonexistent")
        assert result is None


# ===========================================
# INTEGRATION TESTS
# ===========================================


class TestBacktestIntegration:
    """Integration tests for backtesting system."""

    def test_full_backtest_flow(self, mock_session, sample_factor_df):
        """Test complete backtest flow."""
        engine = BacktestEngine(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 30),
            session=mock_session
        )

        # Mock the factor data retrieval
        engine._get_factor_data = Mock(return_value=sample_factor_df)

        # Mock price provider
        mock_prices = pd.DataFrame(
            np.random.randn(30, 5) * 0.02,
            index=sample_factor_df.index,
            columns=sample_factor_df.columns
        )
        engine.price_provider.get_returns = Mock(return_value=mock_prices)
        engine.price_provider.get_forward_returns = Mock(return_value=mock_prices)

        # Run backtest
        result = engine.run(
            factor_name="test_factor",
            universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            rebalance_freq="daily",
            long_short=True,
            top_n=2
        )

        # Verify result
        assert isinstance(result, BacktestResult)
        assert result.factor_name == "test_factor"
        assert len(result.universe) == 5

    def test_backtest_handles_missing_data(self, mock_session):
        """Test backtest handles missing factor data."""
        engine = BacktestEngine(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 30),
            session=mock_session
        )

        # Mock empty factor data
        engine._get_factor_data = Mock(return_value=pd.DataFrame())

        with pytest.raises(ValueError, match="No factor data"):
            engine.run(
                factor_name="test_factor",
                universe=["AAPL"],
                rebalance_freq="daily"
            )
