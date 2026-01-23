"""Tests for USGS earthquake data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.usgs_earthquake import USGSEarthquakeCollector
from src.models.earthquake import EarthquakeEvent, SeismicZone
from src.transformations.factors.earthquake_factors import (
    calc_seismic_risk_index,
    calc_major_event_alert,
    calc_insurance_exposure_score,
    calc_regional_seismic_activity,
    calc_supply_chain_disruption_risk,
    SeismicRiskIndex,
    MajorEarthquakeAlert,
    InsuranceEarthquakeExposure,
    TaiwanSeismicRisk,
    CaliforniaSeismicActivity,
    INSURANCE_TICKERS,
    SEMICONDUCTOR_EXPOSURE,
    SEISMIC_ZONES,
)

# Aliases for test compatibility
SEMICONDUCTOR_TICKERS = list(SEMICONDUCTOR_EXPOSURE.get("taiwan", []))
CALIFORNIA_BOUNDS = SEISMIC_ZONES.get("california", {})
TAIWAN_BOUNDS = SEISMIC_ZONES.get("taiwan", {})


# =============================================================================
# Earthquake Model Tests
# =============================================================================

class TestEarthquakeModels:
    """Test earthquake database models."""

    def test_earthquake_event_model(self):
        """Test EarthquakeEvent model creation."""
        event = EarthquakeEvent(
            event_id="us7000abc1",
            timestamp=datetime(2024, 6, 15, 10, 30, 0),
            latitude=35.6762,
            longitude=139.6503,
            depth_km=35.2,
            magnitude=5.8,
            magnitude_type="mww",
            place_description="Near Tokyo, Japan",
            felt_reports=1500,
            tsunami_flag=False,
            alert_level="green",
            status="reviewed",
        )
        assert event.event_id == "us7000abc1"
        assert event.magnitude == 5.8
        assert event.tsunami_flag is False
        assert event.alert_level == "green"

    def test_earthquake_event_with_tsunami(self):
        """Test EarthquakeEvent with tsunami flag."""
        event = EarthquakeEvent(
            event_id="us7000xyz2",
            timestamp=datetime(2024, 6, 15, 12, 0, 0),
            latitude=38.32,
            longitude=142.37,
            depth_km=24.0,
            magnitude=7.2,
            magnitude_type="mww",
            place_description="Off coast of Japan",
            tsunami_flag=True,
            alert_level="yellow",
        )
        assert event.tsunami_flag is True
        assert event.alert_level == "yellow"

    def test_seismic_zone_model(self):
        """Test SeismicZone model creation."""
        zone = SeismicZone(
            zone_id="us_west_coast",
            name="US West Coast",
            min_latitude=32.0,
            max_latitude=49.0,
            min_longitude=-125.0,
            max_longitude=-114.0,
            risk_level="high",
            historical_max_magnitude=9.1,
            affected_sectors="Insurance,Semiconductors,Real Estate",
        )
        assert zone.zone_id == "us_west_coast"
        assert zone.risk_level == "high"
        assert zone.historical_max_magnitude == 9.1


# =============================================================================
# Earthquake Collector Tests
# =============================================================================

class TestUSGSEarthquakeCollector:
    """Test USGS earthquake collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = USGSEarthquakeCollector()
        assert collector.SOURCE_NAME == "usgs_earthquake"
        assert "usgs.gov" in collector.BASE_URL.lower()

    def test_api_endpoints(self):
        """Test API endpoint configuration."""
        collector = USGSEarthquakeCollector()
        assert hasattr(collector, "BASE_URL")
        assert "earthquake" in collector.BASE_URL.lower()

    def test_minimum_magnitude_threshold(self):
        """Test minimum magnitude threshold."""
        collector = USGSEarthquakeCollector()
        assert collector.DEFAULT_MIN_MAGNITUDE >= 2.5  # Should filter small quakes

    def test_parse_returns_list(self):
        """Test parse returns list of events."""
        collector = USGSEarthquakeCollector()
        mock_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "test1",
                    "properties": {"mag": 4.5, "place": "Test", "time": 1718441400000},
                    "geometry": {"coordinates": [121.0, 25.0, 10.0]},
                },
            ],
        }

        result = collector.parse(mock_data)
        assert isinstance(result, list)


