"""Tests for Google Trends data collection and factors."""

import sys
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
import pandas as pd

# Mock pytrends before importing collector
sys.modules['pytrends'] = MagicMock()
sys.modules['pytrends.request'] = MagicMock()

from src.collectors.google_trends import GoogleTrendsCollector
from src.models.trends import (
    TrendKeyword,
    TrendInterest,
    TrendRelatedQuery,
    TrendComparison,
    TrendBreakout,
)
from src.transformations.factors.trends_factors import (
    calc_search_momentum,
    calc_search_volatility,
    calc_relative_search_strength,
    calc_search_yoy_change,
    calc_category_composite_interest,
    count_recent_breakouts,
    SearchMomentum,
    SearchVolatility,
    SearchYoYChange,
    CategoryInterest,
    RetailSentimentIndex,
)


# =============================================================================
# Trends Model Tests
# =============================================================================

class TestTrendsModels:
    """Test trends database models."""

    def test_trend_keyword_model(self):
        """Test TrendKeyword model creation."""
        keyword = TrendKeyword(
            keyword="iphone",
            category="tech",
            related_tickers=["AAPL"],
            related_sectors=["technology"],
            is_active=True,
        )
        assert keyword.keyword == "iphone"
        assert keyword.category == "tech"
        assert "AAPL" in keyword.related_tickers

    def test_trend_interest_model(self):
        """Test TrendInterest model creation."""
        interest = TrendInterest(
            keyword="bitcoin",
            geo="US",
            date=date.today(),
            interest=75,
            is_partial=False,
        )
        assert interest.keyword == "bitcoin"
        assert interest.interest == 75
        assert interest.geo == "US"

    def test_trend_related_query_model(self):
        """Test TrendRelatedQuery model creation."""
        related = TrendRelatedQuery(
            keyword="stock market",
            geo="US",
            related_query="stock market crash",
            query_type="rising",
            value=500,
        )
        assert related.keyword == "stock market"
        assert related.query_type == "rising"
        assert related.value == 500

    def test_trend_comparison_model(self):
        """Test TrendComparison model creation."""
        comparison = TrendComparison(
            keyword_group="iphone,android",
            geo="US",
            date=date.today(),
            keyword_values={"iphone": 80, "android": 65},
        )
        assert comparison.keyword_group == "iphone,android"
        assert comparison.keyword_values["iphone"] == 80

    def test_trend_breakout_model(self):
        """Test TrendBreakout model creation."""
        breakout = TrendBreakout(
            keyword="nvidia stock",
            geo="US",
            breakout_date=date.today(),
            interest_before=45.0,
            interest_peak=100,
            percent_change=122.2,
        )
        assert breakout.keyword == "nvidia stock"
        assert breakout.percent_change == 122.2


# =============================================================================
# Google Trends Collector Tests
# =============================================================================

