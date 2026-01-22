"""Tests for shipping/AIS data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.marine_traffic import MarineTrafficCollector
from src.models.shipping import (
    Vessel,
    VesselPosition,
    Port,
    PortCall,
    ShippingRoute,
    PortCongestion,
    GlobalShippingIndex,
)
from src.transformations.factors.shipping_factors import (
    calc_port_congestion_index,
    calc_port_activity_change,
    calc_container_vessel_count,
    calc_tanker_activity_index,
    calc_global_congestion_index,
    PortCongestionIndex,
    PortActivityChange,
    ContainerVesselCount,
    TankerActivityIndex,
    GlobalCongestionIndex,
    ChinaUSTradeFlow,
)


# =============================================================================
# Shipping Model Tests
# =============================================================================

class TestShippingModels:
    """Test shipping database models."""

    def test_vessel_model(self):
        """Test Vessel model creation."""
        vessel = Vessel(
            mmsi="123456789",
            imo="IMO1234567",
            name="EVER GIVEN",
            vessel_type="Container",
            vessel_type_code=71,
            flag="PA",
            gross_tonnage=220940,
            length_m=399.94,
            width_m=58.8,
        )
        assert vessel.mmsi == "123456789"
        assert vessel.vessel_type == "Container"
        assert vessel.gross_tonnage == 220940

    def test_vessel_position_model(self):
        """Test VesselPosition model creation."""
        position = VesselPosition(
            mmsi="123456789",
            timestamp=datetime.utcnow(),
            latitude=31.23,
            longitude=121.47,
            speed_knots=12.5,
            course=180.0,
            heading=178.0,
            nav_status="Under way using engine",
            destination="USLAX",
        )
        assert position.latitude == 31.23
        assert position.speed_knots == 12.5
        assert position.destination == "USLAX"

    def test_port_model(self):
        """Test Port model creation."""
        port = Port(
            port_id="CNSHA",
            name="Shanghai",
            country="CN",
            latitude=31.23,
            longitude=121.47,
            port_type="Seaport",
            is_major=True,
            annual_teu_capacity=47000000,
        )
        assert port.port_id == "CNSHA"
        assert port.is_major is True
        assert port.annual_teu_capacity == 47000000

    def test_port_call_model(self):
        """Test PortCall model creation."""
        call = PortCall(
            mmsi="123456789",
            port_id="CNSHA",
            call_type="arrival",
            timestamp=datetime.utcnow(),
            duration_hours=48.5,
            cargo_type="Container",
        )
        assert call.call_type == "arrival"
        assert call.duration_hours == 48.5

    def test_shipping_route_model(self):
        """Test ShippingRoute model creation."""
        route = ShippingRoute(
            route_id="CNSHA-USLAX",
            name="Shanghai to Los Angeles",
            origin_port="CNSHA",
            destination_port="USLAX",
            typical_duration_days=14,
            distance_nm=5780,
            is_major_lane=True,
        )
        assert route.route_id == "CNSHA-USLAX"
        assert route.is_major_lane is True

    def test_port_congestion_model(self):
        """Test PortCongestion model creation."""
        congestion = PortCongestion(
            port_id="USLAX",
            date=date.today(),
            vessels_at_anchor=25,
            vessels_in_port=50,
            avg_wait_time_hours=36.5,
            container_vessels=35,
            tankers=10,
            bulk_carriers=5,
        )
        assert congestion.vessels_at_anchor == 25
        assert congestion.avg_wait_time_hours == 36.5

    def test_global_shipping_index_model(self):
        """Test GlobalShippingIndex model creation."""
        index = GlobalShippingIndex(
            date=date.today(),
            global_activity_index=95.5,
            container_activity_index=102.3,
            tanker_activity_index=88.7,
            china_congestion_index=75.0,
            us_congestion_index=62.5,
        )
        assert index.global_activity_index == 95.5
        assert index.china_congestion_index == 75.0


# =============================================================================
# MarineTraffic Collector Tests
# =============================================================================

class TestMarineTrafficCollector:
    """Test MarineTraffic collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = MarineTrafficCollector(api_key="test_key")
        assert collector.api_key == "test_key"
        assert collector.SOURCE_NAME == "marine_traffic"

    def test_tracked_ports(self):
        """Test tracked ports configuration."""
        collector = MarineTrafficCollector()
        assert len(collector.TRACKED_PORTS) >= 10
        port_ids = [p["port_id"] for p in collector.TRACKED_PORTS]
        assert "CNSHA" in port_ids  # Shanghai
        assert "USLAX" in port_ids  # Los Angeles
        assert "NLRTM" in port_ids  # Rotterdam

    def test_vessel_types(self):
        """Test vessel type mapping."""
        collector = MarineTrafficCollector()
        assert collector.get_vessel_type(70) == "Cargo"
        assert collector.get_vessel_type(80) == "Tanker"
        assert collector.get_vessel_type(30) == "Fishing"
        assert collector.get_vessel_type(60) == "Passenger"

    def test_parse_vessel(self):
        """Test vessel data parsing."""
        collector = MarineTrafficCollector()
        raw = {
            "MMSI": "123456789",
            "IMO": "IMO1234567",
            "SHIPNAME": "TEST VESSEL",
            "CALLSIGN": "ABC123",
            "SHIP_TYPE": 71,
            "FLAG": "US",
            "GT": 50000,
            "LENGTH": 300,
            "WIDTH": 40,
        }

        parsed = collector.parse_vessel(raw)

        assert parsed["mmsi"] == "123456789"
        assert parsed["name"] == "TEST VESSEL"
        assert "Cargo" in parsed["vessel_type"]  # Type 71 = Cargo - Hazardous A
        assert parsed["gross_tonnage"] == 50000

    def test_parse_position(self):
        """Test position data parsing."""
        collector = MarineTrafficCollector()
        raw = {
            "MMSI": "123456789",
            "LAT": 31.23,
            "LON": 121.47,
            "SPEED": 12.5,
            "COURSE": 180,
            "HEADING": 178,
            "STATUS": "Under way",
            "DESTINATION": "USLAX",
        }

        parsed = collector.parse_position(raw)

        assert parsed["mmsi"] == "123456789"
        assert parsed["latitude"] == 31.23
        assert parsed["speed_knots"] == 12.5
        assert parsed["destination"] == "USLAX"

    def test_parse_position_handles_missing_mmsi(self):
        """Test position parsing returns None without MMSI."""
        collector = MarineTrafficCollector()
        raw = {"LAT": 31.23, "LON": 121.47}

        parsed = collector.parse_position(raw)

        assert parsed is None

    def test_haversine_calculation(self):
        """Test haversine distance calculation."""
        collector = MarineTrafficCollector()

        # Shanghai to Los Angeles (approximately 5700 nm)
        distance = collector.haversine_nm(31.23, 121.47, 33.74, -118.26)

        assert 5500 < distance < 6000

    def test_haversine_same_point(self):
        """Test haversine returns 0 for same point."""
        collector = MarineTrafficCollector()

        distance = collector.haversine_nm(31.23, 121.47, 31.23, 121.47)

        assert distance == 0

    def test_calculate_congestion_index(self):
        """Test congestion index calculation."""
        collector = MarineTrafficCollector()

        # Moderate congestion
        index = collector.calculate_congestion_index(50, 24)
        assert 40 < index < 60

        # High congestion
        index_high = collector.calculate_congestion_index(100, 48)
        assert index_high == 100

        # Low congestion
        index_low = collector.calculate_congestion_index(10, 6)
        assert index_low < 20

    def test_parse_returns_structured_data(self):
        """Test parse returns proper structure."""
        collector = MarineTrafficCollector()
        raw_data = [
            {
                "port": {"port_id": "CNSHA", "name": "Shanghai"},
                "vessels": [
                    {"MMSI": "111", "LAT": 31.0, "LON": 121.0, "SHIP_TYPE": 71},
                    {"MMSI": "222", "LAT": 31.1, "LON": 121.1, "SHIP_TYPE": 80},
                ],
            }
        ]

        parsed = collector.parse(raw_data)

        assert "vessels" in parsed
        assert "positions" in parsed
        assert "port_metrics" in parsed
        assert len(parsed["vessels"]) == 2
        assert len(parsed["positions"]) == 2

    def test_detect_port_call(self):
        """Test port call detection."""
        collector = MarineTrafficCollector()
        positions = [
            {"mmsi": "123", "latitude": 31.23, "longitude": 121.47, "speed_knots": 0, "timestamp": datetime.utcnow()},
            {"mmsi": "456", "latitude": 31.24, "longitude": 121.48, "speed_knots": 12, "timestamp": datetime.utcnow()},
        ]

        calls = collector.detect_port_call(positions, 31.23, 121.47, "CNSHA", threshold_nm=5)

        # Only stationary vessel should be detected
        assert len(calls) == 1
        assert calls[0]["mmsi"] == "123"