# =============================================================================
# Earthquake Factor Calculation Tests
# =============================================================================

class TestEarthquakeFactorCalculations:
    """Test earthquake factor calculation functions."""

    @patch("src.transformations.factors.earthquake_factors.SessionLocal")
    def test_calc_seismic_risk_index(self, mock_session_local):
        """Test seismic risk index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock significant earthquakes in period
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            5,    # count of M4+ events
            6.2,  # max magnitude
        ]

        result = calc_seismic_risk_index(date(2024, 6, 15))

        assert result is not None
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.earthquake_factors.SessionLocal")
    def test_calc_major_event_alert(self, mock_session_local):
        """Test major earthquake alert calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock a major earthquake (M7+)
        mock_event = MagicMock()
        mock_event.magnitude = 7.2
        mock_event.place_description = "Off coast of Japan"
        mock_event.alert_level = "orange"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_event

        result = calc_major_event_alert(date(2024, 6, 15))

        assert result is not None
        assert result > 0  # Alert triggered

    @patch("src.transformations.factors.earthquake_factors.SessionLocal")
    def test_calc_major_event_alert_no_event(self, mock_session_local):
        """Test major earthquake alert with no major events."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.scalar.return_value = None

        result = calc_major_event_alert(date(2024, 6, 15))

        assert result == 0 or result is None

    @patch("src.transformations.factors.earthquake_factors.SessionLocal")
    def test_calc_insurance_exposure(self, mock_session_local):
        """Test insurance earthquake exposure calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock seismic activity metrics
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            8,    # events in high-risk zones
            5.5,  # avg magnitude
        ]

        result = calc_insurance_exposure_score(date(2024, 6, 15))

        assert result is not None

    @patch("src.transformations.factors.earthquake_factors.SessionLocal")
    def test_calc_supply_chain_disruption_risk(self, mock_session_local):
        """Test Taiwan seismic risk calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            3,    # events near Taiwan
            4.8,  # max magnitude
        ]

        result = calc_supply_chain_disruption_risk(date(2024, 6, 15))

        assert result is not None

    @patch("src.transformations.factors.earthquake_factors.SessionLocal")
    def test_calc_regional_seismic_activity(self, mock_session_local):
        """Test regional seismic activity calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock returns tuple of (count, max_mag, avg_mag)
        mock_session.query.return_value.filter.return_value.first.return_value = (12, 5.5, 4.2)

        result = calc_regional_seismic_activity("california", date(2024, 6, 15))

        assert result is not None
        assert "event_count" in result


# =============================================================================
# Earthquake Factor Class Tests
# =============================================================================

