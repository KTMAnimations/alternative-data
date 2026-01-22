"""ADS-B Exchange collector for corporate jet tracking."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from haversine import haversine, Unit

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.adsb import Aircraft, FlightPosition, FlightLanding, Airport, CompanyHQ

logger = logging.getLogger(__name__)


class ADSBExchangeCollector(BaseCollector[List[Dict], List[Dict]]):
    """Collector for ADS-B Exchange flight data.

    Tracks corporate jet movements for M&A signals and
    executive travel patterns.
    """

    SOURCE_NAME = "adsb_exchange"
    BASE_URL = "https://adsbexchange-com1.p.rapidapi.com"
    DEFAULT_RATE_LIMIT = 1.0  # RapidAPI has strict limits

    # Corporate jet aircraft types
    CORPORATE_JET_TYPES = {
        "GLF6", "G650", "GLEX", "GL7T",  # Gulfstream
        "CL35", "CL60", "GL5T", "CL30",  # Bombardier
        "C68A", "C700", "C750", "C560",  # Cessna Citation
        "E55P", "E550", "E545",  # Embraer
        "FA7X", "F900", "F2TH",  # Dassault
        "H25B", "HA4T",  # Hawker
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        rapidapi_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the ADS-B Exchange collector.

        Args:
            api_key: ADS-B Exchange API key
            rapidapi_key: RapidAPI key
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.api_key = api_key or settings.adsb_exchange_api_key
        self.rapidapi_key = rapidapi_key or getattr(settings, 'adsb_exchange_rapidapi_key', None)
        self.headers = {
            "X-RapidAPI-Key": self.rapidapi_key or "",
            "X-RapidAPI-Host": "adsbexchange-com1.p.rapidapi.com"
        }

    @property
    def http_client(self) -> httpx.AsyncClient:
        """HTTP client with RapidAPI headers."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self.headers,
            )
        return self._http_client

    async def fetch(self) -> List[Dict]:
        """Fetch aircraft data for tracked corporate jets.

        Returns:
            List of aircraft position data
        """
        session = SessionLocal()
        try:
            # Get list of tracked corporate jets
            aircraft = session.query(Aircraft).filter(
                Aircraft.is_corporate_jet == True
            ).all()

            registrations = [a.registration for a in aircraft if a.registration]
            return await self.fetch_corporate_jets(registrations[:10])  # Limit for rate limits
        finally:
            session.close()

    async def fetch_aircraft_by_registration(self, registration: str) -> Dict:
        """Fetch current position of aircraft by N-number.

        Args:
            registration: Aircraft registration (e.g., N123AB)

        Returns:
            Aircraft position data
        """
        if not self.rapidapi_key:
            raise CollectorError("RapidAPI key not configured")

        await self.rate_limiter.wait()

        url = f"{self.BASE_URL}/v2/registration/{registration}/"
        response = await self.http_client.get(url)
        response.raise_for_status()
        return response.json()

    async def fetch_aircraft_by_icao(self, icao_hex: str) -> Dict:
        """Fetch current position of aircraft by ICAO hex.

        Args:
            icao_hex: Aircraft ICAO 24-bit address

        Returns:
            Aircraft position data
        """
        if not self.rapidapi_key:
            raise CollectorError("RapidAPI key not configured")

        await self.rate_limiter.wait()

        url = f"{self.BASE_URL}/v2/icao/{icao_hex}/"
        response = await self.http_client.get(url)
        response.raise_for_status()
        return response.json()

    async def fetch_aircraft_in_area(
        self,
        lat: float,
        lon: float,
        radius_nm: int = 50
    ) -> List[Dict]:
        """Fetch all aircraft within radius of a point.

        Args:
            lat: Center latitude
            lon: Center longitude
            radius_nm: Radius in nautical miles

        Returns:
            List of aircraft in area
        """
        if not self.rapidapi_key:
            raise CollectorError("RapidAPI key not configured")

        await self.rate_limiter.wait()

        url = f"{self.BASE_URL}/v2/lat/{lat}/lon/{lon}/dist/{radius_nm}/"
        response = await self.http_client.get(url)
        response.raise_for_status()
        return response.json().get("ac", [])

    async def fetch_corporate_jets(self, registrations: List[str]) -> List[Dict]:
        """Fetch positions of multiple corporate jets.

        Args:
            registrations: List of aircraft registrations

        Returns:
            List of aircraft position data
        """
        results = []
        for reg in registrations:
            try:
                data = await self.fetch_aircraft_by_registration(reg)
                if data.get("ac"):
                    results.extend(data["ac"])
            except Exception as e:
                logger.warning(f"Failed to fetch {reg}: {e}")
        return results

    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """Parse aircraft positions into structured format.

        Args:
            raw_data: Raw ADS-B data

        Returns:
            List of parsed position dicts
        """
        parsed = []
        for ac in raw_data:
            try:
                altitude = ac.get("alt_baro")
                on_ground = altitude == "ground" if isinstance(altitude, str) else False

                parsed.append({
                    "icao_hex": ac.get("hex"),
                    "registration": ac.get("r"),
                    "aircraft_type": ac.get("t"),
                    "latitude": ac.get("lat"),
                    "longitude": ac.get("lon"),
                    "altitude_ft": int(altitude) if altitude and altitude != "ground" else 0,
                    "ground_speed_knots": ac.get("gs"),
                    "heading": ac.get("track"),
                    "vertical_rate": ac.get("baro_rate"),
                    "squawk": ac.get("squawk"),
                    "on_ground": on_ground,
                    "flight_id": ac.get("flight", "").strip(),
                    "timestamp": datetime.utcnow(),
                })
            except Exception as e:
                logger.warning(f"Failed to parse aircraft data: {e}")
                continue

        return parsed

    def is_corporate_jet(self, aircraft_type: str) -> bool:
        """Check if aircraft type is a corporate jet.

        Args:
            aircraft_type: ICAO aircraft type code

        Returns:
            True if corporate jet type
        """
        return aircraft_type in self.CORPORATE_JET_TYPES

    def detect_landing(
        self,
        positions: List[Dict],
        altitude_threshold: int = 1000
    ) -> Optional[Dict]:
        """Detect landing from position sequence.

        Args:
            positions: Ordered list of positions (oldest first)
            altitude_threshold: Altitude (ft) to consider as landing

        Returns:
            Landing info dict or None
        """
        if len(positions) < 2:
            return None

        # Look for altitude decrease below threshold
        for i in range(len(positions) - 1):
            prev = positions[i]
            curr = positions[i + 1]

            prev_alt = prev.get("altitude_ft", 0) or 0
            curr_alt = curr.get("altitude_ft", 0) or 0

            # Detect descent below threshold
            if prev_alt > altitude_threshold and curr_alt <= altitude_threshold:
                return {
                    "icao_hex": curr.get("icao_hex"),
                    "landing_timestamp": curr.get("timestamp"),
                    "latitude": curr.get("latitude"),
                    "longitude": curr.get("longitude"),
                }

            # Detect on_ground transition
            if not prev.get("on_ground") and curr.get("on_ground"):
                return {
                    "icao_hex": curr.get("icao_hex"),
                    "landing_timestamp": curr.get("timestamp"),
                    "latitude": curr.get("latitude"),
                    "longitude": curr.get("longitude"),
                }

        return None

    def find_nearest_airport(
        self,
        lat: float,
        lon: float,
        max_distance_km: float = 20
    ) -> Optional[Dict]:
        """Find nearest airport to coordinates.

        Args:
            lat: Latitude
            lon: Longitude
            max_distance_km: Maximum distance to consider

        Returns:
            Airport info or None
        """
        session = SessionLocal()
        try:
            airports = session.query(Airport).all()
            point = (lat, lon)

            nearest = None
            min_distance = float('inf')

            for airport in airports:
                airport_point = (airport.latitude, airport.longitude)
                distance = haversine(point, airport_point, unit=Unit.KILOMETERS)

                if distance < min_distance and distance <= max_distance_km:
                    min_distance = distance
                    nearest = {
                        "icao_code": airport.icao_code,
                        "name": airport.name,
                        "distance_km": distance,
                    }

            return nearest
        finally:
            session.close()

    def find_nearby_company_hq(
        self,
        lat: float,
        lon: float,
        max_distance_km: float = 50
    ) -> Optional[Dict]:
        """Find company HQs near coordinates.

        Args:
            lat: Latitude
            lon: Longitude
            max_distance_km: Maximum distance to consider

        Returns:
            Nearest company HQ info or None
        """
        session = SessionLocal()
        try:
            hqs = session.query(CompanyHQ).all()
            point = (lat, lon)

            nearest = None
            min_distance = float('inf')

            for hq in hqs:
                hq_point = (hq.latitude, hq.longitude)
                distance = haversine(point, hq_point, unit=Unit.KILOMETERS)

                if distance < min_distance and distance <= max_distance_km:
                    min_distance = distance
                    nearest = {
                        "entity_id": hq.entity_id,
                        "company_name": hq.company_name,
                        "distance_km": distance,
                    }

            return nearest
        finally:
            session.close()

    async def store_positions(self, positions: List[Dict]) -> int:
        """Store parsed positions in database.

        Args:
            positions: List of parsed position dicts

        Returns:
            Number of positions stored
        """
        session = SessionLocal()
        count = 0

        try:
            for pos in positions:
                record = FlightPosition(
                    icao_hex=pos["icao_hex"],
                    timestamp=pos["timestamp"],
                    latitude=pos["latitude"],
                    longitude=pos["longitude"],
                    altitude_ft=pos["altitude_ft"],
                    ground_speed_knots=pos["ground_speed_knots"],
                    heading=pos["heading"],
                    vertical_rate=pos["vertical_rate"],
                    squawk=pos["squawk"],
                    on_ground=pos["on_ground"],
                    flight_id=pos["flight_id"],
                )
                session.add(record)
                count += 1

            session.commit()
            logger.info(f"Stored {count} flight positions")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store positions: {e}")
            raise
        finally:
            session.close()

        return count

    async def run_collection(self, registrations: Optional[List[str]] = None) -> int:
        """Run full collection cycle.

        Args:
            registrations: Optional list of specific registrations to track

        Returns:
            Number of positions stored
        """
        logger.info("Starting ADS-B Exchange collection")

        try:
            if registrations:
                raw_data = await self.fetch_corporate_jets(registrations)
            else:
                raw_data = await self.fetch()

            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            count = await self.store_positions(parsed)

            logger.info(f"ADS-B collection complete: {count} positions")
            return count

        finally:
            await self.close()
