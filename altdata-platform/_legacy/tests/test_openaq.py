"""Tests for OpenAQ air quality collector and factors."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock


class TestAirQualityModels:
    """Tests for air quality database models."""

    def test_air_quality_location_model_creation(self):
        """Test AirQualityLocation model can be instantiated."""
        from src.models.air_quality import AirQualityLocation

        location = AirQualityLocation(
            location_id="US-123",
            name="Downtown Monitor",
            city="Los Angeles",
            country="US",
            latitude=34.0522,
            longitude=-118.2437,
            entity="government",
            sensor_type="reference grade",
        )

        assert location.location_id == "US-123"
        assert location.city == "Los Angeles"
        assert location.latitude == 34.0522

    def test_air_quality_measurement_model_creation(self):
        """Test AirQualityMeasurement model can be instantiated."""
        from src.models.air_quality import AirQualityMeasurement

        measurement = AirQualityMeasurement(
            location_id="US-123",
            timestamp=datetime.utcnow(),
            parameter="pm25",
            value=12.5,
            unit="ug/m3",
        )

        assert measurement.parameter == "pm25"
        assert measurement.value == 12.5
        assert measurement.unit == "ug/m3"

    def test_air_quality_daily_model_creation(self):
        """Test AirQualityDaily model can be instantiated."""
        from src.models.air_quality import AirQualityDaily

        daily = AirQualityDaily(
            location_id="US-123",
            date=datetime.utcnow(),
            parameter="pm25",
            avg_value=15.0,
            min_value=8.0,
            max_value=25.0,
            measurement_count=24,
            unit="ug/m3",
        )

        assert daily.avg_value == 15.0
        assert daily.measurement_count == 24

    def test_industrial_zone_model_creation(self):
        """Test IndustrialZone model can be instantiated."""
        from src.models.air_quality import IndustrialZone

        zone = IndustrialZone(
            zone_id="ZONE-001",
            name="Port of Los Angeles",
            city="Los Angeles",
            country="US",
            latitude=33.7398,
            longitude=-118.2623,
            radius_km=15.0,
            zone_type="port",
            associated_companies=["APL", "MAERSK"],
        )

        assert zone.zone_id == "ZONE-001"
        assert zone.zone_type == "port"
        assert zone.radius_km == 15.0


class TestOpenAQCollector:
    """Tests for OpenAQ collector."""

    @pytest.fixture
    def collector(self):
        from src.collectors.openaq import OpenAQCollector
        return OpenAQCollector()

    @pytest.fixture
    def sample_latest_response(self):
        return {
            "results": [
                {
                    "location": {
                        "id": 12345,
                        "name": "Downtown LA",
                        "city": "Los Angeles",
                        "country": {"code": "US"},
                        "coordinates": {"latitude": 34.05, "longitude": -118.24},
                    },
                    "measurements": [
                        {
                            "parameter": {"name": "pm25", "units": "ug/m3"},
                            "value": 12.5,
                            "datetime": {"utc": "2024-01-15T10:00:00Z"},
                        },
                        {
                            "parameter": {"name": "no2", "units": "ppb"},
                            "value": 25.0,
                            "datetime": {"utc": "2024-01-15T10:00:00Z"},
                        },
                    ],
                }
            ]
        }

    @pytest.fixture
    def sample_locations_response(self):
        return {
            "results": [
                {
                    "id": 12345,
                    "name": "Downtown LA Monitor",
                    "city": "Los Angeles",
                    "country": {"code": "US"},
                    "coordinates": {"latitude": 34.05, "longitude": -118.24},
                    "isMobile": False,
                    "entity": "government",
                    "sensorType": "reference grade",
                    "parameters": [
                        {"parameter": "pm25"},
                        {"parameter": "no2"},
                    ],
                }
            ]
        }

    def test_collector_source_name(self, collector):
        """Test collector source name."""
        assert collector.SOURCE_NAME == "openaq"

    def test_parse_latest_measurements(self, collector, sample_latest_response):
        """Test parsing latest measurements response."""
        parsed = collector.parse(sample_latest_response)

        assert len(parsed) == 2
        assert parsed[0]["location_id"] == "12345"
        assert parsed[0]["parameter"] == "pm25"
        assert parsed[0]["value"] == 12.5
        assert parsed[0]["city"] == "Los Angeles"
        assert parsed[1]["parameter"] == "no2"
        assert parsed[1]["value"] == 25.0

    def test_parse_locations(self, collector, sample_locations_response):
        """Test parsing locations response."""
        parsed = collector.parse_locations(sample_locations_response)

        assert len(parsed) == 1
        loc = parsed[0]
        assert loc["location_id"] == "12345"
        assert loc["name"] == "Downtown LA Monitor"
        assert loc["city"] == "Los Angeles"
        assert loc["latitude"] == 34.05
        assert "pm25" in loc["parameters"]

    def test_calculate_aqi_good(self, collector):
        """Test AQI calculation for good air quality."""
        # PM2.5 = 10 ug/m3 should be in "Good" range (0-50)
        aqi = collector.calculate_aqi(10.0)
        assert 0 <= aqi <= 50

    def test_calculate_aqi_moderate(self, collector):
        """Test AQI calculation for moderate air quality."""
        # PM2.5 = 20 ug/m3 should be in "Moderate" range (51-100)
        aqi = collector.calculate_aqi(20.0)
        assert 51 <= aqi <= 100

    def test_calculate_aqi_unhealthy_sensitive(self, collector):
        """Test AQI calculation for unhealthy (sensitive groups)."""
        # PM2.5 = 45 ug/m3 should be in USG range (101-150)
        aqi = collector.calculate_aqi(45.0)
        assert 101 <= aqi <= 150

    def test_calculate_aqi_unhealthy(self, collector):
        """Test AQI calculation for unhealthy air quality."""
        # PM2.5 = 100 ug/m3 should be in "Unhealthy" range (151-200)
        aqi = collector.calculate_aqi(100.0)
        assert 151 <= aqi <= 200

    def test_calculate_aqi_very_unhealthy(self, collector):
        """Test AQI calculation for very unhealthy."""
        # PM2.5 = 200 ug/m3 should be "Very Unhealthy" range (201-300)
        aqi = collector.calculate_aqi(200.0)
        assert 201 <= aqi <= 300

    def test_parse_timestamp(self, collector):
        """Test timestamp parsing."""
        ts = collector._parse_timestamp("2024-01-15T10:00:00Z")
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 15

    def test_parse_timestamp_none(self, collector):
        """Test timestamp parsing with None."""
        assert collector._parse_timestamp(None) is None

    @pytest.mark.asyncio
    async def test_collector_context_manager(self, collector):
        """Test async context manager."""
        async with collector:
            assert collector is not None
            assert collector.SOURCE_NAME == "openaq"


class TestAirQualityFactors:
    """Tests for air quality-derived factors."""

    def test_factor_registry_has_air_quality_factors(self):
        """Test that air quality factors are registered."""
        from src.transformations.base import FactorRegistry
        # Import to trigger registration
        from src.transformations.factors import air_quality_factors

        factors = FactorRegistry.get_all()

        assert "air_quality_anomaly" in factors
        assert "industrial_activity_proxy" in factors
        assert "pollution_trend" in factors
        assert "regional_aqi" in factors

    def test_air_quality_anomaly_factor_definition(self):
        """Test air quality anomaly factor definition."""
        from src.transformations.factors.air_quality_factors import AirQualityAnomaly

        factor = AirQualityAnomaly()
        definition = factor.get_definition()

        assert definition["id"] == "air_quality_anomaly"
        assert definition["category"] == "air_quality"
        assert definition["entity_type"] == "location"
        assert definition["frequency"] == "daily"

    def test_industrial_activity_proxy_factor_definition(self):
        """Test industrial activity proxy factor definition."""
        from src.transformations.factors.air_quality_factors import IndustrialActivityProxy

        factor = IndustrialActivityProxy()
        definition = factor.get_definition()

        assert definition["id"] == "industrial_activity_proxy"
        assert definition["category"] == "air_quality"
        assert definition["entity_type"] == "industrial_zone"

    def test_pollution_trend_factor_definition(self):
        """Test pollution trend factor definition."""
        from src.transformations.factors.air_quality_factors import PollutionTrend

        factor = PollutionTrend()
        definition = factor.get_definition()

        assert definition["id"] == "pollution_trend"
        assert definition["category"] == "air_quality"

    def test_regional_aqi_factor_definition(self):
        """Test regional AQI factor definition."""
        from src.transformations.factors.air_quality_factors import RegionalAQI

        factor = RegionalAQI()
        definition = factor.get_definition()

        assert definition["id"] == "regional_aqi"
        assert definition["category"] == "air_quality"
        assert definition["entity_type"] == "city"


class TestAirQualityDatabaseIntegration:
    """Integration tests for air quality with database."""

    def test_store_air_quality_measurement(self):
        """Test storing air quality measurement in database."""
        from src.models.database import SessionLocal
        from src.models.air_quality import AirQualityMeasurement

        session = SessionLocal()
        try:
            # Clean up
            session.query(AirQualityMeasurement).filter_by(
                location_id="TEST_LOC"
            ).delete()
            session.commit()

            # Insert
            measurement = AirQualityMeasurement(
                location_id="TEST_LOC",
                timestamp=datetime.utcnow(),
                parameter="pm25",
                value=15.5,
                unit="ug/m3",
            )
            session.add(measurement)
            session.commit()

            # Query
            result = session.query(AirQualityMeasurement).filter_by(
                location_id="TEST_LOC"
            ).first()
            assert result is not None
            assert result.parameter == "pm25"
            assert result.value == 15.5

            # Cleanup
            session.delete(result)
            session.commit()

        finally:
            session.close()

    def test_store_air_quality_location(self):
        """Test storing air quality location in database."""
        from src.models.database import SessionLocal
        from src.models.air_quality import AirQualityLocation

        session = SessionLocal()
        try:
            # Clean up
            session.query(AirQualityLocation).filter_by(
                location_id="TEST_LOC_2"
            ).delete()
            session.commit()

            # Insert
            location = AirQualityLocation(
                location_id="TEST_LOC_2",
                name="Test Monitor",
                city="Test City",
                country="US",
                latitude=40.0,
                longitude=-74.0,
            )
            session.add(location)
            session.commit()

            # Query
            result = session.query(AirQualityLocation).filter_by(
                location_id="TEST_LOC_2"
            ).first()
            assert result is not None
            assert result.name == "Test Monitor"
            assert result.latitude == 40.0

            # Cleanup
            session.delete(result)
            session.commit()

        finally:
            session.close()

    def test_calc_air_quality_anomaly_with_data(self):
        """Test air quality anomaly calculation with test data."""
        from src.models.database import SessionLocal
        from src.models.air_quality import AirQualityMeasurement
        from src.transformations.factors.air_quality_factors import calc_air_quality_anomaly

        session = SessionLocal()
        try:
            # Clean up
            session.query(AirQualityMeasurement).filter_by(
                location_id="ANOMALY_TEST"
            ).delete()
            session.commit()

            now = datetime.utcnow()

            # Insert baseline data (avg=10, std~=0)
            for i in range(30):
                measurement = AirQualityMeasurement(
                    location_id="ANOMALY_TEST",
                    timestamp=now - timedelta(days=i+1),
                    parameter="pm25",
                    value=10.0 + (i % 3 - 1),  # Values around 10
                    unit="ug/m3",
                )
                session.add(measurement)

            # Insert current day data with anomaly (high value)
            anomaly_measurement = AirQualityMeasurement(
                location_id="ANOMALY_TEST",
                timestamp=now,
                parameter="pm25",
                value=25.0,  # Significantly higher
                unit="ug/m3",
            )
            session.add(anomaly_measurement)
            session.commit()

            # Calculate anomaly
            anomaly = calc_air_quality_anomaly(
                "ANOMALY_TEST",
                now,
                "pm25",
                lookback_days=30
            )

            assert anomaly is not None
            # Should be positive z-score (above baseline)
            assert anomaly > 0

            # Cleanup
            session.query(AirQualityMeasurement).filter_by(
                location_id="ANOMALY_TEST"
            ).delete()
            session.commit()

        finally:
            session.close()