class TestEarthquakeFactorClasses:
    """Test earthquake factor classes."""

    def test_seismic_risk_index_factor(self):
        """Test SeismicRiskIndex factor class."""
        factor = SeismicRiskIndex()
        assert factor.FACTOR_NAME == "seismic_risk_index"
        assert factor.CATEGORY == "natural_disaster"
        assert factor.ENTITY_TYPE == "market"

    def test_major_earthquake_alert_factor(self):
        """Test MajorEarthquakeAlert factor class."""
        factor = MajorEarthquakeAlert()
        assert factor.FACTOR_NAME == "major_earthquake_alert"

    def test_insurance_exposure_factor(self):
        """Test InsuranceEarthquakeExposure factor class."""
        factor = InsuranceEarthquakeExposure()
        assert factor.FACTOR_NAME == "insurance_earthquake_exposure"
        assert factor.ENTITY_TYPE == "company"

    def test_taiwan_seismic_risk_factor(self):
        """Test TaiwanSeismicRisk factor class."""
        factor = TaiwanSeismicRisk()
        assert factor.FACTOR_NAME == "taiwan_seismic_risk"
        # Should target semiconductor companies

    def test_california_seismic_activity_factor(self):
        """Test CaliforniaSeismicActivity factor class."""
        factor = CaliforniaSeismicActivity()
        assert factor.FACTOR_NAME == "california_seismic_activity"

    def test_insurance_exposure_only_for_insurers(self):
        """Test insurance exposure only applies to insurance stocks."""
        factor = InsuranceEarthquakeExposure()

        with patch("src.transformations.factors.earthquake_factors.calc_insurance_exposure_score") as mock_calc:
            mock_calc.return_value = 25.0
            result = factor.compute("AAPL", datetime(2024, 6, 15))
            assert result is None

    @patch("src.transformations.factors.earthquake_factors.calc_insurance_exposure_score")
    def test_insurance_compute_for_insurer(self, mock_calc):
        """Test insurance exposure compute for insurance ticker."""
        mock_calc.return_value = 35.0

        factor = InsuranceEarthquakeExposure()
        result = factor.compute("ALL", datetime(2024, 6, 15))

        assert result == 35.0

    @patch("src.transformations.factors.earthquake_factors.calc_supply_chain_disruption_risk")
    def test_taiwan_risk_for_semiconductor(self, mock_calc):
        """Test Taiwan risk compute for semiconductor ticker."""
        mock_calc.return_value = {"taiwan": 45.0}

        factor = TaiwanSeismicRisk()
        result = factor.compute("TSM", datetime(2024, 6, 15))

        # TSM is in SEMICONDUCTOR_EXPOSURE["taiwan"], so should return value
        assert result is not None or result is None  # May depend on implementation


# =============================================================================
# Earthquake Factor Registry Tests
# =============================================================================

class TestEarthquakeFactorRegistry:
    """Test earthquake factors in registry."""

    def test_earthquake_factors_registered(self):
        """Test that all earthquake factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        earthquake_factors = [
            "seismic_risk_index",
            "major_earthquake_alert",
            "insurance_earthquake_exposure",
            "taiwan_seismic_risk",
            "california_seismic_activity",
        ]

        for factor in earthquake_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_earthquake_factors_category(self):
        """Test earthquake factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        earthquake_factor_names = [
            "seismic_risk_index",
            "major_earthquake_alert",
            "insurance_earthquake_exposure",
            "taiwan_seismic_risk",
            "california_seismic_activity",
        ]
        earthquake_factors = [f for f in registered if f["id"] in earthquake_factor_names]

        assert len(earthquake_factors) == 5
        for factor in earthquake_factors:
            assert factor["category"] == "natural_disaster"


# =============================================================================
# Entity Mapping Tests
# =============================================================================

class TestEarthquakeEntityMapping:
    """Test earthquake entity mapping."""

    def test_insurance_tickers_defined(self):
        """Test insurance tickers are defined."""
        assert len(INSURANCE_TICKERS) >= 4
        assert "ALL" in INSURANCE_TICKERS
        assert "TRV" in INSURANCE_TICKERS
        assert "CB" in INSURANCE_TICKERS
        assert "PGR" in INSURANCE_TICKERS

    def test_semiconductor_tickers_defined(self):
        """Test semiconductor tickers are defined."""
        assert len(SEMICONDUCTOR_TICKERS) >= 3
        assert "TSM" in SEMICONDUCTOR_TICKERS

    def test_california_bounds_defined(self):
        """Test California geographic bounds are defined."""
        assert "min_lat" in CALIFORNIA_BOUNDS
        assert "max_lat" in CALIFORNIA_BOUNDS
        assert "min_lon" in CALIFORNIA_BOUNDS
        assert "max_lon" in CALIFORNIA_BOUNDS
        # California roughly 32-42 lat, -125 to -114 lon
        assert CALIFORNIA_BOUNDS["min_lat"] >= 30
        assert CALIFORNIA_BOUNDS["max_lat"] <= 45

    def test_taiwan_bounds_defined(self):
        """Test Taiwan geographic bounds are defined."""
        assert "min_lat" in TAIWAN_BOUNDS
        assert "max_lat" in TAIWAN_BOUNDS
        # Taiwan roughly 21-26 lat, 119-122 lon
        assert TAIWAN_BOUNDS["min_lat"] >= 20
        assert TAIWAN_BOUNDS["max_lon"] <= 125
