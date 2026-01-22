"""Sentinel-2 satellite imagery collector."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.satellite import (
    SatelliteLocation,
    SatelliteImage,
    ParkingLotMetrics,
    AgriculturalMetrics,
)

logger = logging.getLogger(__name__)


class SentinelCollector(BaseCollector[Dict, Dict]):
    """Collector for Sentinel-2 satellite imagery.

    Uses Copernicus Open Access Hub API for imagery discovery.
    """

    SOURCE_NAME = "sentinel"
    BASE_URL = "https://scihub.copernicus.eu/dhus"
    DEFAULT_RATE_LIMIT = 0.2  # Conservative rate limit

    # Tracked locations for retail/economic signals
    TRACKED_LOCATIONS = [
        # Retail parking lots
        {
            "location_id": "walmart_bentonville_hq",
            "name": "Walmart HQ Bentonville",
            "type": "parking_lot",
            "lat": 36.3729,
            "lon": -94.2088,
            "company": "Walmart",
            "ticker": "WMT",
        },
        {
            "location_id": "costco_issaquah_hq",
            "name": "Costco HQ Issaquah",
            "type": "parking_lot",
            "lat": 47.5301,
            "lon": -122.0326,
            "company": "Costco",
            "ticker": "COST",
        },
        {
            "location_id": "target_minneapolis_hq",
            "name": "Target HQ Minneapolis",
            "type": "parking_lot",
            "lat": 44.9778,
            "lon": -93.2650,
            "company": "Target",
            "ticker": "TGT",
        },

        # Manufacturing/Distribution
        {
            "location_id": "tesla_fremont_factory",
            "name": "Tesla Fremont Factory",
            "type": "parking_lot",
            "lat": 37.4942,
            "lon": -121.9447,
            "company": "Tesla",
            "ticker": "TSLA",
        },
        {
            "location_id": "amazon_fulfillment_ont8",
            "name": "Amazon ONT8 Fulfillment",
            "type": "parking_lot",
            "lat": 34.0537,
            "lon": -117.6009,
            "company": "Amazon",
            "ticker": "AMZN",
        },

        # Construction sites
        {
            "location_id": "intel_ohio_fab",
            "name": "Intel Ohio Fab Construction",
            "type": "construction",
            "lat": 40.1092,
            "lon": -82.7831,
            "company": "Intel",
            "ticker": "INTC",
        },
        {
            "location_id": "tsmc_arizona_fab",
            "name": "TSMC Arizona Fab",
            "type": "construction",
            "lat": 33.6639,
            "lon": -112.0070,
            "company": "TSMC",
            "ticker": "TSM",
        },

        # Agricultural regions
        {
            "location_id": "iowa_corn_belt",
            "name": "Iowa Corn Belt",
            "type": "agricultural",
            "lat": 42.0046,
            "lon": -93.2140,
            "company": None,
            "ticker": None,
            "crop": "corn",
        },
        {
            "location_id": "california_central_valley",
            "name": "California Central Valley",
            "type": "agricultural",
            "lat": 36.7783,
            "lon": -119.4179,
            "company": None,
            "ticker": None,
            "crop": "mixed",
        },

        # Ports
        {
            "location_id": "port_los_angeles",
            "name": "Port of Los Angeles",
            "type": "port",
            "lat": 33.7405,
            "lon": -118.2723,
            "company": None,
            "ticker": None,
        },
        {
            "location_id": "port_long_beach",
            "name": "Port of Long Beach",
            "type": "port",
            "lat": 33.7545,
            "lon": -118.2137,
            "company": None,
            "ticker": None,
        },
    ]

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the Sentinel collector.

        Args:
            username: Copernicus username
            password: Copernicus password
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.username = username or getattr(settings, 'copernicus_username', None)
        self.password = password or getattr(settings, 'copernicus_password', None)

    def _get_bbox(self, lat: float, lon: float, size_km: float = 5) -> Tuple[float, float, float, float]:
        """Calculate bounding box from center point.

        Args:
            lat: Center latitude
            lon: Center longitude
            size_km: Box size in km

        Returns:
            Tuple of (west, south, east, north)
        """
        # Approximate degrees per km
        lat_per_km = 1 / 111
        lon_per_km = 1 / (111 * abs(lat) / 90) if lat != 0 else 1 / 111

        half_size = size_km / 2
        west = lon - (half_size * lon_per_km)
        east = lon + (half_size * lon_per_km)
        south = lat - (half_size * lat_per_km)
        north = lat + (half_size * lat_per_km)

        return west, south, east, north

    async def fetch(self) -> List[Dict]:
        """Fetch imagery metadata for all tracked locations.

        Returns:
            List of image metadata dicts
        """
        results = []
        for location in self.TRACKED_LOCATIONS:
            try:
                await self.rate_limiter.wait()
                images = await self.search_images(
                    location["lat"],
                    location["lon"],
                    location["location_id"],
                    days_back=30,
                )
                results.append({
                    "location": location,
                    "images": images,
                })
            except Exception as e:
                logger.warning(f"Failed to fetch images for {location['name']}: {e}")
        return results

    async def search_images(
        self,
        lat: float,
        lon: float,
        location_id: str,
        days_back: int = 30,
        cloud_cover_max: float = 30.0,
    ) -> List[Dict]:
        """Search for Sentinel-2 images.

        Args:
            lat: Center latitude
            lon: Center longitude
            location_id: Location identifier
            days_back: Days to search back
            cloud_cover_max: Maximum cloud cover percentage

        Returns:
            List of image metadata dicts
        """
        if not self.username or not self.password:
            raise CollectorError("Copernicus credentials not configured")

        bbox = self._get_bbox(lat, lon)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        # Build OData query
        query = (
            f"footprint:\"Intersects(POLYGON(("
            f"{bbox[0]} {bbox[1]},"
            f"{bbox[2]} {bbox[1]},"
            f"{bbox[2]} {bbox[3]},"
            f"{bbox[0]} {bbox[3]},"
            f"{bbox[0]} {bbox[1]}"
            f")))\" AND "
            f"platformname:Sentinel-2 AND "
            f"cloudcoverpercentage:[0 TO {cloud_cover_max}] AND "
            f"beginposition:[{start_date.isoformat()}Z TO {end_date.isoformat()}Z]"
        )

        try:
            response = await self.http_client.get(
                f"{self.BASE_URL}/search",
                params={"q": query, "format": "json", "rows": 100},
                auth=(self.username, self.password),
            )
            response.raise_for_status()

            data = response.json()
            entries = data.get("feed", {}).get("entry", [])

            # Handle single entry case
            if isinstance(entries, dict):
                entries = [entries]

            return [self._parse_image_entry(e, location_id) for e in entries]

        except Exception as e:
            logger.error(f"Error searching images for {location_id}: {e}")
            return []

    def _parse_image_entry(self, entry: Dict, location_id: str) -> Dict:
        """Parse Copernicus API image entry.

        Args:
            entry: Raw API entry
            location_id: Location identifier

        Returns:
            Parsed image metadata dict
        """
        # Extract attributes
        attrs = {}
        for item in entry.get("str", []) + entry.get("double", []) + entry.get("date", []):
            if isinstance(item, dict) and "name" in item:
                attrs[item["name"]] = item.get("content")

        return {
            "image_id": entry.get("id"),
            "location_id": location_id,
            "title": entry.get("title"),
            "acquisition_date": attrs.get("beginposition"),
            "platform": attrs.get("platformname"),
            "product_type": attrs.get("producttype"),
            "cloud_cover_pct": float(attrs.get("cloudcoverpercentage", 0)),
            "processing_level": attrs.get("processinglevel"),
            "tile_id": attrs.get("tileid"),
            "size_mb": attrs.get("size"),
            "download_link": entry.get("link", [{}])[0].get("href") if entry.get("link") else None,
        }

    def parse(self, raw_data: List[Dict]) -> Dict:
        """Parse raw API responses.

        Args:
            raw_data: List of location/image data

        Returns:
            Parsed data structure
        """
        locations = []
        images = []

        for item in raw_data:
            location = item.get("location", {})
            locations.append({
                "location_id": location.get("location_id"),
                "name": location.get("name"),
                "location_type": location.get("type"),
                "latitude": location.get("lat"),
                "longitude": location.get("lon"),
                "company": location.get("company"),
                "ticker": location.get("ticker"),
            })

            for img in item.get("images", []):
                images.append(img)

        return {
            "locations": locations,
            "images": images,
        }

    def calculate_ndvi(self, nir_band: float, red_band: float) -> float:
        """Calculate Normalized Difference Vegetation Index.

        Args:
            nir_band: Near-infrared reflectance
            red_band: Red reflectance

        Returns:
            NDVI value (-1 to 1)
        """
        if nir_band + red_band == 0:
            return 0
        return (nir_band - red_band) / (nir_band + red_band)

    def calculate_evi(
        self,
        nir_band: float,
        red_band: float,
        blue_band: float,
        gain: float = 2.5,
        c1: float = 6.0,
        c2: float = 7.5,
        l: float = 1.0,
    ) -> float:
        """Calculate Enhanced Vegetation Index.

        Args:
            nir_band: Near-infrared reflectance
            red_band: Red reflectance
            blue_band: Blue reflectance
            gain: Gain factor
            c1, c2, l: Coefficients

        Returns:
            EVI value
        """
        denominator = nir_band + c1 * red_band - c2 * blue_band + l
        if denominator == 0:
            return 0
        return gain * ((nir_band - red_band) / denominator)

    def estimate_parking_occupancy(
        self,
        image_data: Dict,
        total_spaces: int,
    ) -> Dict:
        """Estimate parking lot occupancy from image analysis.

        This is a simplified placeholder - real implementation would use
        computer vision / ML models.

        Args:
            image_data: Processed image data
            total_spaces: Known total parking spaces

        Returns:
            Occupancy metrics dict
        """
        # Placeholder for actual CV analysis
        # In production, this would use object detection models
        return {
            "total_spaces": total_spaces,
            "occupied_spaces": None,
            "occupancy_rate": None,
            "cars_detected": None,
            "trucks_detected": None,
            "confidence_score": 0.0,
        }

    async def store_data(self, parsed: Dict) -> Tuple[int, int]:
        """Store parsed satellite data.

        Args:
            parsed: Parsed data dict

        Returns:
            Tuple of (locations_stored, images_stored)
        """
        session = SessionLocal()
        locations_count = 0
        images_count = 0

        try:
            # Store locations
            for loc in parsed.get("locations", []):
                existing = session.query(SatelliteLocation).filter_by(
                    location_id=loc["location_id"]
                ).first()

                if not existing:
                    session.add(SatelliteLocation(**loc))
                    locations_count += 1

            # Store images
            for img in parsed.get("images", []):
                if not img.get("image_id"):
                    continue

                existing = session.query(SatelliteImage).filter_by(
                    image_id=img["image_id"]
                ).first()

                if not existing:
                    session.add(SatelliteImage(
                        image_id=img["image_id"],
                        location_id=img["location_id"],
                        acquisition_date=self._parse_datetime(img.get("acquisition_date")),
                        platform=img.get("platform"),
                        product_type=img.get("product_type"),
                        cloud_cover_pct=img.get("cloud_cover_pct"),
                        processing_level=img.get("processing_level"),
                        tile_id=img.get("tile_id"),
                    ))
                    images_count += 1

            session.commit()
            logger.info(f"Stored {locations_count} locations, {images_count} images")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store satellite data: {e}")
            raise
        finally:
            session.close()

        return locations_count, images_count

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string.

        Args:
            dt_str: Datetime string

        Returns:
            Parsed datetime or None
        """
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    async def run_collection(self) -> int:
        """Run full collection cycle.

        Returns:
            Total records stored
        """
        logger.info("Starting Sentinel-2 collection")

        try:
            raw_data = await self.fetch()
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            l, i = await self.store_data(parsed)

            total = l + i
            logger.info(f"Sentinel-2 collection complete: {total} records")
            return total

        finally:
            await self.close()
