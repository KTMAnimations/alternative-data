"""Tests for ADS-B Exchange collector and aviation factors."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock


class TestADSBCollector:
    """Tests for ADS-B Exchange collector."""

    @pytest.fixture
    def collector(self):
        from src.collectors.adsb_exchange import ADSBExchangeCollector
        return ADSBExchangeCollector(
            api_key="test_key",
            rapidapi_key="test_rapidapi_key"
        )

    @pytest.fixture
    def sample_aircraft_response(self):
        return {
            "ac": [{
                "hex": "A12345",
                "r": "N123AB",
                "t": "GLF6",
                "lat": 40.7128,
                "lon": -74.0060,
                "alt_baro": 35000,
                "gs": 450,
                "track": 270,
                "baro_rate": -500,
                "squawk": "1200",
                "flight": "  N123AB  ",
            }]
        }

    @pytest.fixture
    def sample_multi_aircraft(self):
        return [
            {
                "hex": "A12345",
                "r": "N123AB",
                "t": "GLF6",
                "lat": 40.7128,
                "lon": -74.0060,
                "alt_baro": 35000,
                "gs": 450,
                "track": 270,
            },
            {
                "hex": "B67890",
                "r": "N456CD",
                "t": "G650",
                "lat": 34.0522,
                "lon": -118.2437,
                "alt_baro": "ground",
                "gs": 0,
                "track": 90,
            }
        ]

    def test_parse_aircraft_data(self, collector, sample_aircraft_response):
        """Test parsing aircraft position data."""
        result = collector.parse(sample_aircraft_response["ac"])

        assert len(result) == 1
        assert result[0]["icao_hex"] == "A12345"
        assert result[0]["registration"] == "N123AB"
        assert result[0]["aircraft_type"] == "GLF6"
        assert result[0]["latitude"] == 40.7128
        assert result[0]["longitude"] == -74.0060
        assert result[0]["altitude_ft"] == 35000
        assert result[0]["ground_speed_knots"] == 450
        assert result[0]["heading"] == 270
        assert result[0]["vertical_rate"] == -500
        assert result[0]["flight_id"] == "N123AB"
        assert result[0]["on_ground"] is False

    def test_parse_ground_aircraft(self, collector, sample_multi_aircraft):
        """Test parsing aircraft on ground."""
        result = collector.parse(sample_multi_aircraft)

        assert len(result) == 2

        # First aircraft is in flight
        assert result[0]["on_ground"] is False
        assert result[0]["altitude_ft"] == 35000

        # Second aircraft is on ground
        assert result[1]["on_ground"] is True
        assert result[1]["altitude_ft"] == 0

    def test_is_corporate_jet(self, collector):
        """Test corporate jet type detection."""
        # Corporate jets
        assert collector.is_corporate_jet("GLF6") is True
        assert collector.is_corporate_jet("G650") is True
        assert collector.is_corporate_jet("CL35") is True

        # Non-corporate jets
        assert collector.is_corporate_jet("B738") is False
        assert collector.is_corporate_jet("A320") is False
        assert collector.is_corporate_jet("C172") is False

    def test_detect_landing_altitude_drop(self, collector):
        """Test landing detection via altitude drop."""
        positions = [
            {"icao_hex": "A12345", "altitude_ft": 5000, "on_ground": False,
             "timestamp": datetime(2024, 1, 15, 10, 0), "latitude": 40.7, "longitude": -74.0},
            {"icao_hex": "A12345", "altitude_ft": 2000, "on_ground": False,
             "timestamp": datetime(2024, 1, 15, 10, 5), "latitude": 40.7, "longitude": -74.0},
            {"icao_hex": "A12345", "altitude_ft": 500, "on_ground": False,
             "timestamp": datetime(2024, 1, 15, 10, 10), "latitude": 40.7, "longitude": -74.0},
        ]

        result = collector.detect_landing(positions)

        assert result is not None
        assert result["icao_hex"] == "A12345"
        assert result["latitude"] == 40.7

    def test_detect_landing_on_ground(self, collector):
        """Test landing detection via on_ground transition."""
        positions = [
            {"icao_hex": "A12345", "altitude_ft": 500, "on_ground": False,
             "timestamp": datetime(2024, 1, 15, 10, 0), "latitude": 40.7, "longitude": -74.0},
            {"icao_hex": "A12345", "altitude_ft": 0, "on_ground": True,
             "timestamp": datetime(2024, 1, 15, 10, 5), "latitude": 40.7, "longitude": -74.0},
        ]

        result = collector.detect_landing(positions)

        assert result is not None
        assert result["icao_hex"] == "A12345"
        assert result["latitude"] == 40.7

    def test_detect_no_landing(self, collector):
        """Test no landing detected when cruising."""
        positions = [
            {"icao_hex": "A12345", "altitude_ft": 35000, "on_ground": False,
             "timestamp": datetime(2024, 1, 15, 10, 0), "latitude": 40.7, "longitude": -74.0},
            {"icao_hex": "A12345", "altitude_ft": 35000, "on_ground": False,
             "timestamp": datetime(2024, 1, 15, 10, 5), "latitude": 40.8, "longitude": -74.1},
        ]

        result = collector.detect_landing(positions)
        assert result is None

    def test_detect_landing_insufficient_data(self, collector):
        """Test landing detection with insufficient data."""
        positions = [
            {"icao_hex": "A12345", "altitude_ft": 35000, "on_ground": False,
             "timestamp": datetime(2024, 1, 15, 10, 0), "latitude": 40.7, "longitude": -74.0},
        ]

        result = collector.detect_landing(positions)
        assert result is None

    def test_collector_source_name(self, collector):
        """Test source name is correct."""
        assert collector.SOURCE_NAME == "adsb_exchange"

    def test_collector_rate_limit(self):
        """Test rate limit configuration."""
        from src.collectors.adsb_exchange import ADSBExchangeCollector

        collector = ADSBExchangeCollector(
            api_key="test",
            rapidapi_key="test",
            rate_limit=2.0
        )
        assert collector.rate_limiter.min_interval == 0.5

    @pytest.mark.asyncio
    async def test_collector_context_manager(self, collector):
        """Test async context manager."""
        async with collector:
            assert collector is not None
            assert collector.SOURCE_NAME == "adsb_exchange"


class TestAviationFactors:
    """Tests for aviation-derived factors."""

    def test_unusual_destination_new_location(self):
        """Test unusual destination detection for new location."""
        from src.transformations.factors.aviation_factors import calc_unusual_destination_alert

        current = {"latitude": 37.7749, "longitude": -122.4194}  # San Francisco
        historical = [
            {"latitude": 40.7128, "longitude": -74.0060},  # NYC
            {"latitude": 34.0522, "longitude": -118.2437},  # LA
        ]

        result = calc_unusual_destination_alert(current, historical)
        assert result == 1  # SF is new

    def test_unusual_destination_known_location(self):
        """Test unusual destination returns 0 for known location."""
        from src.transformations.factors.aviation_factors import calc_unusual_destination_alert

        current = {"latitude": 40.7128, "longitude": -74.0060}  # NYC
        historical = [
            {"latitude": 40.7130, "longitude": -74.0062},  # Near NYC
            {"latitude": 34.0522, "longitude": -118.2437},  # LA
        ]

        result = calc_unusual_destination_alert(current, historical)
        assert result == 0  # Already visited

    def test_unusual_destination_empty_history(self):
        """Test unusual destination with no history."""
        from src.transformations.factors.aviation_factors import calc_unusual_destination_alert

        current = {"latitude": 40.7128, "longitude": -74.0060}
        historical = []

        result = calc_unusual_destination_alert(current, historical)
        assert result == 1  # First destination is always unusual

    def test_unusual_destination_missing_coords(self):
        """Test unusual destination with missing coordinates."""
        from src.transformations.factors.aviation_factors import calc_unusual_destination_alert

        current = {"latitude": None, "longitude": None}
        historical = [{"latitude": 40.7128, "longitude": -74.0060}]

        result = calc_unusual_destination_alert(current, historical)
        assert result == 0  # Cannot determine

    def test_factor_registry_has_aviation_factors(self):
        """Test that aviation factors are registered."""
        from src.transformations.base import FactorRegistry
        # Import to trigger registration
        from src.transformations.factors import aviation_factors

        factors = FactorRegistry.get_all()

        assert "executive_flight_frequency" in factors
        assert "unusual_destination_alert" in factors
        assert "multi_company_colocation" in factors

    def test_executive_flight_frequency_factor_definition(self):
        """Test executive flight frequency factor definition."""
        from src.transformations.factors.aviation_factors import ExecutiveFlightFrequency

        factor = ExecutiveFlightFrequency()
        definition = factor.get_definition()

        assert definition["id"] == "executive_flight_frequency"
        assert definition["category"] == "aviation"
        assert definition["frequency"] == "weekly"


class TestADSBModels:
    """Tests for ADS-B database models."""

    def test_aircraft_model_creation(self):
        """Test Aircraft model can be instantiated."""
        from src.models.adsb import Aircraft

        aircraft = Aircraft(
            icao_hex="A12345",
            registration="N123AB",
            aircraft_type="GLF6",
            owner_name="Test Corp",
            is_corporate_jet=True,
        )

        assert aircraft.icao_hex == "A12345"
        assert aircraft.registration == "N123AB"
        assert aircraft.is_corporate_jet is True

    def test_flight_position_model_creation(self):
        """Test FlightPosition model can be instantiated."""
        from src.models.adsb import FlightPosition

        position = FlightPosition(
            icao_hex="A12345",
            timestamp=datetime.utcnow(),
            latitude=40.7128,
            longitude=-74.0060,
            altitude_ft=35000,
            ground_speed_knots=450,
            heading=270,
            on_ground=False,
        )

        assert position.latitude == 40.7128
        assert position.altitude_ft == 35000

    def test_flight_landing_model_creation(self):
        """Test FlightLanding model can be instantiated."""
        from src.models.adsb import FlightLanding

        landing = FlightLanding(
            icao_hex="A12345",
            landing_timestamp=datetime.utcnow(),
            airport_icao="KJFK",
            latitude=40.6413,
            longitude=-73.7781,
        )

        assert landing.airport_icao == "KJFK"

    def test_airport_model_creation(self):
        """Test Airport model can be instantiated."""
        from src.models.adsb import Airport

        airport = Airport(
            icao_code="KJFK",
            iata_code="JFK",
            name="John F Kennedy International",
            city="New York",
            country="United States",
            latitude=40.6413,
            longitude=-73.7781,
        )

        assert airport.icao_code == "KJFK"
        assert airport.iata_code == "JFK"

    def test_company_hq_model_creation(self):
        """Test CompanyHQ model can be instantiated."""
        from src.models.adsb import CompanyHQ

        hq = CompanyHQ(
            entity_id="AAPL",
            company_name="Apple Inc.",
            city="Cupertino",
            state="CA",
            country="United States",
            latitude=37.3349,
            longitude=-122.0090,
        )

        assert hq.entity_id == "AAPL"
        assert hq.latitude == 37.3349


class TestADSBDatabaseIntegration:
    """Integration tests for ADS-B with database."""

    def test_store_aircraft(self):
        """Test storing aircraft in database."""
        from src.models.database import SessionLocal
        from src.models.adsb import Aircraft

        session = SessionLocal()
        try:
            # Clean up
            session.query(Aircraft).filter_by(icao_hex="TEST123").delete()
            session.commit()

            # Insert
            aircraft = Aircraft(
                icao_hex="TEST123",
                registration="NTEST",
                aircraft_type="G650",
                is_corporate_jet=True,
            )
            session.add(aircraft)
            session.commit()

            # Query
            result = session.query(Aircraft).filter_by(icao_hex="TEST123").first()
            assert result is not None
            assert result.registration == "NTEST"

            # Cleanup
            session.delete(result)
            session.commit()

        finally:
            session.close()

    def test_store_flight_position(self):
        """Test storing flight positions."""
        from src.models.database import SessionLocal
        from src.models.adsb import FlightPosition

        session = SessionLocal()
        try:
            position = FlightPosition(
                icao_hex="TESTPOS",
                timestamp=datetime.utcnow(),
                latitude=40.7128,
                longitude=-74.0060,
                altitude_ft=30000,
                on_ground=False,
            )
            session.add(position)
            session.commit()

            result = session.query(FlightPosition).filter_by(icao_hex="TESTPOS").first()
            assert result is not None
            assert result.altitude_ft == 30000

            session.delete(result)
            session.commit()

        finally:
            session.close()
