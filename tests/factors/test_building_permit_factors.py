"""Tests for building permit factors."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.transformations.factors.building_permit_factors import (
    PermitMomentumFactor,
    PermitToStartRatioFactor,
    RenovationShareIndexFactor,
    PRIMARY_ENTITIES,
)
from src.transformations.factors.base import FactorResult
from src.models.data_sources import BuildingPermitData


class TestPermitMomentumFactor:
    """Tests for PermitMomentumFactor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return PermitMomentumFactor()

    def test_factor_metadata(self, factor):
        """Test factor metadata is correctly set."""
        assert factor.factor_id == "permit_momentum"
        assert factor.name == "Building Permit Momentum"
        assert factor.domain == "real_estate"
        assert set(factor.primary_entities) == set(PRIMARY_ENTITIES)

    def test_get_formula(self, factor):
        """Test LaTeX formula is returned."""
        formula = factor.get_formula()
        assert "PermitMomentum" in formula
        assert "Permits" in formula
        assert "frac" in formula  # LaTeX fraction

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()
        assert len(rationale) > 100  # Substantive explanation
        assert "leading indicator" in rationale.lower()
        assert "homebuilder" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_returns_results_for_all_tickers(self, factor, db_session):
        """Test compute returns results for all primary entities."""
        current_period = date(2024, 1, 1)
        prev_period = date(2023, 12, 1)

        # Create mock permit data
        current_data = BuildingPermitData(
            id=1,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1500000,
            seasonally_adjusted=True,
        )

        prev_data = BuildingPermitData(
            id=2,
            period=prev_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1400000,
            seasonally_adjusted=True,
        )

        # Mock the database session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_current_result = MagicMock()
        mock_current_result.scalar_one_or_none.return_value = current_data
        mock_prev_result = MagicMock()
        mock_prev_result.scalar_one_or_none.return_value = prev_data

        # Setup execute to return different results for different queries
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_current_result
            elif call_count == 2:
                return mock_prev_result
            else:
                # For variance calculation
                mock_variance_result = MagicMock()
                mock_variance_result.scalars.return_value.all.return_value = []
                return mock_variance_result

        mock_session.execute = mock_execute

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(as_of_date=current_period)

            # Should have results for all primary entities
            assert len(results) == len(PRIMARY_ENTITIES)

            # Check all tickers are present
            result_tickers = {r.ticker for r in results}
            assert result_tickers == set(PRIMARY_ENTITIES)

    @pytest.mark.asyncio
    async def test_compute_calculates_correct_momentum(self, factor):
        """Test momentum calculation is correct."""
        current_period = date(2024, 1, 1)
        prev_period = date(2023, 12, 1)

        current_data = BuildingPermitData(
            id=1,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1100000,  # 10% increase
            seasonally_adjusted=True,
        )

        prev_data = BuildingPermitData(
            id=2,
            period=prev_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1000000,
            seasonally_adjusted=True,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = current_data
            elif call_count == 2:
                result.scalar_one_or_none.return_value = prev_data
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_session.execute = mock_execute

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(
                as_of_date=current_period,
                tickers=["DHI"],
            )

            assert len(results) == 1
            # (1100000 - 1000000) / 1000000 = 0.1
            assert float(results[0].mean) == pytest.approx(0.1, rel=0.01)

    @pytest.mark.asyncio
    async def test_compute_returns_empty_on_missing_data(self, factor):
        """Test compute returns empty list when data is missing."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(as_of_date=date(2024, 1, 1))

            assert len(results) == 0


class TestPermitToStartRatioFactor:
    """Tests for PermitToStartRatioFactor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return PermitToStartRatioFactor()

    def test_factor_metadata(self, factor):
        """Test factor metadata is correctly set."""
        assert factor.factor_id == "permit_to_start_ratio"
        assert factor.name == "Permit to Start Ratio"
        assert factor.domain == "real_estate"

    def test_get_formula(self, factor):
        """Test LaTeX formula is returned."""
        formula = factor.get_formula()
        assert "PermitToStartRatio" in formula
        assert "HousingStarts" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()
        assert "pipeline" in rationale.lower()
        assert "backlog" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_calculates_correct_ratio(self, factor):
        """Test ratio calculation is correct."""
        current_period = date(2024, 1, 1)

        permit_data = BuildingPermitData(
            id=1,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1500000,
            seasonally_adjusted=True,
        )

        starts_data = BuildingPermitData(
            id=2,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="housing_starts",
            units_authorized=1400000,
            seasonally_adjusted=True,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = permit_data
            else:
                result.scalar_one_or_none.return_value = starts_data
            return result

        mock_session.execute = mock_execute

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(
                as_of_date=current_period,
                tickers=["DHI"],
            )

            assert len(results) == 1
            # 1500000 / 1400000 = 1.0714...
            expected_ratio = 1500000 / 1400000
            assert float(results[0].mean) == pytest.approx(expected_ratio, rel=0.01)


class TestRenovationShareIndexFactor:
    """Tests for RenovationShareIndexFactor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return RenovationShareIndexFactor()

    def test_factor_metadata(self, factor):
        """Test factor metadata is correctly set."""
        assert factor.factor_id == "renovation_share_index"
        assert factor.name == "Renovation Share Index"
        assert factor.domain == "real_estate"

    def test_get_formula(self, factor):
        """Test LaTeX formula is returned."""
        formula = factor.get_formula()
        assert "RenovationShareIndex" in formula
        assert "SingleFamily" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()
        assert "renovation" in rationale.lower()
        assert "home improvement" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_calculates_correct_index(self, factor):
        """Test index calculation is correct."""
        current_period = date(2024, 1, 1)

        sf_data = BuildingPermitData(
            id=1,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="single_family",
            units_authorized=1000000,
            seasonally_adjusted=True,
        )

        mf_data = BuildingPermitData(
            id=2,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="multi_family_5plus",
            units_authorized=400000,
            seasonally_adjusted=True,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = sf_data
            else:
                result.scalar_one_or_none.return_value = mf_data
            return result

        mock_session.execute = mock_execute

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(
                as_of_date=current_period,
                tickers=["HD"],  # Home improvement
            )

            assert len(results) == 1
            # 400000 / 1000000 = 0.4
            assert float(results[0].mean) == pytest.approx(0.4, rel=0.01)

    @pytest.mark.asyncio
    async def test_metadata_includes_interpretation(self, factor):
        """Test result metadata includes interpretation for different ticker types."""
        current_period = date(2024, 1, 1)

        sf_data = BuildingPermitData(
            id=1,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="single_family",
            units_authorized=1000000,
            seasonally_adjusted=True,
        )

        mf_data = BuildingPermitData(
            id=2,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="multi_family_5plus",
            units_authorized=400000,
            seasonally_adjusted=True,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = sf_data
            else:
                result.scalar_one_or_none.return_value = mf_data
            return result

        mock_session.execute = mock_execute

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(
                as_of_date=current_period,
                tickers=["HD", "DHI"],  # Home improvement and homebuilder
            )

            assert len(results) == 2

            hd_result = next(r for r in results if r.ticker == "HD")
            dhi_result = next(r for r in results if r.ticker == "DHI")

            # HD (home improvement) should have positive interpretation
            assert hd_result.metadata["interpretation"] == "positive"
            # DHI (homebuilder) should have negative interpretation
            assert dhi_result.metadata["interpretation"] == "negative"


class TestFactorValidation:
    """Tests for factor input validation."""

    @pytest.mark.asyncio
    async def test_validate_future_date(self):
        """Test validation fails for future dates."""
        factor = PermitMomentumFactor()
        future_date = date(2099, 1, 1)

        is_valid = await factor.validate_inputs(as_of_date=future_date)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_past_date(self):
        """Test validation passes for past dates."""
        factor = PermitMomentumFactor()
        past_date = date(2023, 6, 15)

        is_valid = await factor.validate_inputs(as_of_date=past_date)
        assert is_valid is True


class TestFactorResultStructure:
    """Tests for FactorResult data structure."""

    def test_factor_result_has_required_fields(self):
        """Test FactorResult has all required fields."""
        result = FactorResult(
            ticker="DHI",
            factor_id="permit_momentum",
            as_of_date=date(2024, 1, 1),
            mean=Decimal("0.05"),
            variance=Decimal("0.001"),
        )

        assert result.ticker == "DHI"
        assert result.factor_id == "permit_momentum"
        assert result.as_of_date == date(2024, 1, 1)
        assert result.mean == Decimal("0.05")
        assert result.variance == Decimal("0.001")
        assert result.data_quality == Decimal("1.0")  # Default
        assert result.revision_status == "original"  # Default

    def test_factor_result_with_metadata(self):
        """Test FactorResult with custom metadata."""
        result = FactorResult(
            ticker="HD",
            factor_id="renovation_share_index",
            as_of_date=date(2024, 1, 1),
            mean=Decimal("0.4"),
            variance=Decimal("0.008"),
            metadata={
                "single_family_permits": 1000000,
                "multi_family_permits": 400000,
                "interpretation": "positive",
            },
        )

        assert result.metadata["single_family_permits"] == 1000000
        assert result.metadata["interpretation"] == "positive"


class TestYoYMoMCalculations:
    """Tests for YoY and MoM calculation correctness."""

    @pytest.mark.asyncio
    async def test_mom_change_calculation(self):
        """Test MoM change is calculated correctly."""
        factor = PermitMomentumFactor()

        # January 2024: 1.5M permits
        # December 2023: 1.4M permits
        # MoM change: (1.5 - 1.4) / 1.4 = 7.14%

        current_period = date(2024, 1, 1)

        current_data = BuildingPermitData(
            id=1,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1500000,
            seasonally_adjusted=True,
        )

        prev_data = BuildingPermitData(
            id=2,
            period=date(2023, 12, 1),
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1400000,
            seasonally_adjusted=True,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = current_data
            elif call_count == 2:
                result.scalar_one_or_none.return_value = prev_data
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_session.execute = mock_execute

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(
                as_of_date=current_period,
                tickers=["DHI"],
            )

            expected_change = (1500000 - 1400000) / 1400000
            assert float(results[0].mean) == pytest.approx(expected_change, rel=0.01)

    @pytest.mark.asyncio
    async def test_negative_mom_change(self):
        """Test negative MoM change is calculated correctly."""
        factor = PermitMomentumFactor()

        current_period = date(2024, 1, 1)

        # Declining permits
        current_data = BuildingPermitData(
            id=1,
            period=current_period,
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1200000,  # Decreased
            seasonally_adjusted=True,
        )

        prev_data = BuildingPermitData(
            id=2,
            period=date(2023, 12, 1),
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1400000,
            seasonally_adjusted=True,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = current_data
            elif call_count == 2:
                result.scalar_one_or_none.return_value = prev_data
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_session.execute = mock_execute

        with patch(
            "src.transformations.factors.building_permit_factors.get_async_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            results = await factor.compute(
                as_of_date=current_period,
                tickers=["DHI"],
            )

            # (1200000 - 1400000) / 1400000 = -0.1429
            expected_change = (1200000 - 1400000) / 1400000
            assert float(results[0].mean) == pytest.approx(expected_change, rel=0.01)
            assert results[0].mean < 0  # Should be negative


class TestPrimaryEntities:
    """Tests for primary entity configuration."""

    def test_primary_entities_include_homebuilders(self):
        """Test primary entities include major homebuilders."""
        homebuilders = ["DHI", "LEN", "PHM"]
        for ticker in homebuilders:
            assert ticker in PRIMARY_ENTITIES

    def test_primary_entities_include_home_improvement(self):
        """Test primary entities include home improvement retailers."""
        home_improvement = ["HD", "LOW"]
        for ticker in home_improvement:
            assert ticker in PRIMARY_ENTITIES

    def test_all_factors_share_same_primary_entities(self):
        """Test all factors use the same primary entities."""
        momentum = PermitMomentumFactor()
        ratio = PermitToStartRatioFactor()
        renovation = RenovationShareIndexFactor()

        assert set(momentum.primary_entities) == set(PRIMARY_ENTITIES)
        assert set(ratio.primary_entities) == set(PRIMARY_ENTITIES)
        assert set(renovation.primary_entities) == set(PRIMARY_ENTITIES)
