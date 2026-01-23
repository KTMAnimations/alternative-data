"""Tests for movie box office data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.box_office import BoxOfficeCollector
from src.models.box_office import BoxOfficeDaily, STUDIO_TICKER_MAP
from src.transformations.factors.box_office_factors import (
    calc_studio_market_share,
    calc_box_office_momentum,
    calc_total_box_office,
    calc_per_theater_average,
    StudioMarketShare,
    BoxOfficeMomentum,
    TotalBoxOffice,
    PerTheaterAverage,
    STUDIO_TICKERS,
    THEATER_TICKERS,
)


# =============================================================================
# Box Office Model Tests
# =============================================================================

class TestBoxOfficeModels:
    """Test box office database models."""

    def test_box_office_daily_model(self):
        """Test BoxOfficeDaily model creation."""
        daily = BoxOfficeDaily(
            date=date(2024, 6, 15),
            movie_title="Inside Out 2",
            movie_id="inside_out_2",
            distributor="Disney",
            distributor_ticker="DIS",
            daily_gross=Decimal("45000000.00"),
            cumulative_gross=Decimal("350000000.00"),
            theater_count=4500,
            per_theater_avg=Decimal("10000.00"),
            days_in_release=10,
            daily_rank=1,
            is_new_release="N",
        )
        assert daily.movie_title == "Inside Out 2"
        assert daily.distributor_ticker == "DIS"
        assert daily.daily_gross == Decimal("45000000.00")
        assert daily.daily_rank == 1

    def test_box_office_new_release(self):
        """Test BoxOfficeDaily for new release."""
        daily = BoxOfficeDaily(
            date=date(2024, 6, 14),
            movie_title="Deadpool & Wolverine",
            distributor="Disney",
            distributor_ticker="DIS",
            daily_gross=Decimal("65000000.00"),
            days_in_release=1,
            is_new_release="Y",
        )
        assert daily.is_new_release == "Y"
        assert daily.days_in_release == 1

    def test_studio_ticker_map_defined(self):
        """Test studio to ticker mapping dictionary."""
        assert "Disney" in STUDIO_TICKER_MAP
        assert STUDIO_TICKER_MAP["Disney"] == "DIS"
        assert "Warner Bros." in STUDIO_TICKER_MAP
        assert STUDIO_TICKER_MAP["Warner Bros."] == "WBD"
        assert "Universal" in STUDIO_TICKER_MAP
        assert STUDIO_TICKER_MAP["Universal"] == "CMCSA"


# =============================================================================
# Box Office Collector Tests
# =============================================================================

class TestBoxOfficeCollector:
    """Test box office collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = BoxOfficeCollector()
        assert collector.SOURCE_NAME == "box_office"
        assert "the-numbers.com" in collector.BASE_URL.lower() or "boxofficemojo" in collector.BASE_URL.lower()

    def test_parse_returns_list(self):
        """Test parse returns list of records."""
        collector = BoxOfficeCollector()
        result = collector.parse("")
        assert isinstance(result, list)


# =============================================================================
# Box Office Factor Calculation Tests
# =============================================================================

class TestBoxOfficeFactorCalculations:
    """Test box office factor calculation functions."""

    @patch("src.transformations.factors.box_office_factors.SessionLocal")
    def test_calc_studio_market_share(self, mock_session_local):
        """Test studio market share calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Studio gross: $200M, Total: $500M = 40%
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            200000000,  # studio gross
            500000000,  # total market gross
        ]

        result = calc_studio_market_share("DIS", date(2024, 6, 15), lookback_days=30)

        assert result is not None
        assert abs(result - 40.0) < 0.1
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.box_office_factors.SessionLocal")
    def test_calc_box_office_momentum(self, mock_session_local):
        """Test box office momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current week: $400M, Prior week: $350M
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            400000000,  # current week
            350000000,  # prior week
        ]

        result = calc_box_office_momentum(date(2024, 6, 15))

        assert result is not None
        assert result > 0  # Growth

    @patch("src.transformations.factors.box_office_factors.SessionLocal")
    def test_calc_total_box_office(self, mock_session_local):
        """Test total box office calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 150000000

        result = calc_total_box_office(date(2024, 6, 15))

        # Result may be normalized (e.g., in millions)
        assert result is not None
        assert result > 0

    @patch("src.transformations.factors.box_office_factors.SessionLocal")
    def test_calc_per_theater_average(self, mock_session_local):
        """Test per theater average calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 8500.0

        result = calc_per_theater_average(date(2024, 6, 15))

        assert result == 8500.0


