"""Tests for rental market factors."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.transformations.factors.rental_factors import (
    RentInflationIndex,
    SFRMultifamilySpread,
)
from src.transformations.factors.base import FactorResult
from src.models.data_sources import ZillowRentalIndex


@pytest.fixture
def rent_inflation_factor():
    """Create RentInflationIndex instance."""
    return RentInflationIndex()


@pytest.fixture
def sfr_mf_spread_factor():
    """Create SFRMultifamilySpread instance."""
    return SFRMultifamilySpread()


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def sample_zillow_records():
    """Sample ZillowRentalIndex records for testing."""
    return [
        # National all properties
        {
            "period": date(2024, 1, 1),
            "geography_level": "national",
            "geography_id": "US",
            "geography_name": "United States",
            "property_type": "all",
            "zori_value": Decimal("2000.00"),
            "mom_change_pct": Decimal("0.5"),
            "yoy_change_pct": Decimal("5.0"),
        },
        # National single family
        {
            "period": date(2024, 1, 1),
            "geography_level": "national",
            "geography_id": "US",
            "geography_name": "United States",
            "property_type": "single_family",
            "zori_value": Decimal("2400.00"),
            "mom_change_pct": Decimal("0.6"),
            "yoy_change_pct": Decimal("6.0"),
        },
        # National multi family
        {
            "period": date(2024, 1, 1),
            "geography_level": "national",
            "geography_id": "US",
            "geography_name": "United States",
            "property_type": "multi_family",
            "zori_value": Decimal("1800.00"),
            "mom_change_pct": Decimal("0.4"),
            "yoy_change_pct": Decimal("4.0"),
        },
    ]


class TestRentInflationIndexInit:
    """Tests for RentInflationIndex initialization."""

    def test_factor_id(self, rent_inflation_factor):
        """Test factor has correct ID."""
        assert rent_inflation_factor.factor_id == "rent_inflation_index"

    def test_factor_name(self, rent_inflation_factor):
        """Test factor has correct name."""
        assert rent_inflation_factor.name == "Rent Inflation Index"

    def test_factor_domain(self, rent_inflation_factor):
        """Test factor is in real_estate domain."""
        assert rent_inflation_factor.domain == "real_estate"

    def test_primary_entities(self, rent_inflation_factor):
        """Test factor has correct primary entities."""
        expected_entities = ["EQR", "AVB", "MAA", "INVH", "AMH"]
        assert rent_inflation_factor.primary_entities == expected_entities

    def test_get_formula(self, rent_inflation_factor):
        """Test formula is defined."""
        formula = rent_inflation_factor.get_formula()
        assert "ZORI" in formula
        assert "frac" in formula  # LaTeX fraction

    def test_get_economic_rationale(self, rent_inflation_factor):
        """Test economic rationale is defined."""
        rationale = rent_inflation_factor.get_economic_rationale()
        assert "CPI" in rationale
        assert "shelter" in rationale.lower() or "Shelter" in rationale


class TestRentInflationIndexCompute:
    """Tests for RentInflationIndex computation."""

    @pytest.mark.asyncio
    async def test_compute_returns_factor_results(self, rent_inflation_factor):
        """Test compute returns list of FactorResult."""
        mock_record = MagicMock()
        mock_record.yoy_change_pct = Decimal("5.0")
        mock_record.zori_value = Decimal("2000.00")
        mock_record.mom_change_pct = Decimal("0.5")
        mock_record.period = date(2024, 1, 1)
        mock_record.geography_level = "national"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            results = await rent_inflation_factor.compute(
                as_of_date=date(2024, 1, 15),
            )

            assert len(results) == 5  # All primary entities
            assert all(isinstance(r, FactorResult) for r in results)

    @pytest.mark.asyncio
    async def test_compute_calculates_correct_factor_value(self, rent_inflation_factor):
        """Test factor value is YoY change divided by 100."""
        yoy_pct = Decimal("5.0")
        expected_factor = yoy_pct / Decimal("100")  # 0.05

        mock_record = MagicMock()
        mock_record.yoy_change_pct = yoy_pct
        mock_record.zori_value = Decimal("2000.00")
        mock_record.mom_change_pct = Decimal("0.5")
        mock_record.period = date(2024, 1, 1)
        mock_record.geography_level = "national"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            results = await rent_inflation_factor.compute(
                as_of_date=date(2024, 1, 15),
            )

            for result in results:
                assert result.mean == expected_factor

    @pytest.mark.asyncio
    async def test_compute_returns_empty_on_no_data(self, rent_inflation_factor):
        """Test compute returns empty list when no data available."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            results = await rent_inflation_factor.compute(
                as_of_date=date(2024, 1, 15),
            )

            assert results == []

    @pytest.mark.asyncio
    async def test_compute_specific_tickers(self, rent_inflation_factor):
        """Test compute only for specific tickers."""
        mock_record = MagicMock()
        mock_record.yoy_change_pct = Decimal("5.0")
        mock_record.zori_value = Decimal("2000.00")
        mock_record.mom_change_pct = Decimal("0.5")
        mock_record.period = date(2024, 1, 1)
        mock_record.geography_level = "national"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            results = await rent_inflation_factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["EQR", "AVB"],
            )

            assert len(results) == 2
            tickers = {r.ticker for r in results}
            assert tickers == {"EQR", "AVB"}

    @pytest.mark.asyncio
    async def test_compute_includes_metadata(self, rent_inflation_factor):
        """Test factor results include metadata."""
        mock_record = MagicMock()
        mock_record.yoy_change_pct = Decimal("5.0")
        mock_record.zori_value = Decimal("2000.00")
        mock_record.mom_change_pct = Decimal("0.5")
        mock_record.period = date(2024, 1, 1)
        mock_record.geography_level = "national"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            results = await rent_inflation_factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["EQR"],
            )

            assert len(results) == 1
            metadata = results[0].metadata
            assert "zori_value" in metadata
            assert "yoy_change_pct" in metadata
            assert "period" in metadata


