"""USGS Earthquake data collector.

Data Source: https://earthquake.usgs.gov/fdsnws/event/1/
Frequency: Real-time (events available within minutes)
Historical: 1900-present
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.models.database import SessionLocal
from src.models.earthquake import EarthquakeEvent

logger = logging.getLogger(__name__)


class USGSEarthquakeCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for USGS earthquake data.

    Uses the USGS Earthquake API to fetch seismic events.
    API is free and generous with rate limits.
    """

    SOURCE_NAME = "usgs_earthquake"
    DEFAULT_RATE_LIMIT = 2.0  # requests per second

    BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    # Default query parameters
    DEFAULT_MIN_MAGNITUDE = 2.5  # Filter out very minor quakes
    DEFAULT_LOOKBACK_DAYS = 7

    async def fetch(
        self,
        min_magnitude: float = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000,
    ) -> Dict:
        """Fetch earthquake events from USGS API.

        Args:
            min_magnitude: Minimum magnitude to include
            start_time: Start of time window
            end_time: End of time window
            limit: Maximum events to return

        Returns:
            GeoJSON response from USGS
        """
        await self.rate_limiter.wait()

        if min_magnitude is None:
            min_magnitude = self.DEFAULT_MIN_MAGNITUDE

        if end_time is None:
            end_time = datetime.utcnow()

        if start_time is None:
            start_time = end_time - timedelta(days=self.DEFAULT_LOOKBACK_DAYS)

        params = {
            "format": "geojson",
            "starttime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endtime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "minmagnitude": min_magnitude,
            "limit": limit,
            "orderby": "time-asc",
        }

        try:
            response = await self.http_client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch USGS data: {e}")
            raise CollectorError(f"USGS fetch failed: {e}")

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse GeoJSON earthquake data.

        Args:
            raw_data: GeoJSON FeatureCollection

        Returns:
            List of parsed earthquake records
        """
        features = raw_data.get("features", [])
        records = []

        for feature in features:
            try:
                record = self._parse_feature(feature)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to parse earthquake feature: {e}")
                continue

        logger.info(f"Parsed {len(records)} earthquake events")
        return records

    def _parse_feature(self, feature: Dict) -> Optional[Dict]:
        """Parse a single GeoJSON feature.

        Args:
            feature: GeoJSON Feature object

        Returns:
            Parsed earthquake record
        """
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])

        if len(coords) < 3:
            return None

        # Parse timestamp (USGS uses milliseconds since epoch)
        event_time = props.get("time")
        if event_time:
            timestamp = datetime.utcfromtimestamp(event_time / 1000)
        else:
            return None

        updated_time = props.get("updated")
        if updated_time:
            updated = datetime.utcfromtimestamp(updated_time / 1000)
        else:
            updated = None

        record = {
            "event_id": feature.get("id"),
            "timestamp": timestamp,
            "updated": updated,
            "longitude": coords[0],
            "latitude": coords[1],
            "depth_km": coords[2],
            "magnitude": props.get("mag"),
            "magnitude_type": props.get("magType"),
            "place_description": props.get("place"),
            "felt_reports": props.get("felt"),
            "cdi": props.get("cdi"),
            "mmi": props.get("mmi"),
            "alert_level": props.get("alert"),
            "tsunami_flag": bool(props.get("tsunami")),
            "status": props.get("status"),
            "net": props.get("net"),
            "nst": props.get("nst"),
            "dmin": props.get("dmin"),
            "rms": props.get("rms"),
            "gap": props.get("gap"),
            "detail_url": props.get("detail"),
        }

        return record

    async def store_events(self, records: List[Dict]) -> int:
        """Store earthquake events in database.

        Args:
            records: Parsed earthquake records

        Returns:
            Number of new records stored
        """
        if not records:
            return 0

        session = SessionLocal()
        stored_count = 0

        try:
            for record in records:
                # Check for existing event
                existing = (
                    session.query(EarthquakeEvent)
                    .filter_by(event_id=record["event_id"])
                    .first()
                )

                if existing:
                    # Update if the event was updated
                    if record.get("updated") and existing.updated:
                        if record["updated"] > existing.updated:
                            for key, value in record.items():
                                if hasattr(existing, key):
                                    setattr(existing, key, value)
                else:
                    event = EarthquakeEvent(**record)
                    session.add(event)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new earthquake events")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store earthquake data: {e}")
            raise
        finally:
            session.close()

    async def run_collection(
        self,
        min_magnitude: float = None,
        lookback_days: int = None,
    ) -> int:
        """Execute full collection cycle.

        Args:
            min_magnitude: Minimum magnitude to fetch
            lookback_days: Days of history to fetch

        Returns:
            Number of new records stored
        """
        logger.info("Starting USGS earthquake collection")

        if lookback_days is None:
            lookback_days = self.DEFAULT_LOOKBACK_DAYS

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=lookback_days)

        try:
            # Fetch data
            raw_data = await self.fetch(
                min_magnitude=min_magnitude,
                start_time=start_time,
                end_time=end_time,
            )

            # Store raw data
            await self.store_raw(raw_data)

            # Parse records
            records = self.parse(raw_data)

            # Validate
            self._validate_records(records)

            # Store in database
            stored = await self.store_events(records)

            logger.info(f"USGS collection complete: {stored} new events")
            return stored

        finally:
            await self.close()

    def _validate_records(self, records: List[Dict]) -> None:
        """Validate parsed records."""
        for record in records:
            mag = record.get("magnitude")
            if mag is not None:
                # Magnitudes should be reasonable (typically 0-10)
                if mag < -2 or mag > 12:
                    logger.warning(
                        f"Unusual magnitude {mag} for event {record.get('event_id')}"
                    )

            # Validate coordinates
            lat = record.get("latitude")
            lon = record.get("longitude")
            if lat is not None and (lat < -90 or lat > 90):
                logger.warning(f"Invalid latitude {lat}")
            if lon is not None and (lon < -180 or lon > 180):
                logger.warning(f"Invalid longitude {lon}")

    async def fetch_significant_events(
        self,
        min_magnitude: float = 5.0,
        lookback_hours: int = 24,
    ) -> List[Dict]:
        """Fetch only significant earthquake events.

        Useful for real-time alerting on major seismic events.

        Args:
            min_magnitude: Minimum magnitude (default 5.0)
            lookback_hours: Hours to look back (default 24)

        Returns:
            List of significant earthquake records
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=lookback_hours)

        raw_data = await self.fetch(
            min_magnitude=min_magnitude,
            start_time=start_time,
            end_time=end_time,
        )

        return self.parse(raw_data)
