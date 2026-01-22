"""Tests for weather data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from src.collectors.weather import OpenWeatherMapCollector
from src.models.weather import (
    WeatherObservation,
    WeatherForecast,
    WeatherAlert,
    WeatherDaily,
)
from src.transformations.factors.weather_factors import (
    calc_heating_degree_days,
    calc_cooling_degree_days,
    calc_retail_weather_index,
    calc_agricultural_stress_index,
    calc_weather_yoy_anomaly,
    calc_precipitation_anomaly,
    HeatingDegreeDays,
    CoolingDegreeDays,
    RetailWeatherIndex,
    AgriculturalStressIndex,
    WeatherYoYAnomaly,
    PrecipitationAnomaly,
)


# =============================================================================
# Weather Model Tests
# =============================================================================

class TestWeatherModels:
    """Test weather database models."""

    def test_weather_observation_model(self):
        """Test WeatherObservation model creation."""
        obs = WeatherObservation(
            location_id="new_york_us",
            city="New York",
            country="US",
            latitude=40.7128,
            longitude=-74.0060,
            timestamp=datetime.utcnow(),
            temp_c=22.5,
            temp_feels_like_c=23.1,
            humidity_pct=65,
            pressure_hpa=1013,
            wind_speed_ms=5.2,
            weather_main="Clear",
        )
        assert obs.location_id == "new_york_us"
        assert obs.temp_c == 22.5
        assert obs.weather_main == "Clear"

    def test_weather_forecast_model(self):
        """Test WeatherForecast model creation."""
        forecast = WeatherForecast(
            location_id="chicago_us",
            city="Chicago",
            country="US",
            forecast_timestamp=datetime.utcnow() + timedelta(days=1),
            fetched_at=datetime.utcnow(),
            temp_c=18.0,
            pop=0.3,
            weather_main="Clouds",
        )
        assert forecast.location_id == "chicago_us"
        assert forecast.pop == 0.3

    def test_weather_alert_model(self):
        """Test WeatherAlert model creation."""
        alert = WeatherAlert(
            location_id="miami_us",
            alert_id="NWS-ALERT-123",
            sender="NWS",
            event="Hurricane",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(days=2),
            severity="Extreme",
            description="Hurricane warning in effect",
        )
        assert alert.event == "Hurricane"
        assert alert.severity == "Extreme"

    def test_weather_daily_model(self):
        """Test WeatherDaily model creation."""
        daily = WeatherDaily(
            location_id="denver_us",
            date=date.today(),
            temp_avg_c=15.0,
            temp_min_c=8.0,
            temp_max_c=22.0,
            precipitation_mm=2.5,
            heating_degree_days=3.0,
            cooling_degree_days=0.0,
        )
        assert daily.temp_avg_c == 15.0
        assert daily.heating_degree_days == 3.0


# =============================================================================
# Weather Collector Tests
# =============================================================================

class TestOpenWeatherMapCollector:
    """Test OpenWeatherMap collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = OpenWeatherMapCollector(api_key="test_key")
        assert collector.api_key == "test_key"
        assert collector.SOURCE_NAME == "openweathermap"

    def test_tracked_cities(self):
        """Test tracked cities configuration."""
        collector = OpenWeatherMapCollector()
        assert len(collector.TRACKED_CITIES) >= 10
        # Check for key cities
        city_names = [c["city"] for c in collector.TRACKED_CITIES]
        assert "New York" in city_names
        assert "Los Angeles" in city_names
        assert "Chicago" in city_names

    def test_parse_current_weather(self):
        """Test parsing current weather response."""
        collector = OpenWeatherMapCollector()
        raw_data = {
            "_city_info": {"city": "New York", "country": "US"},
            "coord": {"lat": 40.7128, "lon": -74.0060},
            "dt": 1700000000,
            "main": {
                "temp": 20.5,
                "feels_like": 19.8,
                "temp_min": 18.0,
                "temp_max": 22.0,
                "humidity": 60,
                "pressure": 1015,
            },
            "wind": {"speed": 4.5, "deg": 180, "gust": 7.2},
            "clouds": {"all": 25},
            "visibility": 10000,
            "rain": {"1h": 0.5},
            "weather": [{"main": "Rain", "description": "light rain", "icon": "10d"}],
        }

        parsed = collector.parse_current(raw_data)

        assert parsed["location_id"] == "new_york_us"
        assert parsed["temp_c"] == 20.5
        assert parsed["humidity_pct"] == 60
        assert parsed["wind_speed_ms"] == 4.5
        assert parsed["rain_1h_mm"] == 0.5
        assert parsed["weather_main"] == "Rain"

    def test_parse_forecast(self):
        """Test parsing forecast response."""
        collector = OpenWeatherMapCollector()
        raw_data = {
            "city": {"name": "Chicago", "country": "US", "coord": {"lat": 41.8781, "lon": -87.6298}},
            "list": [
                {
                    "dt": 1700000000,
                    "main": {"temp": 15.0, "feels_like": 14.0, "humidity": 70},
                    "clouds": {"all": 50},
                    "wind": {"speed": 3.0},
                    "pop": 0.2,
                    "rain": {"3h": 1.0},
                    "weather": [{"main": "Clouds"}],
                },
                {
                    "dt": 1700010800,
                    "main": {"temp": 12.0, "feels_like": 11.0, "humidity": 75},
                    "clouds": {"all": 80},
                    "wind": {"speed": 4.0},
                    "pop": 0.5,
                    "rain": {"3h": 3.0},
                    "weather": [{"main": "Rain"}],
                },
            ],
        }

        parsed = collector.parse_forecast(raw_data)

        assert len(parsed) == 2
        assert parsed[0]["location_id"] == "chicago_us"
        assert parsed[0]["temp_c"] == 15.0
        assert parsed[0]["pop"] == 0.2
        assert parsed[1]["weather_main"] == "Rain"

    def test_calculate_degree_days(self):
        """Test degree day calculations."""
        collector = OpenWeatherMapCollector()

        # Cold day
        hdd, cdd = collector.calculate_degree_days(10.0, base_temp=18.0)
        assert hdd == 8.0
        assert cdd == 0.0

        # Hot day
        hdd, cdd = collector.calculate_degree_days(25.0, base_temp=18.0)
        assert hdd == 0.0
        assert cdd == 7.0

        # At base temp
        hdd, cdd = collector.calculate_degree_days(18.0, base_temp=18.0)
        assert hdd == 0.0
        assert cdd == 0.0

    def test_fetch_current_weather_no_api_key(self):
        """Test fetch fails without API key."""
        import asyncio
        collector = OpenWeatherMapCollector(api_key=None)
        # Reset to None explicitly
        collector.api_key = None

        with pytest.raises(Exception) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                collector.fetch_current_weather(40.7128, -74.0060)
            )
        assert "API key" in str(exc_info.value)

    def test_api_url_configuration(self):
        """Test API URL configuration."""
        collector = OpenWeatherMapCollector(api_key="test_key")
        assert "api.openweathermap.org" in collector.BASE_URL
        assert "3.0" in collector.ONE_CALL_URL

    def test_parse_handles_missing_data(self):
        """Test parsing handles missing optional fields."""
        collector = OpenWeatherMapCollector()
        raw_data = {
            "_city_info": {"city": "Test", "country": "XX"},
            "dt": 1700000000,
            "main": {"temp": 15.0},
            "weather": [{}],
        }

        parsed = collector.parse_current(raw_data)

        assert parsed["temp_c"] == 15.0
        assert parsed["rain_1h_mm"] is None
        assert parsed["wind_speed_ms"] is None