class TestGoogleTrendsCollector:
    """Test Google Trends collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = GoogleTrendsCollector()
        assert collector.SOURCE_NAME == "google_trends"
        assert collector.geo == "US"
        assert collector.hl == "en-US"

    def test_collector_with_custom_geo(self):
        """Test collector with custom geo."""
        collector = GoogleTrendsCollector(geo="GB")
        assert collector.geo == "GB"

    def test_default_keywords(self):
        """Test default keywords configuration."""
        collector = GoogleTrendsCollector()
        assert "retail" in collector.DEFAULT_KEYWORDS
        assert "tech" in collector.DEFAULT_KEYWORDS
        assert "energy" in collector.DEFAULT_KEYWORDS
        assert len(collector.DEFAULT_KEYWORDS["retail"]) > 0

    def test_keyword_tickers_mapping(self):
        """Test keyword to ticker mapping."""
        collector = GoogleTrendsCollector()
        assert "iphone" in collector.KEYWORD_TICKERS
        assert "AAPL" in collector.KEYWORD_TICKERS["iphone"]
        assert "nvidia stock" in collector.KEYWORD_TICKERS

    @patch.object(GoogleTrendsCollector, 'pytrends', new_callable=PropertyMock)
    def test_fetch_interest_over_time(self, mock_pytrends_prop):
        """Test fetching interest over time."""
        collector = GoogleTrendsCollector()

        # Create mock pytrends
        mock_pytrends = MagicMock()
        mock_pytrends_prop.return_value = mock_pytrends

        # Create mock DataFrame
        mock_df = pd.DataFrame({
            "iphone": [80, 85, 90, 88, 75],
            "isPartial": [False, False, False, False, True],
        }, index=pd.date_range("2024-01-01", periods=5))

        mock_pytrends.interest_over_time.return_value = mock_df

        result = collector.fetch_interest_over_time("iphone", "today 3-m")

        assert result is not None
        assert result["keyword"] == "iphone"
        assert len(result["data"]) == 5
        assert result["data"][0]["interest"] == 80

    @patch.object(GoogleTrendsCollector, 'pytrends', new_callable=PropertyMock)
    def test_fetch_interest_empty_result(self, mock_pytrends_prop):
        """Test handling empty results."""
        collector = GoogleTrendsCollector()

        mock_pytrends = MagicMock()
        mock_pytrends_prop.return_value = mock_pytrends
        mock_pytrends.interest_over_time.return_value = pd.DataFrame()

        result = collector.fetch_interest_over_time("obscure_term")

        assert result is None

    @patch.object(GoogleTrendsCollector, 'pytrends', new_callable=PropertyMock)
    def test_fetch_related_queries(self, mock_pytrends_prop):
        """Test fetching related queries."""
        collector = GoogleTrendsCollector()

        mock_pytrends = MagicMock()
        mock_pytrends_prop.return_value = mock_pytrends

        top_df = pd.DataFrame({
            "query": ["iphone 15", "iphone pro"],
            "value": [100, 85],
        })
        rising_df = pd.DataFrame({
            "query": ["iphone 16 release"],
            "value": [500],
        })

        mock_pytrends.related_queries.return_value = {
            "iphone": {"top": top_df, "rising": rising_df}
        }

        result = collector.fetch_related_queries("iphone")

        assert result is not None
        assert result["keyword"] == "iphone"
        assert len(result["top"]) == 2
        assert len(result["rising"]) == 1

    @patch.object(GoogleTrendsCollector, 'pytrends', new_callable=PropertyMock)
    def test_fetch_comparison(self, mock_pytrends_prop):
        """Test fetching keyword comparison."""
        collector = GoogleTrendsCollector()

        mock_pytrends = MagicMock()
        mock_pytrends_prop.return_value = mock_pytrends

        mock_df = pd.DataFrame({
            "iphone": [80, 75],
            "android": [60, 65],
            "isPartial": [False, False],
        }, index=pd.date_range("2024-01-01", periods=2))

        mock_pytrends.interest_over_time.return_value = mock_df

        result = collector.fetch_comparison(["iphone", "android"])

        assert result is not None
        assert result["keywords"] == ["iphone", "android"]
        assert len(result["data"]) == 2
        assert result["data"][0]["values"]["iphone"] == 80

    @patch.object(GoogleTrendsCollector, 'pytrends', new_callable=PropertyMock)
    def test_fetch_comparison_max_keywords(self, mock_pytrends_prop):
        """Test comparison limits to 5 keywords."""
        collector = GoogleTrendsCollector()

        mock_pytrends = MagicMock()
        mock_pytrends_prop.return_value = mock_pytrends
        mock_pytrends.interest_over_time.return_value = pd.DataFrame()

        # This tests internal logic - 6 keywords should be truncated to 5
        keywords = ["a", "b", "c", "d", "e", "f"]
        collector.fetch_comparison(keywords)

        # The payload should only include 5 keywords
        call_args = mock_pytrends.build_payload.call_args
        assert len(call_args[1]["kw_list"]) == 5

    @patch.object(GoogleTrendsCollector, 'pytrends', new_callable=PropertyMock)
    def test_detect_breakout(self, mock_pytrends_prop):
        """Test breakout detection."""
        collector = GoogleTrendsCollector()

        mock_pytrends = MagicMock()
        mock_pytrends_prop.return_value = mock_pytrends

        # Create data with a breakout in recent period
        # Baseline avg ~50, then spike to 100
        dates = pd.date_range(end=date.today(), periods=40)
        values = [50] * 33 + [100, 95, 100, 90, 95, 100, 100]

        mock_df = pd.DataFrame({
            "nvidia": values,
            "isPartial": [False] * 40,
        }, index=dates)

        mock_pytrends.interest_over_time.return_value = mock_df

        result = collector.detect_breakout("nvidia", threshold=1.5, lookback_days=30)

        assert result is not None
        assert result["keyword"] == "nvidia"
        assert result["interest_peak"] == 100
        assert result["percent_change"] > 0

    def test_parse_passthrough(self):
        """Test that parse returns data unchanged."""
        collector = GoogleTrendsCollector()
        data = [{"keyword": "test", "data": []}]
        result = collector.parse(data)
        assert result == data


# =============================================================================
# Trends Factor Calculation Tests
# =============================================================================

class TestTrendsFactorCalculations:
    """Test trends factor calculation functions."""

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_calc_search_momentum(self, mock_session_local):
        """Test search momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Short-term avg: 80, Long-term avg: 60
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [80.0, 60.0]

        result = calc_search_momentum("iphone", date(2024, 6, 15))

        # Momentum = (80 - 60) / 60 = 0.333...
        assert result is not None
        assert abs(result - 0.333) < 0.01
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_calc_search_momentum_no_data(self, mock_session_local):
        """Test momentum returns None when no data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.scalar.return_value = None

        result = calc_search_momentum("unknown_keyword", date(2024, 6, 15))

        assert result is None

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_calc_search_volatility(self, mock_session_local):
        """Test search volatility calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Return mock interest values
        mock_session.query.return_value.filter.return_value.all.return_value = [
            (50,), (60,), (55,), (70,), (45,), (65,)
        ]

        result = calc_search_volatility("bitcoin", date(2024, 6, 15))

        assert result is not None
        assert result > 0  # Should have some volatility

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_calc_search_volatility_insufficient_data(self, mock_session_local):
        """Test volatility returns None with insufficient data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = [(50,), (60,)]

        result = calc_search_volatility("bitcoin", date(2024, 6, 15))

        assert result is None

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_calc_relative_search_strength(self, mock_session_local):
        """Test relative search strength calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Primary: 80, Comparison avg: 40
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [80.0, 40.0, 40.0]

        result = calc_relative_search_strength(
            "iphone",
            date(2024, 6, 15),
            ["android", "samsung"],
        )

        # RSI = 80 / (80 + 40) * 100 = 66.67
        assert result is not None
        assert abs(result - 66.67) < 1

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_calc_search_yoy_change(self, mock_session_local):
        """Test YoY change calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current: 80, Prior year: 50
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [80.0, 50.0]

        result = calc_search_yoy_change("recession", date(2024, 6, 15))

        # YoY = (80 - 50) / 50 * 100 = 60%
        assert result is not None
        assert result == 60.0

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_calc_category_composite_interest(self, mock_session_local):
        """Test category composite interest calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock keywords in category
        mock_session.query.return_value.filter.return_value.all.return_value = [
            ("bitcoin",), ("ethereum",)
        ]
        # Mock average interest
        mock_session.query.return_value.filter.return_value.scalar.return_value = 75.0

        result = calc_category_composite_interest("crypto", date(2024, 6, 15))

        assert result == 75.0

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_count_recent_breakouts(self, mock_session_local):
        """Test breakout counting."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 3

        result = count_recent_breakouts(lookback_days=7)

        assert result == 3


# =============================================================================
# Trends Factor Class Tests
# =============================================================================

class TestTrendsFactorClasses:
    """Test trends factor classes."""

    def test_search_momentum_factor(self):
        """Test SearchMomentum factor class."""
        factor = SearchMomentum()
        assert factor.FACTOR_NAME == "search_momentum"
        assert factor.CATEGORY == "trends"
        assert factor.ENTITY_TYPE == "keyword"

    def test_search_volatility_factor(self):
        """Test SearchVolatility factor class."""
        factor = SearchVolatility()
        assert factor.FACTOR_NAME == "search_volatility"
        assert factor.LOOKBACK_DAYS == 30

    def test_search_yoy_change_factor(self):
        """Test SearchYoYChange factor class."""
        factor = SearchYoYChange()
        assert factor.FACTOR_NAME == "search_yoy_change"
        assert "yoy" in factor.FACTOR_DESCRIPTION.lower() or "year" in factor.FACTOR_DESCRIPTION.lower()

    def test_category_interest_factor(self):
        """Test CategoryInterest factor class."""
        factor = CategoryInterest()
        assert factor.FACTOR_NAME == "category_interest"
        assert factor.ENTITY_TYPE == "category"

    def test_retail_sentiment_index_factor(self):
        """Test RetailSentimentIndex factor class."""
        factor = RetailSentimentIndex()
        assert factor.FACTOR_NAME == "retail_sentiment_index"
        assert factor.ENTITY_TYPE == "market"
        assert len(factor.RETAIL_POSITIVE) > 0
        assert len(factor.RETAIL_NEGATIVE) > 0

    @patch("src.transformations.factors.trends_factors.calc_search_momentum")
    def test_search_momentum_compute(self, mock_calc):
        """Test SearchMomentum compute method."""
        mock_calc.return_value = 0.25

        factor = SearchMomentum()
        result = factor.compute("iphone", datetime(2024, 6, 15))

        assert result == 0.25
        mock_calc.assert_called_once()

    @patch("src.transformations.factors.trends_factors.SessionLocal")
    def test_retail_sentiment_compute(self, mock_session_local):
        """Test RetailSentimentIndex compute method."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Positive avg: 60, Negative avg: 40
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [60.0, 40.0]

        factor = RetailSentimentIndex()
        result = factor.compute("market", datetime(2024, 6, 15))

        # Sentiment = (60 - 40) / (60 + 40) * 100 = 20
        assert result is not None
        assert result == 20.0


# =============================================================================
# Factor Registry Tests
# =============================================================================

class TestTrendsFactorRegistry:
    """Test trends factors in registry."""

    def test_trends_factors_registered(self):
        """Test that all trends factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        trends_factors = [
            "search_momentum",
            "search_volatility",
            "search_yoy_change",
            "category_interest",
            "retail_sentiment_index",
        ]

        for factor in trends_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_trends_factors_category(self):
        """Test trends factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        trends_factors = [f for f in registered if f["category"] == "trends"]

        assert len(trends_factors) >= 5
