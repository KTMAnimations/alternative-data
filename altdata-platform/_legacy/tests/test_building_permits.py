"""Tests for building permits data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.building_permits import BuildingPermitsCollector
from src.models.building_permits import BuildingPermit
from src.transformations.factors.building_permit_factors import (
    calc_permit_momentum,
    calc_sfr_multifamily_ratio,
    calc_permit_level,
    calc_permit_yoy_change,
    PermitMomentum,
    SingleFamilyPermitMomentum,
    SFRMultifamilyRatio,
    BuildingPermitLevel,
    PermitYoYChange,
    HOMEBUILDERS,
    HOME_IMPROVEMENT,
)


# =============================================================================
# Building Permits Model Tests
# =============================================================================

class TestBuildingPermitsModels:
    """Test building permits database models."""

    def test_building_permit_model(self):
        """Test BuildingPermit model creation."""
        permit = BuildingPermit(
            period=date(2024, 6, 1),
            geography_level="national",
            geography_code="US",
            geography_name="United States",
            permit_type="total",
            units_authorized=1500000,
            valuation=Decimal("350000000000.00"),
            is_seasonally_adjusted="Y",
        )
        assert permit.period == date(2024, 6, 1)
        assert permit.units_authorized == 1500000
        assert permit.geography_level == "national"

    def test_building_permit_regional(self):
        """Test BuildingPermit with regional data."""
        permit = BuildingPermit(
            period=date(2024, 6, 1),
            geography_level="state",
            geography_code="TX",
            geography_name="Texas",
            permit_type="single_family",
            units_authorized=25000,
            valuation=Decimal("5000000000.00"),
            is_seasonally_adjusted="N",
        )
        assert permit.geography_level == "state"
        assert permit.geography_code == "TX"
        assert permit.permit_type == "single_family"

    def test_building_permit_types(self):
        """Test different permit types."""
        for permit_type in ["total", "single_family", "multi_family", "5_or_more_units"]:
            permit = BuildingPermit(
                period=date(2024, 6, 1),
                permit_type=permit_type,
            )
            assert permit.permit_type == permit_type


# =============================================================================
# Building Permits Collector Tests
# =============================================================================

class TestBuildingPermitsCollector:
    """Test building permits collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = BuildingPermitsCollector()
        assert collector.SOURCE_NAME == "building_permits"

    def test_parse_returns_list(self):
        """Test parse returns list."""
        collector = BuildingPermitsCollector()
        result = collector.parse({})
        assert isinstance(result, list)


# =============================================================================
# Building Permits Factor Calculation Tests
# =============================================================================

