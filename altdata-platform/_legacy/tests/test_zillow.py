"""Tests for Zillow rental data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.zillow_rental import ZillowRentalCollector
from src.models.zillow_rental import ZillowRentalIndex
from src.transformations.factors.zillow_factors import (
    calc_rent_inflation_index,
    calc_sfr_multifamily_spread,
    calc_rent_momentum,
    calc_rent_level,
    calc_regional_rent_dispersion,
    RentInflationIndex,
    SFRMultifamilySpread,
    RentMomentum,
    NationalRentLevel,
    RegionalRentDispersion,
    APARTMENT_REITS,
    SFR_REITS,
    HOMEBUILDERS,
)


# =============================================================================
# Zillow Model Tests
# =============================================================================

class TestZillowModels:
    """Test Zillow database models."""

    def test_zillow_rental_index_model(self):
        """Test ZillowRentalIndex model creation."""
        index = ZillowRentalIndex(
            period=date(2024, 6, 1),
            region_type="national",
            region_id="0",
            region_name="United States",
            state_code=None,
            property_type="all_homes",
            zori_value=2050.00,
            mom_change=0.5,
            yoy_change=5.2,
            median_listing_price=None,
            inventory_count=None,
        )
        assert index.period == date(2024, 6, 1)
        assert index.zori_value == 2050.00
        assert index.yoy_change == 5.2

    def test_zillow_rental_metro(self):
        """Test ZillowRentalIndex with metro data."""
        index = ZillowRentalIndex(
            period=date(2024, 6, 1),
            region_type="metro",
            region_id="394913",
            region_name="San Francisco, CA",
            state_code="CA",
            property_type="all_homes",
            zori_value=3200.00,
            mom_change=-0.3,
            yoy_change=2.1,
        )
        assert index.region_type == "metro"
        assert index.region_name == "San Francisco, CA"
        assert index.state_code == "CA"

    def test_zillow_rental_sfr(self):
        """Test ZillowRentalIndex with SFR property type."""
        index = ZillowRentalIndex(
            period=date(2024, 6, 1),
            region_type="national",
            property_type="sfr",
            zori_value=2350.00,
            yoy_change=6.5,
        )
        assert index.property_type == "sfr"
        assert index.zori_value == 2350.00


# =============================================================================
# Zillow Collector Tests
# =============================================================================

class TestZillowRentalCollector:
    """Test Zillow rental collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = ZillowRentalCollector()
        assert collector.SOURCE_NAME == "zillow_rental"

    def test_parse_returns_list(self):
        """Test parse returns list of records."""
        collector = ZillowRentalCollector()
        result = collector.parse({})
        assert isinstance(result, list)


# =============================================================================
# Zillow Factor Calculation Tests
# =============================================================================

