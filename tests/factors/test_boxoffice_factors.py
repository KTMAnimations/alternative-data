"""Unit tests for box office factors."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.transformations.factors.boxoffice_factors import (
    OpeningWeekendSurprise,
    StudioMarketShare,
    BOXOFFICE_FACTORS,
)
from src.transformations.factors.base import FactorResult
from src.entity_mapping.studio_ticker_mapping import PRIMARY_TICKERS
from src.models.data_sources import BoxOfficeDaily


class TestOpeningWeekendSurprise:
    """Tests for OpeningWeekendSurprise factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return OpeningWeekendSurprise()

    def test_factor_initialization(self, factor):
        """Test factor is properly initialized."""
        assert factor.factor_id == "opening_weekend_surprise"
        assert factor.name == "Opening Weekend Surprise"
        assert factor.domain == "entertainment"
        assert factor.primary_entities == PRIMARY_TICKERS

    def test_get_formula(self, factor):
        """Test formula is properly defined."""
        formula = factor.get_formula()
        assert formula is not None
        assert "G_{actual}" in formula
        assert "G_{expected}" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is properly defined."""
        rationale = factor.get_economic_rationale()
        assert rationale is not None
        assert len(rationale) > 100
        assert "opening weekend" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_returns_results_for_all_tickers(self, factor):
        """Test compute returns results for all primary tickers."""
        as_of_date = date(2025, 1, 15)

        # Mock the database session
        with patch('src.transformations.factors.boxoffice_factors.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_db = AsyncMock(spec=AsyncSession)

            # Mock the execute method to return empty results
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute.return_value = mock_result

            mock_ctx.__aenter__.return_value = mock_db
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            results = await factor.compute(as_of_date)

            # Should have result for each primary ticker
            assert len(results) == len(PRIMARY_TICKERS)
            for result in results:
                assert isinstance(result, FactorResult)
                assert result.ticker in PRIMARY_TICKERS
                assert result.factor_id == "opening_weekend_surprise"
                assert result.as_of_date == as_of_date

    @pytest.mark.asyncio
    async def test_compute_with_opening_data(self, factor):
        """Test compute with actual opening weekend data."""
        as_of_date = date(2025, 1, 15)

        # Create mock opening weekend data
        mock_opening = MagicMock(spec=BoxOfficeDaily)
        mock_opening.theater_count = 4000
        mock_opening.daily_gross = Decimal("50000000")  # $50M

        with patch('src.transformations.factors.boxoffice_factors.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_db = AsyncMock(spec=AsyncSession)

            # Mock execute to return opening data for DIS
            async def mock_execute(query):
                mock_result = MagicMock()
                # Check if this is a query for DIS
                mock_result.scalars.return_value.all.return_value = [mock_opening]
                return mock_result

            mock_db.execute = mock_execute

            mock_ctx.__aenter__.return_value = mock_db
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            results = await factor.compute(as_of_date, tickers=["DIS"])

            assert len(results) == 1
            result = results[0]
            assert result.ticker == "DIS"
            # With $50M actual vs $34M expected (4000 * $8500), surprise should be positive
            assert result.mean > Decimal("0")
            assert result.data_quality >= Decimal("0.7")
            assert "opening_count" in result.metadata

    @pytest.mark.asyncio
    async def test_compute_no_openings_returns_neutral(self, factor):
        """Test compute returns neutral factor when no openings."""
        as_of_date = date(2025, 1, 15)

        with patch('src.transformations.factors.boxoffice_factors.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_db = AsyncMock(spec=AsyncSession)

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute.return_value = mock_result

            mock_ctx.__aenter__.return_value = mock_db
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            results = await factor.compute(as_of_date, tickers=["DIS"])

            assert len(results) == 1
            result = results[0]
            assert result.mean == Decimal("0")
            assert result.data_quality == Decimal("0.5")
            assert result.metadata["opening_count"] == 0

    def test_compute_variance(self, factor):
        """Test variance computation."""
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        mean = 0.3
        variance = factor._compute_variance(values, mean)

        # Expected variance: sum((v - 0.3)^2) / 4 = 0.025
        assert abs(variance - 0.025) < 0.001

    def test_compute_variance_single_observation(self, factor):
        """Test variance with single observation returns default."""
        values = [0.1]
        variance = factor._compute_variance(values, 0.1)
        assert variance == 0.01  # Default for single observation

    def test_compute_data_quality(self, factor):
        """Test data quality computation based on observation count."""
        assert factor._compute_data_quality(5) == Decimal("1.0")
        assert factor._compute_data_quality(3) == Decimal("0.9")
        assert factor._compute_data_quality(1) == Decimal("0.7")
        assert factor._compute_data_quality(0) == Decimal("0.5")


class TestStudioMarketShare:
    """Tests for StudioMarketShare factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return StudioMarketShare()

    def test_factor_initialization(self, factor):
        """Test factor is properly initialized."""
        assert factor.factor_id == "studio_market_share"
        assert factor.name == "Studio Market Share"
        assert factor.domain == "entertainment"
        assert factor.primary_entities == PRIMARY_TICKERS

    def test_get_formula(self, factor):
        """Test formula is properly defined."""
        formula = factor.get_formula()
        assert formula is not None
        assert "MS_t" in formula
        assert "sum" in formula.lower() or "\\sum" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is properly defined."""
        rationale = factor.get_economic_rationale()
        assert rationale is not None
        assert len(rationale) > 100
        assert "market share" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_returns_results_for_all_tickers(self, factor):
        """Test compute returns results for all primary tickers."""
        as_of_date = date(2025, 1, 15)

        with patch('src.transformations.factors.boxoffice_factors.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_db = AsyncMock(spec=AsyncSession)

            # Mock total market query to return $100M
            mock_market_result = MagicMock()
            mock_market_result.scalar_one_or_none.return_value = Decimal("100000000")

            # Mock studio query to return $0
            mock_studio_result = MagicMock()
            mock_studio_result.scalar_one_or_none.return_value = Decimal("0")

            # Mock daily shares query
            mock_daily_result = MagicMock()
            mock_daily_result.__iter__ = lambda self: iter([])

            mock_db.execute = AsyncMock(side_effect=[
                mock_market_result,  # Total market
                mock_studio_result,  # Studio gross for DIS
                mock_daily_result,   # Daily shares for DIS
                mock_studio_result,  # Studio gross for WBD
                mock_daily_result,   # Daily shares for WBD
                mock_studio_result,  # Studio gross for PARA
                mock_daily_result,   # Daily shares for PARA
                mock_studio_result,  # Studio gross for CMCSA
                mock_daily_result,   # Daily shares for CMCSA
                mock_studio_result,  # Studio gross for SONY
                mock_daily_result,   # Daily shares for SONY
            ])

            mock_ctx.__aenter__.return_value = mock_db
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            results = await factor.compute(as_of_date)

            assert len(results) == len(PRIMARY_TICKERS)
            for result in results:
                assert isinstance(result, FactorResult)
                assert result.ticker in PRIMARY_TICKERS
                assert result.factor_id == "studio_market_share"

    @pytest.mark.asyncio
    async def test_compute_with_market_data(self, factor):
        """Test compute with actual market data."""
        as_of_date = date(2025, 1, 15)

        with patch('src.transformations.factors.boxoffice_factors.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_db = AsyncMock(spec=AsyncSession)

            # Total market: $100M
            mock_market_result = MagicMock()
            mock_market_result.scalar_one_or_none.return_value = Decimal("100000000")

            # Disney gross: $20M (20% share)
            mock_studio_result = MagicMock()
            mock_studio_result.scalar_one_or_none.return_value = Decimal("20000000")

            # Daily shares
            mock_daily_result = MagicMock()
            mock_daily_result.__iter__ = lambda self: iter([])

            mock_db.execute = AsyncMock(side_effect=[
                mock_market_result,
                mock_studio_result,
                mock_daily_result,
            ])

            mock_ctx.__aenter__.return_value = mock_db
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            results = await factor.compute(as_of_date, tickers=["DIS"])

            assert len(results) == 1
            result = results[0]
            assert result.ticker == "DIS"
            assert result.mean == Decimal("0.2")  # 20% market share
            assert result.metadata["studio_gross"] == 20000000
            assert result.metadata["total_market"] == 100000000

    @pytest.mark.asyncio
    async def test_compute_no_market_returns_low_quality(self, factor):
        """Test compute returns low quality when no market data."""
        as_of_date = date(2025, 1, 15)

        with patch('src.transformations.factors.boxoffice_factors.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_db = AsyncMock(spec=AsyncSession)

            # No market data
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = Decimal("0")
            mock_db.execute.return_value = mock_result

            mock_ctx.__aenter__.return_value = mock_db
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            results = await factor.compute(as_of_date, tickers=["DIS"])

            assert len(results) == 1
            result = results[0]
            assert result.mean == Decimal("0")
            assert result.data_quality == Decimal("0.3")
            assert result.metadata.get("no_market_data") is True

    def test_compute_data_quality_by_share(self, factor):
        """Test data quality based on market share magnitude."""
        # High share (>5%)
        assert factor._compute_data_quality(
            Decimal("10000000"),
            Decimal("100000000")
        ) == Decimal("1.0")

        # Medium share (1-5%)
        assert factor._compute_data_quality(
            Decimal("2000000"),
            Decimal("100000000")
        ) == Decimal("0.9")

        # Low share (<1%)
        assert factor._compute_data_quality(
            Decimal("500000"),
            Decimal("100000000")
        ) == Decimal("0.7")

        # No studio data
        assert factor._compute_data_quality(
            Decimal("0"),
            Decimal("100000000")
        ) == Decimal("0.5")


class TestBoxOfficeFactorsExport:
    """Tests for factor exports."""

    def test_boxoffice_factors_list(self):
        """Test BOXOFFICE_FACTORS contains all factors."""
        assert len(BOXOFFICE_FACTORS) == 2
        assert OpeningWeekendSurprise in BOXOFFICE_FACTORS
        assert StudioMarketShare in BOXOFFICE_FACTORS

    def test_all_factors_have_required_attributes(self):
        """Test all factors have required base class attributes."""
        for FactorClass in BOXOFFICE_FACTORS:
            factor = FactorClass()
            assert hasattr(factor, 'factor_id')
            assert hasattr(factor, 'name')
            assert hasattr(factor, 'description')
            assert hasattr(factor, 'domain')
            assert hasattr(factor, 'primary_entities')
            assert factor.domain == "entertainment"

    def test_all_factors_have_formulas(self):
        """Test all factors implement get_formula."""
        for FactorClass in BOXOFFICE_FACTORS:
            factor = FactorClass()
            formula = factor.get_formula()
            assert formula is not None
            assert len(formula) > 0

    def test_all_factors_have_economic_rationale(self):
        """Test all factors implement get_economic_rationale."""
        for FactorClass in BOXOFFICE_FACTORS:
            factor = FactorClass()
            rationale = factor.get_economic_rationale()
            assert rationale is not None
            assert len(rationale) > 50


class TestFactorValidation:
    """Tests for factor input validation."""

    @pytest.fixture
    def opening_factor(self):
        return OpeningWeekendSurprise()

    @pytest.fixture
    def market_share_factor(self):
        return StudioMarketShare()

    @pytest.mark.asyncio
    async def test_validate_future_date_warning(self, opening_factor):
        """Test validation warns for future dates."""
        future_date = date.today() + timedelta(days=30)
        is_valid = await opening_factor.validate_inputs(future_date)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_past_date_ok(self, opening_factor):
        """Test validation accepts past dates."""
        past_date = date.today() - timedelta(days=30)
        is_valid = await opening_factor.validate_inputs(past_date)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_today_ok(self, opening_factor):
        """Test validation accepts today."""
        is_valid = await opening_factor.validate_inputs(date.today())
        assert is_valid is True