# =============================================================================
# Shipping Factor Calculation Tests
# =============================================================================

class TestShippingFactorCalculations:
    """Test shipping factor calculation functions."""

    @patch("src.transformations.factors.shipping_factors.SessionLocal")
    def test_calc_port_congestion_index(self, mock_session_local):
        """Test port congestion index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_congestion = MagicMock()
        mock_congestion.vessels_in_port = 75
        mock_congestion.avg_wait_time_hours = 24

        mock_session.query.return_value.filter.return_value.first.return_value = mock_congestion

        result = calc_port_congestion_index("USLAX", date(2024, 6, 15))

        # vessel_factor = min(75/100, 1) * 50 = 37.5
        # wait_factor = min(24/48, 1) * 50 = 25
        # total = 62.5
        assert result == 62.5
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.shipping_factors.SessionLocal")
    def test_calc_port_congestion_index_no_data(self, mock_session_local):
        """Test congestion returns None when no data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = calc_port_congestion_index("UNKNOWN", date(2024, 6, 15))

        assert result is None

    @patch("src.transformations.factors.shipping_factors.SessionLocal")
    def test_calc_port_activity_change(self, mock_session_local):
        """Test port activity change calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Recent: 70 arrivals in 7 days = 10/day
        # Comparison: 161 arrivals in 23 days = 7/day
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [70, 161]

        result = calc_port_activity_change("CNSHA", date(2024, 6, 15), lookback_days=7, comparison_days=30)

        # Change = (10 - 7) / 7 * 100 = 42.86%
        assert result is not None
        assert abs(result - 42.86) < 1

    @patch("src.transformations.factors.shipping_factors.SessionLocal")
    def test_calc_container_vessel_count(self, mock_session_local):
        """Test container vessel count calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 250

        result = calc_container_vessel_count("asia", date(2024, 6, 15))

        assert result == 250

    @patch("src.transformations.factors.shipping_factors.SessionLocal")
    def test_calc_container_vessel_count_invalid_region(self, mock_session_local):
        """Test container count returns None for invalid region."""
        result = calc_container_vessel_count("invalid", date(2024, 6, 15))

        assert result is None

    @patch("src.transformations.factors.shipping_factors.SessionLocal")
    def test_calc_global_congestion_index(self, mock_session_local):
        """Test global congestion index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Avg vessels: 40, Avg wait: 12 hours
        mock_session.query.return_value.filter.return_value.first.return_value = (40.0, 12.0)

        result = calc_global_congestion_index(date(2024, 6, 15))

        # vessel_factor = min(40/50, 1) * 50 = 40
        # wait_factor = min(12/24, 1) * 50 = 25
        # total = 65
        assert result == 65.0


# =============================================================================
# Shipping Factor Class Tests
# =============================================================================

class TestShippingFactorClasses:
    """Test shipping factor classes."""

    def test_port_congestion_index_factor(self):
        """Test PortCongestionIndex factor class."""
        factor = PortCongestionIndex()
        assert factor.FACTOR_NAME == "port_congestion_index"
        assert factor.CATEGORY == "shipping"
        assert factor.ENTITY_TYPE == "port"

    def test_port_activity_change_factor(self):
        """Test PortActivityChange factor class."""
        factor = PortActivityChange()
        assert factor.FACTOR_NAME == "port_activity_change"
        assert "change" in factor.FACTOR_DESCRIPTION.lower()

    def test_container_vessel_count_factor(self):
        """Test ContainerVesselCount factor class."""
        factor = ContainerVesselCount()
        assert factor.FACTOR_NAME == "container_vessel_count"
        assert factor.ENTITY_TYPE == "region"

    def test_tanker_activity_index_factor(self):
        """Test TankerActivityIndex factor class."""
        factor = TankerActivityIndex()
        assert factor.FACTOR_NAME == "tanker_activity_index"
        assert factor.ENTITY_TYPE == "market"

    def test_global_congestion_index_factor(self):
        """Test GlobalCongestionIndex factor class."""
        factor = GlobalCongestionIndex()
        assert factor.FACTOR_NAME == "global_congestion_index"
        assert "congestion" in factor.FACTOR_DESCRIPTION.lower()

    def test_china_us_trade_flow_factor(self):
        """Test ChinaUSTradeFlow factor class."""
        factor = ChinaUSTradeFlow()
        assert factor.FACTOR_NAME == "china_us_trade_flow"
        assert factor.ENTITY_TYPE == "route"
        assert len(factor.CHINA_PORTS) > 0
        assert len(factor.US_PORTS) > 0

    @patch("src.transformations.factors.shipping_factors.calc_port_congestion_index")
    def test_port_congestion_compute(self, mock_calc):
        """Test PortCongestionIndex compute method."""
        mock_calc.return_value = 55.0

        factor = PortCongestionIndex()
        result = factor.compute("USLAX", datetime(2024, 6, 15))

        assert result == 55.0
        mock_calc.assert_called_once()

    @patch("src.transformations.factors.shipping_factors.calc_global_congestion_index")
    def test_global_congestion_compute(self, mock_calc):
        """Test GlobalCongestionIndex compute method."""
        mock_calc.return_value = 72.5

        factor = GlobalCongestionIndex()
        result = factor.compute("market", datetime(2024, 6, 15))

        assert result == 72.5


# =============================================================================
# Factor Registry Tests
# =============================================================================

class TestShippingFactorRegistry:
    """Test shipping factors in registry."""

    def test_shipping_factors_registered(self):
        """Test that all shipping factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        shipping_factors = [
            "port_congestion_index",
            "port_activity_change",
            "container_vessel_count",
            "tanker_activity_index",
            "global_congestion_index",
            "china_us_trade_flow",
        ]

        for factor in shipping_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_shipping_factors_category(self):
        """Test shipping factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        shipping_factors = [f for f in registered if f["category"] == "shipping"]

        assert len(shipping_factors) >= 6