class TestZillowFactorCalculations:
    """Test Zillow factor calculation functions."""

    @patch("src.transformations.factors.zillow_factors.SessionLocal")
    def test_calc_rent_inflation_index(self, mock_session_local):
        """Test rent inflation index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (5.2,)

        result = calc_rent_inflation_index(date(2024, 6, 15))

        assert result == 5.2
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.zillow_factors.SessionLocal")
    def test_calc_sfr_multifamily_spread(self, mock_session_local):
        """Test SFR/multifamily spread calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # SFR rent: 2350, All homes (includes MF): 2050
        # Spread = (2350 - 2050) / 2050 * 100 = 14.63%
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            (2350.0,),  # SFR
            (2050.0,),  # All homes
        ]

        result = calc_sfr_multifamily_spread(date(2024, 6, 15))

        assert result is not None
        assert abs(result - 14.63) < 0.1

    @patch("src.transformations.factors.zillow_factors.SessionLocal")
    def test_calc_rent_momentum(self, mock_session_local):
        """Test rent momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current: 2050, 3 months ago: 2000
        # Momentum = (2050 - 2000) / 2000 * 100 = 2.5%
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            (2050.0,),  # current
            (2000.0,),  # prior
        ]

        result = calc_rent_momentum(date(2024, 6, 15), lookback_months=3)

        assert result is not None
        assert abs(result - 2.5) < 0.1

    @patch("src.transformations.factors.zillow_factors.SessionLocal")
    def test_calc_rent_level(self, mock_session_local):
        """Test rent level calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (2050.0,)

        result = calc_rent_level(date(2024, 6, 15))

        assert result == 2050.0

    @patch("src.transformations.factors.zillow_factors.SessionLocal")
    def test_calc_regional_rent_dispersion(self, mock_session_local):
        """Test regional rent dispersion calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Latest period
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            date(2024, 6, 1),  # latest period
            3.5,              # std dev of YoY changes
        ]

        result = calc_regional_rent_dispersion(date(2024, 6, 15))

        assert result == 3.5


# =============================================================================
# Zillow Factor Class Tests
# =============================================================================

class TestZillowFactorClasses:
    """Test Zillow factor classes."""

    def test_rent_inflation_index_factor(self):
        """Test RentInflationIndex factor class."""
        factor = RentInflationIndex()
        assert factor.FACTOR_NAME == "rent_inflation_index"
        assert factor.CATEGORY == "real_estate"
        assert factor.FREQUENCY == "monthly"

    def test_sfr_multifamily_spread_factor(self):
        """Test SFRMultifamilySpread factor class."""
        factor = SFRMultifamilySpread()
        assert factor.FACTOR_NAME == "sfr_multifamily_spread"
        assert "sfr" in factor.FACTOR_DESCRIPTION.lower() or "single" in factor.FACTOR_DESCRIPTION.lower()

    def test_rent_momentum_factor(self):
        """Test RentMomentum factor class."""
        factor = RentMomentum()
        assert factor.FACTOR_NAME == "rent_momentum"
        assert factor.LOOKBACK_DAYS >= 30

    def test_national_rent_level_factor(self):
        """Test NationalRentLevel factor class."""
        factor = NationalRentLevel()
        assert factor.FACTOR_NAME == "national_rent_level"
        assert factor.ENTITY_TYPE == "market"

    def test_regional_rent_dispersion_factor(self):
        """Test RegionalRentDispersion factor class."""
        factor = RegionalRentDispersion()
        assert factor.FACTOR_NAME == "regional_rent_dispersion"

    def test_rent_inflation_only_for_real_estate(self):
        """Test rent inflation factor only applies to real estate stocks."""
        factor = RentInflationIndex()

        with patch("src.transformations.factors.zillow_factors.calc_rent_inflation_index") as mock_calc:
            mock_calc.return_value = 5.0
            result = factor.compute("AAPL", datetime(2024, 6, 15))
            assert result is None

    @patch("src.transformations.factors.zillow_factors.calc_rent_inflation_index")
    def test_rent_inflation_compute_for_reit(self, mock_calc):
        """Test rent inflation compute for apartment REIT."""
        mock_calc.return_value = 4.5

        factor = RentInflationIndex()
        result = factor.compute("EQR", datetime(2024, 6, 15))

        assert result == 4.5

    @patch("src.transformations.factors.zillow_factors.calc_rent_momentum")
    def test_rent_momentum_compute_for_sfr_reit(self, mock_calc):
        """Test rent momentum compute for SFR REIT."""
        mock_calc.return_value = 2.8

        factor = RentMomentum()
        result = factor.compute("INVH", datetime(2024, 6, 15))

        assert result == 2.8


# =============================================================================
# Zillow Factor Registry Tests
# =============================================================================

class TestZillowFactorRegistry:
    """Test Zillow factors in registry."""

    def test_zillow_factors_registered(self):
        """Test that all Zillow factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        zillow_factors = [
            "rent_inflation_index",
            "sfr_multifamily_spread",
            "rent_momentum",
            "national_rent_level",
            "regional_rent_dispersion",
        ]

        for factor in zillow_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_zillow_factors_category(self):
        """Test Zillow factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        zillow_factor_names = [
            "rent_inflation_index",
            "sfr_multifamily_spread",
            "rent_momentum",
            "national_rent_level",
            "regional_rent_dispersion",
        ]
        zillow_factors = [f for f in registered if f["id"] in zillow_factor_names]

        assert len(zillow_factors) == 5
        for factor in zillow_factors:
            assert factor["category"] == "real_estate"


# =============================================================================
# Entity Mapping Tests
# =============================================================================

class TestZillowEntityMapping:
    """Test Zillow entity mapping."""

    def test_apartment_reits_defined(self):
        """Test apartment REIT tickers are defined."""
        assert len(APARTMENT_REITS) >= 5
        assert "EQR" in APARTMENT_REITS   # Equity Residential
        assert "AVB" in APARTMENT_REITS   # AvalonBay
        assert "MAA" in APARTMENT_REITS   # Mid-America Apartment
        assert "UDR" in APARTMENT_REITS   # UDR Inc
        assert "CPT" in APARTMENT_REITS   # Camden Property

    def test_sfr_reits_defined(self):
        """Test SFR REIT tickers are defined."""
        assert len(SFR_REITS) >= 2
        assert "INVH" in SFR_REITS  # Invitation Homes
        assert "AMH" in SFR_REITS   # American Homes 4 Rent

    def test_homebuilders_defined(self):
        """Test homebuilder tickers are defined."""
        assert len(HOMEBUILDERS) >= 4
        assert "DHI" in HOMEBUILDERS  # D.R. Horton
        assert "LEN" in HOMEBUILDERS  # Lennar
        assert "PHM" in HOMEBUILDERS  # PulteGroup
