"""OpenAQ air quality data collector."""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.air_quality import (
    AirQualityLocation,
    AirQualityMeasurement,
    AirQualityDaily,
)

logger = logging.getLogger(__name__)


class OpenAQCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for OpenAQ air quality data.

    Uses OpenAQ API v3 for global air quality measurements.
    """

    SOURCE_NAME = "openaq"
    BASE_URL = "https://api.openaq.org/v3"
    DEFAULT_RATE_LIMIT = 5.0  # OpenAQ allows reasonable rates

    # Key pollutants for industrial activity
    INDUSTRIAL_PARAMETERS = ["pm25", "pm10", "no2", "so2", "co"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the OpenAQ collector.

        Args:
            api_key: Optional OpenAQ API key
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.api_key = api_key or getattr(settings, 'openaq_api_key', None)
        self.headers = {}
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key

    @property
    def http_client(self) -> httpx.AsyncClient:
        """HTTP client with API key header."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self.headers,
            )
        return self._http_client

    async def fetch(self) -> Dict:
        """Fetch recent air quality measurements.

        Returns:
            Dict with measurement data
        """
        # Default: fetch latest measurements
        return await self.fetch_latest_measurements()

    async def fetch_latest_measurements(
        self,
        country: str = "US",
        limit: int = 1000,
    ) -> Dict:
        """Fetch latest measurements for a country.

        Args:
            country: ISO country code
            limit: Maximum results

        Returns:
            Measurement data dict
        """
        await self.rate_limiter.wait()

        try:
            params = {
                "country": country,
                "limit": limit,
            }
            response = await self.http_client.get(
                f"{self.BASE_URL}/latest",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"OpenAQ latest fetch error: {e}")
            raise CollectorError(f"Failed to fetch OpenAQ data: {e}")

    async def fetch_measurements_by_location(
        self,
        location_id: int,
        start_date: datetime,
        end_date: datetime,
        parameter: Optional[str] = None,
        limit: int = 10000,
    ) -> Dict:
        """Fetch measurements for a specific location.

        Args:
            location_id: OpenAQ location ID
            start_date: Start of date range
            end_date: End of date range
            parameter: Optional parameter filter (pm25, no2, etc.)
            limit: Maximum results

        Returns:
            Measurement data dict
        """
        await self.rate_limiter.wait()

        try:
            params = {
                "location_id": location_id,
                "date_from": start_date.isoformat(),
                "date_to": end_date.isoformat(),
                "limit": limit,
            }
            if parameter:
                params["parameter"] = parameter

            response = await self.http_client.get(
                f"{self.BASE_URL}/measurements",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"OpenAQ measurements fetch error: {e}")
            raise CollectorError(f"Failed to fetch OpenAQ data: {e}")

    async def fetch_locations_by_coordinates(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50,
        limit: int = 100,
    ) -> Dict:
        """Fetch monitoring locations near coordinates.

        Args:
            lat: Center latitude
            lon: Center longitude
            radius_km: Search radius in km
            limit: Maximum results

        Returns:
            Location data dict
        """
        await self.rate_limiter.wait()

        try:
            # Convert km to meters for API
            radius_m = int(radius_km * 1000)

            params = {
                "coordinates": f"{lat},{lon}",
                "radius": radius_m,
                "limit": limit,
            }
            response = await self.http_client.get(
                f"{self.BASE_URL}/locations",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"OpenAQ locations fetch error: {e}")
            raise CollectorError(f"Failed to fetch OpenAQ locations: {e}")

    async def fetch_locations_by_city(
        self,
        city: str,
        country: str = "US",
        limit: int = 100,
    ) -> Dict:
        """Fetch monitoring locations in a city.

        Args:
            city: City name
            country: ISO country code
            limit: Maximum results

        Returns:
            Location data dict
        """
        await self.rate_limiter.wait()

        try:
            params = {
                "city": city,
                "country": country,
                "limit": limit,
            }
            response = await self.http_client.get(
                f"{self.BASE_URL}/locations",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"OpenAQ city locations fetch error: {e}")
            raise CollectorError(f"Failed to fetch OpenAQ locations: {e}")

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse OpenAQ API response into structured format.

        Args:
            raw_data: Raw API response

        Returns:
            List of parsed measurement dicts
        """
        results = raw_data.get("results", [])
        parsed = []

        for result in results:
            try:
                # Handle latest endpoint format
                if "measurements" in result:
                    location_id = str(result.get("location", {}).get("id", ""))
                    location = result.get("location", {})

                    for measurement in result.get("measurements", []):
                        parsed.append({
                            "location_id": location_id,
                            "location_name": location.get("name"),
                            "city": location.get("city"),
                            "country": location.get("country", {}).get("code"),
                            "latitude": location.get("coordinates", {}).get("latitude"),
                            "longitude": location.get("coordinates", {}).get("longitude"),
                            "parameter": measurement.get("parameter", {}).get("name"),
                            "value": measurement.get("value"),
                            "unit": measurement.get("parameter", {}).get("units"),
                            "timestamp": self._parse_timestamp(measurement.get("datetime", {}).get("utc")),
                        })
                # Handle measurements endpoint format
                elif "value" in result:
                    parsed.append({
                        "location_id": str(result.get("location_id", "")),
                        "parameter": result.get("parameter"),
                        "value": result.get("value"),
                        "unit": result.get("unit"),
                        "timestamp": self._parse_timestamp(result.get("date", {}).get("utc")),
                    })
            except Exception as e:
                logger.warning(f"Failed to parse measurement: {e}")
                continue

        return parsed

    def parse_locations(self, raw_data: Dict) -> List[Dict]:
        """Parse location data from API response.

        Args:
            raw_data: Raw API response

        Returns:
            List of parsed location dicts
        """
        results = raw_data.get("results", [])
        parsed = []

        for location in results:
            try:
                coords = location.get("coordinates", {})
                parsed.append({
                    "location_id": str(location.get("id")),
                    "name": location.get("name"),
                    "city": location.get("city"),
                    "country": location.get("country", {}).get("code"),
                    "latitude": coords.get("latitude"),
                    "longitude": coords.get("longitude"),
                    "is_mobile": location.get("isMobile", False),
                    "entity": location.get("entity"),
                    "sensor_type": location.get("sensorType"),
                    "parameters": [p.get("parameter") for p in location.get("parameters", [])],
                })
            except Exception as e:
                logger.warning(f"Failed to parse location: {e}")
                continue

        return parsed

    def _parse_timestamp(self, ts_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO timestamp string."""
        if not ts_str:
            return None
        try:
            # Handle various ISO formats
            ts_str = ts_str.replace("Z", "+00:00")
            return datetime.fromisoformat(ts_str)
        except ValueError:
            return None

    async def store_measurements(self, measurements: List[Dict]) -> int:
        """Store parsed measurements in database.

        Args:
            measurements: List of parsed measurement dicts

        Returns:
            Number of measurements stored
        """
        session = SessionLocal()
        count = 0

        try:
            for m in measurements:
                if not m.get("location_id") or m.get("value") is None:
                    continue

                record = AirQualityMeasurement(
                    location_id=m["location_id"],
                    timestamp=m.get("timestamp", datetime.utcnow()),
                    parameter=m.get("parameter"),
                    value=m["value"],
                    unit=m.get("unit"),
                )
                session.add(record)
                count += 1

            session.commit()
            logger.info(f"Stored {count} air quality measurements")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store measurements: {e}")
            raise
        finally:
            session.close()

        return count

    async def store_locations(self, locations: List[Dict]) -> int:
        """Store or update location data.

        Args:
            locations: List of parsed location dicts

        Returns:
            Number of locations stored/updated
        """
        session = SessionLocal()
        count = 0

        try:
            for loc in locations:
                if not loc.get("location_id"):
                    continue

                existing = session.query(AirQualityLocation).filter_by(
                    location_id=loc["location_id"]
                ).first()

                if existing:
                    existing.name = loc.get("name") or existing.name
                    existing.city = loc.get("city") or existing.city
                    existing.last_updated = datetime.utcnow()
                else:
                    record = AirQualityLocation(
                        location_id=loc["location_id"],
                        name=loc.get("name"),
                        city=loc.get("city"),
                        country=loc.get("country"),
                        latitude=loc.get("latitude"),
                        longitude=loc.get("longitude"),
                        is_mobile=loc.get("is_mobile", False),
                        entity=loc.get("entity"),
                        sensor_type=loc.get("sensor_type"),
                        parameters=loc.get("parameters"),
                        first_updated=datetime.utcnow(),
                        last_updated=datetime.utcnow(),
                    )
                    session.add(record)
                count += 1

            session.commit()
            logger.info(f"Stored/updated {count} locations")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store locations: {e}")
            raise
        finally:
            session.close()

        return count

    def calculate_aqi(self, pm25: float) -> int:
        """Calculate US EPA Air Quality Index from PM2.5.

        Args:
            pm25: PM2.5 concentration in ug/m3

        Returns:
            AQI value (0-500+)
        """
        # EPA AQI breakpoints for PM2.5 (24-hour average)
        breakpoints = [
            (0, 12.0, 0, 50),      # Good
            (12.1, 35.4, 51, 100), # Moderate
            (35.5, 55.4, 101, 150), # Unhealthy for Sensitive
            (55.5, 150.4, 151, 200), # Unhealthy
            (150.5, 250.4, 201, 300), # Very Unhealthy
            (250.5, 500.4, 301, 500), # Hazardous
        ]

        for bp_lo, bp_hi, aqi_lo, aqi_hi in breakpoints:
            if bp_lo <= pm25 <= bp_hi:
                return int(
                    (aqi_hi - aqi_lo) / (bp_hi - bp_lo) * (pm25 - bp_lo) + aqi_lo
                )

        # Beyond scale
        return 500 if pm25 > 500 else 0

    async def run_collection(
        self,
        country: str = "US",
        limit: int = 1000,
    ) -> int:
        """Run full collection cycle.

        Args:
            country: Country to collect data for
            limit: Maximum measurements to fetch

        Returns:
            Number of measurements stored
        """
        logger.info(f"Starting OpenAQ collection for {country}")

        try:
            raw_data = await self.fetch_latest_measurements(country, limit)
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            count = await self.store_measurements(parsed)

            logger.info(f"OpenAQ collection complete: {count} measurements")
            return count

        finally:
            await self.close()