# =============================================================================
# Weather Factor Calculation Tests
# =============================================================================

class TestWeatherFactorCalculations:
    """Test weather factor calculation functions."""

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_heating_degree_days(self, mock_session_local):
        """Test HDD calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock query results - 3 days with avg temps 5, 10, 15
        mock_results = [
            MagicMock(obs_date=date(2024, 1, 1), avg_temp=5.0),
            MagicMock(obs_date=date(2024, 1, 2), avg_temp=10.0),
            MagicMock(obs_date=date(2024, 1, 3), avg_temp=15.0),
        ]
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_results

        result = calc_heating_degree_days(
            "new_york_us",
            datetime(2024, 1, 1),
            datetime(2024, 1, 3),
            base_temp=18.0,
        )

        # HDD = (18-5) + (18-10) + (18-15) = 13 + 8 + 3 = 24
        assert result == 24.0
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_cooling_degree_days(self, mock_session_local):
        """Test CDD calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock query results - 3 days with avg temps 20, 25, 30
        mock_results = [
            MagicMock(obs_date=date(2024, 7, 1), avg_temp=20.0),
            MagicMock(obs_date=date(2024, 7, 2), avg_temp=25.0),
            MagicMock(obs_date=date(2024, 7, 3), avg_temp=30.0),
        ]
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_results

        result = calc_cooling_degree_days(
            "phoenix_us",
            datetime(2024, 7, 1),
            datetime(2024, 7, 3),
            base_temp=18.0,
        )

        # CDD = (20-18) + (25-18) + (30-18) = 2 + 7 + 12 = 21
        assert result == 21.0

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_heating_degree_days_no_data(self, mock_session_local):
        """Test HDD returns None when no data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        result = calc_heating_degree_days(
            "unknown_location",
            datetime(2024, 1, 1),
            datetime(2024, 1, 3),
        )

        assert result is None

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_retail_weather_index(self, mock_session_local):
        """Test retail weather index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Perfect weather: 20C, no rain, low wind
        mock_obs = MagicMock()
        mock_obs.temp_c = 20.0
        mock_obs.rain_1h_mm = 0
        mock_obs.snow_1h_mm = 0
        mock_obs.wind_speed_ms = 3.0

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_obs

        result = calc_retail_weather_index(["new_york_us"], date(2024, 6, 15))

        # Perfect weather should give score of 100
        assert result == 100.0

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_retail_weather_index_bad_weather(self, mock_session_local):
        """Test retail weather index with bad weather."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Bad weather: cold, rainy, windy
        mock_obs = MagicMock()
        mock_obs.temp_c = 2.0  # Very cold: -40
        mock_obs.rain_1h_mm = 10.0  # Heavy rain: -30
        mock_obs.snow_1h_mm = 0
        mock_obs.wind_speed_ms = 20.0  # Strong wind: -20

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_obs

        result = calc_retail_weather_index(["chicago_us"], date(2024, 1, 15))

        # 100 - 40 - 30 - 20 = 10
        assert result == 10.0

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_agricultural_stress_index(self, mock_session_local):
        """Test agricultural stress index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Create observations with various stress conditions
        obs1 = MagicMock(temp_c=36.0, humidity_pct=50, rain_1h_mm=0)  # Heat stress: +2
        obs2 = MagicMock(temp_c=-2.0, humidity_pct=60, rain_1h_mm=0)  # Frost stress: +3
        obs3 = MagicMock(temp_c=28.0, humidity_pct=25, rain_1h_mm=None)  # Drought: +1

        mock_session.query.return_value.filter.return_value.all.return_value = [obs1, obs2, obs3]

        result = calc_agricultural_stress_index(
            "midwest",
            datetime(2024, 6, 1),
            datetime(2024, 6, 7),
        )

        # Total stress = (2 + 3 + 1) / 3 observations = 2.0
        assert result == 2.0

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_agricultural_stress_invalid_region(self, mock_session_local):
        """Test agricultural stress returns None for invalid region."""
        result = calc_agricultural_stress_index(
            "invalid_region",
            datetime(2024, 6, 1),
            datetime(2024, 6, 7),
        )
        assert result is None

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_weather_yoy_anomaly(self, mock_session_local):
        """Test YoY weather anomaly calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current year avg: 25C, prior year avg: 20C
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [25.0, 20.0]

        result = calc_weather_yoy_anomaly("new_york_us", date(2024, 7, 15))

        # Anomaly = 25 - 20 = 5
        assert result == 5.0

    @patch("src.transformations.factors.weather_factors.SessionLocal")
    def test_calc_precipitation_anomaly(self, mock_session_local):
        """Test precipitation anomaly calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current period: 50mm, prior year: 30mm
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [50.0, 30.0]

        result = calc_precipitation_anomaly("seattle_us", date(2024, 4, 15), lookback_days=30)

        # Anomaly = 50 - 30 = 20
        assert result == 20.0


