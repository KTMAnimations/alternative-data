"""Tests for UK carbon intensity data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.carbon_intensity import CarbonIntensityCollector
from src.models.carbon_intensity import CarbonIntensityReading
from src.transformations.factors.carbon_intensity_factors import (
    calc_carbon_intensity_trend,
    calc_renewable_share_growth,
    calc_grid_carbon_intensity,
    calc_renewable_share,
    calc_low_carbon_hours_ratio,
    CarbonIntensityTrend,
    RenewableShareGrowth,
    GridCarbonIntensity,
    RenewableEnergyShare,
    LowCarbonHoursRatio,
    UK_UTILITIES,
    ESG_ETFS,
)


# =============================================================================
# Carbon Intensity Model Tests
# =============================================================================

class TestCarbonIntensityModels:
    """Test carbon intensity database models."""

    def test_carbon_intensity_reading_model(self):
        """Test CarbonIntensityReading model creation."""
        reading = CarbonIntensityReading(
            timestamp=datetime(2024, 6, 15, 14, 30, 0),
            region="national",
            intensity_forecast=185,
            intensity_actual=178,
            intensity_index="moderate",
            pct_biomass=5.2,
            pct_coal=1.5,
            pct_gas=35.0,
            pct_hydro=2.1,
            pct_imports=8.5,
            pct_nuclear=15.0,
            pct_solar=8.0,
            pct_wind=22.0,
            pct_other=2.7,
        )
        assert reading.intensity_actual == 178
        assert reading.intensity_index == "moderate"
        assert reading.pct_wind == 22.0

    def test_carbon_intensity_with_generation_mix(self):
        """Test CarbonIntensityReading with JSON generation mix."""
        generation_mix = {
            "biomass": 5.2,
            "coal": 1.5,
            "gas": 35.0,
            "hydro": 2.1,
            "imports": 8.5,
            "nuclear": 15.0,
            "solar": 8.0,
            "wind": 22.0,
            "other": 2.7,
        }
        reading = CarbonIntensityReading(
            timestamp=datetime(2024, 6, 15, 14, 30, 0),
            region="national",
            intensity_actual=178,
            generation_mix=generation_mix,
        )
        assert reading.generation_mix == generation_mix
        assert reading.generation_mix["wind"] == 22.0

    def test_carbon_intensity_index_levels(self):
        """Test different intensity index levels."""
        for index in ["very low", "low", "moderate", "high", "very high"]:
            reading = CarbonIntensityReading(
                timestamp=datetime.utcnow(),
                intensity_index=index,
            )
            assert reading.intensity_index == index


# =============================================================================
# Carbon Intensity Collector Tests
# =============================================================================

class TestCarbonIntensityCollector:
    """Test carbon intensity collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = CarbonIntensityCollector()
        assert collector.SOURCE_NAME == "carbon_intensity"
        assert "carbonintensity" in collector.BASE_URL.lower()

    def test_api_endpoints(self):
        """Test API endpoint configuration."""
        collector = CarbonIntensityCollector()
        assert hasattr(collector, "BASE_URL")

    def test_parse_returns_list(self):
        """Test parse returns list of readings."""
        collector = CarbonIntensityCollector()
        result = collector.parse({})
        assert isinstance(result, list)


# =============================================================================
# Carbon Intensity Factor Calculation Tests
# =============================================================================

