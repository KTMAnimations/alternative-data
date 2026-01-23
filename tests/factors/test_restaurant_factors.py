"""Unit tests for restaurant sector factors."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.transformations.factors.restaurant_factors import (
    SeatedDinersMomentum,
    RegionalDiningSpread,
    RestaurantSectorHealth,
    get_restaurant_factors,
    PRIMARY_ENTITIES,
    EXPECTED_REGIONS,
)
from src.transformations.factors.base import FactorResult
from src.models.data_sources import OpenTableMetrics


class TestSeatedDinersMomentum:
    """Tests for the SeatedDinersMomentum factor."""

    @pytest.fixture
    def factor(self):
        """Create a factor instance."""
        return SeatedDinersMomentum(region="US")

    def test_factor_initialization(self, factor):
        """Test factor initializes with correct properties."""
        assert factor.factor_id == "seated_diners_momentum"
        assert factor.name == "Seated Diners Momentum"
        assert factor.domain == "restaurant"
        assert factor.region == "US"
        assert factor.primary_entities == PRIMARY_ENTITIES

    def test_factor_with_different_region(self):
        """Test factor can be initialized with different regions."""
        uk_factor = SeatedDinersMomentum(region="UK")
        assert uk_factor.region == "UK"

    def test_get_formula(self, factor):
        """Test LaTeX formula is returned."""
        formula = factor.get_formula()
        assert "WoW" in formula
        assert "YoY" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is returned."""
        rationale = factor.get_economic_rationale()
        assert len(rationale) > 100
        assert "momentum" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_returns_factor_results(self, factor, db_session):
        """Test compute returns FactorResult objects."""
        # Insert test data
        test_records = [
            OpenTableMetrics(
                week_ending=date(2024, 1, 8),
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("-20.0"),
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("-15.0"),
                wow_change_pct=Decimal("5.0"),  # -15 - (-20) = +5
                data_quality_score=Decimal("1.0"),
            ),
        ]

        for record in test_records:
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            assert len(results) == len(PRIMARY_ENTITIES)
            for result in results:
                assert isinstance(result, FactorResult)
                assert result.factor_id == "seated_diners_momentum"
                assert result.ticker in PRIMARY_ENTITIES
                assert result.mean == Decimal("5.0")

    @pytest.mark.asyncio
    async def test_compute_with_specific_tickers(self, factor, db_session):
        """Test compute with specific tickers."""
        test_record = OpenTableMetrics(
            week_ending=date(2024, 1, 15),
            region="US",
            city=None,
            yoy_seated_diners_pct=Decimal("-15.0"),
            wow_change_pct=Decimal("3.0"),
            data_quality_score=Decimal("1.0"),
        )
        db_session.add(test_record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DRI", "MCD"],
            )

            assert len(results) == 2
            assert all(r.ticker in ["DRI", "MCD"] for r in results)

    @pytest.mark.asyncio
    async def test_compute_no_data_returns_empty(self, factor, db_session):
        """Test compute returns empty list when no data available."""
        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            assert len(results) == 0