class TestBuildingPermitsFactorCalculations:
    """Test building permits factor calculation functions."""

    @patch("src.transformations.factors.building_permit_factors.SessionLocal")
    def test_calc_permit_momentum(self, mock_session_local):
        """Test permit momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current month: 1500, Prior month: 1450
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            (1500000,),  # current month
            (1450000,),  # prior month
        ]

        result = calc_permit_momentum(date(2024, 6, 15))

        assert result is not None
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.building_permit_factors.SessionLocal")
    def test_calc_single_family_momentum(self, mock_session_local):
        """Test single family permit momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            (950000,),   # current SFR
            (920000,),   # prior SFR
        ]

        result = calc_permit_momentum(date(2024, 6, 15), permit_type="single_family")

        assert result is not None
        assert result > 0  # Growth

    @patch("src.transformations.factors.building_permit_factors.SessionLocal")
    def test_calc_sfr_multifamily_ratio(self, mock_session_local):
        """Test SFR to multifamily ratio calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # SFR: 950K, MF: 550K
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            (950000,),   # single family
            (550000,),   # multi family
        ]

        result = calc_sfr_multifamily_ratio(date(2024, 6, 15))

        assert result is not None

    @patch("src.transformations.factors.building_permit_factors.SessionLocal")
    def test_calc_permit_level(self, mock_session_local):
        """Test building permit level calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (1500000,)

        result = calc_permit_level(date(2024, 6, 15))

        assert result == 1500  # Returns in thousands

    @patch("src.transformations.factors.building_permit_factors.SessionLocal")
    def test_calc_permit_yoy_change(self, mock_session_local):
        """Test permit YoY change calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current: 1500K, Prior year: 1400K
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            (1500000,),  # current
            (1400000,),  # prior year
        ]

        result = calc_permit_yoy_change(date(2024, 6, 15))

        assert result is not None


# =============================================================================
# Building Permits Factor Class Tests
# =============================================================================

class TestBuildingPermitsFactorClasses:
    """Test building permits factor classes."""

    def test_permit_momentum_factor(self):
        """Test PermitMomentum factor class."""
        factor = PermitMomentum()
        assert factor.FACTOR_NAME == "permit_momentum"
        assert factor.CATEGORY == "construction"
        assert factor.FREQUENCY == "monthly"

    def test_single_family_momentum_factor(self):
        """Test SingleFamilyPermitMomentum factor class."""
        factor = SingleFamilyPermitMomentum()
        assert factor.FACTOR_NAME == "sfr_permit_momentum"
        assert "single" in factor.FACTOR_DESCRIPTION.lower()

    def test_sfr_multifamily_ratio_factor(self):
        """Test SFRMultifamilyRatio factor class."""
        factor = SFRMultifamilyRatio()
        assert factor.FACTOR_NAME == "sfr_multifamily_ratio"

    def test_building_permit_level_factor(self):
        """Test BuildingPermitLevel factor class."""
        factor = BuildingPermitLevel()
        assert factor.FACTOR_NAME == "building_permit_level"
        assert factor.ENTITY_TYPE == "market"

    def test_permit_yoy_change_factor(self):
        """Test PermitYoYChange factor class."""
        factor = PermitYoYChange()
        assert factor.FACTOR_NAME == "permit_yoy_change"
        assert factor.LOOKBACK_DAYS >= 365

    def test_momentum_only_for_homebuilders(self):
        """Test momentum factor only applies to homebuilders."""
        factor = PermitMomentum()

        with patch("src.transformations.factors.building_permit_factors.calc_permit_momentum") as mock_calc:
            mock_calc.return_value = 5.0
            result = factor.compute("AAPL", datetime(2024, 6, 15))
            assert result is None

    @patch("src.transformations.factors.building_permit_factors.calc_permit_momentum")
    def test_momentum_compute_for_homebuilder(self, mock_calc):
        """Test momentum compute for homebuilder ticker."""
        mock_calc.return_value = 4.5

        factor = PermitMomentum()
        result = factor.compute("DHI", datetime(2024, 6, 15))

        assert result == 4.5

    @patch("src.transformations.factors.building_permit_factors.calc_permit_momentum")
    def test_momentum_compute_for_home_improvement(self, mock_calc):
        """Test momentum compute for home improvement ticker."""
        mock_calc.return_value = 3.5

        factor = PermitMomentum()
        result = factor.compute("HD", datetime(2024, 6, 15))

        assert result == 3.5


# =============================================================================
# Building Permits Factor Registry Tests
# =============================================================================

class TestBuildingPermitsFactorRegistry:
    """Test building permits factors in registry."""

    def test_permit_factors_registered(self):
        """Test that all permit factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        permit_factors = [
            "permit_momentum",
            "sfr_permit_momentum",
            "sfr_multifamily_ratio",
            "building_permit_level",
            "permit_yoy_change",
        ]

        for factor in permit_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_permit_factors_category(self):
        """Test permit factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        permit_factor_names = [
            "permit_momentum",
            "sfr_permit_momentum",
            "sfr_multifamily_ratio",
            "building_permit_level",
            "permit_yoy_change",
        ]
        permit_factors = [f for f in registered if f["id"] in permit_factor_names]

        # Note: sfr_permit_momentum may not be a separate factor
        assert len(permit_factors) >= 4
        for factor in permit_factors:
            assert factor["category"] == "construction"


# =============================================================================
# Entity Mapping Tests
# =============================================================================

class TestBuildingPermitsEntityMapping:
    """Test building permits entity mapping."""

    def test_homebuilder_tickers_defined(self):
        """Test homebuilder tickers are defined."""
        assert len(HOMEBUILDERS) >= 5
        assert "DHI" in HOMEBUILDERS  # D.R. Horton
        assert "LEN" in HOMEBUILDERS  # Lennar
        assert "PHM" in HOMEBUILDERS  # PulteGroup
        assert "TOL" in HOMEBUILDERS  # Toll Brothers
        assert "NVR" in HOMEBUILDERS  # NVR Inc

    def test_home_improvement_tickers_defined(self):
        """Test home improvement tickers are defined."""
        assert len(HOME_IMPROVEMENT) >= 2
        assert "HD" in HOME_IMPROVEMENT   # Home Depot
        assert "LOW" in HOME_IMPROVEMENT  # Lowe's
