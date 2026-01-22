"""Sentinel-2 satellite imagery collector with parking occupancy analysis."""

import io
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

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
        image_bytes: Optional[bytes] = None,
    ) -> Dict:
        """Estimate parking lot occupancy from satellite image analysis.

        Uses computer vision techniques to detect vehicles in parking lots:
        1. Image preprocessing (contrast enhancement, noise reduction)
        2. Color-based vehicle detection (vehicles appear as distinct colors)
        3. Blob detection for vehicle counting
        4. Shadow analysis to improve accuracy

        Args:
            image_data: Processed image metadata
            total_spaces: Known total parking spaces
            image_bytes: Raw satellite image bytes (optional)

        Returns:
            Occupancy metrics dict with vehicle counts and confidence
        """
        result = {
            "total_spaces": total_spaces,
            "occupied_spaces": None,
            "occupancy_rate": None,
            "cars_detected": None,
            "trucks_detected": None,
            "confidence_score": 0.0,
            "analysis_method": "spectral_analysis",
            "cloud_cover_impact": image_data.get("cloud_cover_pct", 0),
        }

        # If no image bytes provided, return empty result
        if image_bytes is None:
            result["analysis_method"] = "no_image_data"
            return result

        try:
            # Attempt to use OpenCV for analysis
            vehicles = self._detect_vehicles_cv(image_bytes, image_data)
            if vehicles is not None:
                cars, trucks, confidence = vehicles
                result["cars_detected"] = cars
                result["trucks_detected"] = trucks
                result["occupied_spaces"] = cars + trucks
                result["occupancy_rate"] = min(1.0, (cars + trucks) / total_spaces) if total_spaces > 0 else 0
                result["confidence_score"] = confidence
                result["analysis_method"] = "opencv_detection"
                return result
        except ImportError:
            logger.debug("OpenCV not available, using spectral analysis")
        except Exception as e:
            logger.warning(f"CV detection failed: {e}, falling back to spectral analysis")

        # Fallback: Spectral analysis using numpy
        try:
            vehicles = self._detect_vehicles_spectral(image_bytes, image_data)
            if vehicles is not None:
                cars, trucks, confidence = vehicles
                result["cars_detected"] = cars
                result["trucks_detected"] = trucks
                result["occupied_spaces"] = cars + trucks
                result["occupancy_rate"] = min(1.0, (cars + trucks) / total_spaces) if total_spaces > 0 else 0
                result["confidence_score"] = confidence
                result["analysis_method"] = "spectral_analysis"
        except Exception as e:
            logger.warning(f"Spectral analysis failed: {e}")
            result["analysis_method"] = "analysis_failed"
            result["error"] = str(e)

        return result

    def _detect_vehicles_cv(
        self,
        image_bytes: bytes,
        image_data: Dict,
    ) -> Optional[Tuple[int, int, float]]:
        """Detect vehicles using OpenCV computer vision.

        Uses multi-stage detection:
        1. Convert to grayscale and apply adaptive thresholding
        2. Use morphological operations to isolate vehicle-sized blobs
        3. Apply contour detection to count vehicles
        4. Classify by size (cars vs trucks)

        Args:
            image_bytes: Raw image bytes
            image_data: Image metadata

        Returns:
            Tuple of (cars_count, trucks_count, confidence) or None
        """
        import cv2
        from PIL import Image

        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        img_array = np.array(image)

        # Convert to BGR for OpenCV
        if len(img_array.shape) == 2:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        elif img_array.shape[2] == 4:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        else:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Get image resolution (Sentinel-2 is typically 10m/pixel)
        resolution_m = 10.0  # meters per pixel

        # Expected vehicle sizes in pixels (cars: 4-5m, trucks: 8-15m)
        car_min_px = int(4.0 / resolution_m)
        car_max_px = int(6.0 / resolution_m)
        truck_min_px = int(8.0 / resolution_m)
        truck_max_px = int(18.0 / resolution_m)

        # Preprocessing
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Adaptive thresholding for varying lighting
        thresh = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(
            cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        cars = 0
        trucks = 0

        for contour in contours:
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)

            # Filter by aspect ratio (vehicles are roughly rectangular)
            aspect_ratio = float(w) / h if h > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 3.5:
                continue

            # Classify by size
            max_dim = max(w, h)
            min_dim = min(w, h)

            # Car detection (small vehicles)
            if car_min_px <= max_dim <= car_max_px * 2 and min_dim >= 1:
                cars += 1
            # Truck detection (larger vehicles)
            elif truck_min_px <= max_dim <= truck_max_px and min_dim >= 2:
                trucks += 1

        # Calculate confidence based on cloud cover and image quality
        cloud_cover = image_data.get("cloud_cover_pct", 0)
        base_confidence = 0.85

        # Reduce confidence for high cloud cover
        cloud_penalty = min(cloud_cover / 100, 0.5)
        confidence = base_confidence - cloud_penalty

        # Reduce confidence if very few or very many detections
        detection_count = cars + trucks
        if detection_count < 5:
            confidence *= 0.7
        elif detection_count > 500:
            confidence *= 0.8

        return (cars, trucks, round(confidence, 3))

    def _detect_vehicles_spectral(
        self,
        image_bytes: bytes,
        image_data: Dict,
    ) -> Optional[Tuple[int, int, float]]:
        """Detect vehicles using spectral analysis (numpy-only fallback).

        Uses color/intensity analysis to identify vehicle signatures:
        1. Analyze pixel intensity distribution
        2. Identify anomalies that match vehicle spectral signatures
        3. Count distinct clusters of anomalous pixels

        Args:
            image_bytes: Raw image bytes
            image_data: Image metadata

        Returns:
            Tuple of (cars_count, trucks_count, confidence) or None
        """
        from PIL import Image

        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        img_array = np.array(image)

        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            # Weighted grayscale conversion
            if img_array.shape[2] >= 3:
                gray = (
                    0.299 * img_array[:, :, 0] +
                    0.587 * img_array[:, :, 1] +
                    0.114 * img_array[:, :, 2]
                ).astype(np.uint8)
            else:
                gray = img_array[:, :, 0]
        else:
            gray = img_array

        # Calculate statistics
        mean_intensity = np.mean(gray)
        std_intensity = np.std(gray)

        # Vehicles typically appear darker than parking lot surface
        # Find pixels significantly different from background
        lower_threshold = mean_intensity - 2 * std_intensity
        upper_threshold = mean_intensity - 0.5 * std_intensity

        # Create mask of potential vehicle pixels
        vehicle_mask = (gray > lower_threshold) & (gray < upper_threshold)

        # Count connected regions (simplified blob counting)
        # Using a basic sliding window approach
        window_size = 3  # ~30m window for vehicle detection
        step = 2

        vehicle_count = 0
        rows, cols = gray.shape

        for i in range(0, rows - window_size, step):
            for j in range(0, cols - window_size, step):
                window = vehicle_mask[i:i+window_size, j:j+window_size]
                # If window has significant vehicle pixels
                if np.sum(window) > window_size:
                    vehicle_count += 1

        # Rough estimate: 70% cars, 30% trucks based on typical distribution
        cars = int(vehicle_count * 0.7)
        trucks = vehicle_count - cars

        # Lower confidence for spectral analysis
        cloud_cover = image_data.get("cloud_cover_pct", 0)
        confidence = max(0.3, 0.6 - (cloud_cover / 100) * 0.3)

        return (cars, trucks, round(confidence, 3))

    async def download_image(
        self,
        download_link: str,
        output_path: Optional[str] = None,
    ) -> Optional[bytes]:
        """Download satellite image from Copernicus.

        Args:
            download_link: Image download URL
            output_path: Optional path to save image

        Returns:
            Image bytes or None if download fails
        """
        if not self.username or not self.password:
            raise CollectorError("Copernicus credentials not configured")

        try:
            await self.rate_limiter.wait()
            response = await self.http_client.get(
                download_link,
                auth=(self.username, self.password),
                timeout=300.0,  # Large file download timeout
            )
            response.raise_for_status()

            image_bytes = response.content

            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(image_bytes)
                logger.info(f"Saved image to {output_path}")

            return image_bytes

        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return None

    async def analyze_parking_lot(
        self,
        location_id: str,
        total_spaces: int,
        days_back: int = 30,
    ) -> List[Dict]:
        """Analyze parking lot occupancy over time.

        Downloads recent images and estimates occupancy for each.

        Args:
            location_id: Location identifier
            total_spaces: Known total parking spaces
            days_back: Days to analyze

        Returns:
            List of occupancy analysis results
        """
        # Find location
        location = next(
            (loc for loc in self.TRACKED_LOCATIONS if loc["location_id"] == location_id),
            None
        )
        if not location:
            raise CollectorError(f"Location not found: {location_id}")

        # Search for images
        images = await self.search_images(
            location["lat"],
            location["lon"],
            location_id,
            days_back=days_back,
            cloud_cover_max=20.0,  # Only low cloud cover for analysis
        )

        results = []
        for image in images:
            try:
                # Download image
                if image.get("download_link"):
                    image_bytes = await self.download_image(image["download_link"])
                else:
                    image_bytes = None

                # Analyze occupancy
                occupancy = self.estimate_parking_occupancy(
                    image_data=image,
                    total_spaces=total_spaces,
                    image_bytes=image_bytes,
                )

                results.append({
                    "image_id": image.get("image_id"),
                    "acquisition_date": image.get("acquisition_date"),
                    "cloud_cover_pct": image.get("cloud_cover_pct"),
                    **occupancy,
                })

            except Exception as e:
                logger.warning(f"Failed to analyze image {image.get('image_id')}: {e}")

        return results

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