class TestRegionalDiningSpread:
    """Tests for the RegionalDiningSpread factor."""

    @pytest.fixture
    def factor(self):
        """Create a factor instance."""
        return RegionalDiningSpread()

    def test_factor_initialization(self, factor):
        """Test factor initializes with correct properties."""
        assert factor.factor_id == "regional_dining_spread"
        assert factor.name == "Regional Dining Spread"
        assert factor.domain == "restaurant"
        assert factor.primary_entities == PRIMARY_ENTITIES

    def test_get_formula(self, factor):
        """Test LaTeX formula is returned."""
        formula = factor.get_formula()
        assert "max" in formula.lower()
        assert "min" in formula.lower()

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is returned."""
        rationale = factor.get_economic_rationale()
        assert len(rationale) > 100
        assert "spread" in rationale.lower() or "dispersion" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_calculates_spread(self, factor, db_session):
        """Test compute calculates max-min spread correctly."""
        # Insert test data for multiple regions
        test_records = [
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("-10.0"),
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="UK",
                city=None,
                yoy_seated_diners_pct=Decimal("-25.0"),  # Min
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="Germany",
                city=None,
                yoy_seated_diners_pct=Decimal("-5.0"),  # Max
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="Australia",
                city=None,
                yoy_seated_diners_pct=Decimal("-15.0"),
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="Canada",
                city=None,
                yoy_seated_diners_pct=Decimal("-12.0"),
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
        ]

        for record in test_records:
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            assert len(results) == len(PRIMARY_ENTITIES)
            # Spread = max(-5) - min(-25) = -5 - (-25) = 20
            assert results[0].mean == Decimal("20.0")
            assert results[0].metadata["max_region"] == "Germany"
            assert results[0].metadata["min_region"] == "UK"

    @pytest.mark.asyncio
    async def test_compute_validates_yoy_range(self, factor, db_session):
        """Test that YoY values are within expected range."""
        # Insert data within valid range (-100 to +200)
        test_records = [
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("-90.0"),  # Near min valid
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
            OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region="UK",
                city=None,
                yoy_seated_diners_pct=Decimal("150.0"),  # Near max valid
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            ),
        ]

        for record in test_records:
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            # Spread = 150 - (-90) = 240
            assert len(results) > 0
            assert results[0].mean == Decimal("240.0")

    @pytest.mark.asyncio
    async def test_compute_all_regions_present(self, factor, db_session):
        """Test that all expected regions are processed."""
        # Insert data for all regions
        for i, region in enumerate(EXPECTED_REGIONS):
            record = OpenTableMetrics(
                week_ending=date(2024, 1, 15),
                region=region,
                city=None,
                yoy_seated_diners_pct=Decimal(str(-10 - i * 5)),
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            )
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            assert len(results) == len(PRIMARY_ENTITIES)


class TestRestaurantSectorHealth:
    """Tests for the RestaurantSectorHealth factor."""

    @pytest.fixture
    def factor(self):
        """Create a factor instance."""
        return RestaurantSectorHealth(region="US", rolling_weeks=4)

    def test_factor_initialization(self, factor):
        """Test factor initializes with correct properties."""
        assert factor.factor_id == "restaurant_sector_health"
        assert factor.name == "Restaurant Sector Health"
        assert factor.domain == "restaurant"
        assert factor.region == "US"
        assert factor.rolling_weeks == 4
        assert factor.primary_entities == PRIMARY_ENTITIES

    def test_factor_with_custom_rolling_weeks(self):
        """Test factor can be initialized with custom rolling weeks."""
        custom_factor = RestaurantSectorHealth(region="UK", rolling_weeks=8)
        assert custom_factor.region == "UK"
        assert custom_factor.rolling_weeks == 8

    def test_get_formula(self, factor):
        """Test LaTeX formula is returned."""
        formula = factor.get_formula()
        assert "Health" in formula
        assert "clamp" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is returned."""
        rationale = factor.get_economic_rationale()
        assert len(rationale) > 100
        assert "health" in rationale.lower() or "0-100" in rationale

    @pytest.mark.asyncio
    async def test_compute_health_score_scale(self, factor, db_session):
        """Test health score is on 0-100 scale."""
        # Insert 4 weeks of data with avg YoY = 0 (should give health = 50)
        for i in range(4):
            week = date(2024, 1, 15) - timedelta(weeks=i)
            record = OpenTableMetrics(
                week_ending=week,
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("0.0"),  # Flat YoY
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            )
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            assert len(results) == len(PRIMARY_ENTITIES)
            # Flat YoY (0%) should give health = 50
            assert results[0].mean == Decimal("50")

    @pytest.mark.asyncio
    async def test_compute_health_score_positive_yoy(self, factor, db_session):
        """Test health score with positive YoY."""
        # Insert 4 weeks of data with avg YoY = +50% (should give health = 75)
        for i in range(4):
            week = date(2024, 1, 15) - timedelta(weeks=i)
            record = OpenTableMetrics(
                week_ending=week,
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("50.0"),  # +50% YoY
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            )
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            # +50% YoY should give health = 50 + (50/2) = 75
            assert results[0].mean == Decimal("75")

    @pytest.mark.asyncio
    async def test_compute_health_score_negative_yoy(self, factor, db_session):
        """Test health score with negative YoY."""
        # Insert 4 weeks of data with avg YoY = -50% (should give health = 25)
        for i in range(4):
            week = date(2024, 1, 15) - timedelta(weeks=i)
            record = OpenTableMetrics(
                week_ending=week,
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("-50.0"),  # -50% YoY
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            )
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            # -50% YoY should give health = 50 + (-50/2) = 25
            assert results[0].mean == Decimal("25")

    @pytest.mark.asyncio
    async def test_compute_health_score_clamped(self, factor, db_session):
        """Test health score is clamped to [0, 100]."""
        # Insert 4 weeks of data with extreme YoY
        for i in range(4):
            week = date(2024, 1, 15) - timedelta(weeks=i)
            record = OpenTableMetrics(
                week_ending=week,
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("150.0"),  # +150% YoY
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            )
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            # +150% YoY would give 50 + 75 = 125, but clamped to 100
            assert results[0].mean == Decimal("100")

    @pytest.mark.asyncio
    async def test_compute_health_score_metadata(self, factor, db_session):
        """Test metadata is included in results."""
        for i in range(4):
            week = date(2024, 1, 15) - timedelta(weeks=i)
            record = OpenTableMetrics(
                week_ending=week,
                region="US",
                city=None,
                yoy_seated_diners_pct=Decimal("10.0"),
                wow_change_pct=None,
                data_quality_score=Decimal("1.0"),
            )
            db_session.add(record)
        await db_session.commit()

        with patch("src.transformations.factors.restaurant_factors.get_async_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_session.return_value.__aexit__ = AsyncMock()

            results = await factor.compute(as_of_date=date(2024, 1, 15))

            assert "region" in results[0].metadata
            assert "rolling_weeks" in results[0].metadata
            assert "rolling_avg_yoy" in results[0].metadata
            assert results[0].metadata["source"] == "opentable"


class TestGetRestaurantFactors:
    """Tests for the factory function."""

    def test_get_restaurant_factors_default(self):
        """Test factory returns all factors with default region."""
        factors = get_restaurant_factors()

        assert len(factors) == 3
        factor_ids = [f.factor_id for f in factors]
        assert "seated_diners_momentum" in factor_ids
        assert "regional_dining_spread" in factor_ids
        assert "restaurant_sector_health" in factor_ids

    def test_get_restaurant_factors_custom_region(self):
        """Test factory with custom region."""
        factors = get_restaurant_factors(region="UK")

        # Check regional factors use UK
        for factor in factors:
            if hasattr(factor, "region"):
                assert factor.region == "UK"

    def test_all_factors_have_required_methods(self):
        """Test all factors implement required methods."""
        factors = get_restaurant_factors()

        for factor in factors:
            # Check required attributes
            assert hasattr(factor, "factor_id")
            assert hasattr(factor, "name")
            assert hasattr(factor, "domain")
            assert hasattr(factor, "primary_entities")

            # Check required methods
            assert callable(getattr(factor, "compute", None))
            assert callable(getattr(factor, "get_formula", None))
            assert callable(getattr(factor, "get_economic_rationale", None))


class TestFactorInputValidation:
    """Tests for factor input validation."""

    @pytest.mark.asyncio
    async def test_validate_inputs_future_date(self):
        """Test validation rejects future dates."""
        factor = SeatedDinersMomentum()
        future_date = date.today() + timedelta(days=30)

        result = await factor.validate_inputs(future_date)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_inputs_past_date(self):
        """Test validation accepts past dates."""
        factor = SeatedDinersMomentum()
        past_date = date.today() - timedelta(days=30)

        result = await factor.validate_inputs(past_date)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_inputs_today(self):
        """Test validation accepts today's date."""
        factor = SeatedDinersMomentum()

        result = await factor.validate_inputs(date.today())
        assert result is True


# Fixtures for sample factor data
@pytest.fixture
def sample_opentable_metrics():
    """Sample OpenTable metrics for factor computation."""
    return [
        {
            "week_ending": date(2024, 1, 8),
            "region": "US",
            "yoy_seated_diners_pct": Decimal("-18.5"),
            "wow_change_pct": Decimal("-2.3"),
        },
        {
            "week_ending": date(2024, 1, 15),
            "region": "US",
            "yoy_seated_diners_pct": Decimal("-15.5"),
            "wow_change_pct": Decimal("3.0"),
        },
        {
            "week_ending": date(2024, 1, 22),
            "region": "US",
            "yoy_seated_diners_pct": Decimal("-12.0"),
            "wow_change_pct": Decimal("3.5"),
        },
        {
            "week_ending": date(2024, 1, 29),
            "region": "US",
            "yoy_seated_diners_pct": Decimal("-10.0"),
            "wow_change_pct": Decimal("2.0"),
        },
    ]