class TestSFRMultifamilySpreadInit:
    """Tests for SFRMultifamilySpread initialization."""

    def test_factor_id(self, sfr_mf_spread_factor):
        """Test factor has correct ID."""
        assert sfr_mf_spread_factor.factor_id == "sfr_multifamily_spread"

    def test_factor_name(self, sfr_mf_spread_factor):
        """Test factor has correct name."""
        assert sfr_mf_spread_factor.name == "SFR-Multifamily Spread"

    def test_factor_domain(self, sfr_mf_spread_factor):
        """Test factor is in real_estate domain."""
        assert sfr_mf_spread_factor.domain == "real_estate"

    def test_primary_entities(self, sfr_mf_spread_factor):
        """Test factor has correct primary entities."""
        expected_entities = ["EQR", "AVB", "MAA", "INVH", "AMH"]
        assert sfr_mf_spread_factor.primary_entities == expected_entities

    def test_factor_loadings_defined(self, sfr_mf_spread_factor):
        """Test factor loadings are defined for all primary entities."""
        for entity in sfr_mf_spread_factor.primary_entities:
            assert entity in sfr_mf_spread_factor.FACTOR_LOADINGS

    def test_sfr_reits_have_positive_loading(self, sfr_mf_spread_factor):
        """Test SFR REITs have positive factor loadings."""
        assert sfr_mf_spread_factor.FACTOR_LOADINGS["INVH"] > 0
        assert sfr_mf_spread_factor.FACTOR_LOADINGS["AMH"] > 0

    def test_mf_reits_have_negative_loading(self, sfr_mf_spread_factor):
        """Test MF REITs have negative factor loadings."""
        assert sfr_mf_spread_factor.FACTOR_LOADINGS["EQR"] < 0
        assert sfr_mf_spread_factor.FACTOR_LOADINGS["AVB"] < 0

    def test_get_formula(self, sfr_mf_spread_factor):
        """Test formula is defined."""
        formula = sfr_mf_spread_factor.get_formula()
        assert "ZORI" in formula
        assert "SFR" in formula
        assert "MF" in formula

    def test_get_economic_rationale(self, sfr_mf_spread_factor):
        """Test economic rationale is defined."""
        rationale = sfr_mf_spread_factor.get_economic_rationale()
        assert "single-family" in rationale.lower() or "SFR" in rationale
        assert "apartment" in rationale.lower() or "multifamily" in rationale.lower()


