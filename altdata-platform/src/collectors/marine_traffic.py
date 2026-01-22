"""MarineTraffic/AIS shipping data collector."""

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.shipping import (
    Vessel,
    VesselPosition,
    Port,
    PortCall,
    PortCongestion,
)

logger = logging.getLogger(__name__)


class MarineTrafficCollector(BaseCollector[Dict, Dict]):
    """Collector for MarineTraffic AIS data.

    Tracks global shipping patterns as economic indicators.
    """

    SOURCE_NAME = "marine_traffic"
    BASE_URL = "https://services.marinetraffic.com/api"
    DEFAULT_RATE_LIMIT = 0.5  # Conservative rate limit

    # Major ports for tracking
    TRACKED_PORTS = [
        # Asia
        {"port_id": "CNSHA", "name": "Shanghai", "country": "CN", "lat": 31.23, "lon": 121.47},
        {"port_id": "SGSIN", "name": "Singapore", "country": "SG", "lat": 1.29, "lon": 103.85},
        {"port_id": "CNSZN", "name": "Shenzhen", "country": "CN", "lat": 22.54, "lon": 114.05},
        {"port_id": "CNNGB", "name": "Ningbo-Zhoushan", "country": "CN", "lat": 29.87, "lon": 121.55},
        {"port_id": "HKHKG", "name": "Hong Kong", "country": "HK", "lat": 22.28, "lon": 114.16},
        {"port_id": "KRPUS", "name": "Busan", "country": "KR", "lat": 35.10, "lon": 129.03},
        {"port_id": "JPYOK", "name": "Yokohama", "country": "JP", "lat": 35.44, "lon": 139.64},

        # Europe
        {"port_id": "NLRTM", "name": "Rotterdam", "country": "NL", "lat": 51.92, "lon": 4.48},
        {"port_id": "DEHAM", "name": "Hamburg", "country": "DE", "lat": 53.55, "lon": 9.99},
        {"port_id": "BEANR", "name": "Antwerp", "country": "BE", "lat": 51.22, "lon": 4.40},
        {"port_id": "GBFXT", "name": "Felixstowe", "country": "GB", "lat": 51.95, "lon": 1.35},

        # Americas
        {"port_id": "USLAX", "name": "Los Angeles", "country": "US", "lat": 33.74, "lon": -118.26},
        {"port_id": "USLGB", "name": "Long Beach", "country": "US", "lat": 33.75, "lon": -118.19},
        {"port_id": "USNYC", "name": "New York", "country": "US", "lat": 40.67, "lon": -74.04},
        {"port_id": "USSAV", "name": "Savannah", "country": "US", "lat": 32.08, "lon": -81.09},
        {"port_id": "USHOU", "name": "Houston", "country": "US", "lat": 29.76, "lon": -95.27},
        {"port_id": "PAMIT", "name": "Panama Canal", "country": "PA", "lat": 9.01, "lon": -79.52},
    ]

    # Vessel type codes
    VESSEL_TYPES = {
        70: "Cargo",
        71: "Cargo - Hazardous A",
        72: "Cargo - Hazardous B",
        73: "Cargo - Hazardous C",
        74: "Cargo - Hazardous D",
        75: "Cargo",
        76: "Cargo",
        77: "Cargo",
        78: "Cargo",
        79: "Cargo",
        80: "Tanker",
        81: "Tanker - Hazardous A",
        82: "Tanker - Hazardous B",
        83: "Tanker - Hazardous C",
        84: "Tanker - Hazardous D",
        85: "Tanker",
        86: "Tanker",
        87: "Tanker",
        88: "Tanker",
        89: "Tanker",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the MarineTraffic collector.

        Args:
            api_key: MarineTraffic API key
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.api_key = api_key or getattr(settings, 'marine_traffic_api_key', None)

    async def fetch(self) -> List[Dict]:
        """Fetch shipping data for all tracked ports.

        Returns:
            List of vessel/port data dicts
        """
        results = []
        for port in self.TRACKED_PORTS:
            try:
                await self.rate_limiter.wait()
                port_data = await self.fetch_port_vessels(
                    port["lat"], port["lon"], port["port_id"]
                )
                results.append({
                    "port": port,
                    "vessels": port_data,
                })
            except Exception as e:
                logger.warning(f"Failed to fetch data for {port['name']}: {e}")
        return results

    async def fetch_port_vessels(
        self,
        lat: float,
        lon: float,
        port_id: str,
        radius_nm: int = 50,
    ) -> List[Dict]:
        """Fetch vessels near a port.

        Args:
            lat: Port latitude
            lon: Port longitude
            port_id: Port identifier
            radius_nm: Search radius in nautical miles

        Returns:
            List of vessel data dicts
        """
        if not self.api_key:
            raise CollectorError("MarineTraffic API key not configured")

        # Simulated response structure - in production would call actual API
        # API endpoint would be something like:
        # f"{self.BASE_URL}/exportvessels/{self.api_key}/protocol:jsono/..."

        await self.rate_limiter.wait()

        params = {
            "apikey": self.api_key,
            "protocol": "json",
            "LATITUDE": lat,
            "LONGITUDE": lon,
            "RANGE": radius_nm,
        }

        try:
            response = await self.http_client.get(
                f"{self.BASE_URL}/exportvessels",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"API call failed for port {port_id}: {e}")
            return []

    def parse(self, raw_data: List[Dict]) -> Dict:
        """Parse raw API responses.

        Args:
            raw_data: List of port/vessel data

        Returns:
            Parsed data structure
        """
        vessels = []
        positions = []
        port_metrics = []

        for port_data in raw_data:
            port = port_data.get("port", {})
            port_vessels = port_data.get("vessels", [])

            # Count vessels by type
            vessel_counts = {
                "container": 0,
                "tanker": 0,
                "bulk": 0,
                "other": 0,
            }

            for v in port_vessels:
                parsed_vessel = self.parse_vessel(v)
                if parsed_vessel:
                    vessels.append(parsed_vessel)

                parsed_position = self.parse_position(v)
                if parsed_position:
                    positions.append(parsed_position)

                # Categorize vessel
                vessel_type = self.get_vessel_type(v.get("SHIP_TYPE", 0))
                if "Container" in vessel_type:
                    vessel_counts["container"] += 1
                elif "Tanker" in vessel_type:
                    vessel_counts["tanker"] += 1
                elif "Bulk" in vessel_type:
                    vessel_counts["bulk"] += 1
                else:
                    vessel_counts["other"] += 1

            port_metrics.append({
                "port_id": port.get("port_id"),
                "date": datetime.utcnow().date(),
                "vessels_in_port": len(port_vessels),
                "container_vessels": vessel_counts["container"],
                "tankers": vessel_counts["tanker"],
                "bulk_carriers": vessel_counts["bulk"],
            })

        return {
            "vessels": vessels,
            "positions": positions,
            "port_metrics": port_metrics,
        }

    def parse_vessel(self, raw: Dict) -> Optional[Dict]:
        """Parse vessel data from API response.

        Args:
            raw: Raw vessel data

        Returns:
            Parsed vessel dict or None
        """
        mmsi = raw.get("MMSI")
        if not mmsi:
            return None

        return {
            "mmsi": str(mmsi),
            "imo": raw.get("IMO"),
            "name": raw.get("SHIPNAME"),
            "callsign": raw.get("CALLSIGN"),
            "vessel_type": self.get_vessel_type(raw.get("SHIP_TYPE", 0)),
            "vessel_type_code": raw.get("SHIP_TYPE"),
            "flag": raw.get("FLAG"),
            "gross_tonnage": raw.get("GT"),
            "deadweight": raw.get("DWT"),
            "length_m": raw.get("LENGTH"),
            "width_m": raw.get("WIDTH"),
            "draught_m": raw.get("DRAUGHT"),
            "year_built": raw.get("YEAR_BUILT"),
        }

    def parse_position(self, raw: Dict) -> Optional[Dict]:
        """Parse position data from API response.

        Args:
            raw: Raw vessel/position data

        Returns:
            Parsed position dict or None
        """
        mmsi = raw.get("MMSI")
        lat = raw.get("LAT") or raw.get("LATITUDE")
        lon = raw.get("LON") or raw.get("LONGITUDE")

        if not mmsi or lat is None or lon is None:
            return None

        return {
            "mmsi": str(mmsi),
            "timestamp": datetime.utcnow(),
            "latitude": float(lat),
            "longitude": float(lon),
            "speed_knots": raw.get("SPEED"),
            "course": raw.get("COURSE"),
            "heading": raw.get("HEADING"),
            "nav_status": raw.get("STATUS"),
            "destination": raw.get("DESTINATION"),
            "eta": self.parse_eta(raw.get("ETA")),
        }

    def parse_eta(self, eta_str: Optional[str]) -> Optional[datetime]:
        """Parse ETA string to datetime.

        Args:
            eta_str: ETA string from API

        Returns:
            Parsed datetime or None
        """
        if not eta_str:
            return None
        try:
            # MarineTraffic format: "MM-DD HH:mm"
            return datetime.strptime(f"2024-{eta_str}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None

    def get_vessel_type(self, type_code: int) -> str:
        """Get vessel type name from code.

        Args:
            type_code: AIS vessel type code

        Returns:
            Vessel type name
        """
        if type_code in self.VESSEL_TYPES:
            return self.VESSEL_TYPES[type_code]

        # Container ships
        if type_code == 71 or 70 <= type_code <= 79:
            return "Cargo"
        # Tankers
        if 80 <= type_code <= 89:
            return "Tanker"
        # Fishing
        if type_code == 30:
            return "Fishing"
        # Passenger
        if 60 <= type_code <= 69:
            return "Passenger"

        return "Other"

    def calculate_congestion_index(self, vessels_count: int, avg_wait: float) -> float:
        """Calculate port congestion index.

        Args:
            vessels_count: Number of vessels at port
            avg_wait: Average wait time in hours

        Returns:
            Congestion index (0-100)
        """
        # Simple formula: normalized vessel count + wait time factor
        vessel_factor = min(vessels_count / 100, 1) * 50
        wait_factor = min(avg_wait / 48, 1) * 50
        return vessel_factor + wait_factor

    def detect_port_call(
        self,
        positions: List[Dict],
        port_lat: float,
        port_lon: float,
        port_id: str,
        threshold_nm: float = 5.0,
    ) -> List[Dict]:
        """Detect port calls from position data.

        Args:
            positions: List of position dicts
            port_lat: Port latitude
            port_lon: Port longitude
            port_id: Port identifier
            threshold_nm: Distance threshold in nautical miles

        Returns:
            List of detected port calls
        """
        port_calls = []

        for pos in positions:
            distance = self.haversine_nm(
                pos["latitude"], pos["longitude"],
                port_lat, port_lon
            )

            if distance <= threshold_nm and pos.get("speed_knots", 0) < 2:
                port_calls.append({
                    "mmsi": pos["mmsi"],
                    "port_id": port_id,
                    "call_type": "arrival",
                    "timestamp": pos["timestamp"],
                })

        return port_calls

    @staticmethod
    def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in nautical miles.

        Args:
            lat1, lon1: First point
            lat2, lon2: Second point

        Returns:
            Distance in nautical miles
        """
        R = 3440.065  # Earth radius in nautical miles

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    async def store_data(self, parsed: Dict) -> Tuple[int, int, int]:
        """Store parsed shipping data.

        Args:
            parsed: Parsed data dict

        Returns:
            Tuple of (vessels_stored, positions_stored, metrics_stored)
        """
        session = SessionLocal()
        vessels_count = 0
        positions_count = 0
        metrics_count = 0

        try:
            # Store vessels
            for vessel in parsed.get("vessels", []):
                existing = session.query(Vessel).filter_by(mmsi=vessel["mmsi"]).first()
                if existing:
                    for key, value in vessel.items():
                        if value is not None:
                            setattr(existing, key, value)
                else:
                    session.add(Vessel(**vessel))
                    vessels_count += 1

            # Store positions
            for position in parsed.get("positions", []):
                session.add(VesselPosition(**position))
                positions_count += 1

            # Store port metrics
            for metric in parsed.get("port_metrics", []):
                session.add(PortCongestion(**metric))
                metrics_count += 1

            session.commit()
            logger.info(
                f"Stored {vessels_count} vessels, {positions_count} positions, "
                f"{metrics_count} port metrics"
            )

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store shipping data: {e}")
            raise
        finally:
            session.close()

        return vessels_count, positions_count, metrics_count

    async def run_collection(self) -> int:
        """Run full collection cycle.

        Returns:
            Total records stored
        """
        logger.info("Starting MarineTraffic collection")

        try:
            raw_data = await self.fetch()
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            v, p, m = await self.store_data(parsed)

            total = v + p + m
            logger.info(f"MarineTraffic collection complete: {total} records")
            return total

        finally:
            await self.close()