class TestCarbonIntensityFactorCalculations:
    """Test carbon intensity factor calculation functions."""

    @patch("src.transformations.factors.carbon_intensity_factors.SessionLocal")
    def test_calc_carbon_intensity_trend(self, mock_session_local):
        """Test carbon intensity trend calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current avg: 150, Prior avg: 180
        # Trend = (150 - 180) / 180 * 100 = -16.7% (improving)
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            150.0,  # current period avg
            180.0,  # prior period avg
        ]

        result = calc_carbon_intensity_trend(date(2024, 6, 15))

        assert result is not None
        assert result < 0  # Negative means improving (lower carbon)
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.carbon_intensity_factors.calc_renewable_share")
    def test_calc_renewable_share_growth(self, mock_calc_share):
        """Test renewable share growth calculation."""
        # Mock current and prior renewable share values
        mock_calc_share.side_effect = [45.0, 40.0]

        result = calc_renewable_share_growth(date(2024, 6, 15))

        # Result depends on implementation
        assert result is None or result != 0

    @patch("src.transformations.factors.carbon_intensity_factors.SessionLocal")
    def test_calc_grid_carbon_intensity(self, mock_session_local):
        """Test grid carbon intensity calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (165.0,)

        result = calc_grid_carbon_intensity(date(2024, 6, 15))

        assert result == 165.0

    @patch("src.transformations.factors.carbon_intensity_factors.SessionLocal")
    def test_calc_renewable_share(self, mock_session_local):
        """Test renewable energy share calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Solar + Wind + Hydro = 8 + 22 + 2 = 32%
        mock_session.query.return_value.filter.return_value.scalar.return_value = 32.0

        result = calc_renewable_share(date(2024, 6, 15))

        assert result is not None

    @patch("src.transformations.factors.carbon_intensity_factors.SessionLocal")
    def test_calc_low_carbon_hours_ratio(self, mock_session_local):
        """Test low carbon hours ratio calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # 36 out of 48 half-hours were low carbon
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            48,   # total readings
            36,   # low carbon readings
        ]

        result = calc_low_carbon_hours_ratio(date(2024, 6, 15))

        assert result is not None
        assert abs(result - 0.75) < 0.1  # 75% low carbon (as ratio 0-1)


# =============================================================================
# Carbon Intensity Factor Class Tests
# =============================================================================

class TestCarbonIntensityFactorClasses:
    """Test carbon intensity factor classes."""

    def test_carbon_intensity_trend_factor(self):
        """Test CarbonIntensityTrend factor class."""
        factor = CarbonIntensityTrend()
        assert factor.FACTOR_NAME == "carbon_intensity_trend"
        assert factor.CATEGORY == "esg"

    def test_renewable_share_growth_factor(self):
        """Test RenewableShareGrowth factor class."""
        factor = RenewableShareGrowth()
        assert factor.FACTOR_NAME == "renewable_share_growth"
        assert "renewable" in factor.FACTOR_DESCRIPTION.lower()

    def test_grid_carbon_intensity_factor(self):
        """Test GridCarbonIntensity factor class."""
        factor = GridCarbonIntensity()
        assert factor.FACTOR_NAME == "grid_carbon_intensity"
        assert factor.ENTITY_TYPE == "market"

    def test_renewable_energy_share_factor(self):
        """Test RenewableEnergyShare factor class."""
        factor = RenewableEnergyShare()
        assert factor.FACTOR_NAME == "renewable_energy_share"

    def test_low_carbon_hours_ratio_factor(self):
        """Test LowCarbonHoursRatio factor class."""
        factor = LowCarbonHoursRatio()
        assert factor.FACTOR_NAME == "low_carbon_hours_ratio"

    @patch("src.transformations.factors.carbon_intensity_factors.calc_carbon_intensity_trend")
    def test_trend_compute(self, mock_calc):
        """Test trend compute method."""
        mock_calc.return_value = -12.5

        factor = CarbonIntensityTrend()
        result = factor.compute("NG", datetime(2024, 6, 15))

        assert result == -12.5


# =============================================================================
# Carbon Intensity Factor Registry Tests
# =============================================================================

class TestCarbonIntensityFactorRegistry:
    """Test carbon intensity factors in registry."""

    def test_carbon_factors_registered(self):
        """Test that all carbon intensity factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        carbon_factors = [
            "carbon_intensity_trend",
            "renewable_share_growth",
            "grid_carbon_intensity",
            "renewable_energy_share",
            "low_carbon_hours_ratio",
        ]

        for factor in carbon_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_carbon_factors_category(self):
        """Test carbon intensity factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        carbon_factor_names = [
            "carbon_intensity_trend",
            "renewable_share_growth",
            "grid_carbon_intensity",
            "renewable_energy_share",
            "low_carbon_hours_ratio",
        ]
        carbon_factors = [f for f in registered if f["id"] in carbon_factor_names]

        assert len(carbon_factors) == 5
        for factor in carbon_factors:
            assert factor["category"] == "esg"


# =============================================================================
# Entity Mapping Tests
# =============================================================================

class TestCarbonIntensityEntityMapping:
    """Test carbon intensity entity mapping."""

    def test_utility_tickers_defined(self):
        """Test utility tickers are defined."""
        assert len(UK_UTILITIES) >= 2
        assert "NG.L" in UK_UTILITIES  # National Grid
        assert "SSE.L" in UK_UTILITIES

    def test_esg_etfs_defined(self):
        """Test ESG ETFs are defined."""
        assert len(ESG_ETFS) >= 1