class TestSFRMultifamilySpreadCompute:
    """Tests for SFRMultifamilySpread computation."""

    @pytest.mark.asyncio
    async def test_compute_returns_factor_results(self, sfr_mf_spread_factor):
        """Test compute returns list of FactorResult."""
        # Create mock records for SFR and MF
        mock_sfr_record = MagicMock()
        mock_sfr_record.zori_value = Decimal("2400.00")
        mock_sfr_record.mom_change_pct = Decimal("0.6")
        mock_sfr_record.yoy_change_pct = Decimal("6.0")

        mock_mf_record = MagicMock()
        mock_mf_record.zori_value = Decimal("1800.00")
        mock_mf_record.mom_change_pct = Decimal("0.4")
        mock_mf_record.yoy_change_pct = Decimal("4.0")

        async def mock_get_zori(session, period, prop_type):
            if prop_type == "single_family":
                return mock_sfr_record
            return mock_mf_record

        mock_session = AsyncMock()
        # Mock execute for variance calculation
        mock_variance_result = MagicMock()
        mock_variance_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_variance_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            with patch.object(
                sfr_mf_spread_factor,
                "_get_zori_record",
                side_effect=mock_get_zori,
            ):
                results = await sfr_mf_spread_factor.compute(
                    as_of_date=date(2024, 1, 15),
                )

                assert len(results) == 5  # All primary entities
                assert all(isinstance(r, FactorResult) for r in results)

    @pytest.mark.asyncio
    async def test_compute_calculates_correct_spread(self, sfr_mf_spread_factor):
        """Test spread calculation is correct."""
        sfr_value = Decimal("2400.00")
        mf_value = Decimal("1800.00")
        expected_spread = (sfr_value - mf_value) / mf_value  # 0.333...

        mock_sfr_record = MagicMock()
        mock_sfr_record.zori_value = sfr_value
        mock_sfr_record.mom_change_pct = Decimal("0.6")
        mock_sfr_record.yoy_change_pct = Decimal("6.0")

        mock_mf_record = MagicMock()
        mock_mf_record.zori_value = mf_value
        mock_mf_record.mom_change_pct = Decimal("0.4")
        mock_mf_record.yoy_change_pct = Decimal("4.0")

        async def mock_get_zori(session, period, prop_type):
            if prop_type == "single_family":
                return mock_sfr_record
            return mock_mf_record

        mock_session = AsyncMock()
        mock_variance_result = MagicMock()
        mock_variance_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_variance_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            with patch.object(
                sfr_mf_spread_factor,
                "_get_zori_record",
                side_effect=mock_get_zori,
            ):
                results = await sfr_mf_spread_factor.compute(
                    as_of_date=date(2024, 1, 15),
                    tickers=["INVH"],  # Loading = 1.0
                )

                assert len(results) == 1
                # Factor value = spread * loading
                # INVH has loading of 1.0, so factor = spread
                assert abs(results[0].mean - expected_spread) < Decimal("0.001")

    @pytest.mark.asyncio
    async def test_compute_applies_factor_loadings(self, sfr_mf_spread_factor):
        """Test factor loadings are correctly applied."""
        sfr_value = Decimal("2400.00")
        mf_value = Decimal("2000.00")
        spread = (sfr_value - mf_value) / mf_value  # 0.2

        mock_sfr_record = MagicMock()
        mock_sfr_record.zori_value = sfr_value
        mock_sfr_record.mom_change_pct = None
        mock_sfr_record.yoy_change_pct = None

        mock_mf_record = MagicMock()
        mock_mf_record.zori_value = mf_value
        mock_mf_record.mom_change_pct = None
        mock_mf_record.yoy_change_pct = None

        async def mock_get_zori(session, period, prop_type):
            if prop_type == "single_family":
                return mock_sfr_record
            return mock_mf_record

        mock_session = AsyncMock()
        mock_variance_result = MagicMock()
        mock_variance_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_variance_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            with patch.object(
                sfr_mf_spread_factor,
                "_get_zori_record",
                side_effect=mock_get_zori,
            ):
                results = await sfr_mf_spread_factor.compute(
                    as_of_date=date(2024, 1, 15),
                )

                results_by_ticker = {r.ticker: r for r in results}

                # INVH: loading = 1.0, factor = 0.2 * 1.0 = 0.2
                invh_factor = results_by_ticker["INVH"].mean
                assert abs(invh_factor - spread * Decimal("1.0")) < Decimal("0.001")

                # EQR: loading = -0.5, factor = 0.2 * -0.5 = -0.1
                eqr_factor = results_by_ticker["EQR"].mean
                assert abs(eqr_factor - spread * Decimal("-0.5")) < Decimal("0.001")

    @pytest.mark.asyncio
    async def test_compute_returns_empty_on_missing_sfr(self, sfr_mf_spread_factor):
        """Test compute returns empty list when SFR data missing."""
        mock_mf_record = MagicMock()
        mock_mf_record.zori_value = Decimal("1800.00")

        async def mock_get_zori(session, period, prop_type):
            if prop_type == "single_family":
                return None
            return mock_mf_record

        mock_session = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            with patch.object(
                sfr_mf_spread_factor,
                "_get_zori_record",
                side_effect=mock_get_zori,
            ):
                results = await sfr_mf_spread_factor.compute(
                    as_of_date=date(2024, 1, 15),
                )

                assert results == []

    @pytest.mark.asyncio
    async def test_compute_returns_empty_on_missing_mf(self, sfr_mf_spread_factor):
        """Test compute returns empty list when MF data missing."""
        mock_sfr_record = MagicMock()
        mock_sfr_record.zori_value = Decimal("2400.00")

        async def mock_get_zori(session, period, prop_type):
            if prop_type == "single_family":
                return mock_sfr_record
            return None

        mock_session = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            with patch.object(
                sfr_mf_spread_factor,
                "_get_zori_record",
                side_effect=mock_get_zori,
            ):
                results = await sfr_mf_spread_factor.compute(
                    as_of_date=date(2024, 1, 15),
                )

                assert results == []

    @pytest.mark.asyncio
    async def test_compute_includes_metadata(self, sfr_mf_spread_factor):
        """Test factor results include correct metadata."""
        sfr_value = Decimal("2400.00")
        mf_value = Decimal("1800.00")

        mock_sfr_record = MagicMock()
        mock_sfr_record.zori_value = sfr_value
        mock_sfr_record.mom_change_pct = None
        mock_sfr_record.yoy_change_pct = None

        mock_mf_record = MagicMock()
        mock_mf_record.zori_value = mf_value
        mock_mf_record.mom_change_pct = None
        mock_mf_record.yoy_change_pct = None

        async def mock_get_zori(session, period, prop_type):
            if prop_type == "single_family":
                return mock_sfr_record
            return mock_mf_record

        mock_session = AsyncMock()
        mock_variance_result = MagicMock()
        mock_variance_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_variance_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.transformations.factors.rental_factors.get_async_session",
            return_value=mock_ctx,
        ):
            with patch.object(
                sfr_mf_spread_factor,
                "_get_zori_record",
                side_effect=mock_get_zori,
            ):
                results = await sfr_mf_spread_factor.compute(
                    as_of_date=date(2024, 1, 15),
                    tickers=["INVH"],
                )

                assert len(results) == 1
                metadata = results[0].metadata
                assert "sfr_zori" in metadata
                assert "mf_zori" in metadata
                assert "raw_spread" in metadata
                assert "factor_loading" in metadata
                assert metadata["sfr_zori"] == float(sfr_value)
                assert metadata["mf_zori"] == float(mf_value)


