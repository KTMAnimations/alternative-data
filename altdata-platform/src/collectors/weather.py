"""OpenWeatherMap collector for weather data."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.weather import WeatherObservation, WeatherForecast, WeatherDaily

logger = logging.getLogger(__name__)


class OpenWeatherMapCollector(BaseCollector[Dict, Dict]):
    """Collector for OpenWeatherMap API data.

    Tracks weather patterns affecting retail, agriculture, and energy sectors.
    """

    SOURCE_NAME = "openweathermap"
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    ONE_CALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
    DEFAULT_RATE_LIMIT = 1.0  # Free tier: 60 calls/min

    # Key cities for retail/economic tracking
    TRACKED_CITIES = [
        # Major US metros (retail, energy demand)
        {"city": "New York", "country": "US", "lat": 40.7128, "lon": -74.0060},
        {"city": "Los Angeles", "country": "US", "lat": 34.0522, "lon": -118.2437},
        {"city": "Chicago", "country": "US", "lat": 41.8781, "lon": -87.6298},
        {"city": "Houston", "country": "US", "lat": 29.7604, "lon": -95.3698},
        {"city": "Phoenix", "country": "US", "lat": 33.4484, "lon": -112.0740},
        {"city": "Dallas", "country": "US", "lat": 32.7767, "lon": -96.7970},
        {"city": "Atlanta", "country": "US", "lat": 33.7490, "lon": -84.3880},
        {"city": "Miami", "country": "US", "lat": 25.7617, "lon": -80.1918},
        {"city": "Seattle", "country": "US", "lat": 47.6062, "lon": -122.3321},
        {"city": "Denver", "country": "US", "lat": 39.7392, "lon": -104.9903},

        # Agricultural regions
        {"city": "Des Moines", "country": "US", "lat": 41.5868, "lon": -93.6250},  # Corn belt
        {"city": "Fresno", "country": "US", "lat": 36.7378, "lon": -119.7871},  # California ag
        {"city": "Omaha", "country": "US", "lat": 41.2565, "lon": -95.9345},  # Midwest ag

        # International (for global retail/supply chain)
        {"city": "London", "country": "GB", "lat": 51.5074, "lon": -0.1278},
        {"city": "Tokyo", "country": "JP", "lat": 35.6762, "lon": 139.6503},
        {"city": "Shanghai", "country": "CN", "lat": 31.2304, "lon": 121.4737},
        {"city": "Frankfurt", "country": "DE", "lat": 50.1109, "lon": 8.6821},
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the OpenWeatherMap collector.

        Args:
            api_key: OpenWeatherMap API key
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.api_key = api_key or getattr(settings, 'openweathermap_api_key', None)

    async def fetch(self) -> List[Dict]:
        """Fetch weather for all tracked cities.

        Returns:
            List of weather data dicts
        """
        return await self.fetch_all_tracked_cities()

    async def fetch_current_weather(self, lat: float, lon: float) -> Dict:
        """Fetch current weather for a location.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Weather data dict
        """
        if not self.api_key:
            raise CollectorError("OpenWeatherMap API key not configured")

        await self.rate_limiter.wait()

        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric"
        }

        response = await self.http_client.get(
            f"{self.BASE_URL}/weather",
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def fetch_forecast(
        self,
        lat: float,
        lon: float,
        days: int = 5
    ) -> Dict:
        """Fetch weather forecast.

        Args:
            lat: Latitude
            lon: Longitude
            days: Number of days to forecast

        Returns:
            Forecast data dict
        """
        if not self.api_key:
            raise CollectorError("OpenWeatherMap API key not configured")

        await self.rate_limiter.wait()

        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
            "cnt": days * 8  # 3-hour intervals
        }

        response = await self.http_client.get(
            f"{self.BASE_URL}/forecast",
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def fetch_all_tracked_cities(self) -> List[Dict]:
        """Fetch current weather for all tracked cities.

        Returns:
            List of weather data for each city
        """
        results = []
        for city in self.TRACKED_CITIES:
            try:
                data = await self.fetch_current_weather(city["lat"], city["lon"])
                data["_city_info"] = city
                results.append(data)
            except Exception as e:
                logger.warning(f"Failed to fetch weather for {city['city']}: {e}")
        return results

    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """Parse weather API responses.

        Args:
            raw_data: List of raw API responses

        Returns:
            List of parsed weather dicts
        """
        parsed = []
        for data in raw_data:
            try:
                parsed.append(self.parse_current(data))
            except Exception as e:
                logger.warning(f"Failed to parse weather data: {e}")
        return parsed

    def parse_current(self, raw_data: Dict) -> Dict:
        """Parse current weather response.

        Args:
            raw_data: Raw API response

        Returns:
            Parsed weather dict
        """
        city_info = raw_data.get("_city_info", {})

        location_id = f"{city_info.get('city', 'unknown')}_{city_info.get('country', 'XX')}".lower().replace(" ", "_")

        return {
            "location_id": location_id,
            "city": city_info.get("city") or raw_data.get("name"),
            "country": city_info.get("country") or raw_data.get("sys", {}).get("country"),
            "latitude": raw_data.get("coord", {}).get("lat"),
            "longitude": raw_data.get("coord", {}).get("lon"),
            "timestamp": datetime.utcfromtimestamp(raw_data.get("dt", 0)),

            "temp_c": raw_data.get("main", {}).get("temp"),
            "temp_feels_like_c": raw_data.get("main", {}).get("feels_like"),
            "temp_min_c": raw_data.get("main", {}).get("temp_min"),
            "temp_max_c": raw_data.get("main", {}).get("temp_max"),

            "humidity_pct": raw_data.get("main", {}).get("humidity"),
            "pressure_hpa": raw_data.get("main", {}).get("pressure"),
            "visibility_m": raw_data.get("visibility"),
            "cloud_cover_pct": raw_data.get("clouds", {}).get("all"),

            "wind_speed_ms": raw_data.get("wind", {}).get("speed"),
            "wind_gust_ms": raw_data.get("wind", {}).get("gust"),
            "wind_direction_deg": raw_data.get("wind", {}).get("deg"),

            "rain_1h_mm": raw_data.get("rain", {}).get("1h"),
            "rain_3h_mm": raw_data.get("rain", {}).get("3h"),
            "snow_1h_mm": raw_data.get("snow", {}).get("1h"),
            "snow_3h_mm": raw_data.get("snow", {}).get("3h"),

            "weather_main": raw_data.get("weather", [{}])[0].get("main"),
            "weather_description": raw_data.get("weather", [{}])[0].get("description"),
            "weather_icon": raw_data.get("weather", [{}])[0].get("icon"),
        }

    def parse_forecast(self, raw_data: Dict) -> List[Dict]:
        """Parse forecast response.

        Args:
            raw_data: Raw forecast API response

        Returns:
            List of parsed forecast dicts
        """
        city = raw_data.get("city", {})
        location_id = f"{city.get('name', 'unknown')}_{city.get('country', 'XX')}".lower().replace(" ", "_")

        parsed = []
        for item in raw_data.get("list", []):
            parsed.append({
                "location_id": location_id,
                "city": city.get("name"),
                "country": city.get("country"),
                "latitude": city.get("coord", {}).get("lat"),
                "longitude": city.get("coord", {}).get("lon"),
                "forecast_timestamp": datetime.utcfromtimestamp(item.get("dt", 0)),
                "fetched_at": datetime.utcnow(),
                "temp_c": item.get("main", {}).get("temp"),
                "temp_feels_like_c": item.get("main", {}).get("feels_like"),
                "humidity_pct": item.get("main", {}).get("humidity"),
                "cloud_cover_pct": item.get("clouds", {}).get("all"),
                "wind_speed_ms": item.get("wind", {}).get("speed"),
                "pop": item.get("pop"),
                "rain_mm": item.get("rain", {}).get("3h"),
                "snow_mm": item.get("snow", {}).get("3h"),
                "weather_main": item.get("weather", [{}])[0].get("main"),
            })
        return parsed

    async def store_observations(self, observations: List[Dict]) -> int:
        """Store parsed observations in database.

        Args:
            observations: List of parsed observation dicts

        Returns:
            Number of observations stored
        """
        session = SessionLocal()
        count = 0

        try:
            for obs in observations:
                record = WeatherObservation(
                    location_id=obs["location_id"],
                    city=obs.get("city"),
                    country=obs.get("country"),
                    latitude=obs.get("latitude"),
                    longitude=obs.get("longitude"),
                    timestamp=obs["timestamp"],
                    temp_c=obs.get("temp_c"),
                    temp_feels_like_c=obs.get("temp_feels_like_c"),
                    temp_min_c=obs.get("temp_min_c"),
                    temp_max_c=obs.get("temp_max_c"),
                    humidity_pct=obs.get("humidity_pct"),
                    pressure_hpa=obs.get("pressure_hpa"),
                    visibility_m=obs.get("visibility_m"),
                    cloud_cover_pct=obs.get("cloud_cover_pct"),
                    wind_speed_ms=obs.get("wind_speed_ms"),
                    wind_gust_ms=obs.get("wind_gust_ms"),
                    wind_direction_deg=obs.get("wind_direction_deg"),
                    rain_1h_mm=obs.get("rain_1h_mm"),
                    rain_3h_mm=obs.get("rain_3h_mm"),
                    snow_1h_mm=obs.get("snow_1h_mm"),
                    snow_3h_mm=obs.get("snow_3h_mm"),
                    weather_main=obs.get("weather_main"),
                    weather_description=obs.get("weather_description"),
                    weather_icon=obs.get("weather_icon"),
                )
                session.add(record)
                count += 1

            session.commit()
            logger.info(f"Stored {count} weather observations")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store observations: {e}")
            raise
        finally:
            session.close()

        return count

    def calculate_degree_days(
        self,
        temp_c: float,
        base_temp: float = 18.0
    ) -> tuple:
        """Calculate heating and cooling degree days.

        Args:
            temp_c: Average temperature in Celsius
            base_temp: Base temperature (default 18C)

        Returns:
            Tuple of (heating_degree_days, cooling_degree_days)
        """
        hdd = max(0, base_temp - temp_c)
        cdd = max(0, temp_c - base_temp)
        return hdd, cdd

    async def run_collection(self) -> int:
        """Run full collection cycle.

        Returns:
            Number of observations stored
        """
        logger.info("Starting OpenWeatherMap collection")

        try:
            raw_data = await self.fetch()
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            count = await self.store_observations(parsed)

            logger.info(f"OpenWeatherMap collection complete: {count} observations")
            return count

        finally:
            await self.close()