# =============================================================================
# Weather Factor Class Tests
# =============================================================================

class TestWeatherFactorClasses:
    """Test weather factor classes."""

    def test_heating_degree_days_factor(self):
        """Test HeatingDegreeDays factor class."""
        factor = HeatingDegreeDays()
        assert factor.FACTOR_NAME == "heating_degree_days"
        assert factor.CATEGORY == "weather"
        assert factor.ENTITY_TYPE == "location"

    def test_cooling_degree_days_factor(self):
        """Test CoolingDegreeDays factor class."""
        factor = CoolingDegreeDays()
        assert factor.FACTOR_NAME == "cooling_degree_days"
        assert factor.CATEGORY == "weather"

    def test_retail_weather_index_factor(self):
        """Test RetailWeatherIndex factor class."""
        factor = RetailWeatherIndex()
        assert factor.FACTOR_NAME == "retail_weather_index"
        assert factor.ENTITY_TYPE == "market"
        assert len(factor.DEFAULT_CITIES) >= 6

    def test_agricultural_stress_index_factor(self):
        """Test AgriculturalStressIndex factor class."""
        factor = AgriculturalStressIndex()
        assert factor.FACTOR_NAME == "agricultural_stress_index"
        assert factor.ENTITY_TYPE == "region"

    def test_weather_yoy_anomaly_factor(self):
        """Test WeatherYoYAnomaly factor class."""
        factor = WeatherYoYAnomaly()
        assert factor.FACTOR_NAME == "weather_yoy_anomaly"
        assert "temperature" in factor.FACTOR_DESCRIPTION.lower() or "anomaly" in factor.FACTOR_DESCRIPTION.lower()

    def test_precipitation_anomaly_factor(self):
        """Test PrecipitationAnomaly factor class."""
        factor = PrecipitationAnomaly()
        assert factor.FACTOR_NAME == "precipitation_anomaly"
        assert factor.LOOKBACK_DAYS == 30

    @patch("src.transformations.factors.weather_factors.calc_heating_degree_days")
    def test_heating_degree_days_compute(self, mock_calc):
        """Test HeatingDegreeDays compute method."""
        mock_calc.return_value = 50.0

        factor = HeatingDegreeDays()
        result = factor.compute("chicago_us", datetime(2024, 1, 15))

        assert result == 50.0
        mock_calc.assert_called_once()

    @patch("src.transformations.factors.weather_factors.calc_retail_weather_index")
    def test_retail_weather_index_compute(self, mock_calc):
        """Test RetailWeatherIndex compute method."""
        mock_calc.return_value = 85.0

        factor = RetailWeatherIndex()
        result = factor.compute("market_us", datetime(2024, 6, 15))

        assert result == 85.0


# =============================================================================
# Factor Registry Tests
# =============================================================================

class TestWeatherFactorRegistry:
    """Test weather factors in registry."""

    def test_weather_factors_registered(self):
        """Test that all weather factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        weather_factors = [
            "heating_degree_days",
            "cooling_degree_days",
            "retail_weather_index",
            "agricultural_stress_index",
            "weather_yoy_anomaly",
            "precipitation_anomaly",
        ]

        for factor in weather_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_weather_factors_category(self):
        """Test weather factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        weather_factors = [f for f in registered if f["category"] == "weather"]

        assert len(weather_factors) >= 6