class TestFactorValidation:
    """Tests for factor validation."""

    @pytest.mark.asyncio
    async def test_validate_inputs_rejects_future_date(self, rent_inflation_factor):
        """Test validation rejects future dates."""
        future_date = date(2030, 1, 1)
        result = await rent_inflation_factor.validate_inputs(future_date)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_inputs_accepts_past_date(self, rent_inflation_factor):
        """Test validation accepts past dates."""
        past_date = date(2024, 1, 1)
        result = await rent_inflation_factor.validate_inputs(past_date)
        assert result is True


class TestDataQuality:
    """Tests for data quality calculations."""

    def test_data_quality_full_data(self, rent_inflation_factor):
        """Test data quality is 1.0 for complete records."""
        mock_record = MagicMock()
        mock_record.mom_change_pct = Decimal("0.5")
        mock_record.yoy_change_pct = Decimal("5.0")

        quality = rent_inflation_factor._calculate_data_quality(mock_record)
        assert quality == Decimal("1.0")

    def test_data_quality_missing_mom(self, rent_inflation_factor):
        """Test data quality reduced when MoM missing."""
        mock_record = MagicMock()
        mock_record.mom_change_pct = None
        mock_record.yoy_change_pct = Decimal("5.0")

        quality = rent_inflation_factor._calculate_data_quality(mock_record)
        assert quality < Decimal("1.0")
        assert quality >= Decimal("0.5")

    def test_data_quality_missing_yoy(self, rent_inflation_factor):
        """Test data quality reduced when YoY missing."""
        mock_record = MagicMock()
        mock_record.mom_change_pct = Decimal("0.5")
        mock_record.yoy_change_pct = None

        quality = rent_inflation_factor._calculate_data_quality(mock_record)
        assert quality < Decimal("1.0")
        assert quality >= Decimal("0.5")

    def test_data_quality_minimum_threshold(self, rent_inflation_factor):
        """Test data quality has minimum threshold."""
        mock_record = MagicMock()
        mock_record.mom_change_pct = None
        mock_record.yoy_change_pct = None

        quality = rent_inflation_factor._calculate_data_quality(mock_record)
        assert quality >= Decimal("0.5")
