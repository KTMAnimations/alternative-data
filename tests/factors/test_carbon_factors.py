"""Unit tests for carbon intensity factors."""

import pytest
import pytest_asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from src.transformations.factors.carbon_factors import (
    CarbonIntensityTrend,
    RenewableShareGrowth,
    create_carbon_intensity_trend,
    create_renewable_share_growth,
    CARBON_FACTORS,
    UK_ENERGY_ENTITIES,
)
from src.transformations.factors.base import FactorResult
from src.models.data_sources import CarbonIntensityReading


class TestCarbonIntensityTrend:
    """Test suite for CarbonIntensityTrend factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return CarbonIntensityTrend()

    def test_factor_attributes(self, factor):
        """Test factor has correct attributes."""
        assert factor.factor_id == "carbon_intensity_mom"
        assert factor.name == "Carbon Intensity MoM Change"
        assert factor.domain == "energy"
        assert factor.primary_entities == UK_ENERGY_ENTITIES
        assert "NG.L" in factor.primary_entities
        assert "SSE.L" in factor.primary_entities

    def test_get_formula(self, factor):
        """Test factor returns LaTeX formula."""
        formula = factor.get_formula()
        assert r"\text{CI}_{MoM}" in formula
        assert r"\bar{I}" in formula

    def test_get_economic_rationale(self, factor):
        """Test factor returns economic rationale."""
        rationale = factor.get_economic_rationale()
        assert "carbon" in rationale.lower()
        assert "intensity" in rationale.lower()
        assert len(rationale) > 100  # Should be substantial explanation

    @pytest.mark.asyncio
    async def test_compute_with_data(self, factor, db_session):
        """Test factor computation with data in database."""
        # Insert test data for current and prior month
        current_month = date(2024, 2, 15)
        prior_month_start = date(2024, 1, 1)

        # Mock the database queries
        with patch.object(factor, '_get_average_intensity') as mock_avg:
            with patch.object(factor, '_get_intensity_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    mock_avg.side_effect = [200.0, 220.0]  # Current, Prior
                    mock_var.return_value = 100.0
                    mock_quality.return_value = Decimal("0.95")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(current_month)

        # Expect results for both primary entities
        assert len(results) == 2

        # Check result structure
        for result in results:
            assert isinstance(result, FactorResult)
            assert result.factor_id == "carbon_intensity_mom"
            assert result.as_of_date == current_month
            assert result.ticker in UK_ENERGY_ENTITIES

    @pytest.mark.asyncio
    async def test_compute_mom_change_calculation(self, factor):
        """Test MoM change calculation is correct."""
        as_of_date = date(2024, 2, 15)

        with patch.object(factor, '_get_average_intensity') as mock_avg:
            with patch.object(factor, '_get_intensity_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    # Current: 200, Prior: 250 => -20% change
                    mock_avg.side_effect = [200.0, 250.0]
                    mock_var.return_value = 50.0
                    mock_quality.return_value = Decimal("0.95")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(as_of_date)

        # Expected: (200 - 250) / 250 * 100 = -20%
        assert len(results) == 2
        expected_change = Decimal("-20.0")
        assert results[0].mean == expected_change

    @pytest.mark.asyncio
    async def test_compute_insufficient_data(self, factor):
        """Test computation returns empty list with insufficient data."""
        as_of_date = date(2024, 2, 15)

        with patch.object(factor, '_get_average_intensity') as mock_avg:
            mock_avg.side_effect = [None, 200.0]  # No current month data

            with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                mock_session.return_value.__aexit__ = AsyncMock()

                results = await factor.compute(as_of_date)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_compute_for_specific_tickers(self, factor):
        """Test computation for specific tickers."""
        as_of_date = date(2024, 2, 15)
        specific_tickers = ["NG.L"]

        with patch.object(factor, '_get_average_intensity') as mock_avg:
            with patch.object(factor, '_get_intensity_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    mock_avg.side_effect = [200.0, 220.0]
                    mock_var.return_value = 50.0
                    mock_quality.return_value = Decimal("0.95")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(as_of_date, tickers=specific_tickers)

        assert len(results) == 1
        assert results[0].ticker == "NG.L"

    @pytest.mark.asyncio
    async def test_metadata_contains_required_fields(self, factor):
        """Test result metadata contains expected fields."""
        as_of_date = date(2024, 2, 15)

        with patch.object(factor, '_get_average_intensity') as mock_avg:
            with patch.object(factor, '_get_intensity_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    mock_avg.side_effect = [200.0, 220.0]
                    mock_var.return_value = 50.0
                    mock_quality.return_value = Decimal("0.95")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(as_of_date)

        assert len(results) > 0
        metadata = results[0].metadata

        assert "region" in metadata
        assert "current_month_avg" in metadata
        assert "prior_month_avg" in metadata
        assert "current_month_start" in metadata
        assert "prior_month_start" in metadata


class TestRenewableShareGrowth:
    """Test suite for RenewableShareGrowth factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return RenewableShareGrowth()

    def test_factor_attributes(self, factor):
        """Test factor has correct attributes."""
        assert factor.factor_id == "renewable_share_growth"
        assert factor.name == "Renewable Share Growth"
        assert factor.domain == "energy"
        assert factor.primary_entities == UK_ENERGY_ENTITIES

    def test_get_formula(self, factor):
        """Test factor returns LaTeX formula."""
        formula = factor.get_formula()
        assert r"\text{RSG}" in formula
        assert r"\bar{R}" in formula

    def test_get_economic_rationale(self, factor):
        """Test factor returns economic rationale."""
        rationale = factor.get_economic_rationale()
        assert "renewable" in rationale.lower()
        assert len(rationale) > 100

    @pytest.mark.asyncio
    async def test_compute_renewable_share_change(self, factor):
        """Test renewable share change calculation."""
        as_of_date = date(2024, 2, 15)

        with patch.object(factor, '_get_average_renewable_pct') as mock_avg:
            with patch.object(factor, '_get_renewable_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    # Current: 45%, Prior: 40% => +5 percentage points
                    mock_avg.side_effect = [45.0, 40.0]
                    mock_var.return_value = 25.0
                    mock_quality.return_value = Decimal("0.90")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(as_of_date)

        assert len(results) == 2
        # Change is in percentage points, not percentage
        expected_change = Decimal("5.0")
        assert results[0].mean == expected_change

    @pytest.mark.asyncio
    async def test_compute_negative_growth(self, factor):
        """Test computation with declining renewable share."""
        as_of_date = date(2024, 2, 15)

        with patch.object(factor, '_get_average_renewable_pct') as mock_avg:
            with patch.object(factor, '_get_renewable_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    # Current: 38%, Prior: 42% => -4 percentage points
                    mock_avg.side_effect = [38.0, 42.0]
                    mock_var.return_value = 20.0
                    mock_quality.return_value = Decimal("0.95")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(as_of_date)

        expected_change = Decimal("-4.0")
        assert results[0].mean == expected_change

    @pytest.mark.asyncio
    async def test_compute_insufficient_data(self, factor):
        """Test computation returns empty list with insufficient data."""
        as_of_date = date(2024, 2, 15)

        with patch.object(factor, '_get_average_renewable_pct') as mock_avg:
            mock_avg.side_effect = [45.0, None]  # No prior month data

            with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                mock_session.return_value.__aexit__ = AsyncMock()

                results = await factor.compute(as_of_date)

        assert len(results) == 0


class TestFactorFactoryFunctions:
    """Test factory functions for creating factors."""

    def test_create_carbon_intensity_trend(self):
        """Test factory creates CarbonIntensityTrend."""
        factor = create_carbon_intensity_trend()
        assert isinstance(factor, CarbonIntensityTrend)
        assert factor.factor_id == "carbon_intensity_mom"

    def test_create_renewable_share_growth(self):
        """Test factory creates RenewableShareGrowth."""
        factor = create_renewable_share_growth()
        assert isinstance(factor, RenewableShareGrowth)
        assert factor.factor_id == "renewable_share_growth"


class TestCarbonFactorsRegistry:
    """Test the carbon factors registry."""

    def test_registry_contains_both_factors(self):
        """Test registry contains both factor types."""
        assert "carbon_intensity_mom" in CARBON_FACTORS
        assert "renewable_share_growth" in CARBON_FACTORS

    def test_registry_classes_are_correct(self):
        """Test registry maps to correct classes."""
        assert CARBON_FACTORS["carbon_intensity_mom"] == CarbonIntensityTrend
        assert CARBON_FACTORS["renewable_share_growth"] == RenewableShareGrowth


class TestUKEnergyEntities:
    """Test UK energy entity constants."""

    def test_primary_entities(self):
        """Test primary entities list."""
        assert "NG.L" in UK_ENERGY_ENTITIES
        assert "SSE.L" in UK_ENERGY_ENTITIES
        assert len(UK_ENERGY_ENTITIES) == 2


class TestFactorInputValidation:
    """Test factor input validation."""

    @pytest.fixture
    def intensity_factor(self):
        """Create intensity factor."""
        return CarbonIntensityTrend()

    @pytest.fixture
    def renewable_factor(self):
        """Create renewable factor."""
        return RenewableShareGrowth()

    @pytest.mark.asyncio
    async def test_validate_future_date(self, intensity_factor):
        """Test validation rejects future dates."""
        future_date = date.today() + timedelta(days=30)
        is_valid = await intensity_factor.validate_inputs(future_date)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_past_date(self, intensity_factor):
        """Test validation accepts past dates."""
        past_date = date(2024, 1, 15)
        is_valid = await intensity_factor.validate_inputs(past_date)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_today(self, renewable_factor):
        """Test validation accepts today's date."""
        today = date.today()
        is_valid = await renewable_factor.validate_inputs(today)
        assert is_valid is True


class TestFactorDataQuality:
    """Test data quality calculations."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return CarbonIntensityTrend()

    @pytest.mark.asyncio
    async def test_data_quality_full_coverage(self, factor):
        """Test data quality with full data coverage."""
        # Mock full coverage scenario
        with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_session.return_value.__aexit__ = AsyncMock()

            # Simulate 10 days with 48 readings per day (480 total)
            result = MagicMock()
            result.scalar.return_value = 480
            mock_ctx.execute = AsyncMock(return_value=result)

            quality = await factor._calculate_data_quality(
                mock_ctx,
                "national",
                date(2024, 1, 1),
                date(2024, 1, 10)
            )

        # With full coverage, quality should be 1.0
        assert quality == Decimal("1.0")


class TestFactorResultStructure:
    """Test factor result structure and content."""

    @pytest.fixture
    def sample_result(self):
        """Create a sample factor result."""
        return FactorResult(
            ticker="NG.L",
            factor_id="carbon_intensity_mom",
            as_of_date=date(2024, 2, 15),
            mean=Decimal("-5.5"),
            variance=Decimal("100.25"),
            data_quality=Decimal("0.95"),
            revision_status="original",
            metadata={
                "region": "national",
                "current_month_avg": 195.5,
                "prior_month_avg": 207.0
            }
        )

    def test_result_has_required_fields(self, sample_result):
        """Test result has all required fields."""
        assert sample_result.ticker is not None
        assert sample_result.factor_id is not None
        assert sample_result.as_of_date is not None
        assert sample_result.mean is not None
        assert sample_result.variance is not None

    def test_result_mean_is_decimal(self, sample_result):
        """Test mean is a Decimal type."""
        assert isinstance(sample_result.mean, Decimal)

    def test_result_variance_is_decimal(self, sample_result):
        """Test variance is a Decimal type."""
        assert isinstance(sample_result.variance, Decimal)

    def test_result_data_quality_in_range(self, sample_result):
        """Test data quality is in valid range (0-1)."""
        assert Decimal("0") <= sample_result.data_quality <= Decimal("1")

    def test_result_metadata_structure(self, sample_result):
        """Test metadata contains expected information."""
        assert "region" in sample_result.metadata
        assert sample_result.metadata["region"] == "national"


class TestMonthBoundaryCalculations:
    """Test month boundary calculations for factors."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return CarbonIntensityTrend()

    @pytest.mark.asyncio
    async def test_month_boundaries_mid_month(self, factor):
        """Test month boundaries calculated correctly for mid-month date."""
        as_of_date = date(2024, 2, 15)

        # Current month should be Feb 1 - Feb 15
        # Prior month should be Jan 1 - Jan 31

        with patch.object(factor, '_get_average_intensity') as mock_avg:
            with patch.object(factor, '_get_intensity_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    mock_avg.side_effect = [200.0, 220.0]
                    mock_var.return_value = 50.0
                    mock_quality.return_value = Decimal("0.95")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(as_of_date)

        # Check metadata has correct month boundaries
        metadata = results[0].metadata
        assert metadata["current_month_start"] == "2024-02-01"
        assert metadata["prior_month_start"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_year_boundary_handling(self, factor):
        """Test January correctly references December of previous year."""
        as_of_date = date(2024, 1, 15)

        with patch.object(factor, '_get_average_intensity') as mock_avg:
            with patch.object(factor, '_get_intensity_variance') as mock_var:
                with patch.object(factor, '_calculate_data_quality') as mock_quality:
                    mock_avg.side_effect = [200.0, 220.0]
                    mock_var.return_value = 50.0
                    mock_quality.return_value = Decimal("0.95")

                    with patch('src.transformations.factors.carbon_factors.get_async_session') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                        mock_session.return_value.__aexit__ = AsyncMock()

                        results = await factor.compute(as_of_date)

        # Check metadata has correct year boundary
        metadata = results[0].metadata
        assert metadata["current_month_start"] == "2024-01-01"
        assert metadata["prior_month_start"] == "2023-12-01"