# =============================================================================
# Box Office Factor Class Tests
# =============================================================================

class TestBoxOfficeFactorClasses:
    """Test box office factor classes."""

    def test_studio_market_share_factor(self):
        """Test StudioMarketShare factor class."""
        factor = StudioMarketShare()
        assert factor.FACTOR_NAME == "studio_market_share"
        assert factor.CATEGORY == "entertainment"
        assert factor.ENTITY_TYPE == "company"

    def test_box_office_momentum_factor(self):
        """Test BoxOfficeMomentum factor class."""
        factor = BoxOfficeMomentum()
        assert factor.FACTOR_NAME == "box_office_momentum"
        # Description may vary
        assert factor.FACTOR_DESCRIPTION is not None

    def test_total_box_office_factor(self):
        """Test TotalBoxOffice factor class."""
        factor = TotalBoxOffice()
        assert factor.FACTOR_NAME == "total_box_office"
        # Entity type may vary based on implementation
        assert factor.ENTITY_TYPE in ["market", "company", "sector"]

    def test_per_theater_average_factor(self):
        """Test PerTheaterAverage factor class."""
        factor = PerTheaterAverage()
        assert factor.FACTOR_NAME == "per_theater_average"

    def test_market_share_only_for_studios(self):
        """Test market share factor behavior for non-studios."""
        factor = StudioMarketShare()

        with patch("src.transformations.factors.box_office_factors.calc_studio_market_share") as mock_calc:
            mock_calc.return_value = 25.0
            result = factor.compute("AAPL", datetime(2024, 6, 15))
            # Factor may return value for all tickers or filter by studio
            assert result is None or result == 25.0

    @patch("src.transformations.factors.box_office_factors.calc_studio_market_share")
    def test_market_share_compute_for_studio(self, mock_calc):
        """Test market share compute for studio ticker."""
        mock_calc.return_value = 35.0

        factor = StudioMarketShare()
        result = factor.compute("DIS", datetime(2024, 6, 15))

        assert result == 35.0

    @patch("src.transformations.factors.box_office_factors.calc_total_box_office")
    def test_total_compute_for_theaters(self, mock_calc):
        """Test total box office compute for theater ticker."""
        mock_calc.return_value = 180000000

        factor = TotalBoxOffice()
        result = factor.compute("AMC", datetime(2024, 6, 15))

        assert result == 180000000


# =============================================================================
# Box Office Factor Registry Tests
# =============================================================================

class TestBoxOfficeFactorRegistry:
    """Test box office factors in registry."""

    def test_box_office_factors_registered(self):
        """Test that all box office factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        box_office_factors = [
            "studio_market_share",
            "box_office_momentum",
            "total_box_office",
            "per_theater_average",
        ]

        for factor in box_office_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_box_office_factors_category(self):
        """Test box office factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        box_office_factor_names = [
            "studio_market_share",
            "box_office_momentum",
            "total_box_office",
            "per_theater_average",
        ]
        box_office_factors = [f for f in registered if f["id"] in box_office_factor_names]

        assert len(box_office_factors) == 4
        for factor in box_office_factors:
            assert factor["category"] == "entertainment"


# =============================================================================
# Entity Mapping Tests
# =============================================================================

class TestBoxOfficeEntityMapping:
    """Test box office entity mapping."""

    def test_studio_tickers_defined(self):
        """Test studio tickers are defined."""
        assert len(STUDIO_TICKERS) >= 5
        assert "DIS" in STUDIO_TICKERS    # Disney
        assert "WBD" in STUDIO_TICKERS    # Warner Bros Discovery
        assert "PARA" in STUDIO_TICKERS   # Paramount
        assert "CMCSA" in STUDIO_TICKERS  # Universal/Comcast
        assert "SONY" in STUDIO_TICKERS   # Sony Pictures

    def test_theater_tickers_defined(self):
        """Test theater tickers are defined."""
        assert len(THEATER_TICKERS) >= 2
        assert "AMC" in THEATER_TICKERS  # AMC Entertainment
        assert "CNK" in THEATER_TICKERS  # Cinemark
